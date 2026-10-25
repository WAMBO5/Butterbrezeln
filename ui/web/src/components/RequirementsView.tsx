import { useMemo, useState } from "react";
import { BookOpen, ChevronDown, ExternalLink, Search } from "lucide-react";
import type { FindingStatus, LineageTarget, Requirement, RunResult } from "../types";
import { FINDING, UNSURE, regulationName } from "../lib/labels";
import { FindingBar, FindingChip } from "./Badges";

const ORDER: FindingStatus[] = ["conflict", "open", "met"];

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

  const totals: Record<FindingStatus, number> = { met: 0, open: 0, conflict: 0 };
  run.findings.forEach((f) => (totals[f.status] += 1));
  const unsure = run.requirements.filter((r) => r.pipeline?.state === "uncertain").length;
  const q = query.trim().toLowerCase();

  return (
    <div className="space-y-3">
      <div className="card space-y-4 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-2xl font-normal tracking-tight">
              {run.requirements.length} requirements from {groups.length} regulations
            </h3>
            <p className="mt-1 text-sm text-mint-900/65">Each requirement links to the original page of its regulation – one click opens the PDF.</p>
          </div>
          <div className="flex flex-wrap gap-1.5 text-xs">
            {ORDER.map((k) => (
              <span key={k} className={`rounded-md px-2.5 py-1 font-medium ring-1 ring-inset ${FINDING[k].chip}`}>
                {totals[k]} {FINDING[k].label}
              </span>
            ))}
            {unsure > 0 && (
              <span className={`rounded-md px-2.5 py-1 font-medium ring-1 ring-inset ${UNSURE.chip}`} title={UNSURE.desc}>
                {unsure} may apply
              </span>
            )}
          </div>
        </div>
        <div className="relative">
          <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mint-900/40" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search requirements, e.g. “marking” or a part" aria-label="Search requirements" className="input !pl-10" />
        </div>
      </div>

      {groups.map(([regulation, items]) => {
        const shown = q ? items.filter((r) => [r.text, r.id, ...(r.pipeline?.parts ?? [])].some((t) => t.toLowerCase().includes(q))) : items;
        if (q && !shown.length) return null;
        const first = items[0].source;
        const expanded = open === regulation || !!q;
        const pdf = first.href?.split("#")[0];
        const counts: Record<FindingStatus, number> = { met: 0, open: 0, conflict: 0 };
        items.forEach((r) => {
          const f = findings.get(r.id);
          if (f) counts[f.status] += 1;
        });
        return (
          <div key={regulation} className="card overflow-hidden">
            <button type="button" aria-expanded={expanded} className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-mint-50/50" onClick={() => setOpen(expanded && !q ? null : regulation)}>
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-mint-50 text-mint-700">
                <BookOpen size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-mint-950">{regulationName(regulation, first.title)}</span>
                <span className="block text-xs text-mint-900/55">
                  {regulation} · version {first.version} · {shown.length} {shown.length === 1 ? "requirement" : "requirements"}
                </span>
                <span className="mt-2 block max-w-xs">
                  <FindingBar counts={counts} total={items.length} />
                </span>
              </span>
              {counts.conflict > 0 && (
                <span className="hidden rounded-md bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/20 sm:inline">
                  {counts.conflict} {counts.conflict === 1 ? "conflict" : "conflicts"}
                </span>
              )}
              {pdf && (
                <a href={pdf} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="hidden items-center gap-1 text-xs font-medium text-mint-700 hover:underline sm:flex">
                  Original <ExternalLink size={12} />
                </a>
              )}
              <ChevronDown size={18} className={`shrink-0 text-mint-900/40 transition ${expanded ? "rotate-180" : ""}`} />
            </button>
            {expanded && (
              <ul className="divide-y divide-mint-900/[0.06] border-t border-mint-900/[0.06]">
                {shown.map((r) => {
                  const f = findings.get(r.id);
                  const p = r.pipeline;
                  return (
                    <li key={r.id} className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-start sm:gap-4">
                      <div className="flex w-32 shrink-0 flex-wrap gap-1.5">
                        {f && <FindingChip status={f.status} />}
                        {p?.state === "uncertain" && (
                          <span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${UNSURE.chip}`} title={`${UNSURE.desc}\n\n${p.reason}`}>
                            {UNSURE.label}
                          </span>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-mint-950">{r.text}</p>
                        {f && f.status !== "open" && <p className="mt-1 text-xs text-mint-900/60">{f.explanation}</p>}
                        {p?.state === "uncertain" && p.reason && <p className="mt-1 text-xs text-amber-700">Why unsure: {p.reason}</p>}
                        {p?.test_case && <p className="mt-1 text-xs text-mint-900/60">Evidence: {p.test_case}</p>}
                        {p && p.parts.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {p.parts.map((part) => (
                              <span key={part} className="rounded bg-mint-900/[0.05] px-1.5 py-0.5 text-[11px] text-mint-900/70">
                                {part}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-3 text-xs">
                        {r.source.href && (
                          <a href={r.source.href} target="_blank" rel="noreferrer" className="flex items-center gap-1 font-medium text-mint-700 hover:underline">
                            Page {r.source.page} <ExternalLink size={11} />
                          </a>
                        )}
                        <button type="button" className="text-mint-900/60 hover:text-mint-950" onClick={() => onLineage({ kind: "requirement", id: r.id })}>
                          Source chain
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
