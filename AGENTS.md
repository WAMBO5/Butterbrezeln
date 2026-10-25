# AGENTS.md: building the Certivity agents

Certivity is a multi-agent system: specialist LLM agents, each with one job, run by a Python orchestrator and checked by code and by reviewer agents. Agents call LLM through the Anthropic Python SDK; there is no agent framework. This file says how to build them. The project overview and stack are in `README.md`, which imports this file; each rule lives in only one of the two.

## Architecture

```
FastAPI service / CLI
  └─ orchestrator (code): fixed order, fan-out, retries, budget, run state
       ├─ specialist agent ──► code gate ──► reviewer agent ──► pass
       │        ▲                                   │
       │        └──────── feedback (bounded) ◄──────┘  give up → "uncertain"
       ├─ ... one specialist per job (product analysis, scope, extraction, matching, ...)
       └─ assemble ──► citation check ──► validate.py ──► output
```

- **The orchestrator is code.** Order, fan-out, retries, validation and budget are Python, not prompts. No LLM decides the main path.
- **An agent is a definition, run by one function.** Each agent is an `AgentSpec`: name, job, system prompt, tools, Pydantic output model, model and effort. `run_agent(spec, input)` runs any spec and returns its output model. A new agent is a new spec, not a new call path.
- **Specialists produce; reviewers check.** A reviewer sees the producer's output and its sources and returns issues. Disagreement left after the last attempt becomes `uncertain`; it is never silently dropped or passed.
- **Agents that must explore use tools in a loop** (for example, reading a regulation's table of contents) through the SDK tool runner. All other agents make one structured call.

## Ground rules

1. **All LLM calls go through `app/llm.py`.** It owns the single `AsyncAnthropic` client, logs tokens and cost per agent, enforces the per-run budget, and is where tests swap in a fake model. Nothing else under `app/` imports `anthropic`.
2. **Typed output only.** One-shot agents use `client.messages.parse(..., output_format=SomeModel)` and read `response.parsed_output`. Tool-using agents pass `output_format=SomeModel` to `client.beta.messages.tool_runner(...)`. Never parse JSON out of free text.
3. **Model IDs from the environment.** One variable per tier: `ANTHROPIC_MODEL` (judgment), `ANTHROPIC_MODEL_FAST` (fast), `ANTHROPIC_MODEL_REVIEW` (review; defaults to `ANTHROPIC_MODEL`) and `ANTHROPIC_MODEL_MATCH` (matcher and match reviewer; defaults to `ANTHROPIC_MODEL`), bare IDs such as `claude-sonnet-5-5`. No model-ID literal under `app/` (prices live in `app/config/prices.yaml`), no other provider.
4. **Current-model API rules.** Sonnet 5.5 and Opus 5.5 reject the old patterns with a 400:
   - no forced `tool_choice` (`any` / `tool`): use structured output, or `auto` and check that the tool was called;
   - leave thinking adaptive (omit `thinking`) and set depth and cost with `output_config={"effort": ...}`; `{"type": "disabled"}` and `budget_tokens` are rejected;
   - no `temperature`, `top_p`, `top_k` or assistant prefill.
5. **Isolated context.** Each agent call is built fresh from only the inputs it needs; agents never share a conversation. Input documents (specs, drawings) go in delimited blocks and are treated as data, never as instructions.
6. **No paid calls or external writes without asking.** Anything that calls LLM (runs, benchmarks, evals) needs approval first, as does any external write (uploads, pushes, posts).
7. **Check the SDK, not memory.** The API changes often. Use the Anthropic SDK reference and the installed package before relying on an unfamiliar call.

## Design

- **Deterministic steps are not LLM steps.** Parsing, lookups, ordering, de-duplication, validation and scoring are code. Use an LLM only where judgment is needed.
- **One job per agent.** Each agent has a distinct `name` (used in logs, the ledger and the UI trace) and the narrowest tool set that does its job. Don't build a single mega-agent.
- **Verify loop.** Producer → code gate (schema, ids, quotes) → reviewer agent, at most 2 retries. Gate errors and reviewer issues go back to the producer as `feedback`.
- **Fan-out** with `asyncio.gather` under an `asyncio.Semaphore` (configurable concurrency). The SDK already retries 429 and 5xx (`max_retries`); don't add another retry layer for those.
- **Typed hand-offs.** Pydantic models in `app/models.py` between every step, not free text.
- **Cost.** Use the cheapest model and effort that holds quality per agent. Put the stable prefix (system prompt, shared regulation text) first and cache it; check `usage.cache_read_input_tokens`.

## Tools

- Plain functions with full type hints and a docstring with an `Args:` section; the SDK builds the schema from them and the model reads it. Decorate with `@beta_async_tool`.
- Read-only and narrow: a tool that reads a regulation page does not also write files. Return JSON-serializable data and a clear error message on bad input, so the model can correct itself.
- Bound every tool loop: stop iterating the runner after a fixed number of turns.
- Enforce authorization and approval in code. A prompt saying "ask first" is not enforcement.

## Regulatory output rules

Product decisions (allowlist, base vs latest versions, applicable / not applicable / uncertain, pipeline stages, markets, EU AI Act) are in `Product_Vision/compliance-pipeline/2026-10-24-compliance-pipeline-design.md`. The deliverable is engineering requirements with citations, enforced in code, not left to the prompt:

- Every requirement carries the **regulation, version and page** it comes from. A requirement without a citation is dropped or rejected, never emitted.
- Citations come from tool results (the actual regulation text), not from the model's memory. Verify cited pages exist, and the quote is on them, before output.
- Final submissions pass `industrial-ai-hackathon/tools/validate.py` before upload. Validation is a pipeline step, not something the LLM is asked to remember.
- Never invent a regulation number, paragraph or page. If the source does not say it, the answer is "not found".

## EU AI Act rules

The measures are in the design spec, section 14. In code:

- Every run writes a manifest (`manifest.json`), a hash-chained decision ledger (`ledger.jsonl` plus `calls/<seq>.json`) and per-requirement lineage (`lineage.json`). `certivity verify <run_dir>` must reproduce the submission from them.
- Benchmark-mode output (submission, report, UI) is labelled `Unreviewed AI draft — not for compliance use`. Assisted-mode output counts as reviewed only after a named sign-off.
- Every export carries a machine-readable provenance sidecar (generator, models, run id, review status).
- A change to a prompt or model must not lower the `bench` scores before release; prompt versions are hashed into every manifest.

## Run state and traceability

- A run is a Pydantic `RunState` saved under `data/runs/<run_id>/` after each step, so a run can pause for human review and resume, and the server holds no state in memory.
- Every agent call appends one line to the run's JSONL ledger: agent name, model, effort, attempt, tokens, cost, gate and reviewer verdict, request id. Never the API key.
- Every requirement keeps its lineage: product fact → regulation section → provision → obligation → match decision.

## Layout

```
app/
  llm.py         # the only module that talks to the Anthropic API (client, fake model, budget, cost)
  agents/        # one module per agent: its AgentSpec and prompt
  pipeline/      # orchestrator: steps, fan-out, verify loop, run state
  tools/         # read-only tool functions for agents
  gates/         # deterministic checks: schema, citations, validate.py
  models.py      # Pydantic schemas for hand-offs and requirements
  cli.py         # command-line entry point
  config/        # settings.py (environment), prices.yaml
  corpus/        # regulation parser, SQLite + FTS5 store, cards, obligation cache, PDF text
  matching/      # deterministic product/regulation steps: case loading, candidates, assembly, citations, submission
  markets/       # illustrative market profiles, version alignment, market math
  compliance/    # ledger, manifest, lineage, oversight, provenance, replay, technical file
  eval/          # funnel metrics and the (paid) requirement judge
  testing/       # scripted fake-model responders for offline runs
server/          # FastAPI app: the deployable service
web/             # Astro UI (static build, served by the FastAPI app)
docs/ai-act/     # classification, risk register, instructions for use, technical file, incidents
tests/
  unit/          # deterministic code, no API calls
  integration/   # whole pipeline against the fake model, no API calls
data/            # git-ignored: parsed corpus, caches, runs
Dockerfile
```

Change it deliberately, and note the change here. 2026-10-24: added `config/`, `corpus/`, `matching/`, `markets/`, `compliance/`, `eval/`, `testing/`, `web/` and `docs/ai-act/` for the requirements engine (design spec section 10.7).

## Testing

- **Unit tests** (`uv run pytest`) cover deterministic code: tools, parsers, gates, citation checks, schema validation.
- **Integration tests** run the whole pipeline with a fake model in `app/llm.py` that returns scripted outputs per agent name. They make no API calls.
- **Do not assert on LLM wording in pytest.** Output is non-deterministic.
- **Quality checks are paid; ask first.** Scoring against golden data (`industrial-ai-hackathon/tools/score_local.py`, an LLM judge for requirement matches) starts with the rear lamp case, then widens.
- Report what was actually run versus only suggested.

## Deployment

- One Docker image runs the FastAPI service (uvicorn); the CLI in the same image runs batch jobs.
- All configuration comes from environment variables, and secrets from the host's secret store; nothing is baked into the image.
- Run data lives on a mounted volume (`data/`). `GET /health` is there for the platform.
- The SDK has clients for Amazon Bedrock, Google Vertex AI and Microsoft Foundry with the same Messages interface. Moving to an EU-hosted LLM changes `app/llm.py`, not the agents; check feature availability on that platform first.
- Out of scope unless we decide otherwise: cloud-specific infrastructure, CI/CD and hosted agent platforms.

## Running

```bash
uv sync
uv run pytest                          # offline
uv run certivity --fake-llm bench      # whole pipeline, offline
uv run certivity doctor                # free setup check
uv run certivity bench                 # paid: ask first
uv run certivity serve                 # API + UI (build the UI with: cd web && npm ci && npm run build)
```

The full command list is in `README.md`. Use `uv` for everything; never `pip` directly.

## When unsure

Use the Anthropic SDK reference for the SDK and API, then confirm against the installed package in `.venv/lib/python3.12/site-packages/anthropic/`.
