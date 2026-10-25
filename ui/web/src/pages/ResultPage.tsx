import { useCallback, useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { BookOpen, CircleCheck, Cpu, Lightbulb, ListChecks, Map as MapIcon, MousePointerClick, Pencil, RotateCcw, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import { motion } from "motion/react";
import { api } from "../api";
import type { Decision, LineageTarget, RunResult, TraceEvent, VerdictStatus } from "../types";
import { centroid, corners } from "../lib/geo";
import { RULE, STATUS, STATUS_ORDER, UNTESTED_FILL, plural } from "../lib/labels";
import { money, totalCost, when } from "../lib/pipeline";
import { summarizeSpec } from "../lib/specSummary";
import { Blueprint } from "../components/Blueprint";
import { CountryCards } from "../components/CountryCards";
import { CountryDrawer } from "../components/CountryDrawer";
import { LineageDrawer } from "../components/LineageDrawer";
import { RequirementsView } from "../components/RequirementsView";
import { SpecView } from "../components/SpecView";
import { CountUp, MarketDonut } from "../components/Stats";
import { StoryView } from "../components/StoryView";
import { Theater } from "../components/Theater";
import { EUROPE_VIEW, FlagPin, MapPin, WorldMap, type Framing } from "../components/WorldMap";

/** "In 2 Ländern ist Ihr Produkt sofort verkaufsbereit, in 1 Land …" */
function summarySentence(counts: Record<VerdictStatus, number>): string {
  const land = (n: number, dativ: boolean) => `${n} ${n === 1 ? "Land" : dativ ? "Ländern" : "Länder"}`;
  const parts = [
    counts.green && `in ${land(counts.green, true)} ist Ihr Produkt sofort verkaufsbereit`,
    counts.yellow && `in ${land(counts.yellow, true)} fehlen nur noch Unterlagen oder Prüfungen`,
    counts.red && `in ${land(counts.red, true)} muss das Produkt selbst angepasst werden`,
    counts.grey && `für ${land(counts.grey, false)} haben wir noch keine Daten`,
  ].filter(Boolean) as string[];
  if (!parts.length) return "";
  const text = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} und ${parts[parts.length - 1]}` : parts[0];
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

type Tab = "map" | "requirements" | "story";
const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: "map", label: "Weltkarte", icon: MapIcon },
  { id: "requirements", label: "Anforderungen", icon: BookOpen },
  { id: "story", label: "So entstand das Ergebnis", icon: Workflow },
];

function Failure({ title, text, onNew }: { title: string; text: string; onNew: () => void }) {
  return (
    <div className="glass mx-auto mt-10 max-w-xl space-y-4 p-8 text-center">
      <h2 className="text-xl font-bold">{title}</h2>
      <p className="text-sm text-slate-400">{text}</p>
      <button type="button" className="btn-primary" onClick={onNew}>
        <RotateCcw size={16} /> Neue Prüfung
      </button>
    </div>
  );
}

interface Props {
  runId: string;
  replay: boolean; // freshly started: show the agents at work at a followable pace
  onNew: () => void;
  onOpenRun: (runId: string) => void;
  onEditMarkets: (run: RunResult) => void;
}

export function ResultPage({ runId, replay, onNew, onOpenRun, onEditMarkets }: Props) {
  const [run, setRun] = useState<RunResult | null>(null);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [live, setLive] = useState<Map<string, TraceEvent>>(new Map());
  const [ready, setReady] = useState(!replay);
  const [tab, setTab] = useState<Tab>("map");
  const [country, setCountry] = useState<string | null>(null);
  const [lineage, setLineage] = useState<LineageTarget | null>(null);
  const [focusEvent, setFocusEvent] = useState<string | null>(null);
  const [showNote, setShowNote] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [r, t] = await Promise.all([api.run(runId), api.trace(runId)]);
    setRun(r);
    setTrace(t);
    return r;
  }, [runId]);

  useEffect(() => {
    let stop: (() => void) | undefined;
    refresh()
      .then((r) => {
        if (r.status !== "running") return;
        stop = api.events(
          runId,
          (e) => setLive((prev) => new Map(prev).set(e.id, e)),
          () => void refresh().catch((e) => setError(String(e))),
        );
      })
      .catch((e) => setError(String(e)));
    return () => stop?.();
  }, [runId, refresh]);

  const events = useMemo(() => {
    const byId = new Map(trace.map((e) => [e.id, e]));
    live.forEach((e, id) => byId.set(id, e));
    return [...byId.values()];
  }, [trace, live]);
  const showResult = useCallback(() => setReady(true), []);

  const verdicts = useMemo(() => Object.values(run?.verdicts ?? {}), [run]);
  // open the map on the assessed markets, e.g. Europe for an EU-27 check
  const markets = useMemo<Framing>(() => ({ fit: verdicts.flatMap((v) => corners(v.iso3)), maxZoom: EUROPE_VIEW.zoom }), [verdicts]);
  const counts = useMemo(() => {
    const c: Record<VerdictStatus, number> = { green: 0, yellow: 0, red: 0, grey: 0 };
    verdicts.forEach((v) => (c[v.status] += 1));
    return c;
  }, [verdicts]);

  const fillFor = useCallback((iso3: string) => {
    const v = run?.verdicts[iso3];
    return v ? STATUS[v.status].color : UNTESTED_FILL;
  }, [run]);
  const glowFor = useCallback((iso3: string) => {
    const v = run?.verdicts[iso3];
    return v && v.status !== "grey" ? STATUS[v.status].color : null;
  }, [run]);
  const tooltipFor = useCallback((iso3: string) => {
    const v = run?.verdicts[iso3];
    if (!v) return "Nicht geprüft – anklicken zum Mitprüfen";
    if (v.status === "green") return "Verkaufsbereit – nichts zu ändern";
    if (v.status === "grey") return "Noch keine Daten zu diesem Land";
    return `${STATUS[v.status].label} · ${plural(v.suggestions.length, "Schritt", "Schritte")} bis zur Freigabe`;
  }, [run]);

  if (error) return <Failure title="Das Ergebnis konnte nicht geladen werden" text={error} onNew={onNew} />;
  if (run?.status === "error") return <Failure title="Da ist etwas schiefgelaufen" text={`Die Prüfung wurde abgebrochen. Technische Details: ${run.error}`} onNew={onNew} />;
  if (!run || run.status === "running" || !ready) return <Theater run={run} events={events} onDone={showResult} />;

  const ask = async (iso3: string, question: string) => {
    await api.ask(runId, iso3, question);
    await refresh();
  };
  const decide = async (suggestionId: string, decision: Decision) => {
    await api.decide(runId, suggestionId, decision);
    await refresh();
  };
  const analyzeWith = async (iso3: string) => {
    const file = new File([run.spec_text], run.spec_name, { type: "text/markdown" });
    const image = run.has_image ? await api.runImage(run.run_id) : null;
    const { run_id } = await api.startRun(file, [...new Set([...run.countries, iso3])], image);
    onOpenRun(run_id);
  };
  const openEvent = (id: string) => {
    setLineage(null);
    setCountry(null);
    setFocusEvent(id); // the story view scrolls to the entry in the technical log
    setTab("story");
  };
  const jumpTo = (status: VerdictStatus) => {
    setTab("map");
    setTimeout(() => document.getElementById(`status-${status}`)?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const product = summarizeSpec(run.spec_text).title;
  const note = run.spec_notes[0];
  const showPins = verdicts.length <= 15;

  return (
    <div className="animate-fade-up space-y-6">
      <section className="glass relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -left-24 -top-28 h-80 w-80 rounded-full bg-teal-400/20 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-32 right-10 h-80 w-[28rem] rounded-full bg-indigo-500/20 blur-3xl" aria-hidden />
        <div className="relative grid gap-8 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <div className="flex gap-6">
            {run.has_image && <Blueprint src={api.runImageUrl(run.run_id)} className="hidden h-36 w-36 shrink-0 sm:block" />}
            <div className="min-w-0">
              <p className="eyebrow flex items-center gap-1.5">
                <CircleCheck size={14} /> Prüfung abgeschlossen
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-5xl">{product}</h1>
              <p className="mt-3 max-w-2xl text-lg leading-relaxed text-slate-300">{summarySentence(counts)}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {run.llm_mode === "rules" ? (
                  <span className="chip border border-white/10 bg-white/[0.04] !text-xs text-slate-300" title="Der KI-Assistent war nicht verbunden; alle Bewertungen stammen aus festen Prüfregeln.">
                    <ListChecks size={13} className="text-teal-300" /> Regelbasierte Prüfung – Vorschläge bitte fachlich prüfen
                  </span>
                ) : (
                  <span className="chip border border-white/10 bg-white/[0.04] !text-xs text-slate-300">
                    <Sparkles size={13} className="text-teal-300" /> KI-gestützt – Vorschläge bitte fachlich prüfen
                  </span>
                )}
                {run.validation?.ok && (
                  <span className="chip bg-emerald-400/10 !text-xs text-emerald-300 ring-1 ring-inset ring-emerald-400/20">
                    <ShieldCheck size={13} /> Alle {run.requirements.length} Fundstellen belegt
                  </span>
                )}
                {run.pipeline && (
                  <span className="chip bg-teal-400/10 !text-xs text-teal-200 ring-1 ring-inset ring-teal-300/20"
                        title={`Gelesen aus ${run.pipeline.path}${run.pipeline.replay_of ? ` (Replay von ${run.pipeline.replay_of})` : ""}${run.pipeline.label ? `\n${run.pipeline.label}` : ""}`}>
                    <Cpu size={13} /> Echter Pipeline-Lauf · {when(run.pipeline.finished_at)}
                    {totalCost(run.pipeline) != null && ` · ${money(totalCost(run.pipeline)!)}`}
                  </span>
                )}
                {run.backend_mode === "mock" && (
                  <span className="chip bg-amber-400/10 !text-xs text-amber-300 ring-1 ring-inset ring-amber-400/20" title="Die Anforderungen stammen aus der Musterlösung des Veranstalters – die Live-Anbindung der Requirements-Engine folgt.">
                    Demo-Daten
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-center">
            <MarketDonut counts={counts} />
            <div className="grid grid-cols-2 gap-2.5">
              {STATUS_ORDER.map((s) => {
                const { icon: Icon, color, label } = STATUS[s];
                return (
                  <button
                    key={s}
                    type="button"
                    disabled={!counts[s]}
                    onClick={() => jumpTo(s)}
                    className="flex w-[10.5rem] items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-3 text-left transition enabled:hover:-translate-y-0.5 enabled:hover:border-white/15 enabled:hover:bg-white/[0.06] disabled:opacity-35"
                  >
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: `${color}1f`, color, boxShadow: counts[s] ? `0 0 24px -6px ${color}` : undefined }}>
                      <Icon size={20} />
                    </span>
                    <span className="min-w-0">
                      <CountUp value={counts[s]} className="block font-display text-2xl font-bold leading-none text-white" />
                      <span className="mt-1 block text-[11px] font-medium leading-tight text-slate-400">{label}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {note && (
        <section className="flex gap-4 rounded-3xl border border-amber-300/20 bg-amber-300/[0.06] p-5">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-amber-300/15 text-amber-300 shadow-[0_0_24px_-6px_#fbbf24]">
            <Lightbulb size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-amber-100">Tipp für Ihre Produktbeschreibung</p>
            <p className="mt-1 text-sm text-amber-100/75">{note.text}</p>
            <div className="mt-2 flex flex-wrap gap-4 text-sm">
              {note.spec_lines && (
                <button type="button" className="font-medium text-amber-300 underline decoration-amber-300/30 underline-offset-2 hover:decoration-amber-300" onClick={() => setShowNote((v) => !v)}>
                  {showNote ? "Stelle ausblenden" : "Stelle in der Beschreibung zeigen"}
                </button>
              )}
              {note.requirement_ids[0] && (
                <button type="button" className="font-medium text-amber-300 underline decoration-amber-300/30 underline-offset-2 hover:decoration-amber-300" onClick={() => setLineage({ kind: "requirement", id: note.requirement_ids[0] })}>
                  Woher wissen wir das?
                </button>
              )}
            </div>
            {showNote && note.spec_lines && (
              <div className="mt-3 animate-fade-up">
                <SpecView text={run.spec_text} highlight={note.spec_lines} context={1} />
              </div>
            )}
          </div>
        </section>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav className="flex max-w-full gap-1 overflow-x-auto rounded-full border border-white/[0.08] bg-white/[0.03] p-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" onClick={() => setTab(id)}
                    className={`relative flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${tab === id ? "text-ink-950" : "text-slate-400 hover:text-white"}`}>
              {tab === id && (
                <motion.span layoutId="result-tab" className="absolute inset-0 rounded-full bg-gradient-to-r from-teal-300 via-cyan-300 to-sky-300 shadow-[0_0_24px_-4px_rgba(45,212,191,0.7)]"
                             transition={{ type: "spring", stiffness: 420, damping: 34 }} />
              )}
              <Icon size={16} className="relative" />
              <span className="relative">{label}</span>
            </button>
          ))}
        </nav>
        <button type="button" className="btn-secondary" onClick={() => onEditMarkets(run)}>
          <Pencil size={15} /> Länder ändern
        </button>
      </div>

      {/* one wrapper after the tabs: the old tab is removed and the new one inserted only once the moving tab pill has been
          measured, so the page never shrinks under the reader and the scroll position stays put */}
      <div>
        {tab === "map" && (
          <div className="space-y-10">
            <div className="glass overflow-hidden p-2">
              <WorldMap fillFor={fillFor} glowFor={glowFor} selected={country} onSelect={setCountry} tooltipFor={tooltipFor} focus={markets} className="rounded-[20px]">
                {showPins &&
                  verdicts.map((v) => (
                    <MapPin key={v.iso3} at={centroid(v.iso3)}>
                      <FlagPin iso3={v.iso3} color={STATUS[v.status].color} small={verdicts.length > 8} onClick={() => setCountry(v.iso3)} />
                    </MapPin>
                  ))}
              </WorldMap>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 text-xs">
                {STATUS_ORDER.map((s) => (
                  <span key={s} className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS[s].color, boxShadow: `0 0 8px ${STATUS[s].color}` }} />
                    <b className="font-semibold text-slate-200">{STATUS[s].label}</b>
                    {s !== "grey" && <span className="text-slate-500">{RULE[s]}</span>}
                  </span>
                ))}
                <span className="flex items-center gap-2 text-slate-500">
                  <span className="h-2.5 w-2.5 rounded-full ring-1 ring-white/15" style={{ background: UNTESTED_FILL }} /> nicht geprüft
                </span>
                <span className="ml-auto flex items-center gap-1.5 text-slate-500">
                  <MousePointerClick size={14} /> Land anklicken für Details
                </span>
              </div>
            </div>
            <CountryCards verdicts={verdicts} onSelect={setCountry} />
          </div>
        )}

        {tab === "requirements" && <RequirementsView run={run} onLineage={setLineage} />}

        {tab === "story" && (
          <StoryView key={focusEvent ?? "story"} run={run} trace={trace} focusId={focusEvent} onCountry={setCountry} onLineage={setLineage} onEvent={openEvent} />
        )}
      </div>

      {country && (
        <CountryDrawer iso3={country} run={run} onClose={() => setCountry(null)} onAsk={ask} onDecide={decide} onLineage={setLineage} onAnalyzeWith={analyzeWith} />
      )}
      {lineage && (
        <LineageDrawer target={lineage} run={run} trace={trace} onClose={() => setLineage(null)} onNavigate={setLineage} onOpenEvent={openEvent} />
      )}
    </div>
  );
}
