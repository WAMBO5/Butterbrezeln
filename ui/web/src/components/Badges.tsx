import { TriangleAlert } from "lucide-react";
import type { Effort, FindingStatus, VerdictStatus } from "../types";
import { COUNTRY_DATA_NOTE, DRAFT_LABEL, DRAFT_NOTE, EFFORT, FINDING, STATUS } from "../lib/labels";

/** "Unreviewed AI draft — not for compliance use": a banner on the result page, a chip in the drawers. */
export function DraftNotice({ compact = false }: { compact?: boolean }) {
  if (compact)
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-400/10 px-2 py-0.5 text-[11px] font-semibold text-amber-200 ring-1 ring-inset ring-amber-400/25" title={`${DRAFT_NOTE} ${COUNTRY_DATA_NOTE}`}>
        <TriangleAlert size={11} /> {DRAFT_LABEL}
      </span>
    );
  return (
    <section role="note" className="flex items-start gap-3 rounded-2xl border border-amber-300/25 bg-amber-300/[0.06] px-4 py-3 text-sm">
      <TriangleAlert size={18} className="mt-0.5 shrink-0 text-amber-300" />
      <p className="text-amber-100/75">
        <b className="font-semibold text-amber-100">{DRAFT_LABEL}</b> · {DRAFT_NOTE} {COUNTRY_DATA_NOTE}
      </p>
    </section>
  );
}

export function StatusPill({ status, size = "sm" }: { status: VerdictStatus; size?: "sm" | "lg" }) {
  const s = STATUS[status];
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ring-1 ring-inset ${s.soft} ${s.text} ${s.ring} ${size === "lg" ? "px-3 py-1 text-sm" : "px-2.5 py-0.5 text-xs"}`}>
      <Icon size={size === "lg" ? 16 : 13} strokeWidth={2.5} />
      {s.label}
    </span>
  );
}

export function EffortChip({ effort }: { effort: Effort }) {
  const e = EFFORT[effort];
  const Icon = e.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${e.chip}`}>
      <Icon size={12} strokeWidth={2.5} />
      {e.label}
    </span>
  );
}

export function FindingChip({ status }: { status: FindingStatus }) {
  const f = FINDING[status];
  return <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${f.chip}`}>{f.label}</span>;
}

/** Share of each finding status as one thin bar (conflicts first). */
export function FindingBar({ counts, total }: { counts: Record<FindingStatus, number>; total: number }) {
  return (
    <span className="flex h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
      {(["konflikt", "offen", "erfuellt"] as FindingStatus[]).map((k) =>
        counts[k] ? <span key={k} style={{ width: `${(counts[k] / Math.max(total, 1)) * 100}%`, background: FINDING[k].color, boxShadow: `0 0 8px ${FINDING[k].color}` }} /> : null,
      )}
    </span>
  );
}

/** Glowing status dot. */
export function StatusDot({ status, size = 10 }: { status: VerdictStatus; size?: number }) {
  const color = STATUS[status].color;
  return <span className="inline-block shrink-0 rounded-full" style={{ width: size, height: size, background: color, boxShadow: `0 0 ${size}px ${color}` }} />;
}
