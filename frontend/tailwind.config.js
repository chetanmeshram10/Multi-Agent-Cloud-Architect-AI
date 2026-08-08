/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        blueprint: {
          bg: "#0B1220",
          panel: "#111A2C",
          panel2: "#0E1626",
          line: "#1E2A40",
          border: "#243352",
        },
        ink: {
          DEFAULT: "#E7ECF3",
          muted: "#8593AD",
          faint: "#5B6883",
        },
        amber: {
          DEFAULT: "#E8A33D",
          soft: "#7A5A29",
        },
        cyan: {
          DEFAULT: "#5EC8D8",
          soft: "#2E4F57",
        },
        ok: "#4ADE80",
        warn: "#F5A623",
        err: "#F87171",
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      backgroundImage: {
        grid: "linear-gradient(#1E2A40 1px, transparent 1px), linear-gradient(90deg, #1E2A40 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "28px 28px",
      },
      keyframes: {
        dash: { to: { strokeDashoffset: "-24" } },
        pulseRing: {
          "0%, 100%": { opacity: "0.55", transform: "scale(1)" },
          "50%": { opacity: "0", transform: "scale(1.6)" },
        },
      },
      animation: {
        dash: "dash 0.9s linear infinite",
        pulseRing: "pulseRing 1.6s ease-out infinite",
      },
    },
  },
  plugins: [],
};
