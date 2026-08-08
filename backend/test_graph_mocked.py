"""
Verifies graph.py control flow (revision loop, terraform retry loop) WITHOUT
calling the real Groq API — every agent function is monkeypatched.
Run: python test_graph_mocked.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unittest.mock import patch

from schemas.models import (
    ArchitectureDesign, ArchitectureService, CostEstimate, CostLineItem,
    Requirements, ReviewResult, TerraformOutput, UserRequest, AppType,
    TrafficTier, LatencyTier, WafPillar,
)

call_counts = {"architect": 0, "review": 0, "devops": 0, "finops": 0}


def fake_analyze_requirements(prompt, request=None):
    return Requirements(
        app_type=AppType.MOBILE_BACKEND,
        app_description="mock",
        expected_traffic=TrafficTier.HIGH,
        latency_requirement=LatencyTier.LOW,
        ha_required=True,
    )


def fake_design_architecture(requirements, request=None, reviewer_feedback=None, revision_number=1):
    call_counts["architect"] += 1
    return ArchitectureDesign(
        services=[ArchitectureService(
            service_name="Amazon S3", purpose="storage",
            waf_pillar_justification="durable storage",
            primary_waf_pillar=WafPillar.RELIABILITY,
        )],
        topology_description="mock topology",
        revision_number=revision_number,
    )


def fake_review_architecture(requirements, architecture):
    call_counts["review"] += 1
    # Reject first 2 times, approve on 3rd -> tests revision loop
    approved = call_counts["review"] >= 3
    return ReviewResult(
        approved=approved,
        waf_score=60 if not approved else 90,
        summary="mock review",
        required_changes=[] if approved else ["fix reliability"],
    )


def fake_generate_terraform(architecture, requirements=None, request=None, retry_count=0):
    call_counts["devops"] += 1
    # Fail first attempt (invalid), pass on retry -> tests terraform retry loop
    passed = call_counts["devops"] >= 2
    return TerraformOutput(
        hcl_code='provider "aws" {}\nresource "aws_s3_bucket" "x" {}',
        validation_passed=passed,
        validation_errors=None if passed else "mock validation failure",
        retry_count=retry_count,
    )


def fake_estimate_costs(requirements, architecture):
    call_counts["finops"] += 1
    return CostEstimate(
        monthly_total_usd=100.0,
        breakdown=[CostLineItem(service_name="Amazon S3", monthly_usd=100.0)],
    )


with patch("agents.requirements_analyst.analyze_requirements", fake_analyze_requirements), \
     patch("agents.solutions_architect.design_architecture", fake_design_architecture), \
     patch("agents.reviewer_agent.review_architecture", fake_review_architecture), \
     patch("agents.devops_agent.generate_terraform", fake_generate_terraform), \
     patch("agents.finops_agent.estimate_costs", fake_estimate_costs):

    # graph.py imports these functions by name at module load, so patch there too
    import orchestration.graph as graph_module
    graph_module.analyze_requirements = fake_analyze_requirements
    graph_module.design_architecture = fake_design_architecture
    graph_module.review_architecture = fake_review_architecture
    graph_module.generate_terraform = fake_generate_terraform
    graph_module.estimate_costs = fake_estimate_costs

    events = []
    def cb(stage, status, detail):
        events.append((stage, status))

    req = UserRequest(prompt="A highly available video streaming backend")
    result = graph_module.run_pipeline(req, progress_cb=cb)

    print("=== call counts ===")
    print(call_counts)
    print("\n=== event log ===")
    for e in events:
        print(e)

    assert call_counts["architect"] == 3, f"expected 3 architect calls (revision loop), got {call_counts['architect']}"
    assert call_counts["review"] == 3, f"expected 3 review calls, got {call_counts['review']}"
    assert call_counts["devops"] == 2, f"expected 2 devops calls (retry loop), got {call_counts['devops']}"
    assert call_counts["finops"] == 1, f"expected 1 finops call, got {call_counts['finops']}"
    assert result.review.approved is True
    assert result.terraform.validation_passed is True
    assert result.cost_estimate.monthly_total_usd == 100.0

    print("\nALL ASSERTIONS PASSED — revision loop and retry loop both work correctly.")
