"""
FastAPI backend for CloudArchitect AI.

Endpoints:
  GET  /api/health              - liveness check
  POST /api/design               - run the full pipeline, return final PipelineState (blocking)
  POST /api/design/stream        - run the full pipeline, stream progress via SSE, end with final state
"""

from __future__ import annotations

import asyncio
import json
import queue
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")

from orchestration.graph import run_pipeline
from schemas.models import CloudProvider, UserRequest

app = FastAPI(title="CloudArchitect AI", version="1.0.0")

# CORS: adjust allow_origins for your deployed frontend URL(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://multi-agent-cloud-architect-ai.vercel.app"],  # tighten this to your frontend's deployed origin before going to prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DesignRequest(BaseModel):
    prompt: str
    preferred_cloud: CloudProvider = CloudProvider.AWS
    target_region: str = "us-east-1"
    environment: str = "prod"


PIPELINE_STAGES = [
    "requirements_analyst",
    "solutions_architect",
    "reviewer_agent",
    "devops_agent",
    "finops_agent",
]


@app.get("/api/health")
def health():
    return {"status": "ok", "stages": PIPELINE_STAGES}


@app.post("/api/design")
def design(req: DesignRequest):
    """Blocking endpoint: runs the full pipeline and returns the final state."""
    user_request = UserRequest(
        prompt=req.prompt,
        preferred_cloud=req.preferred_cloud,
        target_region=req.target_region,
        environment=req.environment,
    )
    try:
        result = run_pipeline(user_request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return json.loads(result.model_dump_json())


@app.post("/api/design/stream")
async def design_stream(req: DesignRequest):
    """
    SSE endpoint: streams {stage, status, detail} events as each agent runs,
    then a final {stage: "pipeline", status: "completed", detail: <PipelineState>} event.
    """
    user_request = UserRequest(
        prompt=req.prompt,
        preferred_cloud=req.preferred_cloud,
        target_region=req.target_region,
        environment=req.environment,
    )

    event_queue: "queue.Queue[dict]" = queue.Queue()
    SENTINEL = object()

    def progress_cb(stage: str, status: str, detail: dict) -> None:
        # detail may contain pydantic-derived nested dicts with enums/datetimes;
        # json.dumps needs default=str for those.
        event_queue.put({"stage": stage, "status": status, "detail": detail})

    def worker() -> None:
        try:
            result = run_pipeline(user_request, progress_cb=progress_cb)
            event_queue.put({
                "stage": "pipeline",
                "status": "completed",
                "detail": json.loads(result.model_dump_json()),
            })
        except Exception as exc:  # noqa: BLE001
            event_queue.put({
                "stage": "pipeline",
                "status": "failed",
                "detail": {"error": str(exc)},
            })
        finally:
            event_queue.put(SENTINEL)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    async def event_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, event_queue.get)
            if item is SENTINEL:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
