import { useEffect, useRef, useState } from "react";
import { Check, Circle, FlaskConical, FolderOpen, Loader2, Play, Square, X } from "lucide-react";
import { api } from "../api";
import { money, when } from "../lib/pipeline";
import type { ExistingAnalysis, PipelineJob } from "../types";

interface Props {
  spec: File;
  image: File | null;
  /** Real mode (header toggle): a real, paid run with the .env API key; otherwise the free scripted demo model. */
  real: boolean;
  /** The approach whose pipeline runs, e.g. "general-approach". */
  approach?: string;
  /** A real run stops when it has spent this much. */
  maxCostUsd?: number;
  /** There already is an analysis for this spec: this starts a fresh one. */
  again?: boolean;
  /** That analysis, offered instead of a paid run (real mode asks before reusing it). */
  existing?: ExistingAnalysis | null;
  onUseExisting?: () => void;
  /** The run has written its submission: the caller opens the result of run `jobId`. */
  onDone: (jobId: string) => void;
  onClose: () => void;
}

const POLL_MS = 2000;

function elapsed(since: string, now: number) {
  const s = Math.max(0, Math.round((now - Date.parse(since)) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Starts a certivity pipeline run on the spec and follows its steps until the submission is written. */
export function PipelineLauncher({ spec, image, real, approach, maxCostUsd, again = false, existing, onUseExisting, onDone, onClose }: Props) {
  const [job, setJob] = useState<PipelineJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const finished = useRef(false);

  const running = job?.status === "running";
  useEffect(() => {
    if (!job || !running) return;
    const t = setInterval(() => {
      setNow(Date.now());
      api.pipelineJob(job.id).then(setJob).catch((e) => setError(String(e)));
    }, POLL_MS);
    return () => clearInterval(t);
  }, [job?.id, running]);

  useEffect(() => {
    if (job?.status === "done" && !finished.current) {
      finished.current = true;
      onDone(job.id);
    }
  }, [job?.status, job?.id, onDone]);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      setJob(await api.startPipeline(spec, image, !real));
      setNow(Date.now());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!job) return;
    setBusy(true);
    try {
      setJob(await api.cancelPipelineJob(job.id));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-mint-950/40 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="pipeline-title">
      <div className="card w-full max-w-lg p-6">
        <div className="flex items-start justify-between gap-4">
          <h3 id="pipeline-title" className="text-xl font-semibold text-mint-950">
            {job ? (job.fake_llm ? "Pipeline run · demo model" : "Pipeline run") : existing ? "This product was analysed before" : again ? "Run the pipeline again" : "No analysis for this product yet"}
          </h3>
          {!running && (
            <button type="button" className="btn-ghost btn-sm -mr-2 -mt-1" onClick={onClose} aria-label="Close">
              <X size={16} />
            </button>
          )}
        </div>

        {!job && (
          <>
            {existing && (
              <p className="mt-3 rounded-lg bg-mint-900/[0.04] p-3 text-sm text-mint-900/80 ring-1 ring-inset ring-mint-900/[0.06]">
                {existing.approach ?? "The pipeline"} analysed this description on {when(existing.finished_at)}
                {existing.fake_llm ? " with the scripted demo model (not a real analysis)" : existing.cost_usd != null ? ` with the AI model for ${money(existing.cost_usd)}` : ""}. Opening it
                makes no model calls; a fresh run below does.
              </p>
            )}
            <p className="mt-3 text-sm leading-relaxed text-mint-900/75">
              {again ? "A fresh run of the pipeline on this description" : "The agents have not analysed this product description yet. The pipeline"}
              {approach ? ` (${approach})` : ""} breaks the product down, narrows the UN Regulations, quotes the obligations and matches them to the parts. When it has finished, the
              result opens here with your markets.
            </p>
            {real ? (
              <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 ring-1 ring-inset ring-amber-600/20">
                <b>Real run</b> with the AI model and the API key from <code>.env</code>: paid, about $5–7 and 15 minutes for a case like the rear lamp
                {maxCostUsd ? `; it stops at $${maxCostUsd.toFixed(0)} and keeps what it has decided so far` : ""}.
              </p>
            ) : (
              <p className="mt-3 rounded-lg bg-mint-900/[0.04] p-3 text-sm text-mint-900/80 ring-1 ring-inset ring-mint-900/[0.06]">
                <b>Demo model:</b> free and done in about a minute, but a scripted stand-in writes the requirements – the result is labelled as not a real analysis.
                Switch the header to <b>Real</b> for an analysis with the AI model.
              </p>
            )}
          </>
        )}

        {job && (
          <>
            <ol className="mt-4 space-y-2">
              {job.steps.map((s) => (
                <li key={s.step} className={`flex items-center gap-2.5 text-sm ${s.state === "pending" ? "text-mint-900/40" : "text-mint-950"}`}>
                  {s.state === "done" ? (
                    <Check size={16} className="shrink-0 text-mint-600" />
                  ) : s.state === "running" && running ? (
                    <Loader2 size={16} className="shrink-0 animate-spin text-mint-600" />
                  ) : (
                    <Circle size={16} className="shrink-0 text-mint-900/25" />
                  )}
                  {s.label}
                </li>
              ))}
            </ol>
            <p className="mt-4 text-xs text-mint-900/60">
              {job.id} · {job.calls} model calls{job.cost_usd ? ` · $${job.cost_usd.toFixed(2)}` : ""}
              {running && ` · ${elapsed(job.started_at, now)}`}
              {job.fake_llm && " · demo model"}
            </p>
            {job.status === "done" && <p className="mt-3 text-sm font-medium text-mint-700">Finished – opening the result …</p>}
            {(job.status === "failed" || job.status === "cancelled") && (
              <div className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
                {job.status === "cancelled" ? "The run was cancelled." : job.error}
                {job.log_tail.length > 0 && <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-rose-800/80">{job.log_tail.join("\n")}</pre>}
              </div>
            )}
          </>
        )}

        {error && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">{error}</p>}

        <div className="mt-6 flex justify-end gap-2">
          {running ? (
            <button type="button" className="btn-outline" disabled={busy} onClick={cancel}>
              <Square size={14} /> Cancel run
            </button>
          ) : (
            job?.status !== "done" && (
              <>
                <button type="button" className="btn-ghost" onClick={onClose}>
                  Close
                </button>
                {existing && onUseExisting && (
                  <button type="button" className="btn-outline" disabled={busy} onClick={onUseExisting}>
                    <FolderOpen size={16} /> Open that analysis (free)
                  </button>
                )}
                <button type="button" className="btn-primary px-6" disabled={busy} onClick={start}>
                  {real ? <Play size={16} /> : <FlaskConical size={16} />} {busy ? "Starting …" : real ? "Start real run (paid)" : "Start demo run (free)"}
                </button>
              </>
            )
          )}
        </div>
      </div>
    </div>
  );
}
