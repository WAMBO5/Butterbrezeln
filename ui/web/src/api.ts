import type { CountryListing, Decision, Health, QAEntry, RunResult, Suggestion, TraceEvent } from "./types";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then(json<Health>),
  countries: () => fetch("/api/countries").then(json<CountryListing>),
  examples: () => fetch("/api/examples").then(json<string[]>),
  example: (name: string) =>
    fetch(`/api/examples/${name}`).then(async (r) => {
      if (!r.ok) throw new Error(`${r.status}`);
      return r.text();
    }),
  /** The example's drawing as an upload-ready file, or null if the case has none. */
  exampleImage: (name: string) =>
    fetch(`/api/examples/${name}/image`).then(async (r) => (r.ok ? new File([await r.blob()], `${name}.png`, { type: "image/png" }) : null)),
  runImageUrl: (id: string) => `/api/runs/${id}/image`,
  /** A run's uploaded drawing as a file again, to start a follow-up run with it. */
  runImage: (id: string) =>
    fetch(`/api/runs/${id}/image`)
      .then(async (r) => (r.ok ? new File([await r.blob()], "drawing.png", { type: "image/png" }) : null))
      .catch(() => null),

  startRun(spec: File, countries: string[], image?: File | null) {
    const form = new FormData();
    form.append("spec", spec);
    form.append("countries", countries.join(","));
    if (image) form.append("image", image);
    return fetch("/api/runs", { method: "POST", body: form }).then(json<{ run_id: string }>);
  },

  run: (id: string) => fetch(`/api/runs/${id}`).then(json<RunResult>),
  trace: (id: string) => fetch(`/api/runs/${id}/trace`).then(json<TraceEvent[]>),

  ask: (id: string, iso3: string, question: string) =>
    fetch(`/api/runs/${id}/countries/${iso3}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }).then(json<QAEntry>),

  decide: (id: string, suggestionId: string, decision: Decision) =>
    fetch(`/api/runs/${id}/suggestions/${suggestionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    }).then(json<Suggestion>),

  /** Server-sent events for a run: every trace step as it starts and ends. */
  events(id: string, onStep: (e: TraceEvent) => void, onDone: () => void): () => void {
    const source = new EventSource(`/api/runs/${id}/events`);
    source.addEventListener("step", (e) => onStep(JSON.parse((e as MessageEvent).data)));
    source.addEventListener("done", () => {
      source.close();
      onDone();
    });
    source.onerror = () => {
      source.close();
      onDone();
    };
    return () => source.close();
  },
};
