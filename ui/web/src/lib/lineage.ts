import type { Finding, LineageLink, LineageTarget, Requirement, RunResult, Source, Suggestion, TraceEvent } from "../types";
import { EFFORT, FINDING, STATUS, plural, regulationName } from "./labels";

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
      title: "Aus Ihrer Produktbeschreibung",
      text: parts.length ? "Betroffene Bauteile:" : `Grundlage: ${run.spec_name}`,
      chips: parts,
      detail: facts.length ? `Angaben: ${facts.map((f) => f.summary).join(" · ")}` : undefined,
      specLines: facts.find((f) => f.spec_lines)?.spec_lines ?? null,
      event: eventOf(of("part")[0] ?? facts[0]),
    },
  ];
  if (scope) {
    steps.push({ key: "scope", title: `Warum ${regulationName(req.source.regulation, req.source.title)} gilt`, text: scope.summary, event: eventOf(scope) });
  }
  steps.push({ key: "provision", title: "Fundstelle in der Vorschrift", text: provision?.summary ?? req.source.label, sources: [req.source], event: eventOf(provision) });
  if (obligation) {
    steps.push({
      key: "obligation",
      title: "Die Pflicht im Originaltext",
      text: quote?.[1] ?? obligation.summary,
      quote: true,
      detail: quote?.[2] ? `Vermerk der Pipeline: ${quote[2]}` : undefined,
      event: eventOf(obligation),
    });
  }
  if (matches.length) {
    steps.push({
      key: "match",
      title: `Abgleich mit Ihrem Produkt: ${state === "uncertain" ? "gilt vielleicht" : "gilt"}`,
      text: reasons.join(" "),
      event: eventOf(matches[0]),
    });
  }
  steps.push({
    key: "requirement",
    title: "Die Anforderung, wie sie abgegeben wird",
    text: req.text,
    quote: true,
    detail: test_case ? `Nachweis: ${test_case}` : undefined,
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
      title: "Aus Ihrer Produktbeschreibung",
      text: finding?.spec_lines ? "Diese Stelle Ihrer Beschreibung ist relevant:" : `Grundlage: ${run.spec_name}`,
      specLines: finding?.spec_lines ?? null,
      event: agentEvent("spec_parser", trace),
    },
    {
      key: "selection",
      title: "Passende Vorschrift ausgewählt",
      text: `${regulationName(req.source.regulation, req.source.title)} (${req.source.regulation}, Version ${req.source.version})`,
      event: selection,
    },
    {
      key: "requirement",
      title: "Die Anforderung im Originaltext",
      text: req.text,
      quote: true,
      sources: [req.source],
    },
  ];
  if (finding) {
    steps.push({
      key: "finding",
      title: `Abgleich mit Ihrem Produkt: ${FINDING[finding.status].label}`,
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
      title: "Entscheidung durch einen Menschen",
      text: e.action.includes("akzeptiert") ? "Vorschlag übernommen." : "Vorschlag abgelehnt.",
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
      title: "Auswirkung auf die Länder",
      text: affected.length
        ? `Führt zu Vorschlägen in: ${affected.map((v) => v.name_de).join(", ")}`
        : idx.findingsByReq.get(req.id)?.status === "offen"
          ? "Ein üblicher Prüfnachweis in allen Ländern – ändert die Ampelfarbe nicht."
          : "Keine Auswirkung auf die Ampelfarbe.",
      links: affected.map((v) => ({ label: v.name_de, target: { kind: "verdict", iso3: v.iso3 } })),
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
      steps.push({ key: "deviation", title: `Regel in ${verdict?.name_de ?? s.country}`, text: s.reason, sources: s.sources });
    }
    if (verdict) {
      steps.push({
        key: "verdict",
        title: `Bewertung für ${verdict.name_de}: ${STATUS[verdict.status].label}`,
        text: verdict.reasons.join(" "),
        sources: verdict.sources,
        event: firstEvent(verdict.trace_ids, idx),
      });
    }
    steps.push({
      key: "suggestion",
      title: `Unser Vorschlag (${EFFORT[s.effort].label})`,
      text: s.change,
      detail: s.deviation_id ? undefined : s.reason,
      sources: s.deviation_id ? undefined : s.sources,
      event: firstEvent(s.trace_ids, idx),
    });
    return [...steps, ...decisionSteps(trace, s.id)];
  }

  const verdict = run.verdicts[target.iso3];
  if (!verdict) return [];
  const engine = trace.find((e) => e.agent === "requirements_engine" && e.action === "Anforderungen ableiten");
  const assessor = trace.find((e) => e.agent === "spec_assessor" && !e.tags.regulation);
  return [
    { key: "spec", title: "Produktbeschreibung gelesen", text: run.spec_name, event: agentEvent("spec_parser", trace) },
    { key: "requirements", title: "Anforderungen aus den Vorschriften abgeleitet", text: engine?.outputs_summary, event: engine },
    { key: "assessment", title: "Mit Ihrem Produkt abgeglichen", text: assessor?.outputs_summary, event: assessor },
    {
      key: "verdict",
      title: `Bewertung für ${verdict.name_de}: ${STATUS[verdict.status].label}`,
      text: verdict.reasons.join(" "),
      sources: verdict.sources,
      event: firstEvent(verdict.trace_ids, idx),
    },
    {
      key: "suggestions",
      title: verdict.suggestions.length ? `${plural(verdict.suggestions.length, "Schritt", "Schritte")} nötig` : "Keine Produktänderung nötig",
      links: verdict.suggestions.map((s) => ({ label: s.change, target: { kind: "suggestion", id: s.id } })),
    },
  ];
}
