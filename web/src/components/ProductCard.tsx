import { useState } from "react";
import { ChevronDown, Package } from "lucide-react";
import { summarizeSpec } from "../lib/specSummary";
import { sectionName } from "../lib/labels";
import { Blueprint } from "./Blueprint";
import { SpecView } from "./SpecView";

/** The uploaded spec.md as a friendly product card instead of raw markdown. */
export function ProductCard({ text, fileName, image }: { text: string; fileName: string; image?: File | null }) {
  const [showRaw, setShowRaw] = useState(false);
  const spec = summarizeSpec(text);
  return (
    <div className="glass animate-fade-up overflow-hidden">
      <div className={`grid gap-0 ${image ? "md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]" : ""}`}>
        {image && (
          <div className="border-b border-white/[0.06] p-4 md:border-b-0 md:border-r">
            <Blueprint file={image} scanning className="aspect-square md:aspect-auto md:h-full" />
          </div>
        )}
        <div>
          <div className="relative flex items-center gap-4 overflow-hidden px-6 py-5">
            <div className="pointer-events-none absolute -left-10 -top-16 h-40 w-64 rounded-full bg-teal-400/20 blur-3xl" aria-hidden />
            <span className="relative grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-teal-300 to-cyan-400 text-ink-950 shadow-[0_0_30px_-6px_rgba(45,212,191,0.8)]">
              <Package size={24} />
            </span>
            <div className="relative">
              <p className="eyebrow">Ihr Produkt</p>
              <h3 className="text-2xl font-bold tracking-tight">{spec.title}</h3>
            </div>
          </div>
          <div className="grid gap-5 border-t border-white/[0.06] p-6 sm:grid-cols-2">
            {spec.sections.map((s, i) => (
              <div key={s.title} className={`animate-fade-up ${s.rows.length ? "sm:col-span-2" : ""}`} style={{ animationDelay: `${120 + i * 70}ms` }}>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{sectionName(s.title)}</p>
                {s.text.map((t, j) => (
                  <p key={j} className="text-sm text-slate-200">{t}</p>
                ))}
                {s.items.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {s.items.map((item) => (
                      <span key={item} className="chip bg-cyan-300/10 !py-0.5 !text-xs text-cyan-100 ring-1 ring-inset ring-cyan-300/20">{item}</span>
                    ))}
                  </div>
                )}
                {s.rows.length > 0 && (
                  <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
                    {s.rows.map((row) => (
                      <p key={row.join("|")} className="text-sm">
                        <span className="font-medium text-white">{row[0]}</span>
                        <span className="text-slate-400"> · {row.slice(1).join(", ")}</span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="border-t border-white/[0.06] px-6 py-3">
        <button type="button" className="flex items-center gap-1 text-xs font-medium text-slate-500 transition hover:text-slate-200" onClick={() => setShowRaw((v) => !v)}>
          <ChevronDown size={14} className={`transition ${showRaw ? "rotate-180" : ""}`} />
          Originaldatei anzeigen ({fileName}{image ? ` + ${image.name}` : ""})
        </button>
        {showRaw && (
          <div className="mt-3 max-h-80 animate-fade-up overflow-y-auto">
            <SpecView text={text} />
          </div>
        )}
      </div>
    </div>
  );
}
