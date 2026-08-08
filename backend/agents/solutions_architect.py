"""
Solutions Architect agent — produces ArchitectureDesign from structured Requirements.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# Allow running standalone: python agents/solutions_architect.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")

from schemas.models import ArchitectureDesign, Requirements, UserRequest
from tools.llm_retry import invoke_with_retry

SYSTEM_PROMPT = """\
You are a senior AWS Solutions Architect.

Given structured requirements, produce a production-ready cloud architecture design.
Default to AWS unless requirements specify otherwise.

Guidelines:
- services: list every AWS service needed; use official names (e.g. "Amazon CloudFront")
- aws_service_code: lowercase Terraform resource prefix (e.g. "cloudfront", "s3", "ecs")
- waf_pillar_justification: tie each service choice to a Well-Architected Framework pillar
- primary_waf_pillar: the main pillar that service addresses
- depends_on: list service_name values this component requires (empty for edge/entry services)
- topology_description: explain request flow, data flow, and component interactions
- network_design: VPC layout, subnets (public/private), NAT, load balancers, CDN edge
- security_controls: IAM least privilege, encryption at rest/in transit, WAF, secrets manager
- disaster_recovery_strategy: required when ha_required or multi_region is true
- scaling_strategy: auto-scaling, caching, CDN, sharding — match expected_traffic tier
- waf_score: self-assess overall design quality 0–100
- waf_pillar_scores: score each of the six WAF pillars 0–100
- approved: always false on first pass; the reviewer agent sets this later
- revision_number: increment when redesigning after reviewer feedback
"""


def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file at the project root."
        )
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key, max_tokens=5000, reasoning_effort="low")


def design_architecture(
    requirements: Requirements,
    request: UserRequest | None = None,
    reviewer_feedback: str | None = None,
    revision_number: int = 1,
) -> ArchitectureDesign:
    """Produce an ArchitectureDesign from structured Requirements."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(ArchitectureDesign)

    context_parts = [
        "Requirements:",
        requirements.model_dump_json(indent=2),
    ]
    if request:
        context_parts.append(
            f"\nDeployment context:"
            f"\n- Preferred cloud: {request.preferred_cloud.value}"
            f"\n- Target region: {request.target_region}"
            f"\n- Environment: {request.environment}"
        )
    if reviewer_feedback:
        context_parts.append(f"\nReviewer feedback (address all items):\n{reviewer_feedback}")
        context_parts.append(f"\nProduce revision {revision_number} of the architecture.")

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

    reqs = analyze_requirements("A highly available video streaming backend")
    output = design_architecture(reqs)
    print(output.model_dump_json(indent=2))