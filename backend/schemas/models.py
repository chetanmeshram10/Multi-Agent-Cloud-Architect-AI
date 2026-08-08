"""
Single source of truth for structured data passed between agents.

Every agent reads from and writes to these Pydantic models. Extend fields here
as the pipeline grows — do not duplicate types in agent modules.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, get_args, get_origin

from pydantic import BaseModel, Field, field_validator, model_validator


def _is_list_annotation(annotation: Any) -> bool:
    """True for `list[...]` and `Optional[list[...]]` annotations."""
    if get_origin(annotation) is list:
        return True
    args = get_args(annotation)
    return any(get_origin(a) is list for a in args)


class NullSafeModel(BaseModel):
    """
    Some LLM providers (observed with Groq's newer tool-calling models) emit
    explicit `null` for list fields that should be an empty array, rather than
    omitting the field or sending `[]`. Coerce those back to `[]` before
    Pydantic validation runs, so a stray null doesn't blow up the whole
    pipeline stage.
    """

    @model_validator(mode="before")
    @classmethod
    def _coerce_null_lists(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for name, field in cls.model_fields.items():
            if data.get(name) is None and name in data and _is_list_annotation(field.annotation):
                data[name] = []
        return data


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class AppType(str, Enum):
    WEB_APP = "web_app"
    API = "api"
    MOBILE_BACKEND = "mobile_backend"
    DATA_PIPELINE = "data_pipeline"
    ML_INFERENCE = "ml_inference"
    STATIC_SITE = "static_site"
    OTHER = "other"


class TrafficTier(str, Enum):
    LOW = "low"  # < 1k RPS
    MEDIUM = "medium"  # 1k-10k RPS
    HIGH = "high"  # 10k-100k RPS
    VERY_HIGH = "very_high"  # > 100k RPS


class LatencyTier(str, Enum):
    STANDARD = "standard"  # > 500 ms acceptable
    LOW = "low"  # < 200 ms p99
    ULTRA_LOW = "ultra_low"  # < 50 ms p99


class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    MULTI_CLOUD = "multi_cloud"


class WafPillar(str, Enum):
    OPERATIONAL_EXCELLENCE = "operational_excellence"
    SECURITY = "security"
    RELIABILITY = "reliability"
    PERFORMANCE_EFFICIENCY = "performance_efficiency"
    COST_OPTIMIZATION = "cost_optimization"
    SUSTAINABILITY = "sustainability"


class ReviewSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class AgentStage(str, Enum):
    REQUIREMENTS = "requirements_analyst"
    ARCHITECTURE = "solutions_architect"
    REVIEW = "reviewer_agent"
    TERRAFORM = "devops_agent"
    FINOPS = "finops_agent"


# ---------------------------------------------------------------------------
# User -> Requirements Analyst
# ---------------------------------------------------------------------------


class UserRequest(NullSafeModel):
    """Raw input from the API or CLI before requirements extraction."""

    prompt: str = Field(..., min_length=1, description="Natural-language project brief")
    preferred_cloud: CloudProvider = CloudProvider.AWS
    target_region: str = Field(default="us-east-1", description="Primary deployment region")
    environment: Literal["dev", "staging", "prod"] = "prod"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Requirements(NullSafeModel):
    """Structured requirements produced by the requirements analyst."""

    app_type: AppType
    app_description: str = Field(..., description="One-paragraph summary of the workload")
    expected_traffic: TrafficTier
    peak_rps_estimate: Optional[int] = Field(
        default=None, ge=0, description="Optional numeric peak requests/sec"
    )
    latency_requirement: LatencyTier
    budget_ceiling_usd: Optional[float] = Field(
        default=None, ge=0, description="Maximum acceptable monthly spend in USD"
    )
    ha_required: bool = Field(
        default=False, description="Whether multi-AZ / failover is mandatory"
    )
    multi_region: bool = Field(default=False)
    compliance_notes: Optional[str] = Field(
        default=None, description="SOC2, HIPAA, PCI-DSS, etc."
    )
    data_classification: Optional[str] = Field(
        default=None, description="e.g. public, internal, confidential, regulated"
    )
    integrations: list[str] = Field(
        default_factory=list,
        description="External systems (Stripe, Auth0, Salesforce, ...)",
    )
    non_functional_requirements: list[str] = Field(
        default_factory=list,
        description="Additional NFRs not captured above",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Ambiguities the analyst could not resolve from the prompt",
    )
    confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Analyst confidence in extraction quality"
    )


# ---------------------------------------------------------------------------
# Requirements Analyst -> Solutions Architect
# ---------------------------------------------------------------------------


class ArchitectureService(NullSafeModel):
    """A single cloud service in the proposed design."""

    service_name: str = Field(..., description='e.g. "Amazon CloudFront"')
    aws_service_code: Optional[str] = Field(
        default=None, description='Terraform/AWS API identifier, e.g. "cloudfront"'
    )
    purpose: str
    waf_pillar_justification: str = Field(
        ..., description="Why this service was chosen, tied to a WAF pillar"
    )
    primary_waf_pillar: WafPillar = WafPillar.RELIABILITY
    estimated_monthly_usd: Optional[float] = Field(default=None, ge=0)
    depends_on: list[str] = Field(
        default_factory=list,
        description="service_name values this component requires",
    )
    configuration_notes: Optional[str] = None


class ArchitectureDesign(NullSafeModel):
    """High-level architecture produced by the solutions architect."""

    services: list[ArchitectureService] = Field(default_factory=list)
    topology_description: str = Field(
        ..., description="Narrative of how components connect and data flows"
    )
    network_design: Optional[str] = Field(
        default=None, description="VPC, subnets, routing, ingress/egress"
    )
    security_controls: list[str] = Field(
        default_factory=list,
        description="IAM, encryption, WAF rules, secrets management, ...",
    )
    disaster_recovery_strategy: Optional[str] = None
    scaling_strategy: Optional[str] = None
    waf_score: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Aggregate WAF alignment score"
    )
    waf_pillar_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Per-pillar scores keyed by WafPillar value",
    )
    reviewer_feedback: Optional[str] = Field(
        default=None, description="Latest consolidated feedback from reviewer"
    )
    revision_number: int = Field(default=1, ge=1)
    approved: bool = Field(
        default=False, description="True once reviewer clears the design"
    )


# ---------------------------------------------------------------------------
# Solutions Architect <-> Reviewer Agent
# ---------------------------------------------------------------------------


class ReviewFinding(NullSafeModel):
    """A single issue or recommendation from the reviewer."""

    severity: ReviewSeverity
    pillar: WafPillar
    title: str
    message: str
    affected_services: list[str] = Field(default_factory=list)
    remediation: Optional[str] = None


class ReviewResult(NullSafeModel):
    """Structured output from the reviewer agent."""

    approved: bool
    waf_score: float = Field(..., ge=0.0, le=100.0)
    waf_pillar_scores: dict[str, float] = Field(default_factory=dict)
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: str = Field(..., description="Executive summary for downstream agents")
    required_changes: list[str] = Field(
        default_factory=list,
        description="Actionable items the architect must address on retry",
    )


# ---------------------------------------------------------------------------
# Architecture -> DevOps Agent
# ---------------------------------------------------------------------------


class TerraformModule(NullSafeModel):
    """One Terraform module or file fragment."""

    name: str
    path: str = Field(..., description='Relative path, e.g. "modules/vpc/main.tf"')
    hcl_code: str
    description: Optional[str] = None


class TerraformOutput(NullSafeModel):
    """Infrastructure-as-code artifact from the DevOps agent."""

    hcl_code: str = Field(..., description="Primary/root Terraform configuration")
    modules: list[TerraformModule] = Field(default_factory=list)
    provider: CloudProvider = CloudProvider.AWS
    target_region: str = "us-east-1"
    validation_passed: bool = False
    validation_errors: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    resources_provisioned: list[str] = Field(
        default_factory=list,
        description="Human-readable list of resources defined in HCL",
    )


# ---------------------------------------------------------------------------
# Architecture -> FinOps Agent
# ---------------------------------------------------------------------------


class CostLineItem(NullSafeModel):
    """Monthly cost for a single service or resource class."""

    service_name: str
    monthly_usd: float = Field(..., ge=0)
    pricing_model: Optional[str] = Field(
        default=None, description='e.g. "on-demand", "reserved", "spot"'
    )
    assumptions: Optional[str] = Field(
        default=None, description="Traffic, storage, or instance assumptions used"
    )
    optimization_suggestions: list[str] = Field(default_factory=list)


class CostEstimate(NullSafeModel):
    """Cost analysis from the FinOps agent."""

    monthly_total_usd: float = Field(..., ge=0)
    annual_total_usd: Optional[float] = Field(default=None, ge=0)
    breakdown: list[CostLineItem] = Field(default_factory=list)
    within_budget: Optional[bool] = None
    budget_ceiling_usd: Optional[float] = Field(default=None, ge=0)
    budget_variance_usd: Optional[float] = Field(
        default=None, description="Positive = over budget, negative = under"
    )
    cost_optimization_summary: Optional[str] = None
    reserved_instance_candidates: list[str] = Field(default_factory=list)

    @field_validator("annual_total_usd", mode="before")
    @classmethod
    def derive_annual_if_missing(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None:
            return v
        monthly = info.data.get("monthly_total_usd")
        if monthly is not None:
            return round(monthly * 12, 2)
        return None


# ---------------------------------------------------------------------------
# Pipeline state (LangGraph shared state)
# ---------------------------------------------------------------------------


class AgentArtifact(NullSafeModel):
    """Audit record of what each agent produced and when."""

    stage: AgentStage
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None
    token_usage: Optional[int] = None


class PipelineState(NullSafeModel):
    """
    Top-level state object passed through the orchestration graph.

    Each agent reads the fields it needs and writes its output back here.
    """

    request: UserRequest
    requirements: Optional[Requirements] = None
    architecture: Optional[ArchitectureDesign] = None
    review: Optional[ReviewResult] = None
    terraform: Optional[TerraformOutput] = None
    cost_estimate: Optional[CostEstimate] = None
    current_stage: AgentStage = AgentStage.REQUIREMENTS
    artifacts: list[AgentArtifact] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def latest_artifact(self, stage: AgentStage) -> Optional[AgentArtifact]:
        matches = [a for a in self.artifacts if a.stage == stage]
        return matches[-1] if matches else None