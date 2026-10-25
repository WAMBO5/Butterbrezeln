import { ArrowRight, Download, FlaskConical, Globe2, RotateCcw, Scale, TriangleAlert } from "lucide-react";
import { api } from "../api";
import type { Benchmark, CountryVerdict, RunResult } from "../types";
import { flag } from "../lib/geo";
import { STATUS, plural } from "../lib/labels";
import { when } from "../lib/pipeline";

const LEVEL: Record<Benchmark["levels"][number]["level"], { label: string; note: string }> = {
  regulation: { label: "Regulations", note: "the right UN Regulations" },
  page: { label: "Pages", note: "the right pages cited" },
  requirement: { label: "Requirements", note: "paired by paragraph – an upper bound on the platform's level" },
};

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** What the challenge scores (submission.json, from the UN Regulations only) next to what we add (the market layer). */
export function BenchmarkStrip({ run, verdicts, onCountry, onRunAgain }: { run: RunResult; verdicts: CountryVerdict[]; onCountry: (iso3: string) => void; onRunAgain: () => void }) {
  const p = run.pipeline;
  const b = p?.benchmark;
  const national = verdicts.filter((v) => v.regime === "national");
  const unece = verdicts.filter((v) => v.regime === "unece_1958");
  const noData = verdicts.filter((v) => v.regime === "not_covered");

  return (
    <section className="grid gap-4 lg:grid-cols-2">
      {p && b && (
        <div className="card flex flex-col p-6">
          <p className="eyebrow flex items-center gap-1.5">
            <Scale size={14} /> Challenge benchmark · UN Regulations only
          </p>
          <h3 className="mt-1 text-2xl font-normal tracking-tight">{plural(b.requirements, "requirement", "requirements")} in submission.json</h3>
          <p className="mt-1 text-sm text-mint-900/65">
            Built only from the challenge data in <code className="text-xs">industrial-ai-hackathon/</code>: the UN Regulations, this spec and its drawing. The market layer next
            to it is ours and not part of the submission or its score.
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {p.fake_llm && (
              <span className="chip bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/25">
                <FlaskConical size={13} /> Demo model – not a real analysis, not a benchmark result
              </span>
            )}
            {p.partial && (
              <span className="chip bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/25" title="Undecided obligations were kept as uncertain requirements.">
                <TriangleAlert size={13} /> Stopped by the budget guard
              </span>
            )}
            <span className={`chip ring-1 ring-inset ${b.valid ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" : "bg-rose-50 text-rose-700 ring-rose-600/20"}`} title={b.problems.join("\n")}>
              {b.valid ? "validate.py passes" : `validate.py: ${plural(b.problems.length, "problem", "problems")}`}
            </span>
            <span className="chip-soft" title={run.pipeline_fresh ? "This pipeline run was started for this check." : "A finished run of this spec, reused: no new model calls."}>
              {run.pipeline_fresh ? "Started for this check" : `Stored run of ${when(p.finished_at)}`}
            </span>
            <span className="chip-soft">{p.approach ?? "demo"} · {p.run_id}</span>
          </div>

          {b.levels.length > 0 ? (
            <>
              <div className="mt-4 grid grid-cols-3 gap-2">
                {b.levels.map((l) => (
                  <div key={l.level} className="well p-3" title={`${l.submitted} submitted / ${l.expected} expected / ${l.matched} matched – ${LEVEL[l.level].note}`}>
                    <p className="text-[11px] font-medium uppercase tracking-wide text-mint-900/55">{LEVEL[l.level].label}</p>
                    <p className="mt-1 text-2xl leading-none text-mint-950">{pct(l.f2)}</p>
                    <p className="mt-1 text-[11px] text-mint-900/55">
                      F2 · P {pct(l.precision)} · R {pct(l.recall)}
                    </p>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-xs text-mint-900/55">
                Against the organisers' reference for {b.case_id}. The platform ranks by requirement-level F2, judged by meaning; the paragraph pairing here is an upper bound on it.
              </p>
            </>
          ) : (
            <p className="mt-4 text-sm text-mint-900/65">No reference solution for this spec (e.g. the held-out case): the challenge platform scores the uploaded submission.json.</p>
          )}

          <div className="mt-auto flex flex-wrap gap-2 pt-5">
            <a className="btn-outline btn-sm" href={api.submissionUrl(run.run_id)} download>
              <Download size={14} /> submission.json
            </a>
            <button type="button" className="btn-ghost btn-sm" onClick={onRunAgain}>
              <RotateCcw size={14} /> Run the pipeline again
            </button>
          </div>
        </div>
      )}

      <div className={`card flex flex-col p-6 ${p && b ? "" : "lg:col-span-2"}`}>
        <p className="eyebrow flex items-center gap-1.5">
          <Globe2 size={14} /> Certivity market layer · our own research
        </p>
        <h3 className="mt-1 text-2xl font-normal tracking-tight">What it takes to ship to {plural(verdicts.length, "market", "markets")}</h3>
        <p className="mt-1 text-sm text-mint-900/65">
          Countries that apply the UN Regulations (1958 Agreement) take the requirements as they are. For countries with their own rules, our researched profiles list what
          changes – certification, marking, tests – each with its source. Research draft, not legal advice; unverified sources are marked.
        </p>
        <ul className="mt-4 space-y-2 text-sm">
          {national.map((v) => (
            <li key={v.iso3}>
              <button type="button" onClick={() => onCountry(v.iso3)} className="group flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-mint-900/[0.04]">
                <span className="text-2xl leading-none">{flag(v.iso3)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-mint-950">How to ship to {v.name}</span>
                  <span className="block text-xs text-mint-900/60">
                    {STATUS[v.status].label} · {plural(v.suggestions.length, "step", "steps")}
                  </span>
                </span>
                <ArrowRight size={16} className="text-mint-700 transition-transform group-hover:translate-x-0.5" />
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-auto pt-4 text-xs text-mint-900/55">
          {unece.length > 0 && `${plural(unece.length, "market applies", "markets apply")} the UN Regulations directly. `}
          {noData.length > 0 && `${plural(noData.length, "market has", "markets have")} no data yet. `}
          Not part of the benchmark score.
        </p>
      </div>
    </section>
  );
}
