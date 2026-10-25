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
    <div className="card animate-fade-up overflow-hidden">
      <div className={`grid ${image ? "md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]" : ""}`}>
        {image && (
          <div className="border-b border-mint-900/[0.06] p-4 md:border-b-0 md:border-r">
            <Blueprint file={image} scanning className="aspect-square md:aspect-auto md:h-full" />
          </div>
        )}
        <div>
          <div className="flex items-center gap-4 px-6 py-5">
            <span className="grid h-11 w-11 place-items-center rounded-md bg-mint-950 text-mint-300">
              <Package size={22} />
            </span>
            <div>
              <p className="eyebrow">Your product</p>
              <h3 className="text-2xl font-normal tracking-tight">{spec.title}</h3>
            </div>
          </div>
          <div className="grid gap-5 border-t border-mint-900/[0.06] p-6 sm:grid-cols-2">
            {spec.sections.map((s) => (
              <div key={s.title} className={s.rows.length ? "sm:col-span-2" : ""}>
                <p className="label mb-1.5">{sectionName(s.title)}</p>
                {s.text.map((t, j) => (
                  <p key={j} className="text-sm text-mint-950">
                    {t}
                  </p>
                ))}
                {s.items.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {s.items.map((item) => (
                      <span key={item} className="chip-soft">
                        {item}
                      </span>
                    ))}
                  </div>
                )}
                {s.rows.length > 0 && (
                  <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
                    {s.rows.map((row) => (
                      <p key={row.join("|")} className="text-sm">
                        <span className="font-medium text-mint-950">{row[0]}</span>
                        <span className="text-mint-900/60"> · {row.slice(1).join(", ")}</span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="border-t border-mint-900/[0.06] px-6 py-3">
        <button type="button" aria-expanded={showRaw} className="flex items-center gap-1 rounded text-xs text-mint-900/55 transition-colors hover:text-mint-950" onClick={() => setShowRaw((v) => !v)}>
          <ChevronDown size={14} className={`transition ${showRaw ? "rotate-180" : ""}`} />
          {showRaw ? "Hide" : "Show"} original file ({fileName}
          {image ? ` + ${image.name}` : ""})
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
