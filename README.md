# Certivity

Industrial Agents Hackathon, Munich, 24–25 October 2026: turn a product specification and/or exploded view into the engineering requirements it must fulfil under UN Regulations, with page-level citations.

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

## Frontend

`ui/` is the one frontend; the approaches are CLI only. It shows finished runs from `data/<approach>/runs/` read only, so run an approach first (`./certivity <approach> run <case folder>`, paid). See `ui/README.md`.

```bash
cd ui && uv sync
uv run uvicorn api.main:app --port 8010      # API (BACKEND_MODE=mock: offline demo)
cd web && npm ci && npm run dev              # http://localhost:5173
```

History of the two approaches stays on the `main` (as of `d58f9e0`) and `general` (as of `39d0fe7`) branches, and on the tags `archive/main-approach` and `archive/general-approach`.
