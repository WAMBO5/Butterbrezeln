import { motion } from "motion/react";
import { ChevronDown, Cpu, ShieldAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import type { RunResult } from "../types";
import { plural } from "../lib/labels";
import { FUNNEL, PIPELINE_AGENT, money, totalCost, when } from "../lib/pipeline";
import { CountUp } from "./Stats";

/** "claude-opus-5-5" -> "Opus 5.5" */
function modelName(id: string): string {
  const m = id.match(/^claude-([a-z]+)-(\d+)-(\d+)/);
  return m ? `${m[1][0].toUpperCase()}${m[1].slice(1)} ${m[2]}.${m[3]}` : id;
}

function Weak({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <details className="group rounded-lg bg-flat-white/60 ring-1 ring-mint-900/[0.06]">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-sm text-mint-900">
        {title}
        <ChevronDown size={15} className="shrink-0 text-mint-900/45 transition group-open:rotate-180" />
      </summary>
      <ul className="max-h-56 list-inside list-disc space-y-1 overflow-y-auto border-t border-mint-900/[0.06] px-3 py-2 text-xs text-mint-900/70">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </details>
  );
}

/** Where the result comes from: the pipeline run, how it narrowed the regulations, who worked on it, where it is unsure. */
export function PipelineRun({ run }: { run: RunResult }) {
  const p = run.pipeline;
  if (!p) return null;
  const stages = FUNNEL.filter((s) => p.funnel[s.key] != null);
  const max = Math.max(...stages.map((s) => p.funnel[s.key]), 1);
  const unsure = run.requirements.filter((r) => r.pipeline?.state === "uncertain").length;
  const cost = totalCost(p);
  const minutes = p.started_at && p.finished_at ? Math.max(1, Math.round((Date.parse(p.finished_at) - Date.parse(p.started_at)) / 60000)) : null;
  const pct = (v?: number) => (v == null ? "–" : `${Math.round(v * 100)}%`);

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow flex items-center gap-1.5">
            <Cpu size={14} /> Data source
          </p>
          <h3 className="mt-1 text-2xl font-normal tracking-tight">{p.fake_llm ? "A demo run of our pipeline (scripted model)" : "A real run of our requirements pipeline"}</h3>
          <p className="mt-1 break-all font-mono text-xs text-mint-900/50">{p.path}</p>
          {p.replay_of && <p className="mt-1 text-xs text-mint-900/50">Replay: matching and assembly recomputed; product analysis, scoping and quotes taken from run {p.replay_of}.</p>}
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="chip-soft">{when(p.finished_at)}{minutes ? ` · ${minutes} min` : ""}</span>
          {cost != null && <span className="chip-soft" title={p.inherited_cost_usd ? `of which ${money(p.inherited_cost_usd)} for the reused steps` : undefined}>{money(cost)} AI cost</span>}
          {p.ledger && (
            <span className={`chip ring-1 ring-inset ${p.ledger.intact ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" : "bg-rose-50 text-rose-700 ring-rose-600/20"}`}
                  title={p.ledger.intact ? `Each entry contains the hash of the previous one; verified up to ${p.ledger.head?.slice(0, 12)}…` : p.ledger.problems.join("\n")}>
              {p.ledger.intact ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}
              {p.ledger.intact ? `Log unchanged (${p.ledger.records} entries verified)` : "Log was altered"}
            </span>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div>
          <p className="mb-3 text-sm font-semibold text-mint-950">How the pipeline narrows down</p>
          <ol className="space-y-2">
            {stages.map((s, i) => {
              const value = p.funnel[s.key];
              const width = Math.max(4, (Math.log10(value + 1) / Math.log10(max + 1)) * 100); // log scale: 4 … 2,000+
              return (
                <li key={s.key} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] items-center gap-3 text-xs">
                  <span className="truncate text-mint-900/65">{s.label}</span>
                  <span className="relative h-7 overflow-hidden rounded-md bg-mint-900/[0.04]">
                    <motion.span
                      initial={{ width: 0 }}
                      whileInView={{ width: `${width}%` }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.08, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                      className="absolute inset-y-0 left-0 rounded-md bg-mint-300/70"
                    />
                    <CountUp value={value} className="absolute inset-y-0 left-2.5 flex items-center text-sm font-semibold text-mint-950" />
                  </span>
                </li>
              );
            })}
          </ol>
          <p className="mt-3 text-xs text-mint-900/55">
            {plural(p.excluded.length, "regulation", "regulations")} excluded, each with a reason – e.g. {p.excluded[0] ? `${p.excluded[0].regulation}: “${p.excluded[0].reason}”` : "–"}
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-semibold text-mint-950">Who did the work</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(p.models).map(([agent, model]) => (
                <span key={agent} className="rounded-md bg-mint-900/[0.05] px-2 py-1 text-[11px] text-mint-900">
                  {PIPELINE_AGENT[agent] ?? agent} <span className="text-mint-900/50">· {modelName(model)}</span>
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-mint-950">
              <TriangleAlert size={15} className="text-amber-600" /> Where the pipeline is unsure
            </p>
            <div className="space-y-2">
              {unsure > 0 && <p className="text-sm text-mint-900/85">{unsure} of {run.requirements.length} requirements may apply – that depends on missing details.</p>}
              <Weak title={`${plural(p.unknowns.length, "point", "points")} your description leaves open`} items={p.unknowns} />
              <Weak title={`${plural(p.open_issues.length, "cross-check objection", "cross-check objections")} not resolved`} items={p.open_issues} />
              <Weak title={`${plural(p.give_ups.length, "step", "steps")} where the pipeline gave up`} items={p.give_ups} />
              {p.review_issues > 0 && <p className="text-xs text-mint-900/55">The final audit raised {plural(p.review_issues, "issue", "issues")} (e.g. duplicates); the pipeline fixed them afterwards.</p>}
              {p.benchmark?.levels.length ? (
                <p className="text-xs text-mint-900/55">
                  Measured against this practice case's reference solution (F2): {p.benchmark.levels.map((l) => `${l.level} ${pct(l.f2)}`).join(", ")}.
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {p.label && <p className="mt-5 text-xs text-mint-900/55">Pipeline label: “{p.label}”</p>}
    </div>
  );
}
