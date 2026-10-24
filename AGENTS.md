# AGENTS.md: building the Certivity pipeline

The backend is two LangGraph pipelines (legal and product) whose judgment steps call LLM through the Anthropic Python SDK. This file says how to build them. The project overview, stack and the coding agent tooling are in `README.md`, which imports this file; each rule lives in only one of the two. The full build contract, agent list and build order are in `industrial-ai-hackathon/BACKEND_PLAN.md`.

## Ground rules

1. **LangGraph graphs of plain typed functions.** Each node is an `async` function that takes the run state and returns the fields it changes. No LangChain agents, CrewAI, or open-ended planners.
2. **Every LLM call goes through `pipeline/llm.py`.** It returns a validated Pydantic model (`messages.parse`), caches the system prompt, uses `output_config.effort` instead of `temperature` (the 5.5 models reject non-default sampling), enables the server-side refusal fallback on Opus/Sonnet, bounds concurrency, waits out transient API errors (429/529/5xx) by repeating the same request, tells content failures (`LLMError.splittable`, answered by splitting the batch) from outages (`APIUnavailableError`, never answered with more requests), and caches every response on disk so re-runs are free and reproducible. Never call `anthropic` anywhere else, and never hard-code a model id.
3. **Check the installed SDK, not just the docs.** Read `.venv/Lib/site-packages/anthropic/` or `.venv/Lib/site-packages/langgraph/` before relying on an unfamiliar API; the `anthropic-sdk` skill describes the current LLM API.
4. **No paid calls or external writes without asking.** Anything that calls LLM, including `python -m pipeline.run`, needs approval first, as does any external write (uploads, pushes, posts).

## Design

- **Deterministic steps are not LLM steps.** Retrieval, section expansion, cross-references, supersession, verification, export and validation are plain code. Use LLM only where judgment is needed.
- **One job per agent.** Component, functionality, applicability, triage, judge, writer: each has its own prompt in `pipeline/prompts.py` and its own output schema in `pipeline/models.py`.
- **Typed hand-offs.** Pass structured data between nodes as Pydantic models or their `model_dump()`, never free text.
- **Bounded loops on state.** The coverage loop stops at `MAX_ROUNDS = 3`; caps live in code, not in prompts.
- **Refs, not ids, in prompts.** Give the model short refs (`P0`, `P1`, ...) and map them back to provision ids in code, so a model can never cite a provision it was not shown.

## Regulatory output rules

Product and data rules (allowlist, base vs latest versions, applicable / not applicable / uncertain states, pipeline stages, data hygiene) are in `industrial-ai-hackathon/AGENTS.md`, and the plan and open decisions are in `industrial-ai-hackathon/PROJECT_PLAN.md`. The rules below add how we enforce them.

The deliverable is engineering requirements with citations. These are enforced in code, not left to the prompt:

- Every requirement carries the **regulation, version and page** it comes from. A requirement without a citation is dropped, never emitted.
- Citations come from the parsed regulation text the model was shown, not from its memory. The verifier checks the quote against the cited provision and every number against the evidence, and drops what fails.
- Final submissions pass `industrial-ai-hackathon/tools/validate.py` before upload. Validation is a deterministic step in the pipeline, not something the LLM is asked to remember.
- Never invent a regulation number, paragraph or page. If the source does not say it, the answer is "not found".

## State and artefacts

- The run state is the `RunState` TypedDict in `pipeline/graph/map.py`. Nodes return only the keys they change.
- Every run writes its artefacts to `runs/<case_id>/<timestamp>/` (`components.json`, `route.json`, `decisions.jsonl`, `trace.jsonl`, `submission.json`, ...). Never write into `industrial-ai-hackathon/` except regenerated `regulations/text/`.

## Layout

```
pipeline/
  config.py            environment configuration
  llm.py               the only LLM caller
  models.py            Pydantic schemas for hand-offs and LLM outputs
  prompts.py           system prompts, one per agent
  catalog/             corpus, normalisation, parser, regulation cards, parser gate
  rag/store.py         Qdrant hybrid store
  graph/product.py     component and functionality agents
  graph/map.py         product run graph: route, retrieve, triage, judge, write, verify, export
  verify/checks.py     verifier, export, validate.py and score_local.py wrappers
  taxonomy/            functions.yaml, markets.yaml (demo only)
  legal.py             python -m pipeline.legal
  run.py               python -m pipeline.run
tests/
  unit/                deterministic code only: parser, normalisation, verifier, export
```

## Testing

- **Unit tests** (`uv run pytest`) cover deterministic code: parser gate, normalisation, supersession, section expansion, verifier, export through `validate.py`, and that the graph compiles. They make no API calls.
- **Do not assert on LLM wording in pytest.** Output is non-deterministic. Behaviour is checked with `tools/score_local.py` on the dev case and with platform uploads of the dev case, both of which need a paid run first.
- Report what was actually run versus only suggested.

## Running

```bash
uv sync
uv run pytest                                                         # offline
uv run python -m pipeline.legal                                       # parse and index the corpus (local, free)
uv run --env-file .env python -m pipeline.run --case cases/dev-rear-lamp   # paid; ask first
uv run --env-file .env python -m pipeline.run --promote runs/dev-rear-lamp/<timestamp>
```

Use `uv` for everything. Never `pip` directly.

## Out of scope unless we decide otherwise

Deployment, publishing, hosted observability, non-UN statutes, crawling, and committing PDFs, held-out inputs or the Qdrant store.

## When unsure

Fetch `https://langchain-ai.github.io/langgraph/llms.txt` with the `langgraph-docs` MCP `fetch_docs` tool, then the specific page; for LLM, read the `anthropic-sdk` skill. Then confirm against the installed package.
