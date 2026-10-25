import type { PipelineRunInfo } from "../types";

export function money(usd: number): string {
  return `$${usd.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function when(ts?: string | null): string {
  return ts ? new Date(ts).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "–";
}

/** What the result cost, including the steps a replay reused from the run it is based on. */
export function totalCost(p: PipelineRunInfo): number | null {
  return p.cost_usd == null ? null : p.cost_usd + (p.inherited_cost_usd ?? 0);
}

/** The run's funnel from all regulations down to the requirements, in the order the pipeline narrows. */
export const FUNNEL: { key: string; label: string }[] = [
  { key: "regulations", label: "Regulations in the corpus" },
  { key: "kept_regulations", label: "Kept for your product" },
  { key: "candidate_provisions", label: "Provisions checked" },
  { key: "obligations", label: "Obligations quoted verbatim" },
  { key: "decisions", label: "Match decisions" },
  { key: "requirements", label: "Requirements" },
];

/** Agent names of the pipeline, in plain words. */
export const PIPELINE_AGENT: Record<string, string> = {
  product_analyst: "Product analysis",
  profile_verifier: "Product cross-check",
  scope_narrower: "Regulation scoping",
  recall_auditor: "Regulation cross-check",
  obligation_extractor: "Obligation quoting",
  requirement_matcher: "Matching",
  match_reviewer: "Match cross-check",
  output_auditor: "Final audit",
};
