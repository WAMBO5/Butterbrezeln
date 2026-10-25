import { createPortal } from "react-dom";
import { motion } from "motion/react";
import { ArrowRight, X } from "lucide-react";
import type { LineageTarget, RunResult, TraceEvent } from "../types";
import { AGENTS, agentOf } from "../lib/agents";
import { buildChain } from "../lib/lineage";
import { actorOf } from "../lib/labels";
import { DraftNotice } from "./Badges";
import { useDrawer } from "../lib/useDrawer";
import { AgentAvatar } from "./Agent";
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

/** "How do we know?": product description -> regulation -> page -> requirement -> check -> country -> suggestion. */
export function LineageDrawer({ target, run, trace, onClose, onNavigate, onOpenEvent }: Props) {
  const chain = buildChain(target, run, trace);
  useDrawer(onClose);
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end bg-mint-950/40 backdrop-blur-[2px]" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label="How do we know?" className="h-full w-full max-w-xl animate-slide-in overflow-y-auto overflow-x-hidden bg-flat-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <header className="sticky top-0 z-10 flex items-center justify-between bg-white/95 px-6 py-4 shadow-[0_1px_0_rgba(17,80,75,0.08)] backdrop-blur">
          <div>
            <p className="eyebrow">Traceability</p>
            <h2 className="text-2xl">How do we know?</h2>
            <p className="text-sm text-mint-900/60">The full chain – every step with its source and author.</p>
            <div className="mt-1.5">
              <DraftNotice compact />
            </div>
          </div>
          <button type="button" className="btn-ghost !p-2" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </header>
        <ol className="px-6 py-6">
          {chain.map((step, i) => {
            const who = step.event ? actorOf(step.event) : null;
            const kind = step.event ? agentOf(step.event.agent) : null;
            return (
              <motion.li
                key={step.key}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.04 + i * 0.06, duration: 0.3 }}
                className="relative pb-8 pl-11"
              >
                {i < chain.length - 1 && <span className="absolute bottom-0 left-[13px] top-8 w-px bg-mint-900/10" aria-hidden />}
                <span className="absolute left-0 top-0 grid h-7 w-7 place-items-center rounded-full bg-mint-950 text-xs font-semibold text-mint-300">{i + 1}</span>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base">{step.title}</h3>
                  {who && kind && step.event && (
                    <button
                      type="button"
                      onClick={() => onOpenEvent(step.event!.id)}
                      title="Open log entry"
                      className="inline-flex items-center gap-1.5 rounded-md bg-mint-900/[0.05] py-0.5 pl-0.5 pr-2 text-xs font-medium text-mint-900 transition-colors hover:bg-mint-900/10"
                    >
                      <AgentAvatar kind={kind} size={20} />
                      {AGENTS[kind].name}
                      <span className="text-mint-900/55">· {who.label}</span>
                    </button>
                  )}
                </div>
                {step.text &&
                  (step.quote ? (
                    <blockquote className="mt-2 rounded-lg border-l-2 border-mint-500 bg-white px-4 py-3 text-sm text-mint-950 ring-1 ring-mint-900/[0.06]">“{step.text}”</blockquote>
                  ) : (
                    <p className="mt-1 text-sm text-mint-900/85">{step.text}</p>
                  ))}
                {step.chips && step.chips.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {step.chips.map((c) => (
                      <span key={c} className="chip-soft">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
                {step.detail && <p className="mt-1 text-sm text-mint-900/60">{step.detail}</p>}
                {step.event?.status === "fallback" && <p className="mt-1 text-xs text-amber-700">Determined by rule check (AI assistant not connected).</p>}
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
                        <button type="button" className="flex items-start gap-1.5 text-left text-sm font-medium text-mint-700 hover:text-mint-950 hover:underline" onClick={() => onNavigate(l.target)}>
                          <ArrowRight size={14} className="mt-0.5 shrink-0" /> {l.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </motion.li>
            );
          })}
          {!chain.length && <li className="text-sm text-mint-900/60">No lineage data found.</li>}
        </ol>
      </aside>
    </div>,
    document.body,
  );
}
