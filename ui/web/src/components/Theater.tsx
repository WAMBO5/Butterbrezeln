import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Check, FastForward, ShieldCheck } from "lucide-react";
import { api } from "../api";
import type { FindingStatus, RunResult, TraceEvent, VerdictStatus } from "../types";
import { AGENTS, PIPELINE, agentOf } from "../lib/agents";
import { GENEVA, centroid, corners, countryName, flag } from "../lib/geo";
import { FINDING, PENDING_FILL, STATUS, STATUS_ORDER, UNTESTED_FILL, plural, regulationName, sectionName } from "../lib/labels";
import { summarizeSpec } from "../lib/specSummary";
import { AgentAvatar } from "./Agent";
import { StatusPill } from "./Badges";
import { Blueprint } from "./Blueprint";
import { CountUp } from "./Stats";
import { AgentPin, FlagPin, MapPin, Trail, WorldMap, useGlide, type Framing, type MapFocus, type MapView } from "./WorldMap";

/** Logged step that closes each pipeline stage, in the order of PIPELINE. */
const STAGE_AGENTS = ["spec_parser", "requirements_engine", "validator", "spec_assessor", "country_assessor"];
const MIN_MS = [1400, 2200, 1400, 1400]; // reader … matcher; the country agent takes as long as its hops
const GENEVA_VIEW: MapView = { coordinates: GENEVA, zoom: 3.2 };
const GENEVA_WIDE: MapView = { coordinates: [GENEVA[0] + 8, GENEVA[1] - 4], zoom: 2.2 };
const ease = [0.22, 1, 0.36, 1] as const;

/** Number of pipeline stages that have finished, in order. */
export function finishedStages(events: TraceEvent[]): number {
  let n = 0;
  for (const agent of STAGE_AGENTS) {
    const e = events.find((x) => x.agent === agent && !x.tags.regulation && !x.tags.country);
    if (!e || e.status === "running") break;
    n += 1;
  }
  return n;
}

function time(ts: string): string {
  return new Date(ts).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

interface Props {
  run: RunResult | null;
  events: TraceEvent[]; // logged steps so far (live while running)
  onDone: () => void;
}

/** The analysis as a show: each agent takes the stage in turn, the country agent travels the map. */
export function Theater({ run, events, onDone }: Props) {
  const [beat, setBeat] = useState(0); // 0-4 = PIPELINE index, 5 = done
  const [hop, setHop] = useState(0); // countries the country agent has reached
  const [skip, setSkip] = useState(false);
  const beatStart = useRef(Date.now());
  const done = run?.status === "done";
  const finished = done ? STAGE_AGENTS.length : finishedStages(events);

  // derived facts for the cards
  const spec = useMemo(() => (run ? summarizeSpec(run.spec_text) : null), [run]);
  const regulations = useMemo(() => {
    const seen = new Map<string, string | undefined>();
    events.filter((e) => agentOf(e.agent) === "researcher" && e.tags.regulation).forEach((e) => seen.set(e.tags.regulation, e.sources[0]?.title ?? undefined));
    if (!seen.size) run?.requirements.forEach((r) => r.source.regulation && seen.set(r.source.regulation, r.source.title ?? undefined));
    return [...seen.entries()].map(([code, title]) => ({ code, name: regulationName(code, title) }));
  }, [events, run]);
  const findingCounts = useMemo(() => {
    const c: Record<FindingStatus, number> = { met: 0, open: 0, conflict: 0 };
    run?.findings.forEach((f) => (c[f.status] += 1));
    return c;
  }, [run]);
  // west to east, so the agent's route reads like a journey
  const order = useMemo(() => [...(run?.countries ?? [])].sort((a, b) => (centroid(a)?.[0] ?? 0) - (centroid(b)?.[0] ?? 0)), [run]);
  const per = Math.max(140, Math.min(750, 4000 / Math.max(order.length, 1))); // ms per country, ~4 s for the whole tour

  const next = useCallback(() => {
    beatStart.current = Date.now();
    setBeat((b) => b + 1);
  }, []);

  // reader … matcher: advance once the stage really finished and had its moment on stage
  useEffect(() => {
    if (beat >= 4 || finished <= beat) return;
    const t = setTimeout(next, Math.max(0, MIN_MS[beat] - (Date.now() - beatStart.current)));
    return () => clearTimeout(t);
  }, [beat, finished, next]);

  // country agent: one hop per country, then done
  useEffect(() => {
    if (beat !== 4 || !done) return;
    const t = hop < order.length ? setTimeout(() => setHop((h) => h + 1), hop === 0 ? 700 : per) : setTimeout(next, 1000);
    return () => clearTimeout(t);
  }, [beat, hop, done, order.length, per, next]);

  useEffect(() => {
    if (beat < 5) return;
    const t = setTimeout(onDone, 2000);
    return () => clearTimeout(t);
  }, [beat, onDone]);

  useEffect(() => {
    if (skip && done) onDone();
  }, [skip, done, onDone]);

  const revealed = useMemo(() => new Set(beat >= 4 ? order.slice(0, hop) : []), [beat, order, hop]);
  const statusOf = (iso3: string): VerdictStatus | undefined => run?.verdicts[iso3]?.status;

  const fillFor = useCallback(
    (iso3: string) => {
      if (revealed.has(iso3)) {
        const s = run?.verdicts[iso3]?.status;
        return s ? STATUS[s].color : UNTESTED_FILL;
      }
      return run?.countries.includes(iso3) ? PENDING_FILL : UNTESTED_FILL;
    },
    [revealed, run],
  );

  // the whole journey from Geneva, kept clear of the card at the bottom
  const tour = useMemo<Framing>(() => ({ fit: [GENEVA, ...order.flatMap(corners)], maxZoom: 3.4, inset: { top: 0.08, bottom: 0.3 } }), [order]);
  const focus: MapFocus = beat === 1 ? GENEVA_VIEW : beat === 2 || beat === 3 ? GENEVA_WIDE : tour;
  const scoutTarget = beat >= 4 ? (hop === 0 ? GENEVA : centroid(order[Math.min(hop, order.length) - 1])) : undefined;
  const scoutAt = useGlide(scoutTarget, Math.min(0.55, (per * 0.8) / 1000));
  const current = beat >= 4 && hop > 0 ? order[Math.min(hop, order.length) - 1] : null;
  const progress = Math.min(1, (Math.min(beat, 4) + (beat >= 4 ? hop / Math.max(order.length, 1) : 0) + (beat >= 5 ? 1 : 0)) / 5);

  const parts = run?.pipeline?.parts ?? []; // what the pipeline's product analyst found
  const results = [
    parts.length ? `${plural(parts.length, "part", "parts")} found` : spec ? `${plural(spec.sections.length, "section", "sections")} found` : "read",
    regulations.length ? `${plural(regulations.length, "regulation", "regulations")} found` : "done",
    run ? `${run.requirements.length} requirements sourced` : "done",
    run ? `${findingCounts.met} met · ${findingCounts.conflict} conflicts` : "done",
    run ? `${plural(order.length, "market", "markets")} rated` : "done",
  ];

  // activity log: what the agents on stage so far have logged
  const log = useMemo(() => {
    const onStage = new Set(PIPELINE.slice(0, Math.min(beat, 4) + 1));
    // in start order, not by time: the steps of a pipeline run keep their original, earlier times
    return events.filter((e) => e.agent !== "orchestrator" && onStage.has(agentOf(e.agent)) && (!e.tags.country || revealed.has(e.tags.country))).slice(-4);
  }, [events, beat, revealed]);

  const counts = useMemo(() => {
    const c: Record<VerdictStatus, number> = { green: 0, yellow: 0, red: 0, grey: 0 };
    Object.values(run?.verdicts ?? {}).forEach((v) => (c[v.status] += 1));
    return c;
  }, [run]);

  const cardLabel = (kind: keyof typeof AGENTS, text: string) => (
    <p className="text-xs font-medium" style={{ color: AGENTS[kind].color }}>
      {text}
    </p>
  );
  const pill = "rounded-md bg-mint-900/[0.05] px-2 py-0.5 text-xs text-mint-950";

  return (
    <div className="animate-fade-up space-y-5 pt-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="flex items-center gap-2">
            <span className="tag">Step 3 of 3</span>
            {!done && (
              <span className="flex items-center gap-1.5 rounded bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rose-500" /> Live
              </span>
            )}
          </p>
          <h1 className="mt-4 text-4xl sm:text-5xl">{beat >= 5 ? "Done – your result is ready" : "Our agents are checking your product"}</h1>
          {run && (
            <p className="mt-3 flex flex-wrap items-center gap-x-2 text-mint-900/65">
              <span className="font-medium text-mint-950">{spec?.title}</span>·<span className="text-lg leading-none">{run.countries.slice(0, 14).map(flag).join(" ")}</span>
              {run.countries.length > 14 && <span className="text-sm">+{run.countries.length - 14}</span>}
            </p>
          )}
        </div>
        <button type="button" className="btn-ghost" onClick={() => (done ? onDone() : setSkip(true))}>
          {skip && !done ? (
            "Showing shortly …"
          ) : (
            <>
              <FastForward size={16} /> Skip
            </>
          )}
        </button>
      </div>

      <div className="h-1 overflow-hidden rounded-full bg-mint-900/[0.08]" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
        <motion.div className="h-full rounded-full bg-mint-400" animate={{ width: `${Math.max(3, progress * 100)}%` }} transition={{ duration: 0.6, ease }} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[19rem_minmax(0,1fr)] xl:grid-cols-[21rem_minmax(0,1fr)]">
        <div className="card flex flex-col p-3">
          <ol className="space-y-1">
            {PIPELINE.map((kind, i) => {
              const state = i < beat ? "done" : i === beat ? "active" : "todo";
              return (
                <li key={kind} className={`flex items-center gap-3 rounded-xl p-2 transition-colors duration-500 ${state === "active" ? "bg-mint-50" : ""}`}>
                  <AgentAvatar kind={kind} size={40} active={state === "active"} className={`transition duration-500 ${state === "todo" ? "opacity-35 grayscale" : ""}`} />
                  <div className="min-w-0 flex-1">
                    <p className={`font-medium ${state === "todo" ? "text-mint-900/40" : "text-mint-950"}`}>{AGENTS[kind].name}</p>
                    <p className="truncate text-sm">
                      {state === "done" ? (
                        <span className="text-mint-900/65">{results[i]}</span>
                      ) : state === "active" ? (
                        <span className="shimmer-text">{AGENTS[kind].does} …</span>
                      ) : (
                        <span className="text-mint-900/35">waiting</span>
                      )}
                    </p>
                  </div>
                  {state === "done" && (
                    <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="grid h-6 w-6 place-items-center rounded-full bg-mint-400 text-mint-950">
                      <Check size={13} strokeWidth={3} />
                    </motion.span>
                  )}
                </li>
              );
            })}
          </ol>

          <div className="mt-3 flex-1 border-t border-mint-900/[0.06] px-2 pt-3">
            <p className="label mb-2">Activity</p>
            {/* fixed height, so the stage beside it keeps its size while entries come and go */}
            <ul className="relative h-[6.25rem] space-y-1.5 overflow-hidden">
              <AnimatePresence initial={false} mode="popLayout">
                {log.map((e) => (
                  <motion.li key={e.id} layout initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="flex items-center gap-2 text-xs">
                    <AgentAvatar kind={agentOf(e.agent)} size={20} />
                    <span className="min-w-0 flex-1 truncate text-mint-900/80">{e.action}</span>
                    <span className="shrink-0 font-mono text-[10px] text-mint-900/40">{time(e.ts_start)}</span>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
            <p className="mt-3 flex items-center gap-1.5 text-[11px] text-mint-900/50">
              <ShieldCheck size={13} className="text-mint-600" /> Every step is logged – fully traceable later.
            </p>
          </div>
        </div>

        <div className="card relative min-h-[22rem] overflow-hidden sm:min-h-[27rem]">
          <div className={`absolute inset-0 transition-opacity duration-700 ${beat === 0 ? "opacity-40" : ""}`}>
            <WorldMap fill fillFor={fillFor} focus={focus} interactive={false}>
              {beat >= 4 && (
                <>
                  {hop > 0 && <Trail from={GENEVA} to={centroid(order[0])} color={AGENTS.scout.color} />}
                  {order.slice(1, hop).map((iso3, i) => (
                    <Trail key={iso3} from={centroid(order[i])} to={centroid(iso3)} color={AGENTS.scout.color} />
                  ))}
                  {order.length <= 16 &&
                    order.slice(0, hop).map((iso3) => {
                      const s = statusOf(iso3);
                      return (
                        <MapPin key={iso3} at={centroid(iso3)}>
                          <FlagPin iso3={iso3} color={s ? STATUS[s].color : STATUS.grey.color} small={order.length > 8} />
                        </MapPin>
                      );
                    })}
                  {beat === 4 && <AgentPin at={scoutAt} kind="scout" label={current ? countryName(current) : "on the way …"} />}
                </>
              )}
              {beat >= 1 && beat <= 3 && <AgentPin at={GENEVA} kind={PIPELINE[beat]} label="UNECE · Geneva" />}
            </WorldMap>
          </div>

          <div className="pointer-events-none absolute inset-x-4 bottom-4 flex justify-start sm:inset-x-6 sm:bottom-6">
            <AnimatePresence mode="wait">
              <motion.div
                key={beat}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.4, ease }}
                className="pointer-events-auto w-full max-w-md rounded-xl bg-white/95 p-4 shadow-lift ring-1 ring-mint-900/10 backdrop-blur"
              >
                {beat === 0 && (
                  <div className="flex gap-4">
                    {run?.has_image && <Blueprint src={api.runImageUrl(run.run_id)} scanning className="h-28 w-28 shrink-0" />}
                    <div className="min-w-0">
                      {cardLabel("reader", `Reader${parts.length ? ` · ${plural(parts.length, "part", "parts")} found` : ""}`)}
                      <p className="text-lg text-mint-950">{spec?.title ?? "Product description"}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {(parts.length ? parts.slice(0, 8) : (spec?.sections ?? []).map((s) => sectionName(s.title))).map((label, i) => (
                          <motion.span key={label} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.25 + i * 0.15 }} className={pill}>
                            {label}
                          </motion.span>
                        ))}
                        {parts.length > 8 && <span className="text-xs text-mint-900/55">+{parts.length - 8}</span>}
                      </div>
                    </div>
                  </div>
                )}
                {beat === 1 && (
                  <div>
                    {cardLabel("researcher", `Researcher · ${run?.pipeline?.funnel.regulations ? `from ${run.pipeline.funnel.regulations} UN vehicle regulations` : "UN vehicle regulations"}`)}
                    <p className="text-lg text-mint-950">{regulations.length ? plural(regulations.length, "applicable regulation", "applicable regulations") : "Looking for applicable regulations …"}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {regulations.slice(0, 10).map((r, i) => (
                        <motion.span key={r.code} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.14 }} className={pill} title={r.code}>
                          {r.name}
                        </motion.span>
                      ))}
                      {regulations.length > 10 && <span className="text-xs text-mint-900/55">+{regulations.length - 10}</span>}
                    </div>
                  </div>
                )}
                {beat === 2 && (
                  <div className="flex items-center gap-5">
                    <div className="text-center">
                      {run ? <CountUp value={run.requirements.length} className="block text-5xl text-mint-950" /> : <span className="text-5xl text-mint-950">…</span>}
                      <span className="text-xs text-mint-900/55">requirements</span>
                    </div>
                    <div className="min-w-0 text-sm text-mint-900/80">
                      {cardLabel("checker", "Checker")}
                      <p>Every requirement with its source: regulation, version, page.</p>
                      {run?.validation && (
                        <p className={`mt-1 flex items-center gap-1.5 font-medium ${run.validation.ok ? "text-emerald-700" : "text-amber-700"}`}>
                          <Check size={15} /> {run.validation.ok ? "All sources confirmed" : `${run.validation.problems.length} sources unclear`}
                        </p>
                      )}
                    </div>
                  </div>
                )}
                {beat === 3 && (
                  <div>
                    {cardLabel("matcher", "Matcher · your product against each requirement")}
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      {(Object.keys(findingCounts) as FindingStatus[]).map((k) => (
                        <div key={k} className="rounded-lg bg-flat-white/70 p-2.5 text-center">
                          <CountUp value={findingCounts[k]} className="block text-2xl text-mint-950" />
                          <span className="flex items-center justify-center gap-1 text-[11px] text-mint-900/65">
                            <span className="h-1.5 w-1.5 rounded-full" style={{ background: FINDING[k].color }} />
                            {FINDING[k].label}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {beat === 4 && (
                  <div className="flex items-center gap-3">
                    <AgentAvatar kind="scout" size={44} active />
                    <div className="min-w-0 flex-1">
                      {cardLabel("scout", `Country agent · ${Math.min(hop, order.length)} of ${order.length}`)}
                      {current ? (
                        <motion.div key={current} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} className="mt-0.5 flex flex-wrap items-center gap-2">
                          <span className="text-xl leading-none">{flag(current)}</span>
                          <span className="font-medium text-mint-950">{countryName(current)}</span>
                          {statusOf(current) && <StatusPill status={statusOf(current)!} />}
                        </motion.div>
                      ) : (
                        <p className="font-medium text-mint-950">Starting the country check …</p>
                      )}
                    </div>
                  </div>
                )}
                {beat >= 5 && (
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="grid h-10 w-10 place-items-center rounded-md bg-mint-400 text-mint-950">
                        <Check size={22} strokeWidth={3} />
                      </span>
                      <div>
                        <p className="text-lg text-mint-950">{plural(order.length, "market", "markets")} rated</p>
                        <p className="flex flex-wrap gap-x-3 text-xs">
                          {STATUS_ORDER.filter((s) => counts[s]).map((s) => (
                            <span key={s} className={STATUS[s].text}>
                              {counts[s]} {STATUS[s].label}
                            </span>
                          ))}
                        </p>
                      </div>
                    </div>
                    <button type="button" className="btn-primary mt-3 w-full" onClick={onDone}>
                      See the result <ArrowRight size={16} />
                    </button>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
