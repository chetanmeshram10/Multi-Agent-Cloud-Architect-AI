"""
Reviewer Agent — evaluates ArchitectureDesign against Requirements and AWS WAF.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# Allow running standalone: python agents/reviewer_agent.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")

from schemas.models import ArchitectureDesign, Requirements, ReviewResult
from tools.llm_retry import invoke_with_retry

SYSTEM_PROMPT = """\
You are a senior AWS Well-Architected Framework reviewer.

Given structured requirements and an architecture design, perform an independent
review. Do not simply accept the architect's self-assessed waf_score — evaluate
the design yourself against all six WAF pillars.

Review criteria:
1. Requirements alignment — does the design satisfy ha_required, latency, traffic,
   budget_ceiling_usd, compliance_notes, and multi_region?
2. Service selection — are services appropriate, complete, and non-redundant?
3. Security — encryption, IAM, network isolation, secrets, WAF rules
4. Reliability — multi-AZ, failover, DR strategy matches HA requirements
5. Performance — CDN, caching, scaling strategy matches traffic/latency tiers
6. Cost — rough sanity check against budget_ceiling_usd if provided

Findings:
- severity "blocker": design cannot proceed until fixed (missing HA, major gap)
- severity "warning": should fix but not blocking (suboptimal choice, missing detail)
- severity "info": suggestion or best-practice note

Approval rules:
- approved = true ONLY when there are zero blocker findings AND waf_score >= 75
- required_changes: list every blocker and warning remediation as actionable strings
- summary: 2–3 sentence executive summary for downstream agents
- waf_pillar_scores: independently score all six pillars 0–100
"""


def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file at the project root."
        )
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key, max_tokens=3000, reasoning_effort="low")


def review_architecture(
    requirements: Requirements,
    architecture: ArchitectureDesign,
) -> ReviewResult:
    """Review an ArchitectureDesign against Requirements and return a ReviewResult."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(ReviewResult)

    context_parts = [
        "Requirements:",
        requirements.model_dump_json(indent=2),
        "\nArchitecture design:",
        architecture.model_dump_json(indent=2),
    ]

    result = invoke_with_retry(
        structured_llm,
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="\n".join(context_parts)),
        ],
    )
    return result


if __name__ == "__main__":
    from agents.requirements_analyst import analyze_requirements
    from agents.solutions_architect import design_architecture

    reqs = analyze_requirements("A highly available video streaming backend")
    design = design_architecture(reqs)
    output = review_architecture(reqs, design)
    print(output.model_dump_json(indent=2))