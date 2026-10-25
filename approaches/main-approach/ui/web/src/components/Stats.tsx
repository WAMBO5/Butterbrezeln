import { useEffect, useState } from "react";
import { animate, motion } from "motion/react";
import type { VerdictStatus } from "../types";
import { STATUS, STATUS_ORDER } from "../lib/labels";

/** A number that counts up when it appears or changes. */
export function CountUp({ value, duration = 1.1, className }: { value: number; duration?: number; className?: string }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const controls = animate(0, value, { duration, ease: [0.22, 1, 0.36, 1], onUpdate: (v) => setShown(Math.round(v)) });
    return () => controls.stop();
  }, [value, duration]);
  return <span className={`tabular-nums ${className ?? ""}`}>{shown}</span>;
}

/** Ring chart of the markets by traffic-light colour, drawn segment by segment. */
export function MarketDonut({ counts, size = 168 }: { counts: Record<VerdictStatus, number>; size?: number }) {
  const total = STATUS_ORDER.reduce((n, s) => n + counts[s], 0);
  const r = 42;
  const c = 2 * Math.PI * r;
  const gap = total > 1 ? 12 : 0; // room for the round caps between segments
  let offset = 0;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="9" />
        {STATUS_ORDER.map((s, i) => {
          if (!counts[s]) return null;
          const length = (counts[s] / total) * c;
          const dash = Math.max(length - gap, 0.01);
          const start = offset;
          offset += length;
          return (
            <motion.circle
              key={s}
              cx="50"
              cy="50"
              r={r}
              fill="none"
              stroke={STATUS[s].color}
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-(start + gap / 2)}
              style={{ filter: `drop-shadow(0 0 4px ${STATUS[s].color})` }}
              initial={{ opacity: 0, strokeDasharray: `0 ${c}` }}
              animate={{ opacity: 1, strokeDasharray: `${dash} ${c - dash}` }}
              transition={{ duration: 0.9, delay: 0.2 + i * 0.25, ease: [0.22, 1, 0.36, 1] }}
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <CountUp value={total} className="block font-display text-4xl font-bold leading-none text-white" />
          <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{total === 1 ? "Markt" : "Märkte"}</span>
        </div>
      </div>
    </div>
  );
}
