import { useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown, Flag, Info, PartyPopper, Send, X } from "lucide-react";
import type { Decision, Effort, LineageTarget, Regime, RunResult, Suggestion } from "../types";
import { AGENTS } from "../lib/agents";
import { countryName, flag } from "../lib/geo";
import { EFFORT, EFFORT_ORDER, STATUS, byEffort, plural, sectionName } from "../lib/labels";
import { useDrawer } from "../lib/useDrawer";
import { AgentAvatar, AgentBot } from "./Agent";
import { EffortChip } from "./Badges";
import { SourceLink, SourceList } from "./SourceLink";

interface Props {
  iso3: string;
  run: RunResult;
  onClose: () => void;
  onAsk: (iso3: string, question: string) => Promise<void>;
  onDecide: (suggestionId: string, decision: Decision) => Promise<void>;
  onLineage: (target: LineageTarget) => void;
  onAnalyzeWith: (iso3: string) => Promise<void>;
}

const QUICK_QUESTIONS = ["What do we need to change?", "Which certificate do we need?", "Which evidence is still missing?"];

const REGIME: Record<Regime, string> = {
  unece_1958: "Recognises the UN vehicle regulations",
  national: "Has its own national rules",
  not_covered: "No country data yet",
};

function StepCard({ s, n, onDecide, onLineage }: { s: Suggestion; n: number; onDecide: Props["onDecide"]; onLineage: Props["onLineage"] }) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const effort = EFFORT[s.effort];
  const decide = async (d: Decision) => {
    setBusy(true);
    try {
      await onDecide(s.id, d);
    } finally {
      setBusy(false);
    }
  };
  const frame =
    s.decision === "accepted" ? "bg-emerald-50/60 ring-emerald-600/25" : s.decision === "rejected" ? "bg-flat-white/50 ring-mint-900/[0.06] opacity-60" : "bg-white ring-mint-900/10";
  return (
    <li className="relative pb-4 pl-11">
      <span className="absolute bottom-0 left-[15px] top-9 w-px bg-mint-900/10" aria-hidden />
      <span
        className="absolute left-0 top-1 grid h-8 w-8 place-items-center rounded-full bg-white text-sm font-semibold"
        style={{ color: effort.color, boxShadow: `inset 0 0 0 1px ${effort.color}66` }}
      >
        {s.decision === "accepted" ? <Check size={15} strokeWidth={3} /> : n}
      </span>
      <div className={`rounded-xl p-4 ring-1 ring-inset transition-colors ${frame}`}>
        <div className="flex flex-wrap items-center gap-2">
          <EffortChip effort={s.effort} />
          <span className="text-xs text-mint-900/50">{effort.desc}</span>
          {s.decision === "accepted" && <span className="ml-auto text-xs font-medium text-emerald-700">✓ accepted</span>}
          {s.decision === "rejected" && <span className="ml-auto text-xs font-medium text-mint-900/55">rejected</span>}
        </div>
        <p className="mt-2 font-medium leading-snug text-mint-950">{s.change}</p>
        <p className="mt-1 text-xs text-mint-900/55">Affects: {sectionName(s.spec_section)}</p>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
              <div className="mt-3 space-y-2 rounded-lg bg-flat-white/70 p-3 text-sm text-mint-900/85">
                <p>{s.reason}</p>
                <SourceList sources={s.sources} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" disabled={busy || s.decision === "accepted"} onClick={() => decide("accepted")} className="btn-primary btn-sm">
            <Check size={14} /> Accept
          </button>
          <button type="button" disabled={busy || s.decision === "rejected"} onClick={() => decide("rejected")} className="btn-outline btn-sm">
            <X size={14} /> Reject
          </button>
          <button type="button" aria-expanded={open} className="ml-auto flex items-center gap-1 rounded text-xs text-mint-900/60 transition-colors hover:text-mint-950" onClick={() => setOpen((v) => !v)}>
            Why? <ChevronDown size={14} className={`transition ${open ? "rotate-180" : ""}`} />
          </button>
          <button type="button" className="link text-xs" onClick={() => onLineage({ kind: "suggestion", id: s.id })}>
            Source chain
          </button>
        </div>
      </div>
    </li>
  );
}

function TypingDots() {
  return (
    <span className="flex items-center gap-1 px-1 py-1">
      {[0, 1, 2].map((i) => (
        <span key={i} className="h-1.5 w-1.5 animate-typing rounded-full bg-mint-600" style={{ animationDelay: `${i * 0.15}s` }} />
      ))}
    </span>
  );
}

export function CountryDrawer({ iso3, run, onClose, onAsk, onDecide, onLineage, onAnalyzeWith }: Props) {
  const verdict = run.verdicts[iso3];
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [askError, setAskError] = useState<string | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);
  const [showAllReasons, setShowAllReasons] = useState(false);
  const [starting, setStarting] = useState(false);
  useDrawer(onClose);

  const ask = async (text: string) => {
    if (!text.trim() || pending) return;
    setPending(text.trim());
    setAskError(null);
    setQuestion("");
    try {
      await onAsk(iso3, text.trim());
    } catch (e) {
      setAskError(String(e));
      setQuestion(text);
    } finally {
      setPending(null);
    }
  };

  const status = verdict ? STATUS[verdict.status] : null;
  const reqById = new Map(run.requirements.map((r) => [r.id, r]));
  const openFindings = run.findings.filter((f) => f.status === "open");
  const qa = run.qa.filter((q) => q.country === iso3);
  const steps = verdict ? [...verdict.suggestions].sort(byEffort) : [];
  const effortCounts = steps.reduce<Partial<Record<Effort, number>>>((c, s) => ({ ...c, [s.effort]: (c[s.effort] ?? 0) + 1 }), {});
  const name = countryName(iso3, verdict?.name);

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-end bg-mint-950/40 backdrop-blur-[2px]" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label={name} className="flex h-full w-full max-w-xl animate-slide-in flex-col bg-flat-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-center justify-between gap-3 bg-white px-6 py-4 shadow-[0_1px_0_rgba(17,80,75,0.08)]">
          <div className="flex items-center gap-4">
            <span className="text-4xl leading-none">{flag(iso3)}</span>
            <div>
              <h2 className="text-2xl">{name}</h2>
              <p className="text-xs text-mint-900/55">{verdict ? REGIME[verdict.regime] : "Not part of this check"}</p>
            </div>
          </div>
          <button type="button" className="btn-ghost !p-2" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </header>

        <div className="flex-1 space-y-8 overflow-y-auto px-6 py-6">
          {!verdict || !status ? (
            <div className="flex flex-col items-center gap-4 py-10 text-center">
              <span className="grid h-24 w-24 place-items-center rounded-2xl" style={{ background: `${AGENTS.scout.color}14` }}>
                <AgentBot color={AGENTS.scout.color} magnifier size={72} />
              </span>
              <p className="max-w-xs text-mint-900/80">{name} was not part of this check. Should the country agent add it?</p>
              <button
                type="button"
                className="btn-primary"
                disabled={starting}
                onClick={async () => {
                  setStarting(true);
                  try {
                    await onAnalyzeWith(iso3);
                  } catch {
                    setStarting(false);
                  }
                }}
              >
                {starting ? "Starting …" : `Check ${name} too`}
              </button>
            </div>
          ) : (
            <>
              <section className={`rounded-2xl p-5 ring-1 ring-inset ${status.soft} ${status.ring}`}>
                <div className="flex items-start gap-3">
                  <status.icon size={26} className={`mt-0.5 shrink-0 ${status.text}`} />
                  <div>
                    <p className={`text-2xl ${status.text}`}>{status.label}</p>
                    <p className="mt-1 text-sm text-mint-900/80">{status.desc}</p>
                  </div>
                </div>
                {steps.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-1.5 pl-[38px]">
                    {EFFORT_ORDER.filter((e) => effortCounts[e]).map((e) => {
                      const Icon = EFFORT[e].icon;
                      return (
                        <span key={e} className={`chip bg-white ring-1 ring-inset ${EFFORT[e].chip.split(" ").filter((c) => !c.startsWith("bg-")).join(" ")}`}>
                          <Icon size={12} /> {effortCounts[e]} × {EFFORT[e].label}
                        </span>
                      );
                    })}
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-4 text-lg">
                  {steps.length ? "Your path to approval" : "What needs doing?"}{" "}
                  {steps.length > 0 && <span className="text-sm font-normal text-mint-900/50">· {plural(steps.length, "step", "steps")}, largest effort first</span>}
                </h3>
                {steps.length ? (
                  <ol>
                    {steps.map((s, i) => (
                      <StepCard key={s.id} s={s} n={i + 1} onDecide={onDecide} onLineage={onLineage} />
                    ))}
                    <li className="flex items-center gap-3">
                      <span className="grid h-8 w-8 place-items-center rounded-full bg-emerald-100 text-emerald-700">
                        <Flag size={15} />
                      </span>
                      <span className="text-sm font-medium text-emerald-800">Ready to sell in {name}</span>
                    </li>
                  </ol>
                ) : verdict.status === "grey" ? (
                  <p className="rounded-xl bg-white p-4 text-sm text-mint-900/65 ring-1 ring-mint-900/[0.06]">Without data on this country we can't name any steps.</p>
                ) : (
                  <div className="flex items-center gap-3 rounded-xl bg-emerald-50 p-4 text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
                    <PartyPopper size={22} />
                    <p className="text-sm font-medium">Nothing to do – your product works as it is.</p>
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-2 text-lg">Background</h3>
                <ul className="space-y-2">
                  {(showAllReasons ? verdict.reasons : verdict.reasons.slice(0, 1)).map((r, i) => (
                    <li key={i} className="flex gap-2 text-sm text-mint-900/85">
                      <Info size={16} className="mt-0.5 shrink-0 text-mint-900/40" />
                      <span className={showAllReasons ? "" : "line-clamp-3"}>{r}</span>
                    </li>
                  ))}
                </ul>
                {(verdict.reasons.length > 1 || (verdict.reasons[0]?.length ?? 0) > 220) && (
                  <button type="button" className="mt-1 pl-6 text-xs text-mint-900/55 hover:text-mint-950" onClick={() => setShowAllReasons((v) => !v)}>
                    {showAllReasons ? "Show less" : "Show more"}
                  </button>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <SourceList sources={verdict.sources} />
                  <button type="button" className="link text-xs" onClick={() => onLineage({ kind: "verdict", iso3 })}>
                    How was this rating reached?
                  </button>
                </div>
                {verdict.regime !== "not_covered" && verdict.open_evidence_count > 0 && (
                  <div className="mt-4 overflow-hidden rounded-xl bg-white ring-1 ring-mint-900/[0.08]">
                    <button type="button" aria-expanded={showEvidence} className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm" onClick={() => setShowEvidence((v) => !v)}>
                      <span>
                        <span className="font-medium text-mint-950">{verdict.open_evidence_count} test records</span>
                        <span className="text-mint-900/60"> – measurements and tests, as for any approval</span>
                      </span>
                      <ChevronDown size={16} className={`shrink-0 text-mint-900/45 transition ${showEvidence ? "rotate-180" : ""}`} />
                    </button>
                    {showEvidence && (
                      <ul className="max-h-72 space-y-3 overflow-y-auto border-t border-mint-900/[0.06] px-4 py-3">
                        {openFindings.map((f) => {
                          const req = reqById.get(f.requirement_id);
                          return (
                            <li key={f.id} className="space-y-1 text-xs">
                              <p className="text-mint-900/85">{req?.text}</p>
                              {req?.pipeline?.test_case && <p className="text-mint-900/55">Evidence: {req.pipeline.test_case}</p>}
                              {req && <SourceLink source={req.source} />}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                )}
              </section>

              <section className="rounded-2xl bg-white p-5 ring-1 ring-mint-900/[0.06]">
                <div className="flex items-center gap-3">
                  <AgentAvatar kind="assistant" size={40} active={!!pending} />
                  <div>
                    <h3 className="text-lg">Ask the assistant</h3>
                    <p className="text-xs text-mint-900/55">Answers come with sources; new steps appear in your path above.</p>
                  </div>
                </div>
                <div className="mt-4 space-y-3">
                  {qa.map((entry) => (
                    <div key={entry.id} className="animate-fade-up space-y-2">
                      <p className="ml-auto w-fit max-w-[85%] rounded-xl rounded-br-sm bg-mint-950 px-4 py-2 text-sm text-white">{entry.question}</p>
                      <div className="flex max-w-[94%] gap-2">
                        <AgentAvatar kind="assistant" size={28} className="mt-1" />
                        <div className="min-w-0 space-y-2 rounded-xl rounded-tl-sm bg-flat-white/80 px-4 py-3 text-sm text-mint-950">
                          <p className="whitespace-pre-line">{entry.answer}</p>
                          {entry.suggestion_ids.length > 0 && <p className="text-xs text-mint-700">{plural(entry.suggestion_ids.length, "new step", "new steps")} added to your path.</p>}
                          <SourceList sources={entry.sources.slice(0, 6)} />
                        </div>
                      </div>
                    </div>
                  ))}
                  {pending && (
                    <div className="space-y-2">
                      <p className="ml-auto w-fit max-w-[85%] rounded-xl rounded-br-sm bg-mint-950 px-4 py-2 text-sm text-white">{pending}</p>
                      <div className="flex items-center gap-2">
                        <AgentAvatar kind="assistant" size={28} active />
                        <span className="rounded-xl rounded-tl-sm bg-flat-white/80 px-3 py-2">
                          <TypingDots />
                        </span>
                      </div>
                    </div>
                  )}
                </div>
                {!qa.length && !pending && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {QUICK_QUESTIONS.map((q) => (
                      <button key={q} type="button" onClick={() => ask(q)} className="rounded-md bg-mint-50 px-3 py-1.5 text-xs text-mint-900 ring-1 ring-inset ring-mint-500/25 transition-colors hover:bg-mint-100">
                        {q}
                      </button>
                    ))}
                  </div>
                )}
                <form
                  className="mt-3 flex items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    ask(question);
                  }}
                >
                  <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={`Ask about ${name} …`} aria-label={`Ask about ${name}`} className="input" />
                  <button type="submit" className="btn-primary !p-3" disabled={!!pending || !question.trim()} aria-label="Send">
                    <Send size={16} />
                  </button>
                </form>
                {askError && <p className="mt-2 text-xs text-rose-700">{askError}</p>}
              </section>
            </>
          )}
        </div>
      </aside>
    </div>,
    document.body,
  );
}
