import type { Finding, LineageLink, LineageTarget, Requirement, RunResult, Source, Suggestion, TraceEvent } from "../types";
import { countryName } from "./geo";
import { EFFORT, FINDING, STATUS, isAccepted, regulationName } from "./labels";

export interface ChainStep {
  key: string;
  title: string;
  text?: string;
  detail?: string;
  quote?: boolean; // show text as an original quotation
  chips?: string[];
  sources?: Source[];
  specLines?: number[] | null;
  event?: TraceEvent;
  links?: { label: string; target: LineageTarget }[];
}

interface Index {
  events: Map<string, TraceEvent>;
  requirements: Map<string, Requirement>;
  findingsByReq: Map<string, Finding>;
  suggestions: Map<string, Suggestion>;
}

function buildIndex(run: RunResult, trace: TraceEvent[]): Index {
  const suggestions = new Map<string, Suggestion>();
  Object.values(run.verdicts).forEach((v) => v.suggestions.forEach((s) => suggestions.set(s.id, s)));
  return {
    events: new Map(trace.map((e) => [e.id, e])),
    requirements: new Map(run.requirements.map((r) => [r.id, r])),
    findingsByReq: new Map(run.findings.map((f) => [f.requirement_id, f])),
    suggestions,
  };
}

const firstEvent = (ids: string[], idx: Index) => ids.map((id) => idx.events.get(id)).find(Boolean);
const agentEvent = (agent: string, trace: TraceEvent[]) => trace.find((e) => e.agent === agent);

/** The pipeline's own chain (lineage.json): product -> why the regulation applies -> page -> quote -> match -> requirement. */
function pipelineSteps(run: RunResult, trace: TraceEvent[], idx: Index, req: Requirement): ChainStep[] {
  const { lineage, parts, state, test_case } = req.pipeline!;
  const of = (step: string) => lineage.filter((l) => l.step === step);
  const eventOf = (l?: LineageLink) => (l?.trace_id ? idx.events.get(l.trace_id) : undefined);
  const facts = of("fact");
  const [scope] = of("scope_decision");
  const [provision] = of("provision");
  const [obligation] = of("obligation");
  const matches = of("match_decision");
  // "quote: <text> (extractor x4, unverified)" and "uncertain; evidence needed: <reason>"
  const quote = obligation?.summary.match(/^quote: ([\s\S]*?)(?: \(([^()]*)\))?$/);
  const reasons = [...new Set(matches.map((l) => l.summary.replace(/^[a-z_]+; [^:]+: /, "")))];
  const assemble = trace.find((e) => e.tags.pipeline_step === "assemble" && !e.tags.calls);

  const steps: ChainStep[] = [
    {
      key: "product",
      title: "From your product description",
      text: parts.length ? "Parts affected:" : `Based on: ${run.spec_name}`,
      chips: parts,
      detail: facts.length ? `Details: ${facts.map((f) => f.summary).join(" · ")}` : undefined,
      specLines: facts.find((f) => f.spec_lines)?.spec_lines ?? null,
      event: eventOf(of("part")[0] ?? facts[0]),
    },
  ];
  if (scope) {
    steps.push({ key: "scope", title: `Why ${regulationName(req.source.regulation, req.source.title)} applies`, text: scope.summary, event: eventOf(scope) });
  }
  steps.push({ key: "provision", title: "Where it says so in the regulation", text: provision?.summary ?? req.source.label, sources: [req.source], event: eventOf(provision) });
  if (obligation) {
    steps.push({
      key: "obligation",
      title: "The obligation, verbatim",
      text: quote?.[1] ?? obligation.summary,
      quote: true,
      detail: quote?.[2] ? `Pipeline note: ${quote[2]}` : undefined,
      event: eventOf(obligation),
    });
  }
  if (matches.length) {
    steps.push({
      key: "match",
      title: `Matched against your product: ${state === "uncertain" ? "may apply" : "applies"}`,
      text: reasons.join(" "),
      event: eventOf(matches[0]),
    });
  }
  steps.push({
    key: "requirement",
    title: "The requirement as delivered",
    text: req.text,
    quote: true,
    detail: test_case ? `Evidence: ${test_case}` : undefined,
    sources: [req.source],
    event: assemble,
  });
  return steps;
}

function requirementSteps(run: RunResult, trace: TraceEvent[], idx: Index, req: Requirement): ChainStep[] {
  if (req.pipeline) return pipelineSteps(run, trace, idx, req);
  const finding = idx.findingsByReq.get(req.id);
  const selection = firstEvent(req.trace_ids, idx);
  const steps: ChainStep[] = [
    {
      key: "spec",
      title: "From your product description",
      text: finding?.spec_lines ? "This part of your description is relevant:" : `Based on: ${run.spec_name}`,
      specLines: finding?.spec_lines ?? null,
      event: agentEvent("spec_parser", trace),
    },
    {
      key: "selection",
      title: "Applicable regulation selected",
      text: `${regulationName(req.source.regulation, req.source.title)} (${req.source.regulation}, version ${req.source.version})`,
      event: selection,
    },
    {
      key: "requirement",
      title: "The requirement, verbatim",
      text: req.text,
      quote: true,
      sources: [req.source],
    },
  ];
  if (finding) {
    steps.push({
      key: "finding",
      title: `Matched against your product: ${FINDING[finding.status].label}`,
      text: finding.explanation,
      detail: finding.suggestion ?? undefined,
      specLines: finding.spec_lines ?? null,
      event: firstEvent(finding.trace_ids, idx),
    });
  }
  return steps;
}

function decisionSteps(trace: TraceEvent[], suggestionId: string): ChainStep[] {
  return trace
    .filter((e) => e.agent === "human_review" && e.tags.suggestion === suggestionId)
    .map((e) => ({
      key: e.id,
      title: "Decision by a human",
      text: isAccepted(e.action) ? "Suggestion accepted." : "Suggestion rejected.",
      detail: e.outputs_summary || undefined,
      event: e,
    }));
}

export function buildChain(target: LineageTarget, run: RunResult, trace: TraceEvent[]): ChainStep[] {
  const idx = buildIndex(run, trace);

  if (target.kind === "requirement") {
    const req = idx.requirements.get(target.id);
    if (!req) return [];
    const steps = requirementSteps(run, trace, idx, req);
    const affected = Object.values(run.verdicts).filter((v) => v.suggestions.some((s) => s.requirement_id === req.id));
    steps.push({
      key: "verdicts",
      title: "Effect on the markets",
      text: affected.length
        ? `Leads to suggestions in: ${affected.map((v) => countryName(v.iso3, v.name)).join(", ")}`
        : idx.findingsByReq.get(req.id)?.status === "open"
          ? "A standard test record in every market – does not change the traffic light."
          : "No effect on the traffic light.",
      links: affected.map((v) => ({ label: countryName(v.iso3, v.name), target: { kind: "verdict", iso3: v.iso3 } })),
    });
    return steps;
  }

  if (target.kind === "suggestion") {
    const s = idx.suggestions.get(target.id);
    if (!s) return [];
    const verdict = run.verdicts[s.country];
    const req = s.requirement_id ? idx.requirements.get(s.requirement_id) : undefined;
    const steps: ChainStep[] = req ? requirementSteps(run, trace, idx, req) : [];
    if (s.deviation_id) {
      steps.push({ key: "deviation", title: `Rule in ${countryName(s.country, verdict?.name)}`, text: s.reason, sources: s.sources });
    }
    if (verdict) {
      steps.push({
        key: "verdict",
        title: `Rating for ${countryName(verdict.iso3, verdict.name)}: ${STATUS[verdict.status].label}`,
        text: verdict.reasons.join(" "),
        sources: verdict.sources,
        event: firstEvent(verdict.trace_ids, idx),
      });
    }
    steps.push({
      key: "suggestion",
      title: `Our suggestion (${EFFORT[s.effort].label})`,
      text: s.change,
      detail: s.deviation_id ? undefined : s.reason,
      sources: s.deviation_id ? undefined : s.sources,
      event: firstEvent(s.trace_ids, idx),
    });
    return [...steps, ...decisionSteps(trace, s.id)];
  }

  const verdict = run.verdicts[target.iso3];
  if (!verdict) return [];
  const engine = trace.find((e) => e.agent === "requirements_engine" && /^(Anforderungen ableiten|Derive requirements)$/i.test(e.action));
  const assessor = trace.find((e) => e.agent === "spec_assessor" && !e.tags.regulation);
  return [
    { key: "spec", title: "Product description read", text: run.spec_name, event: agentEvent("spec_parser", trace) },
    { key: "requirements", title: "Requirements derived from the regulations", text: engine?.outputs_summary, event: engine },
    { key: "assessment", title: "Matched against your product", text: assessor?.outputs_summary, event: assessor },
    {
      key: "verdict",
      title: `Rating for ${countryName(verdict.iso3, verdict.name)}: ${STATUS[verdict.status].label}`,
      text: verdict.reasons.join(" "),
      sources: verdict.sources,
      event: firstEvent(verdict.trace_ids, idx),
    },
    {
      key: "suggestions",
      title: verdict.suggestions.length ? `${verdict.suggestions.length} steps to approval` : "No steps needed",
      links: verdict.suggestions.map((s) => ({ label: s.change, target: { kind: "suggestion", id: s.id } })),
    },
  ];
}
