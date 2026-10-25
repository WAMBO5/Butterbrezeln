import { createPortal } from "react-dom";
import { motion } from "motion/react";
import { ArrowRight, X } from "lucide-react";
import type { LineageTarget, RunResult, TraceEvent } from "../types";
import { AGENTS, agentOf } from "../lib/agents";
import { buildChain } from "../lib/lineage";
import { actorOf } from "../lib/labels";
import { useDrawer } from "../lib/useDrawer";
import { AgentAvatar } from "./Agent";
import { DraftNotice } from "./Badges";
import { SourceList } from "./SourceLink";
import { SpecView } from "./SpecView";

interface Props {
  target: LineageTarget;
  run: RunResult;
  trace: TraceEvent[];
  onClose: () => void;
  onNavigate: (target: LineageTarget) => void;
  onOpenEvent: (eventId: string) => void;
}

/** "Woher wissen wir das?": product description -> regulation -> page -> requirement -> check -> country -> suggestion. */
export function LineageDrawer({ target, run, trace, onClose, onNavigate, onOpenEvent }: Props) {
  const chain = buildChain(target, run, trace);
  useDrawer(onClose);
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end bg-ink-950/60 backdrop-blur-sm" onClick={onClose}>
      <aside className="relative h-full w-full max-w-xl animate-slide-in overflow-y-auto overflow-x-hidden border-l border-white/10 bg-ink-900/95 shadow-2xl backdrop-blur-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-cyan-400/20 blur-3xl" aria-hidden />
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/[0.06] bg-ink-900/85 px-6 py-4 backdrop-blur-xl">
          <div>
            <p className="eyebrow">Nachvollziehbarkeit</p>
            <h2 className="text-xl font-bold">Woher wissen wir das?</h2>
            <p className="text-sm text-slate-400">Die vollständige Kette – jeder Schritt mit Quelle und Urheber.</p>
            <div className="mt-1.5">
              <DraftNotice compact />
            </div>
          </div>
          <button type="button" className="btn-ghost !p-2" onClick={onClose} aria-label="Schließen">
            <X size={20} />
          </button>
        </header>
        <ol className="relative px-6 py-6">
          {chain.map((step, i) => {
            const who = step.event ? actorOf(step.event) : null;
            const kind = step.event ? agentOf(step.event.agent) : null;
            return (
              <motion.li
                key={step.key}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 + i * 0.07, duration: 0.35 }}
                className="relative pb-8 pl-12"
              >
                {i < chain.length - 1 && <span className="absolute bottom-0 left-[15px] top-9 w-px bg-gradient-to-b from-cyan-300/40 to-white/5" aria-hidden />}
                <span className="absolute left-0 top-0 grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-teal-300 to-cyan-400 text-xs font-bold text-ink-950 shadow-[0_0_20px_-4px_rgba(45,212,191,0.8)]">
                  {i + 1}
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-display text-base font-bold text-white">{step.title}</h3>
                  {who && kind && step.event && (
                    <button type="button" onClick={() => onOpenEvent(step.event!.id)} title="Protokolleintrag öffnen"
                            className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] py-0.5 pl-0.5 pr-2.5 text-[11px] font-semibold text-slate-300 ring-1 ring-white/10 transition hover:bg-white/10 hover:text-white">
                      <AgentAvatar kind={kind} size={20} />
                      {AGENTS[kind].name}
                      <span className="font-medium text-slate-500">· {who.label}</span>
                    </button>
                  )}
                </div>
                {step.text &&
                  (step.quote ? (
                    <blockquote className="mt-2 rounded-xl border-l-2 border-cyan-300/60 bg-cyan-300/[0.06] px-4 py-3 text-sm italic text-slate-200">„{step.text}“</blockquote>
                  ) : (
                    <p className="mt-1 text-sm text-slate-300">{step.text}</p>
                  ))}
                {step.chips && step.chips.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {step.chips.map((c) => (
                      <span key={c} className="rounded-full bg-cyan-300/10 px-2.5 py-0.5 text-xs font-medium text-cyan-100 ring-1 ring-cyan-300/20">{c}</span>
                    ))}
                  </div>
                )}
                {step.detail && <p className="mt-1 text-sm text-slate-400">{step.detail}</p>}
                {step.event?.status === "fallback" && <p className="mt-1 text-xs text-amber-300/90">Per Regelprüfung ermittelt (KI-Assistent nicht verbunden).</p>}
                {step.specLines && (
                  <div className="mt-2">
                    <SpecView text={run.spec_text} highlight={step.specLines} context={1} />
                  </div>
                )}
                {step.sources && step.sources.length > 0 && (
                  <div className="mt-2">
                    <SourceList sources={step.sources} />
                  </div>
                )}
                {step.links && step.links.length > 0 && (
                  <ul className="mt-2 space-y-1.5">
                    {step.links.map((l, j) => (
                      <li key={j}>
                        <button type="button" className="flex items-start gap-1.5 text-left text-sm font-medium text-cyan-300 hover:underline" onClick={() => onNavigate(l.target)}>
                          <ArrowRight size={14} className="mt-0.5 shrink-0" /> {l.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </motion.li>
            );
          })}
          {!chain.length && <li className="text-sm text-slate-400">Keine Herkunftsdaten gefunden.</li>}
        </ol>
      </aside>
    </div>,
    document.body,
  );
}
