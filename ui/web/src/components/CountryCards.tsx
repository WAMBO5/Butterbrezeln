import { ChevronRight } from "lucide-react";
import { motion } from "motion/react";
import type { CountryVerdict } from "../types";
import { flag } from "../lib/geo";
import { EFFORT, EFFORT_ORDER, RULE, STATUS, STATUS_ORDER, byEffort, plural } from "../lib/labels";
import { StatusDot, StatusPill } from "./Badges";

/** All assessed countries as cards, grouped by traffic-light colour. */
export function CountryCards({ verdicts, onSelect }: { verdicts: CountryVerdict[]; onSelect: (iso3: string) => void }) {
  return (
    <div className="space-y-10">
      {STATUS_ORDER.map((status) => {
        const items = verdicts.filter((v) => v.status === status).sort((a, b) => a.name_de.localeCompare(b.name_de, "de"));
        if (!items.length) return null;
        const st = STATUS[status];
        return (
          <section key={status} id={`status-${status}`} className="scroll-mt-24">
            <h3 className="mb-4 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-display text-lg font-bold text-white">
              <StatusDot status={status} />
              {st.label}
              <span className="font-sans text-sm font-medium text-slate-500">· {items.length}</span>
              {status !== "grey" && <span className="font-sans text-sm font-normal text-slate-500">– {RULE[status]}</span>}
            </h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {items.map((v, i) => {
                const top = [...v.suggestions].sort(byEffort)[0];
                const efforts = [...new Set(v.suggestions.map((s) => s.effort))].sort((a, b) => EFFORT_ORDER.indexOf(a) - EFFORT_ORDER.indexOf(b));
                return (
                  <motion.button
                    key={v.iso3}
                    type="button"
                    onClick={() => onSelect(v.iso3)}
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    whileHover={{ y: -4 }}
                    viewport={{ once: true, margin: "-30px" }}
                    transition={{ delay: Math.min(i, 8) * 0.05, duration: 0.4 }}
                    className="glass group relative flex flex-col overflow-hidden p-5 text-left transition-colors hover:border-white/20"
                  >
                    <span className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-25 blur-2xl transition-opacity duration-300 group-hover:opacity-50" style={{ background: st.color }} />
                    <span className="pointer-events-none absolute inset-x-6 top-0 h-px" style={{ background: `linear-gradient(90deg, transparent, ${st.color}, transparent)` }} />
                    <div className="relative flex items-center gap-3">
                      <span className="text-4xl leading-none">{flag(v.iso3)}</span>
                      <div className="min-w-0">
                        <p className="truncate font-display text-lg font-bold text-white">{v.name_de}</p>
                        <StatusPill status={v.status} />
                      </div>
                    </div>
                    <p className="relative mt-4 line-clamp-2 flex-1 text-sm text-slate-300">
                      {top ? top.change : v.status === "green" ? "Nichts zu ändern – Ihr Produkt passt so, wie es ist." : st.desc}
                    </p>
                    <div className="relative mt-4 flex items-center justify-between text-xs text-slate-400">
                      <span className="flex items-center gap-1.5">
                        {efforts.map((e) => {
                          const Icon = EFFORT[e].icon;
                          return (
                            <span key={e} title={EFFORT[e].label} className={`grid h-5 w-5 place-items-center rounded-full ${EFFORT[e].iconBg}`}>
                              <Icon size={11} />
                            </span>
                          );
                        })}
                        {v.suggestions.length ? plural(v.suggestions.length, "Schritt", "Schritte") : v.status === "grey" ? "Keine Daten" : "Nichts zu tun"}
                      </span>
                      <span className="flex items-center font-semibold text-cyan-300 opacity-60 transition-opacity group-hover:opacity-100">
                        Details <ChevronRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                      </span>
                    </div>
                  </motion.button>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
