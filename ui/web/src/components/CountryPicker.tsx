import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, CornerDownLeft, Euro, Landmark, Search, Star, X } from "lucide-react";
import type { CountryListing } from "../types";
import { allCountries, countryName, flag } from "../lib/geo";

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
  "UNECE 1958": { label: "UN parties", icon: Landmark },
  "Top markets": { label: "Top markets", icon: Star },
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
    // names that start with the query first ("Chi" -> China before Kampuchea)
    return hits.sort((a, b) => Number(!a.name.toLowerCase().startsWith(q)) - Number(!b.name.toLowerCase().startsWith(q))).slice(0, 6);
  }, [q, everyone]);

  const hint = (iso3: string) => {
    const c = known.get(iso3);
    if (!c) return { text: "no data", cls: "bg-mint-900/[0.05] text-mint-900/55" };
    return c.regime === "unece_1958" ? { text: "UN regulations", cls: "bg-mint-50 text-mint-800" } : { text: "national rules", cls: "bg-violet-50 text-violet-700" };
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

  return (
    <div className="space-y-6">
      <div className="relative">
        <label htmlFor="country-search" className="label mb-2 block">
          Search a country
        </label>
        <div className="relative">
          <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mint-900/40" />
          <input
            id="country-search"
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
            placeholder="e.g. China"
            autoComplete="off"
            className="input !pl-10 !pr-10"
          />
          {q && (
            <button type="button" aria-label="Clear search" className="absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded text-mint-900/45 hover:bg-mint-50 hover:text-mint-950" onClick={() => search("")}>
              <X size={15} />
            </button>
          )}
        </div>
        <AnimatePresence>
          {matches.length > 0 && (
            <motion.ul
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className="absolute z-20 mt-1.5 w-full overflow-hidden rounded-lg bg-white p-1 shadow-lift ring-1 ring-mint-900/10"
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
                      className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors ${i === active ? "bg-mint-50" : ""}`}
                    >
                      <span className="text-xl leading-none">{flag(c.iso3)}</span>
                      <span className="min-w-0 flex-1 truncate text-mint-950">{c.name}</span>
                      {selected.has(c.iso3) ? (
                        <span className="flex items-center gap-1 text-xs font-medium text-mint-700">
                          <Check size={13} /> selected
                        </span>
                      ) : (
                        <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${h.cls}`}>{h.text}</span>
                      )}
                      {i === active && <CornerDownLeft size={13} className="text-mint-900/40" />}
                    </button>
                  </li>
                );
              })}
            </motion.ul>
          )}
        </AnimatePresence>
      </div>

      <div>
        <p className="label mb-2">Quick pick</p>
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
                aria-pressed={all}
                className={`flex flex-col items-center gap-1 rounded-lg px-2 py-3 text-center ring-1 ring-inset transition-colors duration-300 ${
                  all ? "bg-mint-950 text-white ring-mint-950" : "bg-white text-mint-950 ring-mint-900/[0.12] hover:bg-mint-50 hover:ring-mint-500/50"
                }`}
              >
                <Icon size={17} className={all ? "text-mint-300" : "text-mint-600"} />
                <span className="text-xs font-medium leading-tight">{preset.label}</span>
                <span className={`text-[11px] ${all ? "text-mint-50/60" : "text-mint-900/50"}`}>{isos.length} countries</span>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="label">Selected · {selected.size}</p>
          {selected.size > 0 && (
            <button type="button" className="text-xs text-mint-900/55 transition-colors hover:text-rose-600" onClick={() => onChange(new Set())}>
              Clear all
            </button>
          )}
        </div>
        {selected.size ? (
          <div className="flex max-h-56 flex-wrap gap-1.5 overflow-y-auto pr-1">
            <AnimatePresence initial={false}>
              {[...selected]
                .map((iso3) => ({ iso3, name: countryName(iso3, known.get(iso3)?.name) }))
                .sort((a, b) => a.name.localeCompare(b.name, "en"))
                .map(({ iso3, name }) => (
                  <motion.span
                    key={iso3}
                    layout
                    initial={{ opacity: 0, scale: 0.7 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.7 }}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    className="inline-flex items-center gap-1.5 rounded-md bg-mint-50 py-0.5 pl-2 pr-0.5 text-xs font-medium text-mint-900 ring-1 ring-inset ring-mint-500/25"
                  >
                    <span className="text-base leading-none">{flag(iso3)}</span>
                    {name}
                    <button type="button" aria-label={`Remove ${name}`} className="grid h-5 w-5 place-items-center rounded text-mint-900/45 hover:bg-mint-100 hover:text-mint-950" onClick={() => remove(iso3)}>
                      <X size={12} />
                    </button>
                  </motion.span>
                ))}
            </AnimatePresence>
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-mint-900/15 p-4 text-sm text-mint-900/55">No countries selected yet – search above or click the map.</p>
        )}
      </div>
    </div>
  );
}
