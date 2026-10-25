import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CornerDownLeft, Euro, Landmark, Star, X } from "lucide-react";
import type { CountryListing } from "../types";
import { AGENTS } from "../lib/agents";
import { allCountries, countryName, flag } from "../lib/geo";
import { AgentBot } from "./Agent";

/** Where the country agent is on the map: searching a match, or just found and added it. */
export type Scout = { iso3: string; phase: "search" | "found" } | null;

interface Props {
  listing: CountryListing | null;
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  onScout: (scout: Scout) => void;
}

const PRESETS: Record<string, { label: string; icon: typeof Euro }> = {
  "EU-27": { label: "EU", icon: Euro },
  "UNECE 1958": { label: "UN-Vertragsstaaten", icon: Landmark },
  "Top-Märkte": { label: "Top-Märkte", icon: Star },
};

export function CountryPicker({ listing, selected, onChange, onScout }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const known = useMemo(() => new Map(listing?.countries.map((c) => [c.iso3, c]) ?? []), [listing]);
  const everyone = useMemo(allCountries, []);

  const q = query.trim().toLowerCase();
  const matches = useMemo(() => {
    if (!q) return [];
    const hits = everyone.filter((c) => c.name.toLowerCase().includes(q) || c.iso3.toLowerCase() === q);
    // names that start with the query first ("Chi" -> China before Kambodscha)
    return hits.sort((a, b) => Number(!a.name.toLowerCase().startsWith(q)) - Number(!b.name.toLowerCase().startsWith(q))).slice(0, 6);
  }, [q, everyone]);

  const hint = (iso3: string) => {
    const c = known.get(iso3);
    if (!c) return { text: "keine Daten", cls: "bg-slate-400/10 text-slate-400" };
    return c.regime === "unece_1958"
      ? { text: "UN-Vorschriften", cls: "bg-teal-300/10 text-teal-200" }
      : { text: "eigene Vorschriften", cls: "bg-violet-300/10 text-violet-200" };
  };

  const search = (text: string) => {
    setQuery(text);
    setActive(0);
    const t = text.trim().toLowerCase();
    const first = t ? everyone.find((c) => c.name.toLowerCase().startsWith(t)) ?? everyone.find((c) => c.name.toLowerCase().includes(t)) : undefined;
    onScout(first ? { iso3: first.iso3, phase: "search" } : null);
  };
  const add = (isos: string[]) => onChange(new Set([...selected, ...isos]));
  const pick = (iso3: string) => {
    add([iso3]);
    setQuery("");
    onScout({ iso3, phase: "found" });
  };
  const remove = (iso3: string) => {
    const next = new Set(selected);
    next.delete(iso3);
    onChange(next);
  };
  const scout = AGENTS.scout;

  return (
    <div className="space-y-6">
      <div className="relative">
        <p className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Land suchen</p>
        <div className={`flex items-center gap-2 rounded-2xl border bg-white/[0.04] p-1.5 pr-3 transition ${q ? "border-teal-300/40 shadow-[0_0_30px_-8px_rgba(45,212,191,0.6)]" : "border-white/10"}`}>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: `${scout.color}1f` }}>
            <AgentBot color={scout.color} magnifier active={!!q} size={34} />
          </span>
          <input
            value={query}
            onChange={(e) => search(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                const next = (active + (e.key === "ArrowDown" ? 1 : -1) + matches.length) % Math.max(matches.length, 1);
                setActive(next);
                if (matches[next]) onScout({ iso3: matches[next].iso3, phase: "search" });
              } else if (e.key === "Enter" && matches[active]) {
                e.preventDefault();
                pick(matches[active].iso3);
              } else if (e.key === "Escape") {
                search("");
              }
            }}
            placeholder="z. B. China"
            aria-label="Land suchen"
            className="min-w-0 flex-1 bg-transparent text-[15px] text-white placeholder-slate-500 outline-none"
          />
          {q && (
            <button type="button" aria-label="Suche leeren" className="text-slate-500 hover:text-white" onClick={() => search("")}>
              <X size={16} />
            </button>
          )}
        </div>
        <AnimatePresence>
          {matches.length > 0 && (
            <motion.ul
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.15 }}
              className="absolute z-20 mt-2 w-full overflow-hidden rounded-2xl border border-white/10 bg-ink-850/95 p-1 shadow-2xl backdrop-blur-xl"
            >
              {matches.map((c, i) => {
                const h = hint(c.iso3);
                return (
                  <li key={c.iso3}>
                    <button
                      type="button"
                      onMouseEnter={() => {
                        setActive(i);
                        onScout({ iso3: c.iso3, phase: "search" });
                      }}
                      onClick={() => pick(c.iso3)}
                      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition ${i === active ? "bg-white/[0.07]" : ""}`}
                    >
                      <span className="text-xl leading-none">{flag(c.iso3)}</span>
                      <span className="min-w-0 flex-1 truncate font-medium text-white">{c.name}</span>
                      {selected.has(c.iso3) ? (
                        <span className="text-xs font-semibold text-teal-300">✓ gewählt</span>
                      ) : (
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${h.cls}`}>{h.text}</span>
                      )}
                      {i === active && <CornerDownLeft size={13} className="text-slate-500" />}
                    </button>
                  </li>
                );
              })}
            </motion.ul>
          )}
        </AnimatePresence>
      </div>

      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Schnellauswahl</p>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(listing?.presets ?? {}).map(([key, isos]) => {
            const preset = PRESETS[key] ?? { label: key, icon: Star };
            const Icon = preset.icon;
            const all = isos.every((iso3) => selected.has(iso3));
            return (
              <button
                key={key}
                type="button"
                onClick={() => add(isos)}
                className={`group flex flex-col items-center gap-1 rounded-2xl border px-2 py-3 text-center transition hover:-translate-y-0.5 ${
                  all ? "border-teal-300/40 bg-teal-300/10" : "border-white/[0.08] bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]"
                }`}
              >
                <Icon size={18} className="text-teal-300 transition group-hover:scale-110" />
                <span className="text-xs font-semibold leading-tight text-white">{preset.label}</span>
                <span className="text-[11px] text-slate-500">{isos.length} Länder</span>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Ausgewählt · {selected.size}</p>
          {selected.size > 0 && (
            <button type="button" className="text-xs font-medium text-slate-500 transition hover:text-rose-300" onClick={() => onChange(new Set())}>
              Alle entfernen
            </button>
          )}
        </div>
        {selected.size ? (
          <div className="flex max-h-56 flex-wrap gap-1.5 overflow-y-auto pr-1">
            <AnimatePresence initial={false}>
              {[...selected]
                .map((iso3) => ({ iso3, name: known.get(iso3)?.name_de ?? countryName(iso3) }))
                .sort((a, b) => a.name.localeCompare(b.name, "de"))
                .map(({ iso3, name }) => (
                  <motion.span
                    key={iso3}
                    layout
                    initial={{ opacity: 0, scale: 0.6 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.6 }}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    className="inline-flex items-center gap-1.5 rounded-full border border-cyan-300/20 bg-cyan-300/10 py-0.5 pl-2 pr-1 text-xs font-medium text-cyan-50"
                  >
                    <span className="text-base leading-none">{flag(iso3)}</span>
                    {name}
                    <button type="button" aria-label={`${name} entfernen`} className="grid h-5 w-5 place-items-center rounded-full text-cyan-200/70 hover:bg-white/10 hover:text-white" onClick={() => remove(iso3)}>
                      <X size={12} />
                    </button>
                  </motion.span>
                ))}
            </AnimatePresence>
          </div>
        ) : (
          <p className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-slate-500">Noch keine Länder ausgewählt – suchen Sie oben oder klicken Sie auf die Karte.</p>
        )}
      </div>
    </div>
  );
}
