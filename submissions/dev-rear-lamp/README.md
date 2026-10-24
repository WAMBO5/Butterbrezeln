# Dev-case submissions (worked example `dev-rear-lamp`)

Every file here passes `industrial-ai-hackathon/tools/validate.py` and carries `team_id: team-04`, `case_id: dev-rear-lamp`. Upload on https://hackathon.certivity.io (Main challenge → Worked example: vehicle rear lamp). The dev leaderboard keeps our **best** upload; 5 uploads per hour per team, shared by everyone.

| File | Reqs | How it was made | Platform Req F2 (P / R) |
|---|---|---|---|
| `05-ensemble-run4-lane-v7.json` | 347 | `tools/evalkit/ensemble.py` on run 4 (primary) + lane v7 | to upload (estimate ≈ 74–75 %) |
| `04-pipeline-run4.json` | 354 | run 3's scope plan and obligations, matching redone with the final matcher prompt | to upload (estimate ≈ 72–73 %) |
| `03-pipeline-run3.json` | 310 | pipeline, all changes on this branch except the last matcher refinement | **71.0 %** (49.0 / 80.0) |
| `lane-dev-v7.json` | 363 | lane (LLM agents over the corpus, built by another session) | 68.6 % (42.4 / 81.1) |
| `lane-dev-v4.json` | 344 | lane, earlier prompts | 65.7 % (42.2 / 76.3) |
| `02-pipeline-run2.json` | 405 | pipeline, intermediate prompts | 65.2 % (37.5 / 80.0) |
| `01-pipeline-run1.json` | 525 | pipeline, first fixes | 59.5 % (29.1 / 80.5) |

Before these, the team's best was 52.5 % (49.8 % for the 19:35 upload, 695 requirements).

## What changed in the pipeline (branch `pay-to-win`)

- **Budget guard:** the old run hit `CERTIVITY_MAX_COST_USD=5` and dumped every undecided obligation as "uncertain". Run with `CERTIVITY_MAX_COST_USD=20` (a dev run costs $3–6 in reduced mode).
- **Scope:** markings, general requirements, sections for the part's own functions only, component-level sections, annexes only when they set limits, pass/fail criteria or test levels; no admin, approval, COP sampling, examples or measuring grids.
- **Extraction (version x4):** list items split, either/or lists kept whole, test-method sentence plus table rows, exceptions kept with their rule, permissions on the product extracted.
- **Matching:** lab mechanics, alternative tests, presence entries and impossible device categories are not applicable; optional features the spec does not exclude are uncertain (kept).
- **Collector:** a reference to a whole annex no longer pulls the annex in.
- **Parser:** UN GTR 9's regulation text (legform-to-bumper limits, pp. 71–116) was swallowed into one paragraph; fixed (`PARSER_VERSION p2`, rebuild with `uv run certivity build-corpus`).

## Nothing is hard-coded

No generating step reads `expected.json`: only scoring code does (`score_submission`, the funnel, the judge). `tests/unit/test_fairness.py` fails if any expected requirement text appears in an agent prompt or example, and every requirement's quote must be on its cited page of the regulation. The rules were *calibrated* on this worked example, so the dev score is optimistic; the held-out case decides the ranking.

## Reproduce

```bash
uv sync && uv run certivity build-corpus                        # free; needs data/cards for runs (build-corpus --cards ≈ $5)
CERTIVITY_COST_MODE=reduced CERTIVITY_MAX_COST_USD=20 uv run certivity bench
python3 tools/evalkit/ensemble.py out.json data/runs/<id>/submission.json <lane submission.json>
python3 tools/evalkit/check_heldout.py out.json --case <case_id>  # blocks wrong ids, versions, pages
```

The Sunday plan for the held-out case is in `docs/hackathon/sunday-runbook.md`. **For the held-out case the last valid upload counts, not the best.**
