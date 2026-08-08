"""
FinOps Agent — produces CostEstimate from architecture and requirements.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# Allow running standalone: python agents/finops_agent.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")

from schemas.models import ArchitectureDesign, CostEstimate, Requirements
from tools.llm_retry import invoke_with_retry

SYSTEM_PROMPT = """\
You are a senior FinOps analyst specializing in AWS cost estimation.

Given requirements and an architecture design, produce a realistic monthly cost estimate.

Guidelines:
- breakdown: one CostLineItem per service in the architecture (and supporting resources)
- monthly_usd: realistic on-demand pricing based on traffic tier and service choices
- pricing_model: "on-demand", "reserved", or "spot" as appropriate
- assumptions: state instance counts, storage GB, data transfer TB, request volume, etc.
- optimization_suggestions: per-service cost reduction ideas (RI, Savings Plans, S3 tiering, …)
- monthly_total_usd: sum of breakdown items (verify arithmetic)
- annual_total_usd: monthly_total_usd × 12
- budget_ceiling_usd: copy from requirements if provided, else null
- within_budget: true/false/null — compare monthly_total_usd to budget_ceiling_usd
- budget_variance_usd: monthly_total_usd - budget_ceiling_usd (positive = over budget)
- reserved_instance_candidates: services with steady-state compute suitable for RIs/SPs
- cost_optimization_summary: 2–3 sentence executive summary of top savings opportunities
- Use conservative estimates; round to two decimal places
"""


def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file at the project root."
        )
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key, max_tokens=3000, reasoning_effort="low")


def estimate_costs(
    requirements: Requirements,
    architecture: ArchitectureDesign,
) -> CostEstimate:
    """Produce a CostEstimate from Requirements and ArchitectureDesign."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(CostEstimate)

    context_parts = [
        "Requirements:",
        requirements.model_dump_json(indent=2),
        "\nArchitecture design:",
        architecture.model_dump_json(indent=2),
    ]

    result: CostEstimate = invoke_with_retry(
        structured_llm,
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="\n".join(context_parts)),
        ],
    )

    # Reconcile totals from line items (LLM arithmetic can drift)
    updates: dict = {}
    if result.breakdown:
        monthly = round(sum(item.monthly_usd for item in result.breakdown), 2)
        updates["monthly_total_usd"] = monthly
        updates["annual_total_usd"] = round(monthly * 12, 2)

    if requirements.budget_ceiling_usd is not None:
        monthly = updates.get("monthly_total_usd", result.monthly_total_usd)
        ceiling = requirements.budget_ceiling_usd
        updates.update({
            "budget_ceiling_usd": ceiling,
            "within_budget": monthly <= ceiling,
            "budget_variance_usd": round(monthly - ceiling, 2),
        })

    return result.model_copy(update=updates) if updates else result


if __name__ == "__main__":
    from agents.requirements_analyst import analyze_requirements
    from agents.solutions_architect import design_architecture

    reqs = analyze_requirements("A highly available video streaming backend")
    design = design_architecture(reqs)
    output = estimate_costs(reqs, design)
    print(output.model_dump_json(indent=2))