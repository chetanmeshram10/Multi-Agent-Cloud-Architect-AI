import { useState } from "react";

const TABS = [
  { id: "requirements", label: "Requirements" },
  { id: "architecture", label: "Architecture" },
  { id: "review", label: "Review" },
  { id: "terraform", label: "Terraform" },
  { id: "cost", label: "Cost" },
];

const PILLAR_LABELS = {
  operational_excellence: "Operational Excellence",
  security: "Security",
  reliability: "Reliability",
  performance_efficiency: "Performance",
  cost_optimization: "Cost",
  sustainability: "Sustainability",
};

function Empty({ label }) {
  return <p className="text-sm text-ink-faint font-mono py-8 text-center">{label} hasn't run yet.</p>;
}

function Pill({ children, tone = "default" }) {
  const tones = {
    default: "bg-blueprint-panel2 border-blueprint-border text-ink-muted",
    ok: "bg-ok/10 border-ok/40 text-ok",
    warn: "bg-warn/10 border-warn/40 text-warn",
    err: "bg-err/10 border-err/40 text-err",
    cyan: "bg-cyan-soft/40 border-cyan/40 text-cyan",
  };
  return (
    <span className={`inline-block text-xs font-mono border rounded px-2 py-0.5 ${tones[tone]}`}>
      {children}
    </span>
  );
}

function ScoreBar({ label, score }) {
  const tone = score >= 80 ? "#4ADE80" : score >= 60 ? "#F5A623" : "#F87171";
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs font-mono text-ink-muted mb-1">
        <span>{label}</span>
        <span>{score}</span>
      </div>
      <div className="h-1.5 bg-blueprint-panel2 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${score}%`, background: tone }} />
      </div>
    </div>
  );
}

function RequirementsPanel({ requirements }) {
  if (!requirements) return <Empty label="Requirements Analyst" />;
  const r = requirements;
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink leading-relaxed">{r.app_description}</p>
      <div className="flex flex-wrap gap-2">
        <Pill tone="cyan">{r.app_type}</Pill>
        <Pill>{r.expected_traffic} traffic</Pill>
        <Pill>{r.latency_requirement} latency</Pill>
        {r.ha_required && <Pill tone="ok">HA required</Pill>}
        {r.multi_region && <Pill tone="ok">multi-region</Pill>}
        {r.budget_ceiling_usd && <Pill tone="warn">budget ${r.budget_ceiling_usd}/mo</Pill>}
      </div>
      {r.integrations?.length > 0 && (
        <div>
          <p className="font-mono text-xs text-ink-faint uppercase mb-1">Integrations</p>
          <p className="text-sm text-ink-muted">{r.integrations.join(", ")}</p>
        </div>
      )}
      {r.open_questions?.length > 0 && (
        <div>
          <p className="font-mono text-xs text-ink-faint uppercase mb-1">Open questions</p>
          <ul className="text-sm text-ink-muted list-disc list-inside space-y-1">
            {r.open_questions.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </div>
      )}
      <p className="text-xs text-ink-faint font-mono">confidence {(r.confidence_score * 100).toFixed(0)}%</p>
    </div>
  );
}

function ArchitecturePanel({ architecture }) {
  if (!architecture) return <Empty label="Solutions Architect" />;
  const a = architecture;
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink leading-relaxed">{a.topology_description}</p>
      <div className="space-y-2">
        {a.services?.map((s, i) => (
          <div key={i} className="border border-blueprint-border rounded-md p-3 bg-blueprint-panel2">
            <div className="flex items-center justify-between">
              <span className="font-display font-semibold text-sm text-ink">{s.service_name}</span>
              {s.estimated_monthly_usd != null && (
                <span className="font-mono text-xs text-amber">${s.estimated_monthly_usd}/mo</span>
              )}
            </div>
            <p className="text-xs text-ink-muted mt-1">{s.purpose}</p>
            <p className="text-xs text-cyan mt-1 font-mono">{PILLAR_LABELS[s.primary_waf_pillar] || s.primary_waf_pillar}</p>
          </div>
        ))}
      </div>
      {a.network_design && (
        <div>
          <p className="font-mono text-xs text-ink-faint uppercase mb-1">Network</p>
          <p className="text-sm text-ink-muted">{a.network_design}</p>
        </div>
      )}
      {a.security_controls?.length > 0 && (
        <div>
          <p className="font-mono text-xs text-ink-faint uppercase mb-1">Security controls</p>
          <ul className="text-sm text-ink-muted list-disc list-inside space-y-1">
            {a.security_controls.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
      <p className="text-xs text-ink-faint font-mono">revision {a.revision_number} · {a.approved ? "approved" : "pending review"}</p>
    </div>
  );
}

function ReviewPanel({ review }) {
  if (!review) return <Empty label="Reviewer" />;
  const r = review;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Pill tone={r.approved ? "ok" : "err"}>{r.approved ? "Approved" : "Changes requested"}</Pill>
        <span className="font-mono text-sm text-ink-muted">WAF score {r.waf_score}/100</span>
      </div>
      <p className="text-sm text-ink leading-relaxed">{r.summary}</p>
      {Object.keys(r.waf_pillar_scores || {}).length > 0 && (
        <div>
          {Object.entries(r.waf_pillar_scores).map(([k, v]) => (
            <ScoreBar key={k} label={PILLAR_LABELS[k] || k} score={Math.round(v)} />
          ))}
        </div>
      )}
      {r.findings?.length > 0 && (
        <div className="space-y-2">
          <p className="font-mono text-xs text-ink-faint uppercase">Findings</p>
          {r.findings.map((f, i) => (
            <div key={i} className="border border-blueprint-border rounded-md p-3 bg-blueprint-panel2">
              <div className="flex items-center gap-2">
                <Pill tone={f.severity === "blocker" ? "err" : f.severity === "warning" ? "warn" : "default"}>
                  {f.severity}
                </Pill>
                <span className="text-sm font-semibold text-ink">{f.title}</span>
              </div>
              <p className="text-xs text-ink-muted mt-1">{f.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TerraformPanel({ terraform }) {
  if (!terraform) return <Empty label="DevOps" />;
  const t = terraform;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Pill tone={t.validation_passed ? "ok" : "err"}>
          {t.validation_passed ? "Validation passed" : "Validation failed"}
        </Pill>
        {t.retry_count > 0 && <span className="font-mono text-xs text-ink-faint">retries: {t.retry_count}</span>}
      </div>
      {t.validation_errors && <p className="text-sm text-err font-mono">{t.validation_errors}</p>}
      {t.resources_provisioned?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {t.resources_provisioned.map((r, i) => <Pill key={i}>{r}</Pill>)}
        </div>
      )}
      <pre className="bg-blueprint-panel2 border border-blueprint-border rounded-md p-4 text-xs font-mono text-ink-muted overflow-x-auto max-h-96 scrollbar-thin whitespace-pre-wrap">
        {t.hcl_code}
      </pre>
    </div>
  );
}

function CostPanel({ cost }) {
  if (!cost) return <Empty label="FinOps" />;
  const c = cost;
  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-3">
        <span className="font-display font-bold text-2xl text-amber">${c.monthly_total_usd.toLocaleString()}</span>
        <span className="text-xs text-ink-faint font-mono">/ month · ${c.annual_total_usd?.toLocaleString()} / year</span>
      </div>
      {c.budget_ceiling_usd != null && (
        <Pill tone={c.within_budget ? "ok" : "err"}>
          {c.within_budget ? "within budget" : "over budget"} (ceiling ${c.budget_ceiling_usd})
        </Pill>
      )}
      <div className="space-y-2">
        {c.breakdown?.map((item, i) => (
          <div key={i} className="flex items-center justify-between border-b border-blueprint-border pb-2">
            <div>
              <p className="text-sm text-ink">{item.service_name}</p>
              {item.assumptions && <p className="text-xs text-ink-faint">{item.assumptions}</p>}
            </div>
            <span className="font-mono text-sm text-ink-muted">${item.monthly_usd.toLocaleString()}</span>
          </div>
        ))}
      </div>
      {c.cost_optimization_summary && (
        <p className="text-sm text-ink-muted leading-relaxed">{c.cost_optimization_summary}</p>
      )}
    </div>
  );
}

export default function ResultsPanels({ state }) {
  const [active, setActive] = useState("requirements");

  return (
    <div>
      <div className="flex gap-1 border-b border-blueprint-border mb-4 overflow-x-auto scrollbar-thin">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`font-mono text-xs uppercase tracking-wide px-3 py-2 border-b-2 whitespace-nowrap transition-colors ${
              active === tab.id
                ? "border-amber text-amber"
                : "border-transparent text-ink-faint hover:text-ink-muted"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div>
        {active === "requirements" && <RequirementsPanel requirements={state.requirements} />}
        {active === "architecture" && <ArchitecturePanel architecture={state.architecture} />}
        {active === "review" && <ReviewPanel review={state.review} />}
        {active === "terraform" && <TerraformPanel terraform={state.terraform} />}
        {active === "cost" && <CostPanel cost={state.cost_estimate} />}
      </div>
    </div>
  );
}
