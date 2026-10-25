import type { PipelineRunInfo } from "../types";

export function money(usd: number): string {
  return `${usd.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} $`;
}

export function when(ts?: string | null): string {
  return ts ? new Date(ts).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "–";
}

/** What the result cost, including the steps a replay reused from the run it is based on. */
export function totalCost(p: PipelineRunInfo): number | null {
  return p.cost_usd == null ? null : p.cost_usd + (p.inherited_cost_usd ?? 0);
}

/** The run's funnel from all regulations down to the requirements, in the order the pipeline narrows. */
export const FUNNEL: { key: string; label: string }[] = [
  { key: "regulations", label: "Vorschriften im Korpus" },
  { key: "kept_regulations", label: "für Ihr Produkt behalten" },
  { key: "candidate_provisions", label: "Fundstellen geprüft" },
  { key: "obligations", label: "Pflichten wörtlich zitiert" },
  { key: "decisions", label: "Abgleich-Entscheidungen" },
  { key: "requirements", label: "Anforderungen" },
];

/** Agent names of the pipeline, in plain words. */
export const PIPELINE_AGENT: Record<string, string> = {
  product_analyst: "Produktanalyse",
  profile_verifier: "Gegenprüfung Produkt",
  scope_narrower: "Eingrenzung Vorschriften",
  recall_auditor: "Gegenprüfung Vorschriften",
  obligation_extractor: "Pflichten zitieren",
  requirement_matcher: "Abgleich",
  match_reviewer: "Gegenprüfung Abgleich",
  output_auditor: "Schlussprüfung",
};
