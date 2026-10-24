# AGENTS.md: building agents in Certivity

Every agent in this project is a real Google ADK agent (`google-adk` 2.x, Python). This file says how to build them. The project overview, stack and the coding agent tooling are in `README.md`, which imports this file; each rule lives in only one of the two.

## Ground rules

1. **ADK primitives only.** Build agents with `Agent` (an alias of `LlmAgent`), `SequentialAgent` / `ParallelAgent` / `LoopAgent`, `Workflow`, or a custom `BaseAgent`. Do not hand-roll an agent loop, a prompt-chaining framework, or direct `anthropic` / `litellm.completion` calls to stand in for an agent. LLM calls go through ADK.
2. **LLM via LiteLLM, never Gemini.** `model=LiteLlm(model=os.environ["ANTHROPIC_MODEL"])`. No hard-coded model IDs, no `gemini-*` strings, no Google Cloud. The ADK skills default to Gemini and GCP; translate their examples. Check https://adk.dev/agents/models/litellm/index.md for the current LiteLLM configuration.
3. **Check the installed SDK, not just the docs.** The skills and docs can be ahead of or behind 2.13.0. Read `.venv/lib/python3.12/site-packages/google/adk/` before relying on an unfamiliar API. Known mismatch: the cheatsheet says `output_schema` disables tools, but 2.13.0 supports both together (see the note in `agents/llm_agent.py` on `output_schema`).
4. **Look for a recipe first.** For retrieval, approval gates, guardrails, memory, sandboxing and similar, read `.agents/skills/google-agents-cli-adk-code/references/samples.md` and the matching recipe's `AGENTS.md` before designing your own.
5. **No paid calls or external writes without asking.** Anything that calls LLM, including `adk run` and evals, needs approval first, as does any external write (uploads, pushes, posts).

## Design

- **Supervisor + specialists.** A supervisor agent owns the whole task and wraps each specialist in `AgentTool`, so results return to it. Use `sub_agents` transfer only when control is handed off for good.
- **Deterministic steps are not LLM steps.** Fixed ordering, fan-out/fan-in, retries and validation belong in `SequentialAgent` / `ParallelAgent` / `LoopAgent` or a `Workflow` graph, not in a prompt. Use an LLM only where judgment is needed.
- **One job per agent.** Give each agent a distinct `name` (valid identifier, unique in the tree) and a `description` that says when to use it. The supervisor routes on it.
- **Typed hand-offs.** Pass structured data between agents with Pydantic models via `output_schema` and `output_key`, not free text. Parallel agents each get their own `output_key`.
- **Factory functions for sub-agents.** An agent instance can have only one parent. Build agents in `create_*()` functions and call them, rather than sharing module-level instances.
- **Don't build a single mega-agent** with every tool attached. Narrow tool sets make routing and evaluation tractable.

## Tools

- Plain functions with full type hints, no default values, and a clear docstring (the model reads it). Return a JSON-serializable `dict` with a `status` key.
- Take `tool_context: ToolContext` only when you need state or artifacts; don't mention it in the docstring.
- Keep each tool narrow. A tool that reads a regulation page should not also write output files.
- Enforce authorization and approval in code: `FunctionTool(fn, require_confirmation=...)` or `before_tool_callback`. A prompt saying "ask first" is not enforcement.
- Use `AgentTool(agent)` to expose a specialist; make its `description` and (optional) `input_schema` precise.

## Regulatory output rules

The deliverable is engineering requirements with citations. These are enforced in code, not left to the prompt:

- Every requirement carries the **regulation and page** it comes from. A requirement without a citation is dropped or rejected, never emitted.
- Citations must come from tool results (the actual regulation text), not from the model's memory. Verify cited pages exist before output.
- Final submissions pass `industrial-ai-hackathon/tools/validate.py` before upload. Validation is a deterministic step in the pipeline (a function node or tool), not something the LLM is asked to remember.
- Never invent a regulation number, paragraph or page. If the source does not say it, the answer is "not found".

## State and callbacks

- Session `state` carries data between agents. Prefixes: none = session, `user:` = per user, `app:` = app-wide, `temp:` = current invocation only.
- Callbacks (`before_/after_agent`, `before_/after_model`, `before_/after_tool`) are called by keyword, so parameter names must match ADK's exactly. Return `None` to continue or a value to override.
- Use callbacks or plugins for guardrails and logging that must apply regardless of what the prompt says.

## Layout

```
app/                 # agent package; App(name=...) must equal this directory name
  __init__.py        # from . import agent
  agent.py           # defines root_agent
  agents/            # create_*() factories, one module per specialist
  tools/             # tool functions
  models.py          # Pydantic schemas for hand-offs and requirements
tests/
  unit/              # deterministic code only: tools, parsers, validators
  eval/              # behavior checks: datasets + eval config
```

This is the ADK default; change it deliberately, and note the change here.

## Testing

- **Unit tests** (`uv run pytest`) cover deterministic code: tools, parsers, citation checks, schema validation, and that the agent graph composes (see `tests/test_adk_setup.py`, which makes no API calls).
- **Do not assert on LLM wording in pytest.** Output is non-deterministic. Behavior checks belong in ADK evals (`adk eval`, with LLM-as-judge criteria), and eval runs need approval because they are paid.
- Start with 1-2 eval cases, get them passing, then widen.
- Report what was actually run versus only suggested.

## Running

```bash
uv sync
uv run pytest            # offline
uv run adk run app       # one-off smoke test (paid; ask first)
uv run adk web .         # dev UI (paid when you chat; ask first)
```

Use `uv` for everything. Never `pip` directly.

## Out of scope unless we decide otherwise

Deployment, publishing, Cloud Trace / observability, and `agents-cli scaffold create/enhance` (ask first; use `--prototype` and strip Gemini/GCP defaults if we do).

## When unsure

Fetch `https://adk.dev/llms.txt` with the `adk-docs` MCP `fetch_docs` tool, then the specific page. Then confirm against the installed package.
