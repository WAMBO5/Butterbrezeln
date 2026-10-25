import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import type { RunResult, TraceEvent } from "../types";
import { agentOf } from "../lib/agents";
import { agentLabel } from "../lib/labels";
import { AgentAvatar } from "./Agent";
import { SourceList } from "./SourceLink";

const STATUS_DOT: Record<TraceEvent["status"], string> = {
  running: "bg-sky-400 animate-pulse",
  ok: "bg-emerald-400",
  fallback: "bg-amber-400",
  error: "bg-rose-400",
};

function duration(e: TraceEvent): string {
  if (!e.ts_end) return "läuft";
  const ms = new Date(e.ts_end).getTime() - new Date(e.ts_start).getTime();
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

interface Props {
  run: RunResult;
  trace: TraceEvent[];
  focusId?: string | null;
}

const select = "rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-300/40 [&>option]:bg-ink-900";

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
      className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition hover:bg-white/[0.05] ${selected === e.id ? "bg-cyan-300/10 ring-1 ring-cyan-300/30" : ""}`}
      style={{ paddingLeft: 8 + depth * 18 }}
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[e.status]}`} />
      <AgentAvatar kind={agentOf(e.agent)} size={20} />
      <span className="w-32 shrink-0 truncate text-xs font-medium text-slate-500">{agentLabel(e.agent)}</span>
      <span className="flex-1 truncate text-slate-200">{e.action}</span>
      {e.model && <span className="rounded bg-violet-400/15 px-1.5 text-[10px] font-semibold text-violet-200">LLM</span>}
      <span className="w-14 shrink-0 text-right font-mono text-[11px] text-slate-500">{duration(e)}</span>
    </button>
  );

  const tree = (parent: string | null, depth: number): JSX.Element[] => (children.get(parent) ?? []).flatMap((e) => [row(e, depth), ...tree(e.id, depth + 1)]);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div className="glass p-3">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <select className={select} value={agent} onChange={(e) => setAgent(e.target.value)}>
            <option value="">Alle Agenten</option>
            {agents.map((a) => (
              <option key={a} value={a}>
                {agentLabel(a)}
              </option>
            ))}
          </select>
          <select className={select} value={country} onChange={(e) => setCountry(e.target.value)}>
            <option value="">Alle Länder</option>
            {countries.map((c) => (
              <option key={c} value={c}>
                {run.verdicts[c]?.name_de ?? c}
              </option>
            ))}
          </select>
          <span className="text-xs text-slate-500">{trace.length} Schritte</span>
          <button type="button" className="btn-ghost ml-auto !py-1 text-xs" onClick={exportJson}>
            <Download size={14} /> Trace als JSON
          </button>
        </div>
        <div className="max-h-[65vh] space-y-0.5 overflow-y-auto">{filtering ? trace.filter(matches).map((e) => row(e, 0)) : tree(null, 0)}</div>
        <div className="mt-3 flex flex-wrap gap-3 border-t border-white/[0.06] pt-2 text-[11px] text-slate-500">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-400" /> ok</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400" /> Regelwerk statt LLM</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-400" /> Fehler</span>
        </div>
      </div>

      <div className="glass p-5">
        {current ? (
          <dl className="space-y-3 text-sm">
            <div className="flex items-center gap-3">
              <AgentAvatar kind={agentOf(current.agent)} size={40} />
              <div>
                <dt className="text-xs text-slate-500">{agentLabel(current.agent)}</dt>
                <dd className="font-semibold text-white">{current.action}</dd>
              </div>
            </div>
            {current.inputs_summary && (
              <div>
                <dt className="text-xs text-slate-500">Eingabe</dt>
                <dd className="whitespace-pre-line text-slate-300">{current.inputs_summary}</dd>
              </div>
            )}
            {current.outputs_summary && (
              <div>
                <dt className="text-xs text-slate-500">Ausgabe</dt>
                <dd className="whitespace-pre-line text-slate-300">{current.outputs_summary}</dd>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
              <div>
                <dt className="text-slate-500">Status</dt>
                <dd>{current.status}{current.tags.fallback_reason ? ` – ${current.tags.fallback_reason}` : ""}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Dauer</dt>
                <dd>{duration(current)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Start</dt>
                <dd className="font-mono">{current.ts_start}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Modell</dt>
                <dd>{current.model ?? "kein LLM (deterministisch)"}</dd>
              </div>
              {current.prompt_sha256 && (
                <div className="col-span-2">
                  <dt className="text-slate-500">Prompt-SHA256</dt>
                  <dd className="break-all font-mono">{current.prompt_sha256}</dd>
                </div>
              )}
              {current.tokens && (
                <div className="col-span-2">
                  <dt className="text-slate-500">Tokens</dt>
                  <dd>{Object.entries(current.tokens).map(([k, v]) => `${k}: ${v}`).join(" · ")}</dd>
                </div>
              )}
              {current.tags.pipeline_run && (
                <div className="col-span-2">
                  <dt className="text-slate-500">Pipeline-Lauf</dt>
                  <dd className="break-all font-mono">
                    {current.tags.pipeline_run}
                    {current.tags.cost_usd ? ` · ${Number(current.tags.cost_usd).toFixed(4)} $` : ""}
                  </dd>
                </div>
              )}
              <div className="col-span-2">
                <dt className="text-slate-500">Event-ID</dt>
                <dd className="font-mono">{current.id}{current.parent_id ? ` ← ${current.parent_id}` : ""}</dd>
              </div>
            </div>
            {current.sources.length > 0 && (
              <div>
                <dt className="mb-1 text-xs text-slate-500">Quellen</dt>
                <dd>
                  <SourceList sources={current.sources} />
                </dd>
              </div>
            )}
          </dl>
        ) : (
          <p className="text-sm text-slate-500">Schritt links auswählen, um Eingabe, Ausgabe, Modell und Quellen zu sehen.</p>
        )}
      </div>
    </div>
  );
}
