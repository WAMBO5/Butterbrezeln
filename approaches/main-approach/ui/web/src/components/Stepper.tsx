import { Check } from "lucide-react";

const STEPS = ["Produkt", "Märkte", "Ergebnis"];

/** 1 Produkt · 2 Märkte · 3 Ergebnis – where the user is in the flow. */
export function Stepper({ current }: { current: 1 | 2 | 3 }) {
  return (
    <ol className="hidden items-center gap-2 md:flex">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const done = n < current;
        const active = n === current;
        return (
          <li key={label} className="flex items-center gap-2">
            {i > 0 && <span className={`h-px w-8 transition-colors ${done || active ? "bg-gradient-to-r from-teal-300 to-cyan-300" : "bg-white/10"}`} />}
            <span
              className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold transition ${
                done
                  ? "bg-teal-300/15 text-teal-200 ring-1 ring-teal-300/40"
                  : active
                    ? "bg-gradient-to-br from-teal-300 to-cyan-300 text-ink-950 shadow-[0_0_20px_-2px_rgba(45,212,191,0.7)]"
                    : "bg-white/[0.05] text-slate-500 ring-1 ring-white/10"
              }`}
            >
              {done ? <Check size={14} strokeWidth={3} /> : n}
            </span>
            <span className={`text-sm font-medium ${active ? "text-white" : done ? "text-slate-300" : "text-slate-500"}`}>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
