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
    <details className="group rounded-xl bg-white/[0.03] ring-1 ring-white/[0.06]">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-sm text-slate-300">
        {title}
        <ChevronDown size={15} className="shrink-0 text-slate-500 transition group-open:rotate-180" />
      </summary>
      <ul className="max-h-56 list-inside list-disc space-y-1 overflow-y-auto border-t border-white/[0.06] px-3 py-2 text-xs text-slate-400">
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
  const pct = (v?: number) => (v == null ? "–" : `${Math.round(v * 100)} %`);

  return (
    <div className="glass relative overflow-hidden p-6">
      <div className="pointer-events-none absolute -left-20 -top-24 h-64 w-64 rounded-full bg-teal-400/15 blur-3xl" aria-hidden />
      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow flex items-center gap-1.5">
            <Cpu size={14} /> Datenquelle
          </p>
          <h3 className="mt-1 text-2xl font-bold tracking-tight">Ein echter Lauf unserer Requirements-Pipeline</h3>
          <p className="mt-1 break-all font-mono text-xs text-slate-500">{p.path}</p>
          {p.replay_of && <p className="mt-1 text-xs text-slate-500">Replay: Abgleich und Zusammenstellung neu gerechnet; Produktanalyse, Eingrenzung und Zitate aus Lauf {p.replay_of}.</p>}
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="chip border border-white/10 bg-white/[0.04] text-slate-300">{when(p.finished_at)}{minutes ? ` · ${minutes} min` : ""}</span>
          {cost != null && <span className="chip border border-white/10 bg-white/[0.04] text-slate-300" title={p.inherited_cost_usd ? `davon ${money(p.inherited_cost_usd)} für die übernommenen Schritte` : undefined}>{money(cost)} KI-Kosten</span>}
          {p.ledger && (
            <span className={`chip ring-1 ring-inset ${p.ledger.intact ? "bg-emerald-400/10 text-emerald-300 ring-emerald-400/20" : "bg-rose-400/10 text-rose-300 ring-rose-400/25"}`}
                  title={p.ledger.intact ? `Jeder Eintrag enthält den Hash des vorigen; nachgerechnet bis ${p.ledger.head?.slice(0, 12)}…` : p.ledger.problems.join("\n")}>
              {p.ledger.intact ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}
              {p.ledger.intact ? `Protokoll unverändert (${p.ledger.records} Einträge nachgerechnet)` : "Protokoll verändert"}
            </span>
          )}
        </div>
      </div>

      <div className="relative mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div>
          <p className="mb-3 text-sm font-semibold text-white">So grenzt die Pipeline ein</p>
          <ol className="space-y-2">
            {stages.map((s, i) => {
              const value = p.funnel[s.key];
              const width = Math.max(4, (Math.log10(value + 1) / Math.log10(max + 1)) * 100); // log scale: 4 … 2,000+
              return (
                <li key={s.key} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] items-center gap-3 text-xs">
                  <span className="truncate text-slate-400">{s.label}</span>
                  <span className="relative h-7 overflow-hidden rounded-lg bg-white/[0.03]">
                    <motion.span
                      initial={{ width: 0 }}
                      whileInView={{ width: `${width}%` }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.08, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                      className="absolute inset-y-0 left-0 rounded-lg bg-gradient-to-r from-teal-400/50 via-cyan-400/40 to-violet-400/40"
                    />
                    <CountUp value={value} className="absolute inset-y-0 left-2.5 flex items-center font-display text-sm font-bold text-white" />
                  </span>
                </li>
              );
            })}
          </ol>
          <p className="mt-3 text-xs text-slate-500">
            {plural(p.excluded.length, "Vorschrift", "Vorschriften")} ausgeschlossen, jede mit Begründung – z. B. {p.excluded[0] ? `${p.excluded[0].regulation}: „${p.excluded[0].reason}“` : "–"}
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm font-semibold text-white">Wer gearbeitet hat</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(p.models).map(([agent, model]) => (
                <span key={agent} className="rounded-full bg-white/[0.05] px-2.5 py-1 text-[11px] text-slate-300 ring-1 ring-white/[0.08]">
                  {PIPELINE_AGENT[agent] ?? agent} <span className="text-slate-500">· {modelName(model)}</span>
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-white">
              <TriangleAlert size={15} className="text-amber-300" /> Wo die Pipeline unsicher ist
            </p>
            <div className="space-y-2">
              {unsure > 0 && <p className="text-sm text-slate-300">{unsure} von {run.requirements.length} Anforderungen gelten vielleicht – das hängt von fehlenden Angaben ab.</p>}
              <Weak title={`${plural(p.unknowns.length, "Punkt", "Punkte")}, die Ihre Beschreibung offen lässt`} items={p.unknowns} />
              <Weak title={`${plural(p.open_issues.length, "Einwand", "Einwände")} der Gegenprüfung, nicht ausgeräumt`} items={p.open_issues} />
              <Weak title={`${plural(p.give_ups.length, "Schritt", "Schritte")}, bei denen die Pipeline aufgegeben hat`} items={p.give_ups} />
              {p.review_issues > 0 && <p className="text-xs text-slate-500">Die Schlussprüfung hat {plural(p.review_issues, "Hinweis", "Hinweise")} gegeben (z. B. Dubletten); die Pipeline hat danach nachgebessert.</p>}
              {p.score?.page_level && (
                <p className="text-xs text-slate-500">
                  Gemessen an der Musterlösung dieses Übungsfalls: Vorschriften richtig {pct(p.score.regulation_level?.f1)}, Seiten richtig {pct(p.score.page_level.f1)} (F1).
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {p.label && <p className="relative mt-5 text-xs text-slate-500">Kennzeichnung der Pipeline: „{p.label}“</p>}
    </div>
  );
}
