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
    <div className="overflow-x-auto rounded-lg bg-flat-white/70 py-2 font-mono text-[12px] leading-6 text-mint-900/80 ring-1 ring-mint-900/[0.06]">
      {lines.slice(first - 1, last).map((line, i) => {
        const n = first + i;
        const hit = highlight && n >= highlight[0] && n <= highlight[1];
        return (
          <div key={n} className={`whitespace-pre pr-3 ${hit ? "bg-amber-100/70 text-mint-950 shadow-[inset_3px_0_0_#f0b429]" : ""}`}>
            <span className="inline-block w-10 select-none pr-3 text-right text-mint-900/35">{n}</span>
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}
