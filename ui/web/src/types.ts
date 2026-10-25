// Mirrors api/models.py

export type SourceKind = "spec" | "un_regulation" | "country_profile" | "external" | "dataset";
export type FindingStatus = "met" | "open" | "conflict";
export type Effort = "documentation" | "testing" | "design";
export type VerdictStatus = "green" | "yellow" | "red" | "grey";
export type Regime = "unece_1958" | "national" | "not_covered";
export type Decision = "open" | "accepted" | "rejected";

export interface Source {
  kind: SourceKind;
  label: string;
  title?: string | null;
  regulation?: string | null;
  version?: string | null;
  page?: number | null;
  paragraph?: string | null;
  pdf_url?: string | null;
  sha256?: string | null;
  spec_lines?: number[] | null;
  url?: string | null;
  href?: string | null;
  in_certivity_corpus: boolean;
}

/** One link of the pipeline's chain for a requirement (lineage.json), resolved to our trace. */
export interface LineageLink {
  step: string; // part | fact | scope_decision | provision | obligation | match_decision
  ref: string;
  summary: string;
  trace_id?: string | null;
  spec_lines?: number[] | null;
}

/** What the certivity pipeline recorded for one requirement. */
export interface PipelineDetail {
  state: string; // applicable | uncertain
  reason: string;
  evidence_status: string; // evidence_needed | met
  test_case: string;
  parts: string[];
  lineage: LineageLink[];
}

export interface Requirement {
  id: string;
  text: string;
  source: Source;
  trace_ids: string[];
  pipeline?: PipelineDetail | null;
}

export interface Finding {
  id: string;
  requirement_id: string;
  regulation: string;
  status: FindingStatus;
  effort?: Effort | null;
  spec_lines?: number[] | null;
  explanation: string;
  suggestion?: string | null;
  trace_ids: string[];
}

export interface SpecNote {
  id: string;
  text: string;
  spec_lines?: number[] | null;
  requirement_ids: string[];
  trace_ids: string[];
}

export interface Suggestion {
  id: string;
  country: string;
  requirement_id?: string | null;
  deviation_id?: string | null;
  spec_section: string;
  change: string;
  reason: string;
  effort: Effort;
  sources: Source[];
  trace_ids: string[];
  decision: Decision;
}

export interface CountryVerdict {
  iso3: string;
  name: string;
  status: VerdictStatus;
  regime: Regime;
  reasons: string[];
  blocking_finding_ids: string[];
  open_evidence_count: number;
  suggestions: Suggestion[];
  sources: Source[];
  trace_ids: string[];
}

export interface TraceEvent {
  id: string;
  run_id: string;
  parent_id?: string | null;
  agent: string;
  action: string;
  ts_start: string;
  ts_end?: string | null;
  status: "running" | "ok" | "fallback" | "error";
  inputs_summary: string;
  outputs_summary: string;
  model?: string | null;
  prompt_sha256?: string | null;
  tokens?: Record<string, number> | null;
  sources: Source[];
  tags: Record<string, string>;
}

export interface QAEntry {
  id: string;
  country: string;
  question: string;
  answer: string;
  suggestion_ids: string[];
  sources: Source[];
  trace_ids: string[];
}

/** The certivity pipeline run a result was read from (BACKEND_MODE=runs). */
export interface PipelineRunInfo {
  run_id: string;
  case_id: string;
  path: string;
  started_at?: string | null;
  finished_at?: string | null;
  git_commit?: string | null;
  cost_usd?: number | null;
  inherited_cost_usd?: number | null;
  models: Record<string, string>;
  funnel: Record<string, number>;
  product_type?: string | null;
  vehicle_categories: string[];
  parts: string[];
  unknowns: string[];
  open_issues: string[];
  give_ups: string[];
  review_issues: number;
  excluded: { regulation: string; reason: string }[];
  score?: Record<string, Record<string, number>> | null;
  replay_of?: string | null;
  ledger?: { records: number; intact: boolean; problems: string[]; head?: string | null } | null;
  label?: string | null;
}

export interface RunResult {
  run_id: string;
  created_at: string;
  status: "running" | "done" | "error";
  error?: string | null;
  spec_name: string;
  spec_text: string;
  countries: string[];
  backend_mode: string;
  llm_mode: string;
  has_image?: boolean;
  pipeline?: PipelineRunInfo | null;
  requirements: Requirement[];
  findings: Finding[];
  spec_notes: SpecNote[];
  verdicts: Record<string, CountryVerdict>;
  validation?: { ok: boolean; problems: string[] } | null;
  qa: QAEntry[];
}

export interface CountryItem {
  iso3: string;
  name: string;
  regime: Regime;
  has_profile: boolean;
}

export interface CountryListing {
  countries: CountryItem[];
  presets: Record<string, string[]>;
  meta: { sources?: { title: string; url: string; retrieved?: string }[]; notes?: string };
}

export interface Health {
  backend_mode: string;
  llm: { available: boolean; model: string; reason?: string | null };
  countries_loaded: number;
  pipeline?: {
    root: string;
    finished_runs: number;
    cases: string[];
    /** Whether a certivity run can be started from the UI, and why not. */
    launch: { available: boolean; reason?: string | null; fake_llm: boolean };
  } | null;
}

/** A certivity pipeline run started from the UI on an uploaded spec. */
export interface PipelineJob {
  id: string;
  status: "running" | "done" | "failed" | "cancelled";
  started_at: string;
  spec_sha256: string;
  fake_llm: boolean;
  steps: { step: string; label: string; state: "pending" | "running" | "done" }[];
  calls: number;
  cost_usd: number;
  error?: string | null;
  log_tail: string[];
}

// What the lineage drawer is showing
export type LineageTarget =
  | { kind: "requirement"; id: string }
  | { kind: "suggestion"; id: string }
  | { kind: "verdict"; iso3: string };
