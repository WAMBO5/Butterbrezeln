import { useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown, ClipboardList, Flag, Info, Send, X } from "lucide-react";
import type { Decision, Effort, LineageTarget, Regime, RunResult, Suggestion } from "../types";
import { AGENTS } from "../lib/agents";
import { countryName, flag } from "../lib/geo";
import { COUNTRY_DATA_NOTE, EFFORT, EFFORT_ORDER, STATUS, byEffort, plural, sectionName } from "../lib/labels";
import { useDrawer } from "../lib/useDrawer";
import { AgentAvatar, AgentBot } from "./Agent";
import { DraftNotice, EffortChip } from "./Badges";
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

const QUICK_QUESTIONS = ["Was müssen wir ändern?", "Welches Zertifikat brauchen wir?", "Welche Nachweise fehlen noch?"];

const REGIME: Record<Regime, string> = {
  unece_1958: "Erkennt die UN-Fahrzeugvorschriften an",
  national: "Eigene nationale Vorschriften",
  not_covered: "Noch keine Länderdaten",
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
    s.decision === "akzeptiert"
      ? "border-emerald-400/30 bg-emerald-400/[0.06]"
      : s.decision === "verworfen"
        ? "border-white/[0.06] bg-white/[0.02] opacity-55"
        : "border-white/[0.08] bg-white/[0.035] hover:border-white/15";
  return (
    <li className="relative pb-4 pl-12">
      <span className="absolute bottom-0 left-[17px] top-10 w-px bg-gradient-to-b from-white/15 to-white/5" aria-hidden />
      <span
        className="absolute left-0 top-1 grid h-9 w-9 place-items-center rounded-full text-sm font-bold"
        style={{ background: `${effort.color}1f`, color: effort.color, boxShadow: `inset 0 0 0 1px ${effort.color}55, 0 0 20px -6px ${effort.color}` }}
      >
        {s.decision === "akzeptiert" ? <Check size={16} strokeWidth={3} /> : n}
      </span>
      <div className={`rounded-2xl border p-4 transition ${frame}`}>
        <div className="flex flex-wrap items-center gap-2">
          <EffortChip effort={s.effort} />
          <span className="text-[11px] text-slate-500">{effort.desc}</span>
          {s.decision === "akzeptiert" && <span className="ml-auto text-xs font-semibold text-emerald-300">✓ übernommen</span>}
          {s.decision === "verworfen" && <span className="ml-auto text-xs font-semibold text-slate-500">abgelehnt</span>}
        </div>
        <p className="mt-2 font-medium leading-snug text-white">{s.change}</p>
        <p className="mt-1 text-xs text-slate-500">Betrifft: {sectionName(s.spec_section)}</p>
        <button type="button" className="mt-2 flex items-center gap-1 text-xs font-medium text-slate-400 transition hover:text-white" onClick={() => setOpen((v) => !v)}>
          <ChevronDown size={14} className={`transition ${open ? "rotate-180" : ""}`} /> Warum?
        </button>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
              <div className="mt-2 space-y-2 rounded-xl bg-white/[0.04] p-3 text-sm text-slate-300">
                <p>{s.reason}</p>
                <SourceList sources={s.sources} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" disabled={busy || s.decision === "akzeptiert"} onClick={() => decide("akzeptiert")}
                  className="btn !px-3 !py-1.5 bg-emerald-400/15 text-xs text-emerald-200 ring-1 ring-inset ring-emerald-400/30 hover:bg-emerald-400/25 focus-visible:ring-emerald-400/30">
            <Check size={14} /> Übernehmen
          </button>
          <button type="button" disabled={busy || s.decision === "verworfen"} onClick={() => decide("verworfen")} className="btn-secondary !px-3 !py-1.5 text-xs">
            <X size={14} /> Ablehnen
          </button>
          <button type="button" className="ml-auto text-xs font-medium text-cyan-300 hover:underline" onClick={() => onLineage({ kind: "suggestion", id: s.id })}>
            Woher wissen wir das?
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
        <span key={i} className="h-1.5 w-1.5 animate-typing rounded-full bg-indigo-300" style={{ animationDelay: `${i * 0.15}s` }} />
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
  const openFindings = run.findings.filter((f) => f.status === "offen");
  const qa = run.qa.filter((q) => q.country === iso3);
  const steps = verdict ? [...verdict.suggestions].sort(byEffort) : [];
  const effortCounts = steps.reduce<Partial<Record<Effort, number>>>((c, s) => ({ ...c, [s.effort]: (c[s.effort] ?? 0) + 1 }), {});
  const name = verdict?.name_de ?? countryName(iso3);
  const glow = status?.color ?? AGENTS.scout.color;

  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-950/60 backdrop-blur-sm" onClick={onClose}>
      <aside className="relative flex h-full w-full max-w-xl animate-slide-in flex-col overflow-hidden border-l border-white/10 bg-ink-900/95 shadow-2xl backdrop-blur-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full opacity-25 blur-3xl" style={{ background: glow }} aria-hidden />
        <header className="relative flex items-center justify-between gap-3 border-b border-white/[0.06] px-6 py-4">
          <div className="flex items-center gap-4">
            <span className="text-5xl leading-none">{flag(iso3)}</span>
            <div>
              <h2 className="text-2xl font-bold tracking-tight">{name}</h2>
              <p className="text-xs text-slate-400">{verdict ? REGIME[verdict.regime] : "Nicht Teil dieser Prüfung"}</p>
              {verdict && (
                <div className="mt-1.5">
                  <DraftNotice compact />
                </div>
              )}
            </div>
          </div>
          <button type="button" className="btn-ghost !p-2" onClick={onClose} aria-label="Schließen">
            <X size={20} />
          </button>
        </header>

        <div className="relative flex-1 space-y-8 overflow-y-auto px-6 py-6">
          {!verdict || !status ? (
            <div className="flex flex-col items-center gap-4 py-10 text-center">
              <span className="grid h-24 w-24 place-items-center rounded-3xl" style={{ background: `${AGENTS.scout.color}1a` }}>
                <AgentBot color={AGENTS.scout.color} magnifier size={72} />
              </span>
              <p className="max-w-xs text-slate-300">{name} war nicht Teil dieser Prüfung. Soll der Länder-Agent das Land mitprüfen?</p>
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
                {starting ? "Startet …" : `${name} mitprüfen`}
              </button>
            </div>
          ) : (
            <>
              <section className="relative overflow-hidden rounded-3xl p-5" style={{ background: `linear-gradient(135deg, ${status.color}24, ${status.color}06)`, boxShadow: `inset 0 0 0 1px ${status.color}40` }}>
                <div className="flex items-start gap-4">
                  <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl" style={{ background: `${status.color}26`, color: status.color, boxShadow: `0 0 30px -6px ${status.color}` }}>
                    <status.icon size={26} />
                  </span>
                  <div>
                    <p className={`font-display text-2xl font-bold ${status.text}`}>{status.label}</p>
                    <p className="mt-1 text-sm text-slate-300">{status.desc}</p>
                  </div>
                </div>
                {steps.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {EFFORT_ORDER.filter((e) => effortCounts[e]).map((e) => {
                      const Icon = EFFORT[e].icon;
                      return (
                        <span key={e} className={`chip !py-0.5 !text-xs ring-1 ring-inset ${EFFORT[e].chip}`}>
                          <Icon size={12} /> {effortCounts[e]} × {EFFORT[e].label}
                        </span>
                      );
                    })}
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-4 font-display text-lg font-bold">
                  {steps.length ? "Nötige Schritte" : "Was ist zu tun?"}{" "}
                  {steps.length > 0 && <span className="font-sans text-sm font-medium text-slate-500">· {plural(steps.length, "Schritt", "Schritte")}, größter Aufwand zuerst</span>}
                </h3>
                {steps.length ? (
                  <ol>
                    {steps.map((s, i) => (
                      <StepCard key={s.id} s={s} n={i + 1} onDecide={onDecide} onLineage={onLineage} />
                    ))}
                    <li className="flex items-center gap-3">
                      <span className="grid h-9 w-9 place-items-center rounded-full bg-white/[0.06] text-slate-300 ring-1 ring-inset ring-white/15">
                        <Flag size={16} />
                      </span>
                      <span className="text-sm font-semibold text-slate-300">
                        Danach: Zulassung in {name}
                        {verdict.open_evidence_count > 0 && ` mit ${plural(verdict.open_evidence_count, "Prüfnachweis", "Prüfnachweisen")}`}
                      </span>
                    </li>
                  </ol>
                ) : verdict.status === "grey" ? (
                  <p className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 text-sm text-slate-400">Ohne Daten zu diesem Land können wir keine Schritte nennen.</p>
                ) : (
                  <div className="flex items-center gap-3 rounded-2xl bg-emerald-400/10 p-4 text-emerald-200 ring-1 ring-inset ring-emerald-400/25">
                    <ClipboardList size={24} className="shrink-0" />
                    <p className="text-sm font-medium">Keine Produktänderung gefunden. Für die Zulassung bleiben die üblichen Prüfnachweise (unten).</p>
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-2 font-display text-lg font-bold">Hintergrund</h3>
                <ul className="space-y-2">
                  {(showAllReasons ? verdict.reasons : verdict.reasons.slice(0, 1)).map((r, i) => (
                    <li key={i} className="flex gap-2 text-sm text-slate-300">
                      <Info size={16} className="mt-0.5 shrink-0 text-slate-500" />
                      <span className={showAllReasons ? "" : "line-clamp-3"}>{r}</span>
                    </li>
                  ))}
                </ul>
                {(verdict.reasons.length > 1 || (verdict.reasons[0]?.length ?? 0) > 220) && (
                  <button type="button" className="mt-1 pl-6 text-xs font-medium text-slate-400 hover:text-white" onClick={() => setShowAllReasons((v) => !v)}>
                    {showAllReasons ? "Weniger anzeigen" : "Mehr anzeigen"}
                  </button>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <SourceList sources={verdict.sources} />
                  <button type="button" className="text-xs font-medium text-cyan-300 hover:underline" onClick={() => onLineage({ kind: "verdict", iso3 })}>
                    Wie kam diese Bewertung zustande?
                  </button>
                </div>
                {verdict.regime !== "not_covered" && <p className="mt-2 text-xs text-slate-500">{COUNTRY_DATA_NOTE}</p>}
                {verdict.regime !== "not_covered" && verdict.open_evidence_count > 0 && (
                  <div className="mt-4 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.02]">
                    <button type="button" className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm" onClick={() => setShowEvidence((v) => !v)}>
                      <span>
                        <span className="font-semibold text-white">{verdict.open_evidence_count} Prüfnachweise</span>
                        <span className="text-slate-400"> – Messungen und Tests, wie bei jeder Zulassung</span>
                      </span>
                      <ChevronDown size={16} className={`shrink-0 text-slate-500 transition ${showEvidence ? "rotate-180" : ""}`} />
                    </button>
                    {showEvidence && (
                      <ul className="max-h-72 space-y-3 overflow-y-auto border-t border-white/[0.06] px-4 py-3">
                        {openFindings.map((f) => {
                          const req = reqById.get(f.requirement_id);
                          return (
                            <li key={f.id} className="space-y-1 text-xs">
                              <p className="text-slate-300">{req?.text}</p>
                              {req?.pipeline?.test_case && <p className="text-slate-500">Nachweis: {req.pipeline.test_case}</p>}
                              {req && <SourceLink source={req.source} />}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                )}
              </section>

              <section className="rounded-3xl border border-indigo-300/15 bg-indigo-400/[0.05] p-4">
                <div className="flex items-center gap-3">
                  <AgentAvatar kind="assistant" size={44} active={!!pending} />
                  <div>
                    <h3 className="font-display text-lg font-bold">Fragen Sie den Assistenten</h3>
                    <p className="text-xs text-slate-400">Antworten nennen ihre Quellen, wo es welche gibt; neue Schritte erscheinen oben in der Liste.</p>
                  </div>
                </div>
                <div className="mt-4 space-y-3">
                  {qa.map((entry) => (
                    <div key={entry.id} className="animate-fade-up space-y-2">
                      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-gradient-to-br from-teal-300 to-cyan-300 px-4 py-2 text-sm font-medium text-ink-950">{entry.question}</p>
                      <div className="flex max-w-[94%] gap-2">
                        <AgentAvatar kind="assistant" size={28} className="mt-1" />
                        <div className="min-w-0 space-y-2 rounded-2xl rounded-tl-md border border-white/[0.08] bg-white/[0.05] px-4 py-3 text-sm text-slate-200">
                          <p className="whitespace-pre-line">{entry.answer}</p>
                          {entry.suggestion_ids.length > 0 && <p className="text-xs text-teal-300">{plural(entry.suggestion_ids.length, "neuer Schritt", "neue Schritte")} oben ergänzt.</p>}
                          <SourceList sources={entry.sources.slice(0, 6)} />
                        </div>
                      </div>
                    </div>
                  ))}
                  {pending && (
                    <div className="space-y-2">
                      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-gradient-to-br from-teal-300 to-cyan-300 px-4 py-2 text-sm font-medium text-ink-950">{pending}</p>
                      <div className="flex items-center gap-2">
                        <AgentAvatar kind="assistant" size={28} active />
                        <span className="rounded-2xl rounded-tl-md border border-white/[0.08] bg-white/[0.05] px-3 py-2">
                          <TypingDots />
                        </span>
                      </div>
                    </div>
                  )}
                </div>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {QUICK_QUESTIONS.map((q) => (
                    <button key={q} type="button" disabled={!!pending} onClick={() => ask(q)}
                            className="rounded-full border border-indigo-300/20 bg-indigo-300/10 px-3 py-1 text-xs font-medium text-indigo-100 transition hover:bg-indigo-300/20 disabled:opacity-40">
                      {q}
                    </button>
                  ))}
                </div>
                <form
                  className="mt-3 flex items-center gap-2 rounded-full border border-white/10 bg-ink-950/60 p-1 pl-4 transition focus-within:border-cyan-300/40 focus-within:ring-4 focus-within:ring-cyan-300/10"
                  onSubmit={(e) => {
                    e.preventDefault();
                    ask(question);
                  }}
                >
                  <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={`Frage zu ${name} …`} className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none" />
                  <button type="submit" className="btn-primary !p-2.5" disabled={!!pending || !question.trim()} aria-label="Senden">
                    <Send size={16} />
                  </button>
                </form>
                {askError && <p className="mt-2 text-xs text-rose-300">{askError}</p>}
              </section>
            </>
          )}
        </div>
      </aside>
    </div>,
    document.body,
  );
}
