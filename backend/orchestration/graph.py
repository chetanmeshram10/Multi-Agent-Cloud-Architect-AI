"""
Orchestration graph — wires the 5 agents together with LangGraph.

Flow:
    requirements_analyst
        -> solutions_architect
            -> reviewer_agent
                -> [not approved & under revision limit] -> solutions_architect (revise)
                -> [approved | revision limit hit]        -> devops_agent
                                                                -> [terraform invalid & under retry limit] -> devops_agent (retry)
                                                                -> [terraform valid | retry limit hit]      -> finops_agent
                                                                                                                    -> END

Each node is a thin wrapper around the pure agent functions in `agents/*.py`.
The graph only owns control flow (routing + retry/revision counters) and
progress callbacks for streaming to the API layer — it does not contain any
prompting or business logic itself.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Callable, Optional, TypedDict

from langgraph.graph import END, StateGraph

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agents.devops_agent import generate_terraform
from agents.finops_agent import estimate_costs
from agents.requirements_analyst import analyze_requirements
from agents.reviewer_agent import review_architecture
from agents.solutions_architect import design_architecture
from schemas.models import (
    AgentStage,
    ArchitectureDesign,
    CostEstimate,
    PipelineState,
    Requirements,
    ReviewResult,
    TerraformOutput,
    UserRequest,
)

MAX_ARCHITECTURE_REVISIONS = 3
MAX_TERRAFORM_RETRIES = 2

# A progress callback the API layer can hook into for live streaming.
# Signature: (stage: str, status: "started" | "completed" | "failed", detail: dict) -> None
ProgressCallback = Optional[Callable[[str, str, dict], None]]


class GraphState(TypedDict, total=False):
    request: UserRequest
    requirements: Optional[Requirements]
    architecture: Optional[ArchitectureDesign]
    review: Optional[ReviewResult]
    terraform: Optional[TerraformOutput]
    cost_estimate: Optional[CostEstimate]
    revision_number: int
    terraform_retry_count: int
    errors: list[str]
    _progress_cb: ProgressCallback


def _emit(state: GraphState, stage: str, status: str, detail: dict | None = None) -> None:
    cb = state.get("_progress_cb")
    if cb:
        cb(stage, status, detail or {})


def _fail(state: GraphState, stage: str, exc: Exception) -> None:
    msg = f"{stage} failed: {exc}"
    state.setdefault("errors", []).append(msg)
    _emit(state, stage, "failed", {"error": str(exc)})
    print(f"\n[ERROR] {stage} raised an exception:", file=sys.stderr)
    traceback.print_exc()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def node_requirements(state: GraphState) -> GraphState:
    _emit(state, "requirements_analyst", "started")
    try:
        requirements = analyze_requirements(state["request"].prompt, request=state["request"])
        _emit(state, "requirements_analyst", "completed", {"requirements": requirements.model_dump()})
        return {"requirements": requirements}
    except Exception as exc:  # noqa: BLE001
        _fail(state, "requirements_analyst", exc)
        return {"errors": state.get("errors", [])}


def node_architect(state: GraphState) -> GraphState:
    _emit(state, "solutions_architect", "started")
    try:
        review = state.get("review")
        revision_number = state.get("revision_number", 1)
        feedback = None
        if review and not review.approved:
            feedback = "\n".join(review.required_changes) or review.summary

        architecture = design_architecture(
            state["requirements"],
            request=state["request"],
            reviewer_feedback=feedback,
            revision_number=revision_number,
        )
        _emit(state, "solutions_architect", "completed", {"architecture": architecture.model_dump()})
        return {"architecture": architecture}
    except Exception as exc:  # noqa: BLE001
        _fail(state, "solutions_architect", exc)
        return {"errors": state.get("errors", [])}


def node_review(state: GraphState) -> GraphState:
    _emit(state, "reviewer_agent", "started")
    try:
        review = review_architecture(state["requirements"], state["architecture"])
        _emit(state, "reviewer_agent", "completed", {"review": review.model_dump()})
        return {"review": review}
    except Exception as exc:  # noqa: BLE001
        _fail(state, "reviewer_agent", exc)
        # Treat a reviewer failure as "approved" so the pipeline doesn't stall forever.
        return {
            "review": ReviewResult(
                approved=True,
                waf_score=0,
                summary="Reviewer agent failed; proceeding without independent review.",
            ),
            "errors": state.get("errors", []),
        }


def node_bump_revision(state: GraphState) -> GraphState:
    return {"revision_number": state.get("revision_number", 1) + 1}


def node_devops(state: GraphState) -> GraphState:
    _emit(state, "devops_agent", "started")
    try:
        retry_count = state.get("terraform_retry_count", 0)
        terraform = generate_terraform(
            state["architecture"],
            requirements=state["requirements"],
            request=state["request"],
            retry_count=retry_count,
        )
        _emit(state, "devops_agent", "completed", {"terraform": terraform.model_dump()})
        return {"terraform": terraform}
    except Exception as exc:  # noqa: BLE001
        _fail(state, "devops_agent", exc)
        return {
            "terraform": TerraformOutput(
                hcl_code="",
                validation_passed=False,
                validation_errors=str(exc),
                retry_count=state.get("terraform_retry_count", 0),
            ),
            "errors": state.get("errors", []),
        }


def node_bump_terraform_retry(state: GraphState) -> GraphState:
    return {"terraform_retry_count": state.get("terraform_retry_count", 0) + 1}


def node_finops(state: GraphState) -> GraphState:
    _emit(state, "finops_agent", "started")
    try:
        cost_estimate = estimate_costs(state["requirements"], state["architecture"])
        _emit(state, "finops_agent", "completed", {"cost_estimate": cost_estimate.model_dump()})
        return {"cost_estimate": cost_estimate}
    except Exception as exc:  # noqa: BLE001
        _fail(state, "finops_agent", exc)
        return {"errors": state.get("errors", [])}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


def route_after_review(state: GraphState) -> str:
    review = state.get("review")
    revision_number = state.get("revision_number", 1)
    if review is not None and review.approved:
        return "proceed"
    if revision_number >= MAX_ARCHITECTURE_REVISIONS:
        return "proceed"  # give up revising, move on with best effort
    return "revise"


def route_after_devops(state: GraphState) -> str:
    terraform = state.get("terraform")
    retry_count = state.get("terraform_retry_count", 0)
    if terraform is not None and terraform.validation_passed:
        return "proceed"
    if retry_count >= MAX_TERRAFORM_RETRIES:
        return "proceed"  # give up retrying, move on with best effort
    return "retry"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("requirements_analyst", node_requirements)
    graph.add_node("solutions_architect", node_architect)
    graph.add_node("reviewer_agent", node_review)
    graph.add_node("bump_revision", node_bump_revision)
    graph.add_node("devops_agent", node_devops)
    graph.add_node("bump_terraform_retry", node_bump_terraform_retry)
    graph.add_node("finops_agent", node_finops)

    graph.set_entry_point("requirements_analyst")
    graph.add_edge("requirements_analyst", "solutions_architect")
    graph.add_edge("solutions_architect", "reviewer_agent")

    graph.add_conditional_edges(
        "reviewer_agent",
        route_after_review,
        {"revise": "bump_revision", "proceed": "devops_agent"},
    )
    graph.add_edge("bump_revision", "solutions_architect")

    graph.add_conditional_edges(
        "devops_agent",
        route_after_devops,
        {"retry": "bump_terraform_retry", "proceed": "finops_agent"},
    )
    graph.add_edge("bump_terraform_retry", "devops_agent")

    graph.add_edge("finops_agent", END)

    return graph.compile()


_COMPILED_GRAPH = None


def get_graph():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_graph()
    return _COMPILED_GRAPH


def run_pipeline(request: UserRequest, progress_cb: ProgressCallback = None) -> PipelineState:
    """Run the full pipeline synchronously and return a validated PipelineState."""
    graph = get_graph()
    initial_state: GraphState = {
        "request": request,
        "revision_number": 1,
        "terraform_retry_count": 0,
        "errors": [],
        "_progress_cb": progress_cb,
    }
    final_state = graph.invoke(initial_state, config={"recursion_limit": 50})

    return PipelineState(
        request=final_state["request"],
        requirements=final_state.get("requirements"),
        architecture=final_state.get("architecture"),
        review=final_state.get("review"),
        terraform=final_state.get("terraform"),
        cost_estimate=final_state.get("cost_estimate"),
        current_stage=AgentStage.FINOPS,
        errors=final_state.get("errors", []),
    )


if __name__ == "__main__":
    def _print_progress(stage: str, status: str, detail: dict) -> None:
        print(f"[{status.upper()}] {stage}")

    req = UserRequest(prompt="A highly available video streaming backend")
    result = run_pipeline(req, progress_cb=_print_progress)
    print("\n--- FINAL PIPELINE STATE ---")
    print(result.model_dump_json(indent=2))