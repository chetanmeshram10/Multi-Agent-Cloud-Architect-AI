"""
Requirements Analyst agent — extracts structured Requirements from natural language.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# Allow running standalone: python agents/requirements_analyst.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")

from schemas.models import Requirements, UserRequest
from tools.llm_retry import invoke_with_retry

SYSTEM_PROMPT = """\
You are a senior cloud solutions requirements analyst.

Given a natural-language project brief, extract structured cloud architecture
requirements. Infer reasonable defaults when details are missing, but list any
assumptions as open_questions.

Guidelines:
- app_type: pick the closest AppType enum value
- expected_traffic: estimate tier from context (video streaming → high/very_high)
- latency_requirement: streaming and real-time workloads need low or ultra_low
- ha_required: true for anything described as "highly available", "HA", "99.9%+"
- multi_region: true only if global distribution or DR across regions is implied
- confidence_score: lower when the prompt is vague; higher when specifics are given
"""


def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file at the project root."
        )
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key, max_tokens=3500, reasoning_effort="low")


def analyze_requirements(user_prompt: str, request: UserRequest | None = None) -> Requirements:
    """Extract structured Requirements from a natural-language brief."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(Requirements)

    context_parts = [f"Project brief:\n{user_prompt}"]
    if request:
        context_parts.append(
            f"\nAdditional context:"
            f"\n- Preferred cloud: {request.preferred_cloud.value}"
            f"\n- Target region: {request.target_region}"
            f"\n- Environment: {request.environment}"
        )

    result = invoke_with_retry(
        structured_llm,
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="\n".join(context_parts)),
        ],
    )
    return result


if __name__ == "__main__":
    output = analyze_requirements("A highly available video streaming backend")
    print(output.model_dump_json(indent=2))