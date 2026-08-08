"""
DevOps Agent — generates Terraform HCL from an approved architecture design.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# Allow running standalone: python agents/devops_agent.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")

from schemas.models import ArchitectureDesign, CloudProvider, Requirements, TerraformOutput, UserRequest
from tools.llm_retry import invoke_with_retry
from tools.terraform_validator import validate_terraform

SYSTEM_PROMPT = """\
You are a senior DevOps / Platform engineer specializing in Terraform on AWS.

Given an architecture design, produce production-ready Terraform HCL that implements it.

Guidelines:
- hcl_code: complete root main.tf content including terraform {} and provider "aws" blocks
- modules: optional sub-modules for VPC, compute, CDN, storage, etc. with path and hcl_code
- target_region: use the deployment region from context (default us-east-1)
- provider: aws
- resources_provisioned: human-readable list of every AWS resource created
- Use modern Terraform syntax (required_providers, no deprecated patterns)
- Tag all resources with Environment and Project tags via default_tags or per-resource tags
- Include variables for environment name and region where appropriate
- Do NOT use placeholders, "...", or TODO — output complete, apply-ready HCL
- Match every service in the architecture to at least one Terraform resource
- IMPORTANT — keep HCL concise: use `for_each` or `count` for any repeated
  per-AZ resources (subnets, NAT gateways, EIPs, route table associations,
  etc.) instead of writing a separate near-identical resource block for each
  AZ. This is both more idiomatic Terraform and keeps output size manageable.
"""


def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file at the project root."
        )
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key, max_tokens=6000, reasoning_effort="low")


def generate_terraform(
    architecture: ArchitectureDesign,
    requirements: Requirements | None = None,
    request: UserRequest | None = None,
    retry_count: int = 0,
) -> TerraformOutput:
    """Generate TerraformOutput from an ArchitectureDesign."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(TerraformOutput)

    target_region = request.target_region if request else "us-east-1"

    # Terraform generation only needs the concrete infra facts, not the
    # narrative fields (topology description, DR/scaling prose, WAF scores).
    # Sending the full architecture dump burns a large chunk of the account's
    # per-minute token budget on context the model doesn't need to write HCL,
    # leaving too little room for the (often large) generated output.
    compact_architecture = {
        "services": [
            {
                "service_name": s.service_name,
                "aws_service_code": s.aws_service_code,
                "purpose": s.purpose,
                "depends_on": s.depends_on,
                "configuration_notes": s.configuration_notes,
            }
            for s in architecture.services
        ],
        "network_design": architecture.network_design,
        "security_controls": architecture.security_controls,
    }

    context_parts = [
        "Architecture design (services, network, security only):",
        json.dumps(compact_architecture, indent=2),
        f"\nTarget region: {target_region}",
    ]
    if requirements:
        compact_requirements = {
            "app_type": requirements.app_type.value,
            "expected_traffic": requirements.expected_traffic.value,
            "ha_required": requirements.ha_required,
            "multi_region": requirements.multi_region,
            "compliance_notes": requirements.compliance_notes,
        }
        context_parts.extend([
            "\nRequirements (honour ha_required, environment constraints):",
            json.dumps(compact_requirements, indent=2),
        ])
    if request:
        context_parts.append(f"\nEnvironment: {request.environment}")

    result: TerraformOutput = invoke_with_retry(
        structured_llm,
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="\n".join(context_parts)),
        ],
    )

    passed, error = validate_terraform(result.hcl_code)
    return result.model_copy(
        update={
            "provider": CloudProvider.AWS,
            "target_region": target_region,
            "validation_passed": passed,
            "validation_errors": error,
            "retry_count": retry_count,
        }
    )


if __name__ == "__main__":
    from agents.requirements_analyst import analyze_requirements
    from agents.solutions_architect import design_architecture

    reqs = analyze_requirements("A highly available video streaming backend")
    design = design_architecture(reqs)
    output = generate_terraform(design, requirements=reqs)
    print(output.model_dump_json(indent=2))