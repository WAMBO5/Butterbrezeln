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

Each approach is a self-contained `uv` project with its own `README.md`, `AGENTS.md`, `README.md`, `pyproject.toml` and tests. Work from inside its folder:

```bash
cd approaches/general-approach
uv sync
uv run pytest
```

Each folder holds a symlink `industrial-ai-hackathon -> ../../industrial-ai-hackathon`, because the code looks for that folder relative to its working directory. The Docker builds copy that folder, so build them from a context that resolves the link (or set `CERTIVITY_CHALLENGE_DIR`).

## Frontend

`ui/` is the one frontend; the approaches are CLI only. It shows finished runs from `data/<approach>/runs/` read only, so run an approach first (`./certivity <approach> run <case folder>`, paid). See `ui/README.md`.

```bash
cd ui && uv sync
uv run uvicorn api.main:app --port 8010      # API (BACKEND_MODE=mock: offline demo)
cd web && npm ci && npm run dev              # http://localhost:5173
```

History of the two approaches stays on the `main` (as of `d58f9e0`) and `general` (as of `39d0fe7`) branches, and on the tags `archive/main-approach` and `archive/general-approach`.
