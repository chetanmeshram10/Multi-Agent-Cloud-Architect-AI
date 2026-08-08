export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const STAGES = [
  {
    id: "requirements_analyst",
    code: "01",
    label: "Requirements Analyst",
    verb: "Reading the brief",
  },
  {
    id: "solutions_architect",
    code: "02",
    label: "Solutions Architect",
    verb: "Drafting the design",
  },
  {
    id: "reviewer_agent",
    code: "03",
    label: "Reviewer",
    verb: "Checking against the Well-Architected Framework",
  },
  {
    id: "devops_agent",
    code: "04",
    label: "DevOps",
    verb: "Writing Terraform",
  },
  {
    id: "finops_agent",
    code: "05",
    label: "FinOps",
    verb: "Pricing it out",
  },
];
