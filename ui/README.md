# Marktfreigabe-Check

Upload a product spec (`spec.md`), pick target countries, and get a traffic-light verdict per country:
green (no product change found; approval and test evidence still to come), yellow (the product stays,
documents, marking or tests are missing), red (the product itself must change), grey (no country data).
Every requirement links to its page in the UN Regulation PDF, and every agent step is logged so the
whole chain spec → regulation → page → requirement → finding → verdict → suggestion is traceable.

Every result view carries the label *Unreviewed AI draft — not for compliance use*: the verdicts are a
draft for an engineer to check, not an approval decision.

## Run

From `ui/`, in the repository's uv environment (`uv sync` at the repository root):

```bash
# API on port 8010 (8000 is `certivity serve`)
uv run uvicorn api.main:app --port 8010 --reload --reload-dir api   # BACKEND_MODE=mock: offline demo

# UI (Node 20+), proxies /api to :8010
cd web && npm ci && npm run dev        # http://localhost:5173
```

By default the UI shows finished runs of the certivity pipeline, read only: no run is started from here.
An uploaded `spec.md` is matched to the run whose manifest lists the same spec hash. A run started with
`uv run certivity run <case folder>` shows up once its folder has `submission.json` and `lineage.json`.

Regulation PDFs for the source links (hackathon data, not committed), from the repository root:

```bash
uv run python industrial-ai-hackathon/tools/fetch_regulations.py --role base
```

Missing PDFs fall back to the remote `pdf_url` from `regulations/index.json`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_MODE` | `runs` | `runs` reads finished pipeline runs; `mock` replays `cases/<case>/expected.json` (labelled as mock in the trace); `engine` calls `ENGINE_ENTRYPOINT` in-process |
| `PIPELINE_ROOT` | the repository root | pipeline checkout; runs are read from its `data/runs/` and from `../sunday-data/<sample>/runs/`, likewise for the sibling checkouts `../Brezel/Butterbrezeln` and `../Butterbrezeln-general` |
| `PIPELINE_RUN_DIRS` | – | replaces those run folders (`:`-separated) |
| `PIPELINE_RUN` | – | run id(s) to show when several finished runs share a spec; otherwise the latest |
| `ENGINE_ENTRYPOINT` | – | `module:function` that returns main-goal requirements, see `api/backend_client.py` |
| `LLM_MODE` | `off` | `off`: the rule set only, no LLM calls; `on`: LLM checks the spec and answers country questions when credentials resolve (paid, ask first), with the rule set as fallback |
| `LLM_MODEL` | `ANTHROPIC_MODEL` | model for those calls; there is no built-in default |
| `ANTHROPIC_API_KEY` | – | or `ant auth login`; only used with `LLM_MODE=on` |
| `RUNS_DIR` | `ui/runs` | the UI's own results and traces (git-ignored) |

## Traffic-light rule (`api/assess.py: compute_status`)

The LLM only classifies findings and the effort of each fix; the colour is computed by a fixed rule:
any `design` fix → red; only `doku_kennzeichnung` / `pruefung_zertifizierung` fixes → yellow; nothing to
fix → green (open evidence such as missing measurements is listed but does not change the colour).
Countries without UNECE 1958 membership and without a curated profile are grey.

Country data lives in `data/countries.json` (UNECE 1958 contracting parties, with sources) and
`data/country_profiles/<ISO3>.json` (national rules outside the Certivity corpus, marked as such in UI
and trace). Both are a research draft (retrieved 2026-10-25), not legal advice, and the UI says so.

## Traceability

Each run writes `runs/<run_id>/result.json` and `runs/<run_id>/trace.jsonl`: agent, action, inputs,
outputs, model, prompt SHA-256, token usage and sources per step. Accepting or rejecting a suggestion
is logged as a `human_review` step. This follows the logging, transparency and human-oversight ideas
of EU AI Act Art. 12–14; it is not a conformity claim.

## Tests

```bash
uv run pytest api/tests -q   # from ui/, offline on the golden files
```
