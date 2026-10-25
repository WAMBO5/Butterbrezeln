import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ChevronDown, CircleCheck, Download, Eye, MousePointerClick, ScrollText, UserCheck } from "lucide-react";
import type { FindingStatus, LineageTarget, RunResult, TraceEvent } from "../types";
import { AGENTS, agentOf, type AgentKind } from "../lib/agents";
import { flag } from "../lib/geo";
import { FINDING, RULE, STATUS, STATUS_ORDER, actorOf, plural, regulationName, sectionName } from "../lib/labels";
import { summarizeSpec } from "../lib/specSummary";
import { AgentAvatar } from "./Agent";
import { FindingBar, StatusDot } from "./Badges";
import { PipelineRun } from "./PipelineRun";
import { SourceLink } from "./SourceLink";
import { TraceView } from "./TraceView";

function time(ts?: string | null): string {
  return ts ? new Date(ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
}

const PRINCIPLES: { icon: LucideIcon; article: string; title: string; text: string }[] = [
  { icon: ScrollText, article: "Art. 12", title: "Protokollierung", text: "Jeder Agentenschritt wird automatisch mit Zeit, Eingabe, Ergebnis und Quelle festgehalten." },
  { icon: Eye, article: "Art. 13", title: "Transparenz", text: "Jede Aussage nennt ihre Fundstelle; KI-, Regel- und Menschen-Schritte sind gekennzeichnet." },
  { icon: UserCheck, article: "Art. 14", title: "Menschliche Aufsicht", text: "Vorschläge gelten erst, wenn ein Mensch sie übernimmt – jede Entscheidung wird protokolliert." },
];

// ---------------------------------------------------------------- flow graph

interface Edge {
  from: string;
  to: string;
  color: string;
}

interface GraphProps {
  run: RunResult;
  trace: TraceEvent[];
  onCountry: (iso3: string) => void;
  onLineage: (target: LineageTarget) => void;
  onEvent: (id: string) => void;
}

/** Product -> agents -> regulations -> countries, drawn as connected nodes; hovering lights up one path. */
function FlowGraph({ run, trace, onCountry, onLineage, onEvent }: GraphProps) {
  const box = useRef<HTMLDivElement>(null);
  const nodes = useRef(new Map<string, HTMLElement>());
  const [paths, setPaths] = useState<(Edge & { d: string })[]>([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [hot, setHot] = useState<string | null>(null);

  const spec = useMemo(() => summarizeSpec(run.spec_text), [run.spec_text]);
  const regs = useMemo(() => {
    const findings = new Map(run.findings.map((f) => [f.requirement_id, f.status]));
    const map = new Map<string, { code: string; title?: string | null; reqs: string[]; counts: Record<FindingStatus, number> }>();
    run.requirements.forEach((r) => {
      const code = r.source.regulation ?? "?";
      const entry = map.get(code) ?? { code, title: r.source.title, reqs: [], counts: { erfuellt: 0, offen: 0, konflikt: 0 } };
      entry.reqs.push(r.id);
      const status = findings.get(r.id);
      if (status) entry.counts[status] += 1;
      map.set(code, entry);
    });
    return [...map.values()].sort((a, b) => b.reqs.length - a.reqs.length);
  }, [run]);
  const verdicts = useMemo(() => Object.values(run.verdicts).sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status) || a.name_de.localeCompare(b.name_de, "de")), [run]);
  const grouped = verdicts.length > 12; // many markets: one node per colour instead of one per country
  const groups = useMemo(() => STATUS_ORDER.filter((s) => verdicts.some((v) => v.status === s)), [verdicts]);
  const findingCounts = useMemo(() => {
    const c: Record<FindingStatus, number> = { erfuellt: 0, offen: 0, konflikt: 0 };
    run.findings.forEach((f) => (c[f.status] += 1));
    return c;
  }, [run.findings]);

  // which regulations stand behind a country's steps (all of them if the steps are national rules only)
  const regsOf = useMemo(() => {
    const regOfReq = new Map(run.requirements.map((r) => [r.id, r.source.regulation ?? "?"]));
    const all = new Set(regs.map((r) => r.code));
    return new Map(
      verdicts.map((v) => {
        const hit = new Set(v.suggestions.map((s) => (s.requirement_id ? regOfReq.get(s.requirement_id) : undefined)).filter((c): c is string => !!c));
        return [v.iso3, hit.size ? hit : all];
      }),
    );
  }, [run.requirements, regs, verdicts]);

  const edges = useMemo<Edge[]>(
    () => [
      { from: "product", to: "researcher", color: AGENTS.reader.color },
      ...regs.map((r) => ({ from: "researcher", to: `reg:${r.code}`, color: AGENTS.researcher.color })),
      ...regs.map((r) => ({ from: `reg:${r.code}`, to: "review", color: AGENTS.checker.color })),
      { from: "review", to: "scout", color: AGENTS.matcher.color },
      ...(grouped
        ? groups.map((s) => ({ from: "scout", to: `group:${s}`, color: STATUS[s].color }))
        : verdicts.map((v) => ({ from: "scout", to: `country:${v.iso3}`, color: STATUS[v.status].color }))),
    ],
    [regs, verdicts, grouped, groups],
  );

  const lit = useMemo(() => {
    if (!hot) return null;
    const on = new Set([hot]);
    const chain = ["product", "researcher", "review", "scout"];
    if (hot.startsWith("country:") || hot.startsWith("group:")) {
      const members = hot.startsWith("country:") ? [hot.slice(8)] : verdicts.filter((v) => `group:${v.status}` === hot).map((v) => v.iso3);
      chain.forEach((n) => on.add(n));
      members.forEach((iso3) => regsOf.get(iso3)?.forEach((code) => on.add(`reg:${code}`)));
    } else if (hot.startsWith("reg:")) {
      const code = hot.slice(4);
      chain.forEach((n) => on.add(n));
      // the markets whose steps go back to this regulation; if none, it applied everywhere without trouble
      const hit = verdicts.filter((v) => regsOf.get(v.iso3)?.has(code) && v.suggestions.length);
      (hit.length ? hit : verdicts).forEach((v) => on.add(grouped ? `group:${v.status}` : `country:${v.iso3}`));
    } else {
      edges.forEach((e) => {
        if (e.from === hot) on.add(e.to);
        if (e.to === hot) on.add(e.from);
      });
    }
    return on;
  }, [hot, verdicts, regsOf, edges, grouped]);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => {
      const base = el.getBoundingClientRect();
      setSize({ w: base.width, h: base.height });
      setPaths(
        edges.flatMap((e) => {
          const a = nodes.current.get(e.from)?.getBoundingClientRect();
          const b = nodes.current.get(e.to)?.getBoundingClientRect();
          if (!a || !b) return [];
          const x1 = a.right - base.left;
          const y1 = a.top + a.height / 2 - base.top;
          const x2 = b.left - base.left;
          const y2 = b.top + b.height / 2 - base.top;
          const dx = Math.max(20, (x2 - x1) * 0.55);
          return [{ ...e, d: `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}` }];
        }),
      );
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    document.fonts?.ready.then(measure);
    return () => observer.disconnect();
  }, [edges]);

  const place = (id: string) => (el: HTMLElement | null) => {
    if (el) nodes.current.set(id, el);
    else nodes.current.delete(id);
  };
  const node = (id: string, onClick: () => void, className: string, children: ReactNode, title?: string) => {
    const dim = lit && !lit.has(id);
    return (
      <button
        ref={place(id)}
        type="button"
        title={title}
        onMouseEnter={() => setHot(id)}
        onMouseLeave={() => setHot(null)}
        onFocus={() => setHot(id)}
        onBlur={() => setHot(null)}
        onClick={onClick}
        className={`relative w-full rounded-2xl border bg-ink-900/90 text-left backdrop-blur transition duration-300 ${
          dim ? "border-white/[0.05] opacity-30" : hot === id ? "border-white/30 shadow-[0_0_30px_-8px_rgba(103,232,249,0.6)]" : "border-white/[0.09] hover:border-white/20"
        } ${className}`}
      >
        {children}
      </button>
    );
  };
  const agentNode = (id: string, kind: AgentKind, label: string, text: string, event?: TraceEvent, second?: AgentKind) =>
    node(
      id,
      () => event && onEvent(event.id),
      "flex flex-col items-center gap-2 px-2 py-3 text-center",
      <>
        <span className="flex -space-x-3">
          <AgentAvatar kind={kind} size={48} active={hot === id} />
          {second && <AgentAvatar kind={second} size={48} active={hot === id} />}
        </span>
        <span className="text-xs font-bold leading-tight text-white">{label}</span>
        <span className="text-[11px] leading-tight text-slate-500">{text}</span>
      </>,
      "Klick öffnet den Protokolleintrag",
    );

  const specEvent = trace.find((e) => e.agent === "spec_parser");
  const engineEvent = trace.find((e) => e.agent === "requirements_engine" && !e.tags.regulation) ?? trace.find((e) => e.agent.startsWith("requirements_engine"));
  const assessorEvent = trace.find((e) => e.agent === "spec_assessor" && !e.tags.regulation);
  const countryEvent = trace.find((e) => e.agent === "country_assessor" && !e.tags.country);
  const column = "space-y-2";

  return (
    <div ref={box} className="relative">
      <svg className="pointer-events-none absolute inset-0 hidden lg:block" width={size.w} height={size.h} aria-hidden>
        {paths.map((p) => {
          const on = !lit || (lit.has(p.from) && lit.has(p.to));
          return (
            <g key={`${p.from}>${p.to}`} style={{ opacity: on ? 1 : 0.08, transition: "opacity 250ms" }}>
              <path d={p.d} fill="none" stroke={p.color} strokeOpacity={0.22} strokeWidth={lit && on ? 3 : 1.6} />
              <path d={p.d} fill="none" stroke={p.color} strokeWidth={lit && on ? 2.2 : 1.4} strokeDasharray="4 12" strokeLinecap="round" className="animate-dash" />
            </g>
          );
        })}
      </svg>

      <div className="relative grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_104px_minmax(0,1.3fr)_132px_104px_minmax(0,1fr)] lg:items-center lg:gap-x-8">
        <div>
          {node(
            "product",
            () => specEvent && onEvent(specEvent.id),
            "p-4",
            <>
              <div className="flex items-center gap-3">
                <AgentAvatar kind="reader" size={40} active={hot === "product"} />
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-300">Ihr Produkt</p>
                  <p className="truncate font-display font-bold text-white">{spec.title}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {spec.sections.map((s) => (
                  <span key={s.title} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] text-slate-300">{sectionName(s.title)}</span>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-slate-500">gelesen vom Lese-Agenten</p>
            </>,
            "Klick öffnet den Protokolleintrag",
          )}
        </div>

        <div>{agentNode("researcher", "researcher", AGENTS.researcher.name, plural(regs.length, "Vorschrift", "Vorschriften"), engineEvent)}</div>

        <div className={column}>
          {regs.map((r) =>
            node(
              `reg:${r.code}`,
              () => onLineage({ kind: "requirement", id: r.reqs[0] }),
              "px-3 py-2",
              <>
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-white">{regulationName(r.code, r.title)}</span>
                  <span className="shrink-0 text-[11px] text-slate-500">{r.reqs.length}</span>
                </span>
                <span className="mt-1.5 flex items-center gap-2">
                  <span className="shrink-0 font-mono text-[10px] text-violet-300">{r.code}</span>
                  <FindingBar counts={r.counts} total={r.reqs.length} />
                </span>
              </>,
              `${r.reqs.length} Anforderungen · Klick zeigt die Herkunft`,
            ),
          )}
        </div>

        <div>{agentNode("review", "checker", "Prüf- & Abgleich-Agent", `${run.requirements.length} belegt · ${findingCounts.konflikt} Widersprüche`, assessorEvent, "matcher")}</div>

        <div>{agentNode("scout", "scout", AGENTS.scout.name, plural(verdicts.length, "Markt", "Märkte"), countryEvent)}</div>

        <div className={column}>
          {grouped
            ? groups.map((s) => {
                const members = verdicts.filter((v) => v.status === s);
                return node(
                  `group:${s}`,
                  () => onCountry(members[0].iso3),
                  "px-3 py-2.5",
                  <>
                    <span className="flex items-center gap-2">
                      <StatusDot status={s} />
                      <span className="text-sm font-semibold text-white">{plural(members.length, "Land", "Länder")}</span>
                      <span className={`text-[11px] font-medium ${STATUS[s].text}`}>{STATUS[s].label}</span>
                    </span>
                    <span className="mt-1 block truncate text-base leading-none">{members.slice(0, 12).map((v) => flag(v.iso3)).join(" ")}</span>
                  </>,
                );
              })
            : verdicts.map((v) =>
                node(
                  `country:${v.iso3}`,
                  () => onCountry(v.iso3),
                  "flex items-center gap-2.5 px-3 py-2",
                  <>
                    <span className="text-2xl leading-none">{flag(v.iso3)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-white">{v.name_de}</span>
                      <span className={`block text-[11px] font-medium ${STATUS[v.status].text}`}>{STATUS[v.status].label}</span>
                    </span>
                    <StatusDot status={v.status} />
                  </>,
                  "Klick öffnet das Land",
                ),
              )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- timeline

interface StepProps {
  kind: AgentKind;
  title: string;
  event?: TraceEvent;
  actor?: string;
  children?: ReactNode;
  last?: boolean;
}

function Step({ kind, title, event, actor, children, last }: StepProps) {
  const who = actor ?? (event ? actorOf(event).label : null);
  return (
    <li className="relative pb-8 pl-16">
      {!last && <span className="absolute bottom-0 left-[23px] top-14 w-px bg-gradient-to-b from-white/15 to-white/[0.03]" aria-hidden />}
      <AgentAvatar kind={kind} size={48} className="absolute left-0 top-0" />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h4 className="font-display text-base font-bold text-white">{title}</h4>
        <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] font-semibold text-slate-300 ring-1 ring-white/10">
          {AGENTS[kind].name}
          {who ? <span className="font-medium text-slate-500"> · {who}</span> : null}
        </span>
        {event && <span className="font-mono text-[11px] text-slate-500">{time(event.ts_start)}</span>}
      </div>
      <div className="mt-2 space-y-2 text-sm text-slate-400">{children}</div>
    </li>
  );
}

interface Props {
  run: RunResult;
  trace: TraceEvent[];
  focusId?: string | null;
  onCountry: (iso3: string) => void;
  onLineage: (target: LineageTarget) => void;
  onEvent: (id: string) => void;
}

/** "How the result came about": the agents as a flow graph, the steps in plain language, the technical log on demand. */
export function StoryView({ run, trace, focusId, onCountry, onLineage, onEvent }: Props) {
  const [technical, setTechnical] = useState(!!focusId);
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focusId) logRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focusId]);

  const find = (pred: (e: TraceEvent) => boolean) => trace.find(pred);
  const specEvent = find((e) => e.agent === "spec_parser");
  const engineEvent = find((e) => e.agent === "requirements_engine" && e.action === "Anforderungen ableiten");
  const regulationEvents = trace.filter((e) => agentOf(e.agent) === "researcher" && e.tags.regulation);
  const validatorEvent = find((e) => e.agent === "validator");
  const assessorEvent = find((e) => e.agent === "spec_assessor" && !e.tags.regulation);
  const assessorUsedAi = trace.some((e) => e.agent === "spec_assessor" && (e.model || e.tags.source === "pipeline"));
  const countryEvent = find((e) => e.agent === "country_assessor" && !e.tags.country);
  const questions = trace.filter((e) => e.agent === "qa_agent");
  const decisions = trace.filter((e) => e.agent === "human_review");
  // with a pipeline run, its product analysis and scoping are the steps that did the work
  const analyzeEvent = find((e) => e.tags.pipeline_step === "analyze" && !e.tags.calls);
  const scopeEvent = find((e) => e.tags.pipeline_step === "scope" && !e.tags.calls);
  const parts = run.pipeline?.parts ?? [];

  const sections = summarizeSpec(run.spec_text).sections.map((s) => sectionName(s.title));
  const counts: Record<FindingStatus, number> = { erfuellt: 0, offen: 0, konflikt: 0 };
  run.findings.forEach((f) => (counts[f.status] += 1));
  const verdicts = Object.values(run.verdicts);

  const download = () => {
    const blob = new Blob([JSON.stringify({ run, trace }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `protokoll-${run.run_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="glass relative overflow-hidden p-6">
        <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-violet-500/20 blur-3xl" aria-hidden />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="eyebrow">Nachvollziehbarkeit</p>
            <h3 className="mt-1 text-2xl font-bold tracking-tight">Wer hat was auf welcher Grundlage entschieden?</h3>
            <p className="mt-1 text-slate-400">Fahren Sie über ein Land oder eine Vorschrift – der Weg dorthin leuchtet auf. Ein Klick öffnet Details, Fundstelle oder Protokolleintrag.</p>
          </div>
          <button type="button" className="btn-secondary" onClick={download}>
            <Download size={16} /> Protokoll herunterladen
          </button>
        </div>
        <div className="relative mt-8">
          <FlowGraph run={run} trace={trace} onCountry={onCountry} onLineage={onLineage} onEvent={onEvent} />
        </div>
        <p className="relative mt-5 flex items-center gap-1.5 text-xs text-slate-500">
          <MousePointerClick size={14} /> Linienfarbe = Agent bzw. Ampelfarbe des Landes
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {PRINCIPLES.map(({ icon: Icon, article, title, text }) => (
          <div key={article} className="glass p-5">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-300/10 text-teal-300 ring-1 ring-inset ring-teal-300/20">
                <Icon size={20} />
              </span>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">EU AI Act · {article}</p>
                <p className="font-display font-bold text-white">{title}</p>
              </div>
            </div>
            <p className="mt-3 text-sm text-slate-400">{text}</p>
          </div>
        ))}
      </div>
      <p className="-mt-2 text-center text-xs text-slate-500">Umgesetzt nach dem Vorbild des EU AI Act – keine Aussage zur rechtlichen Konformität.</p>

      <div className="glass p-6">
        <h3 className="mb-6 font-display text-xl font-bold">Die Schritte im Einzelnen</h3>
        <ol>
          <Step kind="reader" title="Produktbeschreibung gelesen" event={analyzeEvent ?? specEvent}>
            <p>{parts.length ? `${plural(parts.length, "Bauteil", "Bauteile")} mit Funktionen und Materialien erkannt:` : `${plural(sections.length, "Abschnitt", "Abschnitte")} erkannt:`}</p>
            <div className="flex flex-wrap gap-1.5">
              {(parts.length ? parts : sections).map((s) => (
                <span key={s} className="rounded-full bg-white/[0.06] px-2.5 py-0.5 text-xs text-slate-300">{s}</span>
              ))}
            </div>
          </Step>

          <Step kind="researcher" title={`${plural(regulationEvents.length, "passende Vorschrift", "passende Vorschriften")} gefunden`} event={scopeEvent ?? engineEvent}>
            <p>
              {run.pipeline?.funnel.regulations
                ? `Von ${run.pipeline.funnel.regulations} internationalen Fahrzeugvorschriften hat die Pipeline nur die behalten, die für dieses Produkt gelten – jede mit Begründung:`
                : "Aus über 50 internationalen Fahrzeugvorschriften wurden nur die ausgewählt, die für dieses Produkt gelten:"}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {regulationEvents.map((e) => {
                const source = e.sources[0];
                return source ? (
                  <span key={e.id} className="inline-flex items-center gap-1.5 rounded-full bg-violet-400/10 py-0.5 pl-3 pr-1 text-xs font-medium text-violet-100 ring-1 ring-inset ring-violet-300/20">
                    {regulationName(e.tags.regulation, source.title)}
                    <SourceLink source={source} />
                  </span>
                ) : null;
              })}
            </div>
            {run.backend_mode === "mock" && <p className="text-xs text-amber-300/90">Demo-Daten: Die Anforderungen stammen aus der Musterlösung des Veranstalters, nicht aus einer Live-Auswertung.</p>}
          </Step>

          <Step kind="checker" title={`${run.requirements.length} Anforderungen abgeleitet`} event={validatorEvent}>
            <p>Jede Anforderung nennt ihre Fundstelle: Vorschrift, Version und Seite.</p>
            {run.validation && (
              <p className={`flex items-center gap-1.5 font-medium ${run.validation.ok ? "text-emerald-300" : "text-rose-300"}`}>
                <CircleCheck size={16} />
                {run.validation.ok ? "Alle Fundstellen automatisch gegen das offizielle Verzeichnis geprüft." : `${run.validation.problems.length} Fundstellen konnten nicht bestätigt werden.`}
              </p>
            )}
          </Step>

          <Step kind="matcher" title="Mit Ihrem Produkt abgeglichen" event={assessorEvent} actor={assessorUsedAi ? "KI" : "Regelprüfung"}>
            <p className="flex flex-wrap gap-x-3">
              {(["erfuellt", "offen", "konflikt"] as FindingStatus[]).map((k) => (
                <b key={k} className="font-semibold" style={{ color: FINDING[k].color }}>
                  {counts[k]} {FINDING[k].label}
                </b>
              ))}
              {run.spec_notes.length > 0 && <span>· {plural(run.spec_notes.length, "Hinweis", "Hinweise")} zur Beschreibung</span>}
            </p>
          </Step>

          <Step kind="scout" title={`${plural(verdicts.length, "Land", "Länder")} bewertet`} event={countryEvent}>
            <p>Die Farbe folgt einer festen, nachvollziehbaren Regel – nicht dem Bauchgefühl einer KI:</p>
            <div className="flex flex-wrap gap-2">
              {STATUS_ORDER.map((s) => (
                <span key={s} className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.04] px-3 py-1 text-xs text-slate-300 ring-1 ring-white/10">
                  <StatusDot status={s} size={8} />
                  <b className="font-semibold text-white">{STATUS[s].label}:</b> {RULE[s]}
                </span>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              {verdicts.map((v) => (
                <button key={v.iso3} type="button" onClick={() => onCountry(v.iso3)} className="inline-flex items-center gap-1.5 text-xs text-slate-300 hover:text-white" title={v.name_de}>
                  {flag(v.iso3)} <StatusDot status={v.status} size={7} />
                </button>
              ))}
            </div>
          </Step>

          {questions.length > 0 && (
            <Step kind="assistant" title={`${plural(questions.length, "Frage", "Fragen")} an den Assistenten`} event={questions[0]}>
              <ul className="list-inside list-disc">
                {questions.map((e) => (
                  <li key={e.id}>{e.inputs_summary}</li>
                ))}
              </ul>
            </Step>
          )}

          <Step kind="human" title="Entscheidungen durch Menschen" actor="Mensch" last>
            {decisions.length ? (
              <ul className="space-y-1">
                {decisions.map((e) => (
                  <li key={e.id}>
                    <span className="font-mono text-xs text-slate-500">{time(e.ts_start)}</span>{" "}
                    <b className={e.action.includes("akzeptiert") ? "text-emerald-300" : "text-slate-300"}>{e.action.includes("akzeptiert") ? "übernommen" : "abgelehnt"}:</b> {e.inputs_summary}
                  </li>
                ))}
              </ul>
            ) : (
              <p>Noch keine Vorschläge übernommen oder abgelehnt. Die Agenten entscheiden nicht allein – jede Übernahme wird hier festgehalten.</p>
            )}
          </Step>
        </ol>
      </div>

      <PipelineRun run={run} />

      <div ref={logRef} className="scroll-mt-24">
        <button type="button" className="btn-ghost" onClick={() => setTechnical((v) => !v)}>
          <ChevronDown size={16} className={`transition ${technical ? "rotate-180" : ""}`} /> Technisches Protokoll für Fachleute
        </button>
        {technical && (
          <div className="mt-3 animate-fade-up">
            <TraceView run={run} trace={trace} focusId={focusId} />
          </div>
        )}
      </div>
    </div>
  );
}
