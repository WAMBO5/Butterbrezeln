# Backend plan

Backend for the Certivity hackathon demo. Two LangGraph pipelines share one functionality vocabulary. The legal pipeline indexes UN texts in Qdrant and can be re-run when a file changes. The product pipeline turns a spec and an exploded view into components and functionalities, retrieves every provision that is even loosely connected, judges it, and writes cited obligations.

The hackathon upload is a requirements JSON built from market slice `unece_all`. Markets and recommendations are a demo capability and are never uploaded.

This document is the backend build contract. UI layout lives elsewhere. The API section is the contract the UI calls.

## Decisions

Taken 24 October, 16:45–17:30.

| Topic | Decision |
|---|---|
| Stack | LangGraph orchestration, Anthropic Python SDK called directly. No ADK, no LiteLLM. |
| Retrieval | A functionality agent rewrites the product and its components as functionalities and queries. Qdrant hybrid search finds every connected regulation and provision. Judges filter. |
| Before the held-out upload | Export path, sub-goal, evidence UI. Everything else after 13:00. |
| Markets | Several selectable markets, demo only, outside the hackathon scope. Never affect the export. |

## Stack

- Python 3.12, `uv`, root [pyproject.toml](../pyproject.toml).
- LangGraph. Nodes are plain typed functions. No LangChain agent, CrewAI, or open planner.
- Every LLM call goes through `pipeline/llm.py` on the Anthropic SDK:
  - structured outputs into Pydantic models: the schema goes into `output_config.format` (what `messages.parse` sends), but the call is `create` and the reply is validated in `llm.py`, so `stop_reason` is read first. A refusal is an `LLMError`; a reply cut off at `max_tokens` is a `TruncatedError` (retrying the same request fails the same way, so callers split the batch);
  - prompt caching on the stable prefix (rubric, then product profile), varying content after the breakpoint;
  - depth via `output_config.effort` (`low` for triage). No `temperature` or `top_p`: the 5.5 models reject non-default values;
  - transient failures (429, 529, 5xx, timeouts): the SDK retries briefly (`max_retries=3`), then `llm.py` waits and sends the same request again (30, 60, 120, 240 s, outside the semaphore); only if that also fails is an `APIUnavailableError` raised, which callers must not answer with more requests. Bounded concurrency is one semaphore. An explicit per-request timeout (600 s, 10 s to connect) is required: without it the SDK refuses non-streaming calls it estimates at over 10 minutes. A wrong key or model id still stops the run;
  - disk cache keyed by model plus request hash. Sampling cannot be pinned, so the cache is what makes a run reproducible.
- Model ids are plain (`claude-opus-5-5`, `claude-haiku-5-5`). Strip a leftover `anthropic/` prefix.
- Qdrant via `qdrant-client`. Collection `provisions`. Local path `QDRANT_PATH` (default `data/qdrant`). `QDRANT_URL` and `QDRANT_API_KEY` use the same client against a server.
- Embeddings are local `fastembed`: dense `BAAI/bge-small-en-v1.5` (cosine, 384), sparse `Qdrant/bm25`. Qdrant stores them; hybrid query (dense + BM25 with IDF, reciprocal rank fusion) runs over an in-memory copy of the stored vectors, because local-mode Qdrant evaluates filters point by point in Python (10 to 16 s per query). With a Qdrant server (`QDRANT_URL`) the same method works unchanged.
- `python -m pipeline.run` checks before any paid call that every base version is fully indexed (point count equals parsed provision count) and that the store can be opened.
- PyMuPDF for text and tables, `rapidfuzz` for alignment, `jsonschema` for `validate.py`.
- FastAPI for the run API. Organizer scripts in [tools/](tools/) stay unchanged and are called as subprocesses or imported only for validation and local scoring.
- Failure policy: a failed LLM batch never aborts the run and is never silently dropped. It is logged (`batch_failed`), counted in the result (`failed_batches`) and, for content failures (`LLMError.splittable`: refusal, truncated or malformed reply, rejected request), retried as smaller batches (judge, writer). Whatever still fails stays visible: unjudged provisions are labelled `unjudged` (never exported), unwritten ones are listed in the `writer_lost` trace row. The disk cache is read defensively (a corrupt file is a miss) and written atomically; a request that ran into `max_tokens` leaves a `.truncated` marker so a re-run does not pay for it again (delete the marker to retry). Triage is the one deliberate exception: a failed triage batch keeps all its candidates, since triage only saves judge calls.
- Config from the environment: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_MODEL_FAST`, `TEAM_ID` (default `team-04`), `HACKATHON_DIR` (default `industrial-ai-hackathon`), `QDRANT_PATH`, optional `QDRANT_URL`, optional `QDRANT_API_KEY`.

`ANTHROPIC_MODEL` does vision, functionalities, regulation applicability, judging, obligation writing, citation re-evaluation, and recommendation wording. `ANTHROPIC_MODEL_FAST` does triage and tagging.

## Agents

Every node is a LangGraph node. **Agent** means a LLM call through `pipeline/llm.py`; *step* means deterministic code.

Legal pipeline (re-run when PDFs change):

- *Ingest and parse step*: turns each PDF into page-marked, normalised provisions with paragraph id, page, heading path and tables, and upserts them into Qdrant.
- **Version-diff agent** (sub-goal): aligns old and new provisions, renumbered ones included, and proposes `modified`, `removed` or `added` for the old requirements, with a reason.
- **Function tagger agent** (P2): labels stored provisions with functionality ids to raise later recall.

Product run (`pipeline.run`):

1. **Component agent**: reads the spec and exploded view and lists parts with stated attributes, unknowns and conflicts.
2. **Functionality agent**: rewrites the product and each part as functionalities in regulatory vocabulary, with search queries; rewrites the queries when coverage has gaps.
3. *Retrieve step*: hybrid search for every query; collects every connected regulation and provision.
4. **Regulation applicability agent**: decides from scope text and top hits whether each connected regulation is applicable, not applicable or uncertain; supersession is then applied deterministically.
5. *Section expansion step*: adds the neighbouring provisions under each hit's numbered heading.
6. **Triage agent** (fast model): discards candidates that are clearly unrelated to the product.
7. **Judge agent**: labels each remaining provision `keep`, `reject` or `uncertain`, keeping conditional obligations with their condition.
8. *Cross-reference step*: attaches the paragraphs, tables and annexes a kept provision refers to.
9. **Requirement writer agent**: turns each kept provision into one-obligation requirements with a verbatim quote, paragraph and page.
10. **Citation re-evaluator agent** (P1): checks conditions and numbers against the cited text; supported, rewrite once, or drop.
11. *Verifier and export steps*: drop rows whose regulation, version, page, quote or numbers fail; write `submission.json`; run `validate.py`.

Demo only (P2): a **matcher agent** marks each requirement `met`, `gap` or `unknown` against part attributes; *envelope and set-cover steps* compute selected-market requirements and the fewest component changes; a **recommendation agent** words those changes.

## Layout

```
pipeline/               at the repo root, not inside the organizer folder
  taxonomy/functions.yaml
  taxonomy/markets.yaml
  prompts/
  llm.py                Anthropic SDK wrapper: parse, caching, effort, disk cache, concurrency
  catalog/              extract, normalise, parse, tables, regulation cards, supersession
  rag/                  qdrant schema, upsert, hybrid query, section expansion, references
  graph/state.py
  graph/tools.py
  graph/legal.py        ingest, tag, version-diff
  graph/product.py      components, functionalities
  graph/map.py          retrieve, applicability, triage, judge, write, re-evaluate, verify
  graph/demo.py         match, envelope, recommend (P2)
  verify/
  eval/
  api/
  run.py                python -m pipeline.run
  legal.py              python -m pipeline.legal
  subgoal.py            python -m pipeline.subgoal
tests/
```

The organizer folder (`HACKATHON_DIR`) is read as data. Runs land in `runs/<case_id>/<timestamp>/` at the repo root. Promote copies only `submission.json` to `out/`. PDFs, `runs/`, `out/`, `data/`, held-out inputs and `.env` stay untracked.

## Shared vocabulary

`functions.yaml` ids are the join key for bindings and markets.

- Ids come from the corpus, not from the two known cases: the 28 device types in R48 §6 (`rear_position_lamp`, `stop_lamp`, `reversing_lamp`, `front_fog_lamp`, `direction_indicator`, `daytime_running_lamp`, `rear_retro_reflector`, …), the device lists in the R148, R149 and R150 scopes, and `lens_colour`, `light_source`, `emc`, `installation_lighting`, `bumper_protection`, `pedestrian_impact`, `external_projection`.
- A functionality that fits no id is `unmapped`. It is still retrieved, judged and traced, and its requirements bind to the component that produced it. Agents may not invent ids.

## Markets (demo only)

A capability outside this hackathon: the corpus is UN Regulations only. Selectable in the UI and labelled as a demo. Built after the 13:00 upload.

`markets.yaml`:

- `unece_all` — every regulation in [regulations/index.json](regulations/index.json). This is the export market.
- `lighting_signal` — UN R148, UN R48, UN R150, UN R10.
- `bumper_pedestrian` — UN R42, UN R127, UN GTR 9, UN R26.
- `china` — `regulation_ids: []`. Empty on purpose. No obligations, no recommendation.

A selected slice filters the envelope and the recommendation payload. It never filters or changes the export. Export always retrieves and judges `unece_all` at `role=base`.

## Legal pipeline

`uv run python -m pipeline.legal`

Re-run when PDFs change. No product input.

### Ingest

1. Read `index.json`. Download is still [tools/fetch_regulations.py](tools/fetch_regulations.py).
2. PyMuPDF writes the existing page-marker format (`=== PDF page N ===` and the `version | page X of Y` header) into `regulations/text/`. This replaces the `tools/extract_regulations.py` named in PROJECT_PLAN.md, which is not in the repo. Verify SHA-256. Skip files that already match. OCR only for a page with no text.
3. Normalise a matching copy of the text next to the raw text: Unicode NFKC (base texts contain 306 `ﬁ` and 153 `²`), hyphenated line breaks joined, whitespace collapsed. Page markers stay untouched. Quotes and citations always map back to the raw page.
4. Parse without a model. A new provision starts at a UNECE paragraph number or an annex heading. Lettered items `(a)(b)(i)` stay children of that paragraph. The citation paragraph is the numbered id (`6.14.5`, `Annex 3 1.2`), not the letter. Tables come from `page.find_tables()` and attach to the nearest provision on the same page. Record start page and page span. Rules that matter (each came from a bug found in review, and each has a test):
   - Numbering is tracked per level: the highest child seen under every accepted paragraph. A numbered line is a paragraph only if it is the next, or a near-next, child of a known parent. Wrapped lines that start with a number (`1. The objective luminous flux ...`), table rows (`5 Functional hinge`, `9 FAIL FAIL`) and a bare `8.` are therefore never paragraphs, and one stray match cannot derail the rest. Top-level numbers in the main body must be short headings; unpunctuated numbers (`5.7 Grouped, ...`, `1 Scope`) must be exactly the next number.
   - More shapes found by the second review round: `ANNEX 1 COMMUNICATION` in capitals (R32), a non-breaking hyphen in `Annex 13 - Appendix 4`; unpunctuated paragraphs such as `2.4 "Floor line" means ...` (any length, a capital or a quote, exactly the next number); lower-case list items after a line ending in `:` or `;` (`3.1.2.1. the length and width`) unless they open with a wrapped-reference word (`above`, `of`, `to` ...); a bare number or `(a)` right after a line ending in `paragraph`, `and` or `to` is a wrapped reference; main-body `Appendix N Title` sections (R10, R49); form fields with dot leaders (`Trade name or mark ......`) are flagged `rationale`, never retrieved.
   - Annex headings come in many shapes: `Annex 1a Information document`, `Annex 4 - Part I TITLE`, `Annex 6 Appendix 2 - Title`, `Annex 8 (reserved)`, a bare `Annex 5`. A heading needs a capitalised title (so `Annex 2 to this Regulation.` is a mention, not a heading), and annexes only advance, by at most two numbers. Annex paragraphs are labelled `Annex 6 Part 4 4.1`.
   - Text before the first paragraph (the introduction) becomes a provision `Introduction` flagged `rationale`: it is kept for the regulation card and never retrieved or cited. UN GTRs open with a long rationale part that is flagged the same way.
   - A corpus-wide test checks that every strict-looking annex heading in all 56 base texts opens an annex, and that no regulation we rely on has a provision that swallows its neighbours (before: UN R26 had one of 10,900 characters).
5. Upsert Qdrant. Point id is UUID5 of `provision_id`. Payload:

- `provision_id`, `regulation`, `role`, `version_label`, `page`, `page_span`, `paragraph`, `section`, `heading_path`, `text`, `text_norm`, `children`, `table_text`, `function_ids`

A version counts as indexed only when the stored `(provision_id, paragraph, section, page)` of all its points equal what the parser produces now, so an index built by an older parser, a partial index or leftover points are all re-indexed (a count check missed those). Re-indexing reuses the stored dense vector of every provision whose BM25 vector (cheap, deterministic) is unchanged, so only provisions whose text changed are embedded again; the old points of a version are deleted only after the new ones are computed. Embedding uses half the logical cores (`EMBED_THREADS`), measured 3 to 5 times faster than onnxruntime's default (about 10 to 15 texts per second on this machine, so a full index from scratch takes about 45 minutes).

Payload indexes: `regulation`, `role`, `version_label`, `paragraph`, `section`, `function_ids`. `section` is the numbered heading a provision sits under (`6.10` for `6.10.4.1`, `Annex 6 Part 4` inside that annex); section expansion filters on it.

Regulation-level function hints are written on ingest (R148 lighting groups, R10 `emc`, R42 `bumper_protection`, R127 and UN GTR 9 `pedestrian_impact`, R26 `external_projection`, R48 `installation_lighting`, R150 `rear_retro_reflector`). Hints are recall aids, not a keep decision.

### Function tagger (P2)

Incrementally label `function_ids` on points the mapping graph retrieved, then upsert those payload fields. `python -m pipeline.legal tag --all` sweeps the collection. Not needed before the held-out upload.

### Version-diff agent

`uv run python -m pipeline.subgoal --case subgoal/dev`

This is the legal pipeline noticing a new file. It is also the hackathon sub-goal.

1. Parse old and new with the same parser.
2. Align on normalized paragraph ids. If the id moved, align by text similarity (`rapidfuzz`) before calling the pair removed-plus-added (R175 `6.5` becomes `6.6`).
3. Map each row of [subgoal/dev/requirements_old.json](subgoal/dev/requirements_old.json) by `source.paragraph`, with page as a hint.
4. Unchanged text emits nothing. Modified text proposes `modified` plus `new_text` and a reason. A removed provision with no alignment proposes `removed`. A new obligation with no old requirement proposes `added` and `requirement_id: null`.
5. Re-read old and new text once. Drop a row whose `change` label does not match the delta. Drop `modified` when the obligation text did not change. Drop `added` when it restates an old requirement.
6. Score locally (id recall, exact `change` match, unmatched `added` count) and run `tools/validate.py --requirements-old`.

Gold file [subgoal/dev/expected.json](subgoal/dev/expected.json) has 24 changes (17 `added`, 6 `modified`, 1 `removed`). Unchanged requirements must not be emitted.

### Supersession

Each consolidated regulation names its predecessors in the Introduction, not in its scope: "This Regulation combines the provisions of … UN Regulations Nos. …". Parse that sentence into `supersedes` on the regulation card.

- R148: 4, 6, 7, 23, 38, 50, 77, 87, 91.
- R149: 19, 98, 112, 113, 119, 123.
- R150: 3, 27, 69, 70, 104.

Drop a predecessor only when its successor is applicable. R48 is never dropped because R148 exists. The rear-lamp export must not cite R3, R6, R7, R23, or R38 when R148 and R150 are kept.

### Parser gate

Every gold citation in [cases/dev-rear-lamp/expected.json](cases/dev-rear-lamp/expected.json) for UN R10 7.2.0, UN R48 9.3.0, UN R148 1.6.0, and UN R150 1.2.1 must be found on that base version, using the paragraph normalizer from [tools/score_local.py](tools/score_local.py). `Annex 8 2.1` matches `annex 8, 2.1.`. `5.4.2.3` does not match `5.4.23`.

## Product pipeline

First stage of `uv run python -m pipeline.run --case cases/dev-rear-lamp`.

### Component agent

Read `spec.md`. If `exploded_view.png` exists, send it to `ANTHROPIC_MODEL`. Emit:

- `id`, `name`, `parent_id`
- `attributes` that the spec or image states
- `unknowns`
- `conflicts` when spec and image disagree; keep both
- optional `hotspot` `{x, y, w, h}` in 0–1 image coordinates (P2)

Do not invent vehicle category, materials, or a manufacturer role. The root node is the product assembly.

### Functionality agent

Rewrites the product and each component as functionalities. Per functionality:

- `id` — a `functions.yaml` id or `unmapped`
- `statement` — what it does in regulatory vocabulary ("emits red light to the rear to show the vehicle's presence and width")
- `component_ids`
- `queries` — the label, a regulatory paraphrase, and one made-up sentence phrased like a UN "shall" provision

Statements use only facts from the spec or image; product context (vehicle category, mounting position) is included when stated. For the rear lamp, stop lamp, rear position lamp, reversing lamp, retro-reflector, lens, and LED module must receive the matching ids. A part with no evidence stays ungrouped. Installation obligations bind to the assembly root later, not to a fastener.

The functionality agent also owns query rewrites in the coverage loop.

## Mapping graph

Second stage of `pipeline.run`. Caps live on graph state: `max_retrieval_rounds = 3`, `max_requirement_rewrites = 1`.

### Tools

Tool results are provision records, not model summaries.

- `search_provisions(query, regulation_ids, k)` — hybrid query, `role=base` on the export path.
- `read_provision(provision_id)` — text, children, tables, heading, page span.
- `read_page(regulation, version, page)` — page-marked text.
- `lookup_reference(regulation, version, ref)` — payload filter for `paragraph 5.8.1`, `Table 4`, `Annex 3` inside the same version.
- `regulation_card(regulation_id)` — title, version label, role, scope text, `supersedes`.

The citation re-evaluator may call `read_provision` and `lookup_reference`. It may not introduce a regulation that was not retrieved or named in the cited text.

### Retrieve

Too many hits is expected. Recall comes first; the judges filter.

1. **Connected regulations.** Run every query through a global hybrid search on `role=base` with a high k (start at 200). Every regulation with a hit is connected. Load its card.
2. **Regulation applicability.** `ANTHROPIC_MODEL` reads each connected regulation's card and top hits against the product facts and labels it `applicable`, `not_applicable`, or `uncertain` with a reason. Then apply supersession. Write `route.json`. Do not drop a connected regulation without a trace row.
3. **Provisions.** Inside each applicable or uncertain regulation, search every query with `k = 40`.
4. **Section expansion.** Deterministic. A hit pulls in the other provisions with the same `section` (a hit on R48 `6.10.4.1` adds the rest of `6.10`). Cap at 80 provisions per section; log when the cap cuts.
5. **Triage.** `ANTHROPIC_MODEL_FAST` drops candidates that are clearly about another device, vehicle category, or topic. Write `retrieval_grades.jsonl`. Triage never drops a provision that shares a section with a hit graded relevant.

### Judge

`ANTHROPIC_MODEL` labels each remaining candidate `keep`, `reject`, or `uncertain` against the component facts and the scope.

- `keep` markings, photometric limits, colour, installation, test limits, and EMC when they constrain this product.
- `keep` conditional obligations, with the condition carried into the requirement text. The gold does this: G-0094/95 ("where optional lamps are installed"), G-0109/110 ("where a rear side-marker lamp is installed"), G-0143/144 (both the 12 V and the 24 V profile).
- `reject` other lamp functions, filament-only rules on an LED lamp, definitions with no obligation, and other vehicle categories.
- `unjudged` is set by code, never by the model: the judge call failed (also after splitting the batch) or skipped the ref twice. Never exported.
- `uncertain` only when the whole provision depends on a missing product fact that cannot be written as a condition. Before Sunday, measure exporting versus withholding `uncertain` rows with two dev uploads; F2 favours exporting.

If a functionality or an applicable regulation has no `keep`, and rounds remain, the functionality agent rewrites its queries using scope words from `keep` and `reject` hits that are still on-topic. Do not invent outside vocabulary. At the cap, record the coverage gap and continue.

After the judge, expand cross-references with `lookup_reference`. That step is deterministic.

### Match (P2)

Bind each kept provision to components whose function ids intersect; `unmapped` functionalities bind to their own components. Assembly-level installation provisions bind to the root.

- `met` — a stated attribute satisfies the obligation (red-tinted lens versus “shall emit red light”).
- `gap` — a stated attribute contradicts it.
- `unknown` — the spec is silent. Unknown is not a redesign and is not a recommendation input.

### Envelope (P2)

Computed only for the user-selected slices whose `regulation_ids` are non-empty.

- Same quantity on two slices: keep the stricter threshold and cite every slice that states a threshold.
- Different quantities: keep the union. Do not merge them into one number.
- `china` is reported as not in the envelope.

The export does not use the envelope.

### Requirement writer

One engineering obligation per row, from `unece_all` provisions labeled `keep`, base version only. Several rows may share a paragraph when the paragraph has several obligations (R48 `6.14.5` is two gold rows). Tables become rows (R150 Table 3, R10 Tables 3a/3b). Each draft carries a verbatim quote from the raw text.

Citation re-evaluation with `ANTHROPIC_MODEL` (P1):

- `supported` — obligation, conditions, and numbers are in the cited text.
- `rewrite` — the obligation is there but a condition or number is wrong. One return to the writer. The citation stays on that provision unless the numbers live in an already attached cross-reference.
- `drop` — the obligation is not in the cited text. No new corpus search from this node.

Marking obligations that are in the text stay `supported`.

### Verifier

Deterministic, after the model nodes. Fail closed: drop and log, do not ask the model to patch. Compare normalised text on both sides.

- Regulation and `version_label` exist in `index.json`, and the role is `base`.
- The cited page is the provision's first page, as in the gold file (all its multi-page provisions cite their first page); it must be inside that PDF.
- Paragraph key matches a parsed provision.
- The evidence quote has at least 20 characters and, normalised, is a substring of the normalised provision plus attached table and cross-reference text. A quote written with an ellipsis (`...`, `[...]`) is matched fragment by fragment, in order, each fragment at least 10 characters.
- The draft text must be supported by that evidence: at least 45% of its content words occur in the provision, its heading path or the attached references (every gold row is at or above 50%).
- Every numeric token in `text` appears in that evidence, or in the numbers of the provision's children, parents and (main body) siblings. Numbers are canonical first: `1,200`, `1 200` and `1200` are equal, `3.00` is `3`, a power of ten is evaluated whatever its spelling (`10^3`, a superscript exponent, or the exponent flattened by PDF extraction as in `6.0∙101`, all give their value). Digit runs glued to letters (`M1`, `N2`, `UN R48`) are identifiers, not quantities. A draft may read a spaced number joined or split; either reading may be the supported one.
- A fuzzy quote match (extraction artefacts only, score at least 96) must keep the quote's numbers, in order, as a subsequence of the aligned evidence.
- `text` is non-empty and at most 2,000 characters.
- Deduplicate exact normalized text under the same regulation, version and paragraph label. Do not merge distinct obligations.

Drop counts per reason go into `trace.jsonl`, separately for triage, judge, re-evaluation and verifier.

Export shape is [schemas/submission_main.schema.json](schemas/submission_main.schema.json): `team_id`, `case_id`, `requirements[].id/text/source`. `test_case` is omitted. Ids are `R-001` onward. Validate with [tools/validate.py](tools/validate.py). Score with [tools/score_local.py](tools/score_local.py).

### Recommendation (P2)

Input is `gap` bindings on the selected non-empty slices only.

Greedy set cover: pick the component that closes the most selected-slice gaps, repeat until every gap is covered. Effort is the number of components. A change is a synergy when those gaps sit in two or more selected slices.

The change sentence quotes the obligation and names the component. It does not add a millimetre, a material, or a supplier that the provision does not state.

Other loaded slices the user did not select, using the same judged bindings:

- No gaps: already shippable to that slice.
- All remaining gaps on one component: only that component blocks the slice.
- Otherwise: N components still block the slice.
- `china`: no regulations loaded, no change computed.

## API

FastAPI. One process owns the graphs. Disk cache Anthropic calls by model plus request hash. Bound concurrency.

P0 and P1, before the held-out upload:

- `POST /api/runs` — body `{ "case_id" }` or an uploaded spec plus optional image. Starts product graph then mapping graph. Returns `run_id`.
- `GET /api/runs/{run_id}` — stage, trace tail, errors.
- `GET /api/runs/{run_id}/components` — components, functionalities, parent links.
- `GET /api/runs/{run_id}/route` — connected regulations with applicability and reasons.
- `GET /api/runs/{run_id}/requirements` — export rows plus uncertain rows flagged `exported: false`.
- `GET /api/runs/{run_id}/evidence` — query `regulation`, `version`, `page`. Returns page-marked text.
- `GET /api/pdf/{regulation}/{version}` — the local PDF, so the UI (PDF.js) opens `#page=N`. Never committed.
- `POST /api/runs/{run_id}/export` — writes validated `submission.json` into the run folder.
- `POST /api/runs/{run_id}/promote` — copies that file to `out/` only when `TEAM_ID` is set and `validate.py` passes.
- `POST /api/subgoal/runs` — body `{ "case_id": "subgoal/dev" }`.
- `GET /api/subgoal/runs/{run_id}` — changes plus re-evaluation notes.

P2, after the upload (demo only):

- `GET /api/runs/{run_id}/markets` — slices, which are selected, which are empty.
- `POST /api/runs/{run_id}/markets` — set the selected slice ids. Recomputes envelope and recommendations from the judged bindings. Does not re-judge and does not change `submission.json`.
- `GET /api/runs/{run_id}/envelope` — per function, for the selected slices.
- `GET /api/runs/{run_id}/recommendations` — change set, synergies, other-slice sentences.

Run folder files: `components.json`, `functionalities.json`, `route.json`, `retrieval_grades.jsonl`, `decisions.jsonl`, `requirement_reevals.jsonl`, `requirements_trace.jsonl` (quote and match kind per exported row), `verifier_drops.jsonl`, `trace.jsonl`, `submission.json`, `score.json`; P2 adds `bindings.jsonl`, `envelope.json`, `recommendations.json`.

## Build order

Owners are the PROJECT_PLAN workstreams: A regulation data, B product understanding, C matching and evaluation, D app and demo.

P0, Saturday night, in order:

1. A — ingest, normalisation, parser, parser gate.
2. A — Qdrant upsert, hybrid query, section field.
3. B — component and functionality agents on `dev-rear-lamp`, cached.
4. C — retrieve, applicability, section expansion, triage, judge, writer, verifier, export; `validate.py`, `score_local.py`, first dev upload.
5. D — P0 API, PDF route, UI with stages, requirements and page links.

P1, Saturday night:

- A — sub-goal pipeline after the parser gate; local score and `validate.py`.
- C — citation re-evaluation; calibration on dev (at most 5 uploads per hour); the `uncertain` export comparison.

P2, after the 13:00 upload: markets, envelope, recommendations, match, hotspots, tagger sweep.

## Gates

1. Parser recovers gold paragraph keys for R10, R48, R148, and R150.
2. Applicability and judge recall of those four regulations on `unece_all` is 1.0.
3. Retrieval stops at three rounds. Requirement rewrite happens once.
4. `score_local.py` regulation recall is 1.0, then raise precision by dropping predecessors.
5. Paragraph-key recall is the offline stand-in for requirement recall. Log drops from triage, the judge, the citation re-evaluation, and the verifier separately.
6. The requirement-level score of a dev upload is recorded before Sunday.
7. Recommendation fixture (P2): two slices, one shared component gap, one synergy, and an “only this component” sentence for the unselected slice. `china` adds nothing.
8. Sub-goal local scorer, then `validate.py` on every promoted file.

Do not tune to gold ids. If citation re-evaluation drops gold paragraphs, loosen the drop rule before raising `k`.

## Tests

- Paragraph normalizer matches `score_local.py`.
- Parser fixture from a real R148 page, including an annex id.
- Text normalisation: a quote containing `ﬁ` or `²` passes the verifier's substring and number checks.
- Supersession: the Introduction regex yields the R148 list; R48 is never superseded.
- In-memory Qdrant: upsert, hybrid query, payload filter on `role=base`.
- Section expansion: a hit on R48 `6.10.4.1` pulls in the rest of `6.10`, and the cap is logged.
- Fake judge: all rejects take the rewrite edge, then stop at the cap.
- Fake judge: a conditional obligation is exported with its condition.
- Recommendation set-cover fixture and empty China fixture.
- Verifier rejects a `latest` version, an unknown regulation, and a number that is not in the evidence.
- Sub-goal renumber fixture, and a drop of `modified` when the text did not change.
- Export builder passes `validate.py` on a tiny file.

## Sunday

- Download the held-out zip from the link on screen and unzip it into `industrial-ai-hackathon/`. This repo vendors the organizer package, so `git pull` does not bring it. Held-out inputs stay out of git ([LICENSE-DATA.md](LICENSE-DATA.md)).
- `tools/fetch_regulations.py`, then `uv run python -m pipeline.legal` so new PDFs upsert into the existing collection.
- If the held-out spec is a bumper and the applicability keep-set has none of R42, R127, UN GTR 9, or R26, stop before the writer.
- Promote the `unece_all` JSON only. Do not promote recommendations.
- The last valid held-out upload counts. Uploads close at 13:00. Replace it only when the new file validates and is agreed to be better.

## Out of scope

Non-UN statutes, crawling, case law, a review queue, an unconstrained planner, invented design dimensions, and committing PDFs, held-out inputs or the Qdrant store. Astro screens are not part of this backend plan. The API above is what they consume.
