import { useRef, useState } from "react";
import { API_BASE, STAGES } from "./constants";
import PipelineTrace from "./components/PipelineTrace";
import BriefForm from "./components/BriefForm";
import ResultsPanels from "./components/ResultsPanels";

const idleStatuses = Object.fromEntries(STAGES.map((s) => [s.id, "idle"]));

export default function App() {
  const [statuses, setStatuses] = useState(idleStatuses);
  const [loopInfo, setLoopInfo] = useState({ revision_number: 1, terraform_retry_count: 0 });
  const [running, setRunning] = useState(false);
  const [pipelineState, setPipelineState] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const abortRef = useRef(null);

  const runPipeline = async (payload) => {
    setRunning(true);
    setErrorMsg(null);
    setPipelineState(null);
    setStatuses(idleStatuses);
    setLoopInfo({ revision_number: 1, terraform_retry_count: 0 });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/api/design/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Server responded with ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop();

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.slice(5).trim();
          if (!jsonStr) continue;
          const event = JSON.parse(jsonStr);
          handleEvent(event);
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        setErrorMsg(err.message || "Something went wrong talking to the backend.");
      }
    } finally {
      setRunning(false);
    }
  };

  const handleEvent = (event) => {
    const { stage, status, detail } = event;

    if (stage === "pipeline") {
      if (status === "completed") {
        setPipelineState(detail);
      } else if (status === "failed") {
        setErrorMsg(detail?.error || "Pipeline failed.");
      }
      return;
    }

    // Backend emits "started" / "completed" / "failed"; PipelineTrace expects
    // "running" / "done" / "failed". Normalize here rather than in the graph,
    // since "started"/"completed" read more naturally in backend logs.
    const STATUS_MAP = { started: "running", completed: "done", failed: "failed" };
    setStatuses((prev) => ({ ...prev, [stage]: STATUS_MAP[status] || status }));

    if (stage === "solutions_architect" && status === "completed" && detail?.architecture) {
      setLoopInfo((prev) => ({ ...prev, revision_number: detail.architecture.revision_number || prev.revision_number }));
    }
    if (stage === "devops_agent" && status === "completed" && detail?.terraform) {
      setLoopInfo((prev) => ({ ...prev, terraform_retry_count: detail.terraform.retry_count || 0 }));
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="relative border-b border-blueprint-border overflow-hidden">
        <div
          className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 w-[560px] h-[280px] rounded-full opacity-[0.15] blur-3xl"
          style={{ background: "radial-gradient(closest-side, #5EC8D8, transparent)" }}
        />
        <div className="relative max-w-6xl mx-auto px-6 pt-12 pb-8 md:pt-16 md:pb-10">
          <div className="flex items-start justify-between gap-6">
            <div>
              <p className="font-mono text-[11px] text-cyan tracking-[0.2em] uppercase mb-3">
                AI-orchestrated infrastructure design
              </p>
              <h1 className="font-display font-bold text-4xl md:text-5xl text-ink tracking-tight leading-none">
                CloudArchitect <span className="text-amber">AI</span>
              </h1>
              <p className="text-sm md:text-base text-ink-muted mt-4 max-w-xl leading-relaxed">
                Describe a workload in plain English. Five specialist agents draft, review,
                cost, and provision the AWS architecture — live, in front of you.
              </p>
            </div>
            <a
              href="https://github.com"
              className="shrink-0 text-xs font-mono text-ink-faint hover:text-cyan border border-blueprint-border hover:border-cyan/50 rounded px-3 py-1.5 transition-colors"
            >
              view source
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-10 flex-1 w-full">
        <section className="bg-blueprint-panel border border-blueprint-border rounded-xl p-6 md:p-8">
          <PipelineTrace statuses={statuses} loopInfo={loopInfo} />
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          <div className="lg:col-span-2">
            <div className="bg-blueprint-panel border border-blueprint-border rounded-xl p-6 sticky top-6">
              <h2 className="font-display font-semibold text-sm text-ink mb-4 uppercase tracking-wide">
                Describe the workload
              </h2>
              <BriefForm onSubmit={runPipeline} disabled={running} />
              {errorMsg && (
                <p className="mt-4 text-sm text-err font-mono border border-err/30 bg-err/5 rounded-md p-3">
                  {errorMsg}
                </p>
              )}
            </div>
          </div>

          <div className="lg:col-span-3">
            <div className="bg-blueprint-panel border border-blueprint-border rounded-xl p-6 min-h-[400px]">
              <h2 className="font-display font-semibold text-sm text-ink mb-4 uppercase tracking-wide">
                Results
              </h2>
              {pipelineState ? (
                <ResultsPanels state={pipelineState} />
              ) : (
                <p className="text-sm text-ink-faint font-mono py-12 text-center">
                  {running ? "Working through the pipeline — watch the trace above." : "Submit a brief to see results here."}
                </p>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-blueprint-border mt-auto">
        <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs font-mono">
          <span className="text-ink-faint">
            Requirements Analyst → Solutions Architect → Reviewer → DevOps → FinOps, orchestrated with LangGraph.
          </span>
          <span className="text-ink-faint">
            Built by <span className="text-ink-muted">Chetan Meshram</span>
          </span>
        </div>
      </footer>
    </div>
  );
}
