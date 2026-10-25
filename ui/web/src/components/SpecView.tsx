/** The product description as a document; cited lines are highlighted. */
export function SpecView({ text, highlight, context }: { text: string; highlight?: number[] | null; context?: number }) {
  const lines = text.split("\n");
  let first = 1;
  let last = lines.length;
  if (highlight && context !== undefined) {
    first = Math.max(1, highlight[0] - context);
    last = Math.min(lines.length, highlight[1] + context);
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-white/[0.08] bg-ink-950/60 py-2 font-mono text-[12px] leading-6 text-slate-400">
      {lines.slice(first - 1, last).map((line, i) => {
        const n = first + i;
        const hit = highlight && n >= highlight[0] && n <= highlight[1];
        return (
          <div key={n} className={`whitespace-pre pr-3 ${hit ? "bg-amber-300/15 text-amber-100 shadow-[inset_3px_0_0_#fbbf24]" : ""}`}>
            <span className="inline-block w-10 select-none pr-3 text-right text-slate-600">{n}</span>
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}
