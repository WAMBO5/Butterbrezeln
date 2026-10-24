# Instructions for use (Art. 13)

## Intended purpose

Certivity drafts the engineering requirements a vehicle component must meet under the UN Regulations in its corpus, from the component's specification and/or exploded view. Each requirement cites the regulation, version, page and paragraph it comes from. The draft is a starting point for homologation and design engineers, who review it and decide.

It is not intended to decide type approval, to replace a technical service, or to judge whether a physical part complies.

## Users

Homologation, compliance and design engineers who can read UN Regulations. No personal data is needed or requested.

## Modes

- **Assisted** (product use): the run pauses for your review of the product profile (C1), the chosen regulations and sections (C2) and the final requirements (C3). You confirm, change with a reason, or stop. A named sign-off (C4) is required before the export counts as reviewed.
- **Benchmark** (challenge use): the run does not pause. Everything it produces is labelled *Unreviewed AI draft — not for compliance use*.

## Limits

- Only the UN Regulations of the corpus (`regulations/index.json`) are known: no national law, no standards, no other regulations.
- Requirements cite the base version of each regulation. The latest versions are used only for the illustrative market view and the sub-goal.
- Markets are illustrative samples with made-up names, not real law.
- Evidence is judged from the specification only. *Evidence needed* means the specification does not show it; it does not mean the part fails.
- A run that reaches its budget is partial: later items are kept as uncertain and the report says so.
- Uncertain items and disagreements between the agents are kept and marked, never hidden.

## How to review and sign off

1. Read the product profile: are all parts there, with the right properties? Remove or correct with a reason.
2. Read the excluded regulations as well as the kept ones. The ones the full-text search ranked high for a part come first.
3. Open the citation of any requirement you rely on: the page text opens with the quote highlighted. "Why is this here?" shows the chain from your product to the page.
4. Decide every open item (uncertain, disagreement, give-up), then sign off with your name.

## Declared accuracy

Measured on the worked example (the rear lamp) with the latest `bench` run. The requirement-level score is judged on the challenge platform and is not included here.

<!-- metrics:start -->
Latest bench run `20261024T170226656653Z-dev-rear-lamp` (benchmark mode, 2026-10-24T17:10:47.701493+00:00).

| level | precision | recall | F1 |
|---|---|---|---|
| regulation level | 0.800 | 1.000 | 0.889 |
| page level | 0.474 | 0.981 | 0.639 |

- Golden regulations kept by the scope plan: 4/4.
- Golden pages inside the chosen sections: 100.0%.
- Golden requirements with a similar extracted obligation: 74.7%.
- Requirements: 695 (654 applicable and 816 uncertain part decisions).
- Cost: $4.92 (partial run: the budget was reached).
- Validation with `tools/validate.py`: no problems.
<!-- metrics:end -->
