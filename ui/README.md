# Market Approval Check

Upload a product spec (`spec.md`), pick target countries, and get a traffic-light verdict per country:
green (no product change found; approval and test evidence still to come), yellow (the product stays,
documents, marking or tests are missing), red (the product itself must change), grey (no country data).
Every requirement links to its page in the UN Regulation PDF, and every agent step is logged so the
whole chain spec → regulation → page → requirement → finding → verdict → suggestion is traceable.

Every result view carries the label *Unreviewed AI draft — not for compliance use*: the verdicts are a
draft for an engineer to check, not an approval decision.

## Run

From the repository root, one process on one port (builds the web app, then serves it with the API):

```bash
./certivity ui            # http://localhost:8010
./certivity ui --demo     # runs started from the UI only use the free scripted model
```

For UI work, from `ui/`, which is its own uv project (`uv sync`):

```bash
# API on port 8010
uv run uvicorn api.main:app --port 8010 --reload --reload-dir api   # BACKEND_MODE=mock: offline demo

# UI (Node 20+), proxies /api to :8010
cd web && npm ci && npm run dev        # http://localhost:5173
```

By default the UI shows finished runs of the certivity pipeline from `data/*/runs/`. An uploaded `spec.md`
is matched to the run whose manifest lists the same spec hash: the latest real run (a demo-model run only if
there is no real one; failed runs never). A run started with `./certivity <approach> run <case folder>` (from the
repository root) shows up once its folder has `submission.json` and `lineage.json`.

If no finished run matches, or on "Run the pipeline again", the UI starts one: the upload is written to
`<PIPELINE_ROOT>/data/uploads/upload-<sha8>/` and `./certivity <PIPELINE_APPROACH> run` (default
`general-approach`) runs there as a subprocess (`api/pipeline_jobs.py`), one run at a time; the dialog follows its
steps from `trace.jsonl` and opens exactly that run when it has finished. The **Demo / Real** switch in the
header decides (kept per browser; demo by default):

- **Real**: paid model calls with the API key from the root `.env`, about $5–7 and 15 minutes for the rear lamp, into `data/<approach>/runs/`;
  it stops at `PIPELINE_MAX_COST_USD` (default $12) and keeps what it has decided so far.
  A result started in real mode also answers country questions with the model (`LLM_MODE` only sets the default
  for demo results). Real is only offered when `GET /api/health` reports `real.available`: an
  `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` and `ANTHROPIC_MODEL_FAST`, the parsed catalog and the regulation cards;
  otherwise `real.reason` says what is missing, and the API refuses real runs in code (`pipeline_jobs.real_problem`).
  The key itself is never sent to the browser.
- **Demo**: the scripted stand-in, free and quick, labelled as not a real analysis. Its runs go to
  `runs/pipeline-demo/runs/` with their own data folder (`runs/pipeline-demo/data/<approach>/`: the approach's
  catalog and the shared cards linked, an extraction cache of its own). The approaches key their extraction cache
  by provision text and extractor version, not by model, so a demo run on `data/shared/obligations.sqlite` would
  leave scripted obligations that later real runs reuse.

`PIPELINE_FAKE_LLM=1` (or `./certivity ui --demo`) allows only the demo model. The API reads the `.env` at the
repository root (`.env.example`; the environment wins over it), so the UI and the approaches share one key and
one set of models; restart `./certivity ui` after editing it.

## Benchmark and market layer

The result page keeps the two apart. **Challenge benchmark** (`api/benchmark.py`): the pipeline run's
`submission.json`, built only from the challenge data (UN Regulations, spec, drawing), downloadable, and, when
the spec equals a challenge case with `expected.json`, scored with the organisers' `score_local.py` at regulation
and page level plus the requirement level as one-to-one (regulation, paragraph) pairing, an upper bound on the
platform's requirement-level F2 (the same pairing as general-approach `tools/evalkit/score.py`). F2 = 5PR / (4P + R)
is the ranking metric. **Market layer**: the country verdicts from `data/` below, with a "How to ship to …"
entry for each market with national rules. It is not in `submission.json` and never changes the score.

Regulation PDFs for the source links (hackathon data, not committed), from the repository root (in an approach's environment):

```bash
./certivity main-approach -- python industrial-ai-hackathon/tools/fetch_regulations.py --role base
```

Missing PDFs fall back to the remote `pdf_url` from `regulations/index.json`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_MODE` | `runs` | `runs` reads finished pipeline runs; `mock` replays `cases/<case>/expected.json` (labelled as mock in the trace); `engine` calls `ENGINE_ENTRYPOINT` in-process |
| `PIPELINE_ROOT` | the repository root | runs are read from its `data/*/runs/` (one folder per approach) |
| `PIPELINE_RUN_DIRS` | – | replaces those run folders (`:`-separated) |
| `PIPELINE_APPROACH` | `general-approach` | the approach whose `./certivity` launcher starts runs from the UI; they land in `data/<approach>/runs/` |
| `PIPELINE_MAX_COST_USD` | `12` | budget of a real run started from the UI (`CERTIVITY_MAX_COST_USD` of that run) |
| `PIPELINE_CMD` | `PIPELINE_ROOT/certivity <approach>` | replaces the command that starts runs from the UI |
| `PIPELINE_FAKE_LLM` | – | `1`: runs started from the UI may only use `--fake-llm` (no API calls, not a real analysis) |
| `PIPELINE_RUN` | – | run id(s) to show when several finished runs share a spec; otherwise the latest |
| `ENGINE_ENTRYPOINT` | – | `module:function` that returns main-goal requirements, see `api/backend_client.py` |
| `LLM_MODE` | `off` | `off`: the rule set only, no model calls; `on`: the model checks the spec and answers country questions when credentials resolve (paid, ask first), with the rule set as fallback |
| `LLM_MODEL` | `ANTHROPIC_MODEL` | model for those calls; there is no built-in default |
| `ANTHROPIC_API_KEY` | – | in the root `.env`: real pipeline runs and model answers in real mode (for `LLM_MODE=on` alone, `ant auth login` works too) |
| `RUNS_DIR` | `ui/runs` | the UI's own results and traces (git-ignored) |

## Traffic-light rule (`api/assess.py: compute_status`)

The LLM only classifies findings and the effort of each fix; the colour is computed by a fixed rule:
any `design` fix → red; only `documentation` / `testing` fixes → yellow; nothing to
fix → green (open evidence such as missing measurements is listed but does not change the colour).
Countries without UNECE 1958 membership and without a curated profile are grey.

Country data lives in `data/countries.json` (UNECE 1958 contracting parties, with sources) and
`data/country_profiles/<ISO3>.json` (national rules outside the Certivity corpus, marked as such in UI
and trace). Both are a research draft (retrieved 2026-10-25), not legal advice, and the UI says so.

A profile is only used for the products it was researched for. `covers` is one group or a list of groups
(`id`, `products` matched against the spec title, `regulations` of which the run must cite one, `product`
for the message); a group may carry its own `summary` and `certification` that replace the profile's. A
deviation with `applies_to: ["<group id>"]` only counts for those products, so lamp rules such as CCC or
DOT never show up for a bumper. CHN and USA cover rear lamps and front bumpers. The bumper items, the
shared materials screening (CHN-17, USA-16) and the standards behind them come from
`data/sources/regulatory-map-cn-us.md` (assessment 2026-10-25, **not independently reverified**): they carry
`verified: false`, which the UI shows as "source not verified", and they are only documentation or testing
steps because the map names no known design gap. Where the map is weaker than an earlier, sourced entry
(e.g. the CCC rule for rear lamps, GAP-022), the earlier entry stays.

## Traceability

Each run writes `runs/<run_id>/result.json` and `runs/<run_id>/trace.jsonl`: agent, action, inputs,
outputs, model, prompt SHA-256, token usage and sources per step. Accepting or rejecting a suggestion
is logged as a `human_review` step. This follows the logging, transparency and human-oversight ideas
of EU AI Act Art. 12–14; it is not a conformity claim.

## Tests

```bash
uv run pytest api/tests -q   # from ui/, offline on the golden files
```
