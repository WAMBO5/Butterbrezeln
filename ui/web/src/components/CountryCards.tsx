import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import type { CountryVerdict } from "../types";
import { countryName, flag } from "../lib/geo";
import { EFFORT, EFFORT_ORDER, RULE, STATUS, STATUS_ORDER, byEffort, plural } from "../lib/labels";
import { StatusDot } from "./Badges";

/** All assessed countries as cards, grouped by traffic-light colour. */
export function CountryCards({ verdicts, onSelect }: { verdicts: CountryVerdict[]; onSelect: (iso3: string) => void }) {
  return (
    <div className="space-y-10">
      {STATUS_ORDER.map((status) => {
        const items = verdicts
          .map((v) => ({ v, name: countryName(v.iso3, v.name) }))
          .filter(({ v }) => v.status === status)
          .sort((a, b) => a.name.localeCompare(b.name, "en"));
        if (!items.length) return null;
        const st = STATUS[status];
        return (
          <section key={status} id={`status-${status}`} className="scroll-mt-24">
            <h3 className="mb-4 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xl font-normal">
              <StatusDot status={status} />
              {st.label}
              <span className="text-base text-mint-900/45">{items.length}</span>
              {status !== "grey" && <span className="text-sm text-mint-900/55">· {RULE[status]}</span>}
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {items.map(({ v, name }, i) => {
                const top = [...v.suggestions].sort(byEffort)[0];
                const efforts = [...new Set(v.suggestions.map((s) => s.effort))].sort((a, b) => EFFORT_ORDER.indexOf(a) - EFFORT_ORDER.indexOf(b));
                return (
                  <motion.button
                    key={v.iso3}
                    type="button"
                    onClick={() => onSelect(v.iso3)}
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-30px" }}
                    transition={{ delay: Math.min(i, 8) * 0.04, duration: 0.35 }}
                    className="card group flex flex-col p-5 text-left transition-shadow duration-300 hover:shadow-lift hover:ring-mint-500/40"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-3xl leading-none">{flag(v.iso3)}</span>
                      <p className="min-w-0 flex-1 truncate text-lg text-mint-950">{name}</p>
                      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: st.color }} title={st.label} />
                    </div>
                    <p className="mt-3 line-clamp-2 flex-1 text-sm text-mint-900/70">
                      {top ? top.change : v.status === "green" ? "Nothing to change – your product works as it is." : st.desc}
                    </p>
                    <div className="mt-4 flex items-center justify-between border-t border-mint-900/[0.06] pt-3 text-xs text-mint-900/60">
                      <span className="flex items-center gap-1.5">
                        {efforts.map((e) => {
                          const Icon = EFFORT[e].icon;
                          return (
                            <span key={e} title={EFFORT[e].label} className={`grid h-5 w-5 place-items-center rounded ${EFFORT[e].iconBg}`}>
                              <Icon size={11} />
                            </span>
                          );
                        })}
                        {v.suggestions.length ? plural(v.suggestions.length, "step", "steps") : v.status === "grey" ? "No data" : "Nothing to do"}
                      </span>
                      <span className="flex items-center gap-1 font-medium text-mint-700 transition-colors group-hover:text-mint-950">
                        Details <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
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
