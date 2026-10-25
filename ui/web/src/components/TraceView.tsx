import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import type { RunResult, TraceEvent } from "../types";
import { agentOf } from "../lib/agents";
import { countryName } from "../lib/geo";
import { agentLabel } from "../lib/labels";
import { AgentAvatar } from "./Agent";
import { SourceList } from "./SourceLink";

const STATUS_DOT: Record<TraceEvent["status"], string> = {
  running: "bg-sky-500 animate-pulse",
  ok: "bg-emerald-500",
  fallback: "bg-amber-500",
  error: "bg-rose-500",
};

function duration(e: TraceEvent): string {
  if (!e.ts_end) return "running";
  const ms = new Date(e.ts_end).getTime() - new Date(e.ts_start).getTime();
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

interface Props {
  run: RunResult;
  trace: TraceEvent[];
  focusId?: string | null;
}

const select = "rounded-md bg-white px-3 py-2 text-sm text-mint-950 outline-none ring-1 ring-inset ring-mint-900/15 focus:ring-2 focus:ring-mint-400";

/** Every agent step as a tree: who did what, with which model, from which sources. */
export function TraceView({ run, trace, focusId }: Props) {
  const [selected, setSelected] = useState<string | null>(focusId ?? null);
  const [agent, setAgent] = useState("");
  const [country, setCountry] = useState("");
  useEffect(() => {
    if (focusId) setSelected(focusId);
  }, [focusId]);

  const children = useMemo(() => {
    const map = new Map<string | null, TraceEvent[]>();
    trace.forEach((e) => {
      const key = e.parent_id ?? null;
      map.set(key, [...(map.get(key) ?? []), e]);
    });
    return map;
  }, [trace]);
  const agents = [...new Set(trace.map((e) => e.agent))];
  const countries = [...new Set(trace.map((e) => e.tags.country).filter(Boolean))];
  const filtering = !!agent || !!country;
  const matches = (e: TraceEvent) => (!agent || e.agent === agent) && (!country || e.tags.country === country);
  const current = trace.find((e) => e.id === selected) ?? null;

  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ run, trace }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `trace-${run.run_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const row = (e: TraceEvent, depth: number) => (
    <button
      type="button"
      key={e.id}
      onClick={() => setSelected(e.id)}
      className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-mint-50 ${selected === e.id ? "bg-mint-50 ring-1 ring-inset ring-mint-500/40" : ""}`}
      style={{ paddingLeft: 8 + depth * 18 }}
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[e.status]}`} />
      <AgentAvatar kind={agentOf(e.agent)} size={20} />
      <span className="w-32 shrink-0 truncate text-xs text-mint-900/55">{agentLabel(e.agent)}</span>
      <span className="flex-1 truncate text-mint-950">{e.action}</span>
      {e.model && <span className="rounded bg-violet-50 px-1.5 text-[10px] font-semibold text-violet-700">LLM</span>}
      <span className="w-14 shrink-0 text-right font-mono text-[11px] text-mint-900/50">{duration(e)}</span>
    </button>
  );

  const tree = (parent: string | null, depth: number): JSX.Element[] => (children.get(parent) ?? []).flatMap((e) => [row(e, depth), ...tree(e.id, depth + 1)]);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div className="card p-3">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <select className={select} value={agent} onChange={(e) => setAgent(e.target.value)}>
            <option value="">All agents</option>
            {agents.map((a) => (
              <option key={a} value={a}>
                {agentLabel(a)}
              </option>
            ))}
          </select>
          <select className={select} value={country} onChange={(e) => setCountry(e.target.value)}>
            <option value="">All countries</option>
            {countries.map((c) => (
              <option key={c} value={c}>
                {countryName(c, run.verdicts[c]?.name)}
              </option>
            ))}
          </select>
          <span className="text-xs text-mint-900/55">{trace.length} steps</span>
          <button type="button" className="btn-ghost btn-sm ml-auto" onClick={exportJson}>
            <Download size={14} /> Trace as JSON
          </button>
        </div>
        <div className="max-h-[65vh] space-y-0.5 overflow-y-auto">{filtering ? trace.filter(matches).map((e) => row(e, 0)) : tree(null, 0)}</div>
        <div className="mt-3 flex flex-wrap gap-3 border-t border-mint-900/[0.06] pt-2 text-[11px] text-mint-900/55">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> ok</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Rules instead of LLM</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500" /> Error</span>
        </div>
      </div>

      <div className="card p-5">
        {current ? (
          <dl className="space-y-3 text-sm">
            <div className="flex items-center gap-3">
              <AgentAvatar kind={agentOf(current.agent)} size={40} />
              <div>
                <dt className="text-xs text-mint-900/55">{agentLabel(current.agent)}</dt>
                <dd className="font-semibold text-mint-950">{current.action}</dd>
              </div>
            </div>
            {current.inputs_summary && (
              <div>
                <dt className="text-xs text-mint-900/55">Input</dt>
                <dd className="whitespace-pre-line text-mint-900/85">{current.inputs_summary}</dd>
              </div>
            )}
            {current.outputs_summary && (
              <div>
                <dt className="text-xs text-mint-900/55">Output</dt>
                <dd className="whitespace-pre-line text-mint-900/85">{current.outputs_summary}</dd>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 text-xs text-mint-900/85">
              <div>
                <dt className="text-mint-900/55">Status</dt>
                <dd>{current.status}{current.tags.fallback_reason ? ` – ${current.tags.fallback_reason}` : ""}</dd>
              </div>
              <div>
                <dt className="text-mint-900/55">Duration</dt>
                <dd>{duration(current)}</dd>
              </div>
              <div>
                <dt className="text-mint-900/55">Started</dt>
                <dd className="font-mono">{current.ts_start}</dd>
              </div>
              <div>
                <dt className="text-mint-900/55">Model</dt>
                <dd>{current.model ?? "no LLM (deterministic)"}</dd>
              </div>
              {current.prompt_sha256 && (
                <div className="col-span-2">
                  <dt className="text-mint-900/55">Prompt SHA-256</dt>
                  <dd className="break-all font-mono">{current.prompt_sha256}</dd>
                </div>
              )}
              {current.tokens && (
                <div className="col-span-2">
                  <dt className="text-mint-900/55">Tokens</dt>
                  <dd>{Object.entries(current.tokens).map(([k, v]) => `${k}: ${v}`).join(" · ")}</dd>
                </div>
              )}
              {current.tags.pipeline_run && (
                <div className="col-span-2">
                  <dt className="text-mint-900/55">Pipeline run</dt>
                  <dd className="break-all font-mono">
                    {current.tags.pipeline_run}
                    {current.tags.cost_usd ? ` · ${Number(current.tags.cost_usd).toFixed(4)} $` : ""}
                  </dd>
                </div>
              )}
              <div className="col-span-2">
                <dt className="text-mint-900/55">Event ID</dt>
                <dd className="font-mono">{current.id}{current.parent_id ? ` ← ${current.parent_id}` : ""}</dd>
              </div>
            </div>
            {current.sources.length > 0 && (
              <div>
                <dt className="mb-1 text-xs text-mint-900/55">Sources</dt>
                <dd>
                  <SourceList sources={current.sources} />
                </dd>
              </div>
            )}
          </dl>
        ) : (
          <p className="text-sm text-mint-900/55">Select a step on the left to see its input, output, model and sources.</p>
        )}
      </div>
    </div>
  );
}
