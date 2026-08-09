import { useState } from "react";

const EXAMPLES = [
  { text: "An internal analytics dashboard for a 40-person startup, low budget", recommended: true },
  { text: "A simple REST API backend for a mobile app, moderate traffic, single region" },
  { text: "A static company website with a contact form, low traffic" },
];

export default function BriefForm({ onSubmit, disabled }) {
  const [prompt, setPrompt] = useState("");
  const [region, setRegion] = useState("us-east-1");
  const [environment, setEnvironment] = useState("prod");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim() || disabled) return;
    onSubmit({ prompt: prompt.trim(), target_region: region, environment });
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="block font-mono text-xs text-ink-faint tracking-wide uppercase mb-2">
          Project brief
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. An internal analytics dashboard for a 40-person startup, low budget"
          rows={4}
          disabled={disabled}
          className="w-full bg-blueprint-panel2 border border-blueprint-border rounded-md px-4 py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-cyan/50 focus:border-cyan disabled:opacity-50 resize-none"
        />
        <div className="flex flex-wrap gap-2 mt-2">
          {EXAMPLES.map((ex) => (
            <button
              type="button"
              key={ex.text}
              disabled={disabled}
              onClick={() => setPrompt(ex.text)}
              className={`text-xs font-mono rounded px-2 py-1 border transition-colors disabled:opacity-40 ${
                ex.recommended
                  ? "text-amber border-amber/50 hover:border-amber bg-amber/5"
                  : "text-ink-faint border-blueprint-border hover:text-cyan hover:border-cyan/50"
              }`}
            >
              {ex.recommended && "✓ "}
              {ex.text.length > 40 ? ex.text.slice(0, 40) + "…" : ex.text}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block font-mono text-xs text-ink-faint tracking-wide uppercase mb-2">
            Target region
          </label>
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            disabled={disabled}
            className="w-full bg-blueprint-panel2 border border-blueprint-border rounded-md px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-cyan/50 disabled:opacity-50"
          >
            <option value="us-east-1">us-east-1 (N. Virginia)</option>
            <option value="us-west-2">us-west-2 (Oregon)</option>
            <option value="eu-west-1">eu-west-1 (Ireland)</option>
            <option value="ap-south-1">ap-south-1 (Mumbai)</option>
          </select>
        </div>
        <div>
          <label className="block font-mono text-xs text-ink-faint tracking-wide uppercase mb-2">
            Environment
          </label>
          <select
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
            disabled={disabled}
            className="w-full bg-blueprint-panel2 border border-blueprint-border rounded-md px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-cyan/50 disabled:opacity-50"
          >
            <option value="prod">Production</option>
            <option value="staging">Staging</option>
            <option value="dev">Development</option>
          </select>
        </div>
      </div>

      <button
        type="submit"
        disabled={disabled || !prompt.trim()}
        className="mt-1 bg-amber text-blueprint-bg font-display font-semibold text-sm rounded-md py-3 hover:bg-amber/90 active:scale-[0.99] transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {disabled ? "Designing…" : "Run the pipeline"}
      </button>
    </form>
  );
}