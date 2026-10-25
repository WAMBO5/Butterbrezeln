import { useCallback } from "react";
import { motion } from "motion/react";
import type { VerdictStatus } from "../types";
import { AGENTS, PIPELINE } from "../lib/agents";
import { centroid, countryName, flag } from "../lib/geo";
import { STATUS, UNTESTED_FILL } from "../lib/labels";
import { AgentAvatar } from "./Agent";
import { AgentPin, FlagPin, MapPin, WorldMap } from "./WorldMap";

// illustrative only – labelled "Beispiel" in the UI
const PREVIEW: Record<string, VerdictStatus> = { DEU: "green", FRA: "green", ESP: "green", JPN: "green", AUS: "green", CHN: "yellow", IND: "yellow", USA: "red", CAN: "red", BRA: "grey" };

const CARDS: { iso3: string; text: string; className: string; delay: number }[] = [
  // over Greenland and Siberia, clear of the pins and the agent
  { iso3: "DEU", text: "Keine Änderung nötig", className: "left-[30%] top-[3%]", delay: 0.5 },
  { iso3: "CHN", text: "2 Schritte nötig", className: "right-[3%] top-[2%]", delay: 0.8 },
  { iso3: "USA", text: "Produktänderung nötig", className: "bottom-[10%] left-[6%]", delay: 1.1 },
];

/** Landing visual: a live-looking world map with the country agent at work. */
export function HeroVisual() {
  const fillFor = useCallback((iso3: string) => (PREVIEW[iso3] ? STATUS[PREVIEW[iso3]].color : UNTESTED_FILL), []);
  const glowFor = useCallback((iso3: string) => (PREVIEW[iso3] && PREVIEW[iso3] !== "grey" ? STATUS[PREVIEW[iso3]].color : null), []);
  return (
    <div className="relative">
      <div className="pointer-events-none absolute -inset-10 rounded-full bg-gradient-to-tr from-teal-400/20 via-cyan-400/10 to-indigo-500/20 blur-3xl" aria-hidden />
      <div className="glass relative overflow-hidden p-2">
        <WorldMap fillFor={fillFor} glowFor={glowFor} interactive={false} className="rounded-[20px]">
          {Object.entries(PREVIEW)
            .filter(([iso3]) => iso3 !== "CHN")
            .map(([iso3, status]) => (
              <MapPin key={iso3} at={centroid(iso3)}>
                <FlagPin iso3={iso3} color={STATUS[status].color} small />
              </MapPin>
            ))}
          <AgentPin at={centroid("CHN")} label="prüft China …" />
        </WorldMap>
        <span className="absolute bottom-4 right-4 rounded-full bg-ink-950/70 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400 ring-1 ring-white/10 backdrop-blur">
          Beispiel
        </span>
      </div>
      {CARDS.map((c) => {
        const status = STATUS[PREVIEW[c.iso3]];
        return (
          <motion.div
            key={c.iso3}
            initial={{ opacity: 0, y: 16, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: c.delay, type: "spring", stiffness: 260, damping: 22 }}
            className={`absolute hidden sm:block ${c.className}`}
          >
            <div className="flex animate-float items-center gap-2.5 rounded-2xl border border-white/10 bg-ink-900/80 px-3 py-2 shadow-2xl backdrop-blur-xl" style={{ animationDelay: `${c.delay}s` }}>
              <span className="text-2xl leading-none">{flag(c.iso3)}</span>
              <span>
                <span className="flex items-center gap-1.5 text-xs font-semibold text-white">
                  {countryName(c.iso3)}
                  <span className="h-2 w-2 rounded-full" style={{ background: status.color, boxShadow: `0 0 8px ${status.color}` }} />
                </span>
                <span className={`block text-[11px] font-medium ${status.text}`}>{c.text}</span>
              </span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

/** The five agents in the order they work, connected by a flowing line. */
export function AgentLineup() {
  return (
    <div className="relative">
      <div className="absolute left-[10%] right-[10%] top-9 hidden h-px overflow-hidden bg-white/10 md:block" aria-hidden>
        <div className="h-full w-full animate-shimmer bg-[linear-gradient(90deg,transparent_35%,rgba(103,232,249,0.9)_50%,transparent_65%)] [background-size:200%_100%]" />
      </div>
      <ol className="relative grid gap-4 sm:grid-cols-2 md:grid-cols-5">
        {PIPELINE.map((kind, i) => {
          const a = AGENTS[kind];
          return (
            <motion.li
              key={kind}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ delay: i * 0.09, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="group flex flex-col items-center text-center"
            >
              <span className="relative transition duration-300 group-hover:-translate-y-1">
                <AgentAvatar kind={kind} size={72} active />
                <span className="absolute -right-1 -top-1 grid h-6 w-6 place-items-center rounded-full bg-ink-900 text-[11px] font-bold text-white ring-1 ring-white/15">{i + 1}</span>
              </span>
              <p className="mt-3 font-display text-base font-bold text-white">{a.name}</p>
              <p className="mt-0.5 max-w-[14rem] text-sm text-slate-400">{a.does}</p>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
