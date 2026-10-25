import { Check } from "lucide-react";

const STEPS = ["Product", "Markets", "Result"];

/** 1 Product · 2 Markets · 3 Result – where the user is in the flow. Finished steps are clickable to go back. */
export function Stepper({ current, onSelect }: { current: 1 | 2 | 3; onSelect?: (step: 1 | 2 | 3) => void }) {
  return (
    <ol className="hidden items-center gap-1 rounded-lg bg-white p-1 ring-1 ring-mint-900/[0.06] md:flex" aria-label="Progress">
      {STEPS.map((label, i) => {
        const n = (i + 1) as 1 | 2 | 3;
        const done = n < current;
        const active = n === current;
        return (
          <li key={label} aria-current={active ? "step" : undefined}>
            <button
              type="button"
              disabled={!done || !onSelect}
              onClick={() => onSelect?.(n)}
              className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors duration-300 ${
                active ? "bg-mint-950 text-white" : done ? "text-mint-900 hover:bg-mint-100/60" : "text-mint-900/45"
              } disabled:cursor-default`}
            >
            <span
              className={`grid h-5 w-5 place-items-center rounded-full text-[11px] font-semibold ${
                active ? "bg-mint-400 text-mint-950" : done ? "bg-mint-100 text-mint-800" : "bg-mint-900/[0.06]"
              }`}
            >
              {done ? <Check size={12} strokeWidth={3} /> : n}
            </span>
            {label}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
