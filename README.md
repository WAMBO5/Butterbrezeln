# Certivity

Industrial Agents Hackathon, Munich, 24–25 October 2026: turn a product specification and/or exploded view into the engineering requirements it must fulfil under UN Regulations, with page-level citations, and show what it takes to sell the product in each target market.

## Run it yourself

You need [uv](https://docs.astral.sh/uv/) (it brings Python 3.12), Node 20+ and bash (macOS or Linux). An Anthropic API key only for real runs.

```bash
cp .env.example .env                                  # then set ANTHROPIC_API_KEY (the models are preset)
./certivity general-approach build-corpus             # free, once: parses the regulations into data/
./certivity ui                                        # http://localhost:8010
```

That is enough for **Demo** mode. For **Real** mode, build the regulation cards once (they are shared by both approaches) and check the setup:

```bash
CERTIVITY_MAX_COST_USD=8 ./certivity general-approach build-corpus --cards   # paid, about $5 once: one summary card per regulation
./certivity general-approach doctor                                          # free: key, models, corpus, catalog, cards
```

In the app:

1. **Demo / Real** (switch in the header). *Demo* is free: a scripted stand-in model writes the requirements of new runs, labelled as not a real analysis. *Real* uses LLM with the key from `.env`: new pipeline runs and the answers to country questions are paid. The switch stays greyed out, with the reason, until the key, the models and the corpus are in place; restart `./certivity ui` after editing `.env`.
2. **Product**: pick an example (rear lamp, front bumper) or drop your own `spec.md`, optionally with its exploded view.
3. **Markets**: China and the US are preselected; add any country. **Start agents**.
4. If the spec has no analysis yet, the app starts the pipeline (`general-approach`) in the background and shows its steps: a real run costs about $5–7 and 15 minutes for the rear lamp and stops at $12 (`PIPELINE_MAX_COST_USD` in `.env`). The result opens when it has finished. **Run the pipeline again** on a result starts a fresh run.

Real and demo runs are kept apart: real runs go to `data/<approach>/runs/`, demo runs to `ui/runs/pipeline-demo/` with their own extraction cache, and a real result always wins over a demo one for the same spec. The same pipeline runs from the command line: `./certivity general-approach run industrial-ai-hackathon/cases/dev-rear-lamp` (paid), then `./certivity general-approach score <run dir>` (free). Source links open the regulation PDFs once they are fetched (hackathon data, not committed): `./certivity general-approach -- python industrial-ai-hackathon/tools/fetch_regulations.py --role base`.

## Layout

| Path | What |
| --- | --- |
| `industrial-ai-hackathon/` | Challenge material, regulations, cases, scoring tools and the challenge brief (shared by both approaches) |
| `Product_Vision/` | Product design shared by both approaches |
| `ideas.md` | Product ideas |
| `ui/` | The web frontend for the whole solution (the market-approval UI: API and React app); reads the runs of every approach |
| `approaches/main-approach/` | The approach that was on `main` (requirements engine) |
| `approaches/general-approach/` | The approach that was on `general` (general, outcome-based pipeline, evalkit, submissions) |
| `certivity` | Launcher: runs one approach on the shared data |
| `data/` | Git-ignored: every approach's corpus, caches and runs (below) |

Each approach is a self-contained `uv` project with its own `README.md`, `AGENTS.md`, `README.md`, `pyproject.toml` and tests. Switch between them with the launcher, which runs from the approach's folder (so paths are relative to it):

```bash
./certivity general-approach doctor                                            # its CLI: uv run certivity ...
./certivity main-approach run industrial-ai-hackathon/cases/heldout-front-bumper
./certivity general-approach -- pytest                                         # anything else: uv run ...
```

`cd approaches/<approach> && uv run ...` works the same. A new approach is a new folder under `approaches/`; the launcher sets up its data on first use.

### Data

| Path | What |
| --- | --- |
| `industrial-ai-hackathon/` | The source: regulation text and PDFs, cases, expected answers. Each approach links to it as `approaches/<approach>/industrial-ai-hackathon` |
| `data/shared/` | Shared by all approaches: regulation cards (`cards/`) and the extraction cache (`obligations.sqlite`, keyed by each approach's extractor version) |
| `data/<approach>/` | One approach's own data: `catalog.sqlite` (built by its parser) and `runs/<run_id>/`; `cards` and `obligations.sqlite` link to `data/shared/`. The approach sees it as `approaches/<approach>/data` |

The catalog stays per approach: the parsers differ, and each rebuilds a catalog written by another parser. Never let an approach create `approaches/<approach>/data` as a real folder; that splits its data from the rest.

## The product

```bash
./certivity ui            # http://localhost:8010: builds the web app and serves it with its API
./certivity ui --demo     # the same, but only the free demo model (e.g. for a public demo)
```

`ui/` is the one frontend; the approaches are CLI only. Upload a spec (or pick an example), choose markets, and it shows:

- **Challenge benchmark**: the pipeline run's `submission.json`, built only from the challenge data in `industrial-ai-hackathon/` (UN Regulations, the spec, its drawing), with its F2 score at regulation, page and requirement level when the spec is a challenge case with a reference (`dev-rear-lamp`), and a download.
- **Market layer**: our own country research on top (`ui/data/`): which markets take the UN Regulations as they are, and what changes for markets with national rules (China and the US for rear lamps and front bumpers). It is not in `submission.json` and never changes the score.

It reads every approach's finished runs in `data/*/runs/` (failed runs never, demo runs only when there is no real one). For a spec without a run it starts one in the background with `general-approach` (`PIPELINE_APPROACH`), real or demo as the header switch says. All settings live in the one `.env` at the repository root (`.env.example`); details in `ui/README.md`.

History of the two approaches stays on the `main` (as of `d58f9e0`) and `general` (as of `39d0fe7`) branches, and on the tags `archive/main-approach` and `archive/general-approach`.
