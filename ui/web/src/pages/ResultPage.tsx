import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { BookOpen, CircleCheck, Cpu, Lightbulb, ListChecks, Map as MapIcon, MousePointerClick, Pencil, RotateCcw, ShieldCheck, Sparkles, Workflow } from "lucide-react";
import { motion } from "motion/react";
import { api } from "../api";
import type { Decision, LineageTarget, RunResult, TraceEvent, VerdictStatus } from "../types";
import { centroid, corners } from "../lib/geo";
import { DraftNotice } from "../components/Badges";
import { RULE, STATUS, STATUS_ORDER, UNTESTED_FILL, plural } from "../lib/labels";
import { money, totalCost, when } from "../lib/pipeline";
import { summarizeSpec } from "../lib/specSummary";
import { Blueprint } from "../components/Blueprint";
import { CountryCards } from "../components/CountryCards";
import { CountryDrawer } from "../components/CountryDrawer";
import { LineageDrawer } from "../components/LineageDrawer";
import { RequirementsView } from "../components/RequirementsView";
import { SpecView } from "../components/SpecView";
import { CountUp } from "../components/Stats";
import { StoryView } from "../components/StoryView";
import { Theater } from "../components/Theater";
import { EUROPE_VIEW, FlagPin, MapPin, WorldMap, type Framing } from "../components/WorldMap";

/** "In 2 markets no product change was found, in 1 market …" */
function summarySentence(counts: Record<VerdictStatus, number>): string {
  const markets = (n: number) => plural(n, "market", "markets");
  const parts = [
    counts.green && `in ${markets(counts.green)} no product change was found`,
    counts.yellow && `in ${markets(counts.yellow)} documents or tests are missing`,
    counts.red && `in ${markets(counts.red)} the product itself has to change`,
    counts.grey && `for ${markets(counts.grey)} we have no data yet`,
  ].filter(Boolean) as string[];
  if (!parts.length) return "";
  const text = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

type Tab = "map" | "requirements" | "story";
const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: "map", label: "Markets", icon: MapIcon },
  { id: "requirements", label: "Requirements", icon: BookOpen },
  { id: "story", label: "How we got here", icon: Workflow },
];

function Failure({ title, text, onNew }: { title: string; text: string; onNew: () => void }) {
  return (
    <div className="card mx-auto mt-10 max-w-xl space-y-4 p-8 text-center">
      <h2 className="text-2xl">{title}</h2>
      <p className="text-sm text-mint-900/65">{text}</p>
      <button type="button" className="btn-primary" onClick={onNew}>
        <RotateCcw size={16} /> New check
      </button>
    </div>
  );
}

function Meta({ icon: Icon, children, title }: { icon: LucideIcon; children: ReactNode; title?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5" title={title}>
      <Icon size={14} className="text-mint-300" /> {children}
    </span>
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
  const markets = useMemo<Framing>(() => ({ fit: verdicts.flatMap((v) => corners(v.iso3)), keep: verdicts.map((v) => centroid(v.iso3)).filter((c): c is [number, number] => !!c), maxZoom: EUROPE_VIEW.zoom }), [verdicts]);
  const counts = useMemo(() => {
    const c: Record<VerdictStatus, number> = { green: 0, yellow: 0, red: 0, grey: 0 };
    verdicts.forEach((v) => (c[v.status] += 1));
    return c;
  }, [verdicts]);

  const fillFor = useCallback(
    (iso3: string) => {
      const v = run?.verdicts[iso3];
      return v ? STATUS[v.status].color : UNTESTED_FILL;
    },
    [run],
  );
  const tooltipFor = useCallback(
    (iso3: string) => {
      const v = run?.verdicts[iso3];
      if (!v) return "Not checked – click to add it";
      if (v.status === "green") return "No product change needed – test evidence open";
      if (v.status === "grey") return "No data for this country yet";
      return `${STATUS[v.status].label} · ${plural(v.suggestions.length, "step", "steps")}`;
    },
    [run],
  );

  if (error) return <Failure title="The result could not be loaded" text={error} onNew={onNew} />;
  if (run?.status === "error") return <Failure title="Something went wrong" text={`The check was aborted. Technical details: ${run.error}`} onNew={onNew} />;
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
  const cost = run.pipeline ? totalCost(run.pipeline) : null;

  return (
    <div className="animate-fade-up space-y-6">
      <DraftNotice />
      <section className="band p-6 sm:p-10">
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <div className="flex gap-6">
            {run.has_image && <Blueprint src={api.runImageUrl(run.run_id)} className="hidden h-32 w-32 shrink-0 bg-white sm:block" />}
            <div className="min-w-0">
              <p className="flex items-center gap-1.5 text-mint-300">
                <CircleCheck size={16} /> Check complete
              </p>
              <h1 className="mt-2 text-4xl text-white sm:text-5xl">{product}</h1>
              <p className="mt-4 max-w-2xl text-lg leading-relaxed text-mint-50/75">{summarySentence(counts)}</p>
              <p className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-mint-50/60">
                {run.llm_mode === "rules" ? (
                  <Meta icon={ListChecks} title="The AI assistant was not connected; every rating comes from fixed rules.">
                    Rule-based – please review suggestions
                  </Meta>
                ) : (
                  <Meta icon={Sparkles}>AI-assisted – please review suggestions</Meta>
                )}
                {run.validation?.ok && <Meta icon={ShieldCheck} title="Regulation, version and page of every source exist in the official index. This does not check that the requirement itself is right.">
                    All {run.requirements.length} sources formally valid
                  </Meta>}
                {run.pipeline && (
                  <Meta
                    icon={Cpu}
                    title={`Read from ${run.pipeline.path}${run.pipeline.replay_of ? ` (replay of ${run.pipeline.replay_of})` : ""}${run.pipeline.label ? `\n${run.pipeline.label}` : ""}`}
                  >
                    Pipeline run · {when(run.pipeline.finished_at)}
                    {cost != null && ` · ${money(cost)}`}
                  </Meta>
                )}
                {run.backend_mode === "mock" && (
                  <span className="rounded bg-amber-300/20 px-1.5 text-amber-200" title="Requirements come from the organiser's reference solution – the live requirements engine is not connected yet.">
                    Demo data
                  </span>
                )}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2">
            {STATUS_ORDER.map((s) => {
              const { icon: Icon, color, label } = STATUS[s];
              return (
                <button
                  key={s}
                  type="button"
                  disabled={!counts[s]}
                  onClick={() => jumpTo(s)}
                  className="flex min-w-[10rem] flex-col gap-3 rounded-xl bg-white/[0.06] p-4 text-left transition-colors duration-300 enabled:hover:bg-white/[0.12] disabled:opacity-40"
                >
                  <Icon size={20} style={{ color }} />
                  <span>
                    <CountUp value={counts[s]} className="block text-3xl leading-none text-white" />
                    <span className="mt-1.5 block text-xs text-mint-50/65">{label}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {note && (
        <section className="flex gap-4 rounded-2xl bg-amber-50 p-5 ring-1 ring-inset ring-amber-600/20">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-amber-100 text-amber-700">
            <Lightbulb size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-mint-950">Tip for your product description</p>
            <p className="mt-1 text-sm text-mint-900/80">{note.text}</p>
            <div className="mt-2 flex flex-wrap gap-4 text-sm">
              {note.spec_lines && (
                <button type="button" className="link" onClick={() => setShowNote((v) => !v)}>
                  {showNote ? "Hide passage" : "Show passage in the description"}
                </button>
              )}
              {note.requirement_ids[0] && (
                <button type="button" className="link" onClick={() => setLineage({ kind: "requirement", id: note.requirement_ids[0] })}>
                  How do we know?
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
        <nav className="flex max-w-full gap-1 overflow-x-auto rounded-lg bg-white p-1 ring-1 ring-mint-900/[0.06]" role="tablist">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`relative flex shrink-0 items-center gap-2 rounded-md px-4 py-2 text-sm transition-colors duration-300 ${tab === id ? "text-white" : "text-mint-900/70 hover:text-mint-950"}`}
            >
              {tab === id && <motion.span layoutId="result-tab" className="absolute inset-0 rounded-md bg-mint-950" transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
              <Icon size={16} className={`relative ${tab === id ? "text-mint-300" : ""}`} />
              <span className="relative">{label}</span>
            </button>
          ))}
        </nav>
        <button type="button" className="btn-outline" onClick={() => onEditMarkets(run)}>
          <Pencil size={14} /> Change markets
        </button>
      </div>

      {/* one wrapper after the tabs: the old tab is removed and the new one inserted only once the moving tab pill has been
          measured, so the page never shrinks under the reader and the scroll position stays put */}
      <div>
        {tab === "map" && (
          <div className="space-y-10">
            <div className="card overflow-hidden">
              <WorldMap fillFor={fillFor} selected={country} onSelect={setCountry} tooltipFor={tooltipFor} focus={markets}>
                {showPins &&
                  verdicts.map((v) => (
                    <MapPin key={v.iso3} at={centroid(v.iso3)}>
                      <FlagPin iso3={v.iso3} color={STATUS[v.status].color} small={verdicts.length > 8} onClick={() => setCountry(v.iso3)} />
                    </MapPin>
                  ))}
              </WorldMap>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-mint-900/[0.06] px-4 py-3 text-xs">
                {STATUS_ORDER.map((s) => (
                  <span key={s} className="flex items-center gap-2" title={RULE[s]}>
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS[s].color }} />
                    <span className="font-medium text-mint-950">{STATUS[s].label}</span>
                    {s !== "grey" && <span className="hidden text-mint-900/55 lg:inline">{RULE[s]}</span>}
                  </span>
                ))}
                <span className="flex items-center gap-2 text-mint-900/55">
                  <span className="h-2.5 w-2.5 rounded-full ring-1 ring-inset ring-mint-900/10" style={{ background: UNTESTED_FILL }} /> Not checked
                </span>
                <span className="ml-auto flex items-center gap-1.5 text-mint-900/55">
                  <MousePointerClick size={14} /> Click a country for details
                </span>
              </div>
            </div>
            <CountryCards verdicts={verdicts} onSelect={setCountry} />
          </div>
        )}

        {tab === "requirements" && <RequirementsView run={run} onLineage={setLineage} />}

        {tab === "story" && <StoryView key={focusEvent ?? "story"} run={run} trace={trace} focusId={focusEvent} onCountry={setCountry} onLineage={setLineage} onEvent={openEvent} />}
      </div>

      {country && <CountryDrawer iso3={country} run={run} onClose={() => setCountry(null)} onAsk={ask} onDecide={decide} onLineage={setLineage} onAnalyzeWith={analyzeWith} />}
      {lineage && <LineageDrawer target={lineage} run={run} trace={trace} onClose={() => setLineage(null)} onNavigate={setLineage} onOpenEvent={openEvent} />}
    </div>
  );
}
