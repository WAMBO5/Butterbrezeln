import { useMemo, useState } from "react";
import { BookOpen, ChevronDown, ExternalLink, Search } from "lucide-react";
import type { FindingStatus, LineageTarget, Requirement, RunResult } from "../types";
import { FINDING, UNSURE, regulationName } from "../lib/labels";
import { FindingBar, FindingChip } from "./Badges";

const ORDER: FindingStatus[] = ["konflikt", "offen", "erfuellt"];

/** Requirements grouped by regulation; every row links to its page in the original PDF. */
export function RequirementsView({ run, onLineage }: { run: RunResult; onLineage: (t: LineageTarget) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const findings = useMemo(() => new Map(run.findings.map((f) => [f.requirement_id, f])), [run.findings]);

  const groups = useMemo(() => {
    const map = new Map<string, Requirement[]>();
    run.requirements.forEach((r) => {
      const key = r.source.regulation ?? "?";
      map.set(key, [...(map.get(key) ?? []), r]);
    });
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [run.requirements]);

  const totals: Record<FindingStatus, number> = { erfuellt: 0, offen: 0, konflikt: 0 };
  run.findings.forEach((f) => (totals[f.status] += 1));
  const unsure = run.requirements.filter((r) => r.pipeline?.state === "uncertain").length;
  const q = query.trim().toLowerCase();

  return (
    <div className="space-y-4">
      <div className="glass flex flex-wrap items-center justify-between gap-4 p-6">
        <div>
          <h3 className="font-display text-xl font-bold">
            {run.requirements.length} Anforderungen aus {groups.length} Vorschriften
          </h3>
          <p className="text-sm text-slate-400">Jede Anforderung ist mit der Originalseite der Vorschrift verknüpft – ein Klick öffnet das PDF.</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {ORDER.map((k) => (
            <span key={k} className={`rounded-full px-3 py-1 font-semibold ring-1 ring-inset ${FINDING[k].chip}`}>
              {totals[k]} {FINDING[k].label}
            </span>
          ))}
          {unsure > 0 && (
            <span className={`rounded-full px-3 py-1 font-semibold ring-1 ring-inset ${UNSURE.chip}`} title={UNSURE.desc}>
              davon {unsure} {unsure === 1 ? "gilt" : "gelten"} vielleicht
            </span>
          )}
        </div>
        <div className="relative w-full">
          <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="In den Anforderungen suchen, z. B. „marking“ oder ein Bauteil" className="input !pl-10" />
        </div>
      </div>

      {groups.map(([regulation, items]) => {
        const shown = q
          ? items.filter((r) => [r.text, r.id, ...(r.pipeline?.parts ?? [])].some((t) => t.toLowerCase().includes(q)))
          : items;
        if (q && !shown.length) return null;
        const first = items[0].source;
        const expanded = open === regulation || !!q;
        const pdf = first.href?.split("#")[0];
        const counts: Record<FindingStatus, number> = { erfuellt: 0, offen: 0, konflikt: 0 };
        items.forEach((r) => {
          const f = findings.get(r.id);
          if (f) counts[f.status] += 1;
        });
        return (
          <div key={regulation} className="glass overflow-hidden">
            <button type="button" className="flex w-full items-center gap-4 px-5 py-4 text-left transition hover:bg-white/[0.03]" onClick={() => setOpen(expanded && !q ? null : regulation)}>
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-violet-400/10 text-violet-300 ring-1 ring-inset ring-violet-300/20">
                <BookOpen size={20} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold text-white">{regulationName(regulation, first.title)}</span>
                <span className="block text-xs text-slate-500">
                  {regulation} · Version {first.version} · {shown.length} {shown.length === 1 ? "Anforderung" : "Anforderungen"}
                </span>
                <span className="mt-2 block max-w-xs">
                  <FindingBar counts={counts} total={items.length} />
                </span>
              </span>
              {counts.konflikt > 0 && <span className="hidden rounded-full bg-rose-400/10 px-2.5 py-0.5 text-xs font-semibold text-rose-300 ring-1 ring-inset ring-rose-400/25 sm:inline">{counts.konflikt} Widerspruch</span>}
              {pdf && (
                <a href={pdf} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="hidden items-center gap-1 text-xs font-medium text-cyan-300 hover:underline sm:flex">
                  Original <ExternalLink size={12} />
                </a>
              )}
              <ChevronDown size={18} className={`shrink-0 text-slate-500 transition ${expanded ? "rotate-180" : ""}`} />
            </button>
            {expanded && (
              <ul className="divide-y divide-white/[0.05] border-t border-white/[0.06]">
                {shown.map((r) => {
                  const f = findings.get(r.id);
                  const p = r.pipeline;
                  return (
                    <li key={r.id} className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-start sm:gap-4">
                      <div className="flex w-32 shrink-0 flex-wrap gap-1.5">
                        {f && <FindingChip status={f.status} />}
                        {p?.state === "uncertain" && (
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${UNSURE.chip}`} title={`${UNSURE.desc}\n\n${p.reason}`}>
                            {UNSURE.label}
                          </span>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-slate-200">{r.text}</p>
                        {f && f.status !== "offen" && <p className="mt-1 text-xs text-slate-500">{f.explanation}</p>}
                        {p?.state === "uncertain" && p.reason && <p className="mt-1 text-xs text-amber-200/70">Warum unsicher: {p.reason}</p>}
                        {p?.test_case && <p className="mt-1 text-xs text-slate-500">Nachweis: {p.test_case}</p>}
                        {p && p.parts.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {p.parts.map((part) => (
                              <span key={part} className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[11px] text-slate-400">{part}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-3 text-xs">
                        {r.source.href && (
                          <a href={r.source.href} target="_blank" rel="noreferrer" className="flex items-center gap-1 font-medium text-cyan-300 hover:underline">
                            Seite {r.source.page} <ExternalLink size={11} />
                          </a>
                        )}
                        <button type="button" className="font-medium text-slate-400 hover:text-white" onClick={() => onLineage({ kind: "requirement", id: r.id })}>
                          Herkunft
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
