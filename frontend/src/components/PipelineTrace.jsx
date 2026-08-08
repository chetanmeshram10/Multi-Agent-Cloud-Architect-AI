import { STAGES } from "../constants";

const NODE_X = [90, 290, 500, 710, 910];
const NODE_Y = 120;
const R = 30;

function statusColor(status) {
  switch (status) {
    case "running":
      return { stroke: "#5EC8D8", fill: "#0E1626", text: "#5EC8D8" };
    case "done":
      return { stroke: "#4ADE80", fill: "#12241C", text: "#4ADE80" };
    case "failed":
      return { stroke: "#F87171", fill: "#241414", text: "#F87171" };
    default:
      return { stroke: "#243352", fill: "#111A2C", text: "#5B6883" };
  }
}

export default function PipelineTrace({ statuses, loopInfo, activeStage }) {
  const segments = [
    [NODE_X[0], NODE_X[1]],
    [NODE_X[1], NODE_X[2]],
    [NODE_X[2], NODE_X[3]],
    [NODE_X[3], NODE_X[4]],
  ];

  const segmentActive = (i) => {
    // segment i is "active" (data flowing) if the stage it leads into is running or done
    const targetStage = STAGES[i + 1]?.id;
    const st = statuses[targetStage];
    return st === "running" || st === "done";
  };

  const revising = loopInfo.revision_number > 1 && statuses.solutions_architect !== "done" || (statuses.reviewer_agent === "running" && loopInfo.revision_number > 1);
  const retrying = loopInfo.terraform_retry_count > 0 && statuses.devops_agent !== "done";

  return (
    <div className="w-full">
      <svg viewBox="0 0 1000 240" className="w-full h-auto select-none" role="img" aria-label="Agent pipeline status">
        {/* revise loop arc: reviewer -> architect */}
        <path
          d={`M ${NODE_X[2] - R} ${NODE_Y - R} C ${NODE_X[2] - 80} 30, ${NODE_X[1] + 80} 30, ${NODE_X[1] + R} ${NODE_Y - R}`}
          fill="none"
          stroke={revising ? "#E8A33D" : "#1E2A40"}
          strokeWidth="2"
          strokeDasharray="6 6"
          className={revising ? "animate-dash" : ""}
          markerEnd={revising ? "url(#arrow-amber)" : "url(#arrow-line)"}
        />
        {loopInfo.revision_number > 1 && (
          <text x={(NODE_X[1] + NODE_X[2]) / 2} y="24" textAnchor="middle" className="fill-amber font-mono" fontSize="12">
            revise · pass {loopInfo.revision_number}
          </text>
        )}

        {/* retry self-loop: devops */}
        <path
          d={`M ${NODE_X[3] + R * 0.7} ${NODE_Y + R * 0.7} C ${NODE_X[3] + 55} ${NODE_Y + 60}, ${NODE_X[3] - 55} ${NODE_Y + 60}, ${NODE_X[3] - R * 0.7} ${NODE_Y + R * 0.7}`}
          fill="none"
          stroke={retrying ? "#E8A33D" : "#1E2A40"}
          strokeWidth="2"
          strokeDasharray="6 6"
          className={retrying ? "animate-dash" : ""}
          markerEnd={retrying ? "url(#arrow-amber)" : "url(#arrow-line)"}
        />
        {loopInfo.terraform_retry_count > 0 && (
          <text x={NODE_X[3]} y="212" textAnchor="middle" className="fill-amber font-mono" fontSize="12">
            retry · attempt {loopInfo.terraform_retry_count + 1}
          </text>
        )}

        <defs>
          <marker id="arrow-amber" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="#E8A33D" />
          </marker>
          <marker id="arrow-line" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="#243352" />
          </marker>
        </defs>

        {/* main connecting segments */}
        {segments.map(([x1, x2], i) => {
          const active = segmentActive(i);
          return (
            <line
              key={i}
              x1={x1 + R}
              y1={NODE_Y}
              x2={x2 - R}
              y2={NODE_Y}
              stroke={active ? "#4ADE80" : "#243352"}
              strokeWidth="2"
              strokeDasharray={active ? "0" : "5 5"}
              markerEnd="url(#arrow-line)"
            />
          );
        })}

        {/* nodes */}
        {STAGES.map((stage, i) => {
          const status = statuses[stage.id] || "idle";
          const c = statusColor(status);
          const x = NODE_X[i];
          return (
            <g key={stage.id}>
              {status === "running" && (
                <circle cx={x} cy={NODE_Y} r={R} fill="none" stroke={c.stroke} strokeWidth="2" className="animate-pulseRing" />
              )}
              <circle cx={x} cy={NODE_Y} r={R} fill={c.fill} stroke={c.stroke} strokeWidth="2" />
              <text x={x} y={NODE_Y - 4} textAnchor="middle" className="font-mono" fontSize="11" fill={c.text}>
                {stage.code}
              </text>
              <text x={x} y={NODE_Y + 12} textAnchor="middle" fontSize="16" fill={c.text}>
                {status === "done" ? "✓" : status === "failed" ? "!" : status === "running" ? "" : ""}
              </text>
              <text x={x} y={NODE_Y + R + 22} textAnchor="middle" className="fill-ink font-display font-semibold" fontSize="13">
                {stage.label}
              </text>
              <text x={x} y={NODE_Y + R + 40} textAnchor="middle" className="fill-ink-faint font-mono" fontSize="10">
                {status === "running" ? stage.verb : status === "done" ? "complete" : status === "failed" ? "error" : "waiting"}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
