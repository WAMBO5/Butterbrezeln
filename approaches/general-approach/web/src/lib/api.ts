// Client for the Certivity FastAPI service (server/main.py). Same origin when the UI is served by
// `certivity serve`; http://localhost:8000 when it runs on the Astro dev server.
export const API_BASE: string =
  import.meta.env.PUBLIC_API_BASE ??
  (typeof window !== "undefined" && window.location.port === "4321" ? "http://localhost:8000" : "");

export type State = "applicable" | "uncertain" | "not_applicable";
export type Evidence = "met" | "not_met" | "evidence_needed";

export interface Source { regulation: string; version: string; page: number; paragraph: string | null }
export interface Requirement {
  id: string; text: string; source: Source; part_ids: string[]; obligation_ids: string[];
  state: "applicable" | "uncertain"; reason: string; evidence_status: Evidence; test_case: string | null;
}
export interface Fact { fact_id: string; key: string; value: string; unit: string | null; source: "spec" | "drawing"; quote: string }
export interface Part { part_id: string; name: string; functions: string[]; properties: string[]; materials: string[]; facts: Fact[] }
export interface Profile { product_type: string; vehicle_categories: string[]; parts: Part[]; relations: string[]; unknowns: string[] }
export interface Decision {
  regulation: string; version_label: string; state: State; path: string; part_ids: string[];
  sections: { part_id: string; section_ids: string[] }[]; reason: string; evidence: string[];
  consolidation_override: string | null;
}
export interface Plan { decisions: Decision[]; parts_without_regulation: string[] }
export interface ScoreLevel { precision: number; recall: number; f1: number; n_submitted: number; n_expected: number; n_matched: number }
export interface Run {
  run_id: string; case_id: string; case_dir: string; mode: "benchmark" | "assisted"; markets: string[];
  status: "running" | "awaiting_review" | "done" | "stopped" | "failed"; step: string | null;
  checkpoint: string | null; checkpoint_errors: string[]; started_at: string; finished_at: string | null;
  error: string | null; partial: boolean; stopped: boolean; profile: Profile | null; plan: Plan | null;
  safety_hits: { regulation: string; query: string; best_rank: number; excluded: boolean }[];
  requirements: Requirement[]; stage_counts: Record<string, number>;
  cost: { spent_usd?: number; max_cost_usd?: number; per_agent?: Record<string, AgentCost> };
  validation_problems: string[]; score: Record<string, ScoreLevel> | null; give_ups: string[];
  markets_result: MarketsResult | null; open_items: string[]; human_actions: Record<string, unknown>[];
  review_status: "reviewed" | "unreviewed"; label: string | null; missing_texts: string[]; quotes: Record<string, string>;
}
export interface AgentCost { model: string; calls: number; input: number; output: number; cache_read: number; cache_write: number; cost_usd: number }
export interface RunListItem { run_id: string; case_id: string; mode: string; status: string; checkpoint: string | null; started_at: string; requirements: number; cost_usd: number; partial: boolean }
export interface CaseItem { case_id: string; case_dir: string; has_expected: boolean; files: string[] }
export interface LineageLink { step: string; ref: string; summary: string }
export interface Page { regulation: string; version: string; page: number; text: string; pages: number; highlight: [number, number] | null }
export interface LedgerRecord { seq: number; ts: string; kind: string; actor: string; meta: Record<string, any> }
export interface MarketVerdict { market_id: string; verdict: "ready" | "evidence_needed" | "blocked" | "not_covered"; blocking: string[]; missing_evidence: string[]; extras: string[] }
export interface MarketsResult {
  markets: { profiles: MarketProfile[]; sets: Record<string, { requirement_id: string; regulation: string; version_label: string; page: number; paragraph: string; text: string; change: string }[]>;
             core_extras: { core: string[]; extras: Record<string, string[]>; envelope: string[] }; verdicts: MarketVerdict[]; fix_ranking: { requirement_id: string; markets_held_back: string[] }[] };
  ship_plan: ShipPlan | null;
}
export interface MarketProfile { market_id: string; name: string; illustrative: boolean; rules: { regulation: string; status: string; version_role: string }[]; outside_corpus: { document_id: string; quote: string }[] }
export interface ShipPlan { envelope_summary: string; actions: { title: string; kind: string; requirement_ids: string[]; markets_unlocked: string[]; rationale: string }[]; synergies: string[]; caveats: string[] }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  health: () => call<{ status: string; fake_llm: boolean }>("/health"),
  cases: () => call<CaseItem[]>("/cases"),
  runs: () => call<RunListItem[]>("/runs"),
  run: (id: string) => call<Run>(`/runs/${encodeURIComponent(id)}`),
  start: (case_dir: string, markets: string[], mode: string) => call<{ run_id: string }>("/runs", json({ case_dir, markets, mode })),
  upload: (form: FormData) => call<{ run_id: string }>("/runs/upload", { method: "POST", body: form }),
  ledger: (id: string) => call<LedgerRecord[]>(`/runs/${encodeURIComponent(id)}/ledger`),
  lineage: (id: string, rid: string) => call<{ requirement_id: string; links: LineageLink[] }>(`/runs/${encodeURIComponent(id)}/requirements/${encodeURIComponent(rid)}/lineage`),
  page: (reg: string, version: string, page: number, quote?: string) =>
    call<Page>(`/pages/${encodeURIComponent(reg)}/${encodeURIComponent(version)}/${page}` + (quote ? `?quote=${encodeURIComponent(quote)}` : "")),
  provision: (id: string) => call<{ text: string; page_start: number; paragraph: string }>(`/provisions/${encodeURIComponent(id)}`),
  checkpoints: (id: string) => call<{ status: string; checkpoint: string | null; errors: string[]; excluded: Decision[]; open_items: string[] }>(`/runs/${encodeURIComponent(id)}/checkpoints`),
  resume: (id: string, checkpoint: string, reviewer: string, actions: { action: string; target_id?: string | null; reason?: string | null; payload?: Record<string, unknown> | null }[]) =>
    call<{ status: string }>(`/runs/${encodeURIComponent(id)}/checkpoints/${checkpoint}`, json({ reviewer, actions })),
  stop: (id: string, reviewer: string, reason: string) => call<{ status: string }>(`/runs/${encodeURIComponent(id)}/stop`, json({ reviewer, reason })),
  signoff: (id: string, reviewer: string, statement: string) => call<{ reviewer: string; ts: string }>(`/runs/${encodeURIComponent(id)}/signoff`, json({ reviewer, statement })),
  markets: () => call<MarketProfile[]>("/markets"),
  rerunMarkets: (id: string, markets: string[]) => call<{ status: string }>(`/runs/${encodeURIComponent(id)}/markets`, json({ markets })),
  events: (id: string) => new EventSource(API_BASE + `/runs/${encodeURIComponent(id)}/events`),
  url: (path: string) => API_BASE + path,
};

export const runId = (): string | null => new URLSearchParams(window.location.search).get("id");
