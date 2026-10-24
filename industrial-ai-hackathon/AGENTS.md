# Agent Instructions

## Project goal

Build a demo for the Certivity Industrial Agents Hackathon that takes a product specification and/or exploded view and returns applicable engineering requirements with verifiable regulation, version, and page citations. Read `PROJECT_PLAN.md` for the current plan and explicit open decisions.

## Scope and source of truth

- The challenge package is the source of truth for allowed regulations, versions, case inputs, schemas, validation, and scoring.
- Use `regulations/index.json` as the final-output allowlist. Do not cite external regulations in a challenge submission unless the organizer changes the rules.
- For page citations, use the exact PDF downloaded for the cited regulation/version. Preserve PDF page and paragraph identifiers through extraction and retrieval.
- Main-goal benchmark requirements use the base version. Do not substitute a latest-version page.
- Keep source wording separate from generated engineering wording. Every generated obligation must be traceable to one or more source provisions and product facts.
- Regulation (EU) 2018/858 is a possible internal product classification/applicability aid. Verify any Annex II interpretation and edition before encoding rules. It is not part of the submission citation allowlist in the current challenge package.
- Do not add external legal corpora, case-law datasets, or crawlers to the hackathon MVP without an explicit team decision.

## Product behavior

- Separate one-time functionality-group catalog preparation from per-product applicability decisions.
- The candidate catalog should favor recall; the final adjudicator should remove candidates unsupported by the product facts or legal scope. Do not pad the result with speculative obligations.
- Keep explicit states for applicable, not applicable, and uncertain. Never silently infer missing product attributes.
- Emit one engineering obligation per final requirement. Preserve scope, conditions, exceptions, quantities, and units.
- Keep candidate retrieval, applicability judgment, requirement writing, citation verification, JSON validation, and UI presentation as separate stages.
- The held-out demo must run from its provided input to results without manual file edits.

## Data and Git hygiene

- Downloaded PDFs and generated regulation text are local challenge data. Do not stage or commit them by default; check `.gitignore` and Git status before preparing a commit.
- Commit extraction/search code, dependency manifests, schemas, prompts, and project documentation as agreed by the team.
- Do not remove source PDFs or modify source challenge files to make extraction or scoring easier.
- Keep the text extraction page markers intact. Any later preprocessing must retain a path back to the original PDF page and paragraph.
- Respect `LICENSE-DATA.md`; challenge data is for hackathon use only.

## Working agreement

- Preserve the four workstream ownership areas in `PROJECT_PLAN.md`; coordinate changes at module boundaries.
- Record assumptions and unresolved choices rather than treating brainstormed ideas as approved requirements.
- Avoid creating extra agents, services, or external dependencies unless they materially improve the held-out result and can be explained in the demo.
- Keep the main-goal path ahead of optional version comparison and future multi-region features until the end-to-end MVP works.
- Before submission, validate the JSON and inspect its sources. Use the worked example to diagnose regulation-, page-, and requirement-level errors separately.
- Do not upload a replacement held-out result unless it is valid and the team has reviewed it; the last valid held-out upload counts.

