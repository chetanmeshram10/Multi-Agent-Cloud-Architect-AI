# CloudArchitect AI

A multi-agent system that turns a plain-English project brief into an AWS architecture,
an independent Well-Architected review, apply-ready Terraform, and a monthly cost estimate.

```
Requirements Analyst → Solutions Architect → Reviewer ⇄ (revise) → DevOps ⇄ (retry) → FinOps
```

Built with **LangGraph** (orchestration), **Groq** (LLM inference), **FastAPI** (backend API),
and **React + Tailwind** (frontend).

---

## ⚠️ Rotate your Groq API key first

An earlier Groq key was pasted directly into a Cursor chat transcript that got shared for this
build. Treat that key as compromised — rotate it now at
[console.groq.com](https://console.groq.com/keys) before doing anything else, then put the new
key in `backend/.env` (never in code, never in chat) as:

```
GROQ_API_KEY=your_new_key_here
```

---

## Project structure

```
cloudarchitect-ai/
├── backend/
│   ├── agents/                  # 5 standalone agent modules (LLM calls)
│   ├── orchestration/graph.py   # LangGraph wiring: revision loop + retry loop
│   ├── schemas/models.py        # single source of truth Pydantic models
│   ├── tools/terraform_validator.py
│   ├── main.py                  # FastAPI app (blocking + SSE streaming endpoints)
│   ├── test_graph_mocked.py     # verifies control flow without calling the LLM
│   ├── requirements.txt
│   └── .env                     # GROQ_API_KEY — lives HERE, inside backend/ (gitignored)
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── constants.js
    │   └── components/
    │       ├── PipelineTrace.jsx   # live animated agent trace
    │       ├── BriefForm.jsx
    │       └── ResultsPanels.jsx
    └── .env                      # VITE_API_URL — lives HERE, inside frontend/ (gitignored)
```

## Run it locally

**Backend**

```bash
cd backend
python -m venv venv && source venv/bin/activate      # optional
pip install -r requirements.txt
cp .env.example .env                                  # then paste your Groq key in
python main.py                                        # http://localhost:8000
```

Sanity-check the graph's control flow **without spending Groq quota**:

```bash
python test_graph_mocked.py
```

Sanity-check each agent standalone (uses real Groq calls, as before):

```bash
python agents/requirements_analyst.py
```

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL=http://localhost:8000 for local dev
npm run dev                # http://localhost:5173
```

Open `http://localhost:5173`, describe a workload, and watch the trace light up as each
agent runs. Results land in the tabs on the right as they complete.

## How the pipeline is wired (`orchestration/graph.py`)

- **Revision loop**: if the Reviewer doesn't approve the design, the Architect gets the
  `required_changes` back and produces a new revision — up to `MAX_ARCHITECTURE_REVISIONS`
  (default 3), after which the pipeline proceeds with the best attempt so it never stalls.
- **Terraform retry loop**: if the generated HCL fails `terraform_validator.py`'s checks,
  DevOps retries — up to `MAX_TERRAFORM_RETRIES` (default 2).
- Every node reports progress via a callback, which `main.py` turns into Server-Sent Events
  so the frontend can show live status per agent instead of one long spinner.

## API

- `GET /api/health` — liveness check
- `POST /api/design` — blocking; runs the full pipeline, returns the final state as JSON
- `POST /api/design/stream` — SSE; streams `{stage, status, detail}` per agent, then a final
  `{stage: "pipeline", status: "completed", detail: <full state>}` event

Both accept:
```json
{ "prompt": "A highly available video streaming backend", "target_region": "us-east-1", "environment": "prod" }
```

## Deploying the demo

A simple, free-tier-friendly path:

1. **Backend → Render (or Railway/Fly.io)**
   - New Web Service from this repo, root directory `backend/`
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Env var: `GROQ_API_KEY`
   - Note the deployed URL, e.g. `https://cloudarchitect-api.onrender.com`

2. **Frontend → Vercel (or Netlify)**
   - Import this repo, root directory `frontend/`
   - Build command: `npm run build`, output dir: `dist`
   - Env var: `VITE_API_URL=https://cloudarchitect-api.onrender.com`

3. **Lock down CORS**: in `backend/main.py`, change
   `allow_origins=["*"]` to your actual Vercel URL before sharing the demo publicly —
   the wildcard is fine for local testing but you don't want a public API open to any origin.

4. Groq's free tier has real rate limits — if the demo gets hammered, requests will 429.
   Consider a short client-side cooldown on the submit button, or a small in-memory queue,
   if you expect concurrent visitors during a demo.

## Free-tier gotcha to plan around

Render/Railway free tiers spin down on inactivity — the first request after idling can take
10–20s to cold-start, which will look like the pipeline is stuck. Worth a "waking up the
backend…" message client-side, or a paid always-on tier if this is going in front of
reviewers/recruiters.
