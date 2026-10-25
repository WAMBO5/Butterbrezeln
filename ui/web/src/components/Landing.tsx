import { useCallback } from "react";
import { motion } from "motion/react";
import type { VerdictStatus } from "../types";
import { AGENTS, PIPELINE } from "../lib/agents";
import { centroid } from "../lib/geo";
import { RULE, STATUS, STATUS_ORDER, UNTESTED_FILL } from "../lib/labels";
import { AgentAvatar } from "./Agent";
import { AgentPin, FlagPin, MapPin, WorldMap } from "./WorldMap";

// illustrative only – labelled "Example" in the UI
const PREVIEW: Record<string, VerdictStatus> = { DEU: "green", FRA: "green", ESP: "green", JPN: "green", AUS: "green", CHN: "yellow", IND: "yellow", USA: "red", CAN: "red", BRA: "grey" };

/** Landing visual: a world map with the country agent at work, framed like the product shots on certivity.io. */
export function HeroVisual() {
  const fillFor = useCallback((iso3: string) => (PREVIEW[iso3] ? STATUS[PREVIEW[iso3]].color : UNTESTED_FILL), []);
  return (
    <figure className="rounded-[clamp(1rem,0.6rem+1.2vw,1.5rem)] bg-mint-600/30 p-2 shadow-2xl backdrop-blur sm:p-3">
      <div className="relative overflow-hidden rounded-xl bg-white">
        <WorldMap fillFor={fillFor} interactive={false}>
          {Object.entries(PREVIEW)
            .filter(([iso3]) => iso3 !== "CHN")
            .map(([iso3, status]) => (
              <MapPin key={iso3} at={centroid(iso3)}>
                <FlagPin iso3={iso3} color={STATUS[status].color} small />
              </MapPin>
            ))}
          <AgentPin at={centroid("CHN")} label="checking China …" />
        </WorldMap>
        <span className="absolute bottom-3 right-3 rounded bg-mint-950/80 px-2 py-1 text-[11px] font-medium text-mint-50">Example</span>
      </div>
      <figcaption className="flex flex-wrap gap-x-5 gap-y-1.5 px-2 pb-1 pt-3 text-xs text-mint-50/75">
        {STATUS_ORDER.filter((s) => s !== "grey").map((s) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: STATUS[s].color }} />
            <span className="text-white">{STATUS[s].label}</span> {RULE[s].toLowerCase()}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

/** The five agents in the order they work. */
export function AgentLineup() {
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {PIPELINE.map((kind, i) => {
        const a = AGENTS[kind];
        return (
          <motion.li
            key={kind}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ delay: i * 0.07, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="card flex flex-col gap-4 p-5"
          >
            <div className="flex items-center justify-between">
              <AgentAvatar kind={kind} size={52} active />
              <span className="font-mono text-xs text-mint-900/40">0{i + 1}</span>
            </div>
            <div>
              <p className="font-semibold text-mint-950">{a.name}</p>
              <p className="mt-1 text-sm text-mint-900/65">{a.does.charAt(0).toUpperCase() + a.does.slice(1)}</p>
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}
