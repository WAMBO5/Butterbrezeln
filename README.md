# Certivity requirements engine

From a vehicle component's specification and/or exploded view to the engineering requirements it must meet under the UN Regulations of the challenge corpus, each cited to regulation, version, page and paragraph. Built for the Industrial Agents Hackathon (Munich, 24–25 October 2026).

Specialist LLM agents, each checked by code and by a verifier agent, are run by a plain-Python orchestrator. The design is in `Product_Vision/compliance-pipeline/`; how the agents are built is in `AGENTS.md`.

## Set up

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY (never commit it) and CERTIVITY_TEAM_ID
uv sync
uv run certivity doctor     # free: key set, models, corpus, catalog
uv run pytest               # offline, no API calls
```

## Run

| Command | Paid | What it does |
| --- | --- | --- |
| `uv run certivity doctor [--ping]` | `--ping`: cents | Checks the setup; `--ping` makes one tiny call per model tier |
| `uv run certivity build-corpus [--cards] [--prefill]` | `--cards` ≈ $5, `--prefill` | Parses the corpus (free); writes regulation cards; pre-fills obligations |
| `uv run certivity run <case_dir> [--markets a,b] [--mode benchmark\|assisted]` | yes | The full pipeline; writes `data/runs/<id>/` |
| `uv run certivity bench` | yes | `run` + validate + score on the rear lamp |
| `uv run certivity score <run_dir> [--judge]` | `--judge` | Validation, `score_local.py`, funnel metrics; `--judge` estimates the requirement level |
| `uv run certivity verify <run_dir>` | no | Checks the ledger's hash chain and replays the submission from it |
| `uv run certivity signoff <run_dir> --reviewer NAME` | no | Named sign-off; refused while items are open |
| `uv run certivity subgoal <subgoal_dir>` | yes | Sub-goal: which old requirements change in the new version |
| `uv run certivity markets list` / `markets add NAME --source FILE` | `add`: yes | Market profiles; builds one from cited sources |
| `uv run certivity technical-file` | no | Regenerates the measured parts of `docs/ai-act/` |
| `uv run certivity serve` | when runs start | API and UI on http://127.0.0.1:8000 |

Every command takes `--fake-llm`, a scripted stand-in model, for offline demos and tests.

The UI is an Astro app in `web/`; `certivity serve` serves its build. Build it once with `cd web && npm ci && npm run build`. For UI work, run `npm run dev` there (it talks to the API on port 8000).

`CERTIVITY_COST_MODE=reduced` runs the match reviewer only on disputed decisions and skips the extraction verifier. A budget guard (`CERTIVITY_MAX_COST_USD`, default $5) stops a run; a stopped run is marked partial in its report.

## Modes

- **Benchmark** (default for `run` and `bench`): no pauses. Every output is labelled *Unreviewed AI draft — not for compliance use*.
- **Assisted** (`--mode assisted`, or the UI): pauses for review of the product profile, the chosen regulations and the requirements, then needs a named sign-off before the export counts as reviewed.

## Held-out case

```bash
uv run python industrial-ai-hackathon/tools/fetch_regulations.py      # new PDFs
uv run certivity build-corpus --extract-missing --cards               # text for new PDFs, cards for new regulations
uv run certivity run industrial-ai-hackathon/cases/<held-out-case>
uv run certivity score data/runs/<run_id>                             # validate.py must pass
```

Uploading the submission stays a manual, reviewed step.

## Limits

Only the UN Regulations of the corpus are known; requirements cite the base versions; markets are illustrative samples, not real law; evidence is judged from the specification only. See `docs/ai-act/instructions-for-use.md`.

## Output of a run (`data/runs/<run_id>/`)

`submission.json` (challenge format) and `submission.provenance.json`, `requirements.json`, `lineage.json` (why each requirement is there), `profile.json`, `scope_plan.json`, `markets.json` and `ship_plan.json` when markets are selected, `report.md`, `manifest.json`, `ledger.jsonl` with `calls/`, `trace.jsonl`, `state.json`.
