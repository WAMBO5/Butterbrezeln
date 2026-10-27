# General pipeline: spec to cited requirements for any product

**Date:** 2026-10-25 · **Branch:** `general` (from `pay-to-win` f7dfbf7) · **Status:** sections 3–7 implemented, offline tests pass; not yet measured on a paid run. Decided with the team: role tags at extraction, rule on every obligation and keep unsure, three scope samples, regulations and sections kept at 2 of 3, a separate match tier.

The pay-to-win branch reached 76.9 % requirement F2 on the rear-lamp worked example; fix/precision peaked at 52.5 % with the same architecture. This note keeps what made the difference, removes what was fitted to the rear lamp, and rebuilds the funnel around one principle: regulations prescribe outcomes, specs describe construction.

## 1. What made the dev score

| Principle | Evidence on dev |
|---|---|
| **Unsure stays in, flagged.** Three states; `uncertain` is submitted for an engineer to confirm. | fix/precision dropped unsure items: recall 24–52 %. pay-to-win kept them: recall 80–89 %, precision about the same (50–57 %). |
| **No silent drops.** Every item at every step gets an explicit ruling; a gate rejects gaps. | pay-to-win's match gate raises `missing_decision`; fix/precision's "unlisted = out" lost obligations without a trace. |
| **One requirement per independently verifiable constraint.** Lists, table rows, conditional permissions split; exceptions stay with their rule. | Requirements per cited paragraph: experts 1.57, pay-to-win 1.51, fix/precision 1.34. |
| **Narrow by structure at the top, by meaning at the bottom.** | Regulation and page levels were near-perfect in every run; the requirement level decided the ranking. |
| **The strongest model where judgment is densest.** | Same scope and obligations, matching only: Sonnet 74.0 % → Opus 74.7 % → Opus with the reviewer on every batch 76.9 %. Opus on scope added wrong regulations. |
| **Finish every run.** | A budget stop turned undecided obligations into 695 noisy requirements (49.8 %). |

F2 = 5·m / (4·G + n). An extra requirement raises F2 when its chance of matching exceeds F2/5, about 15 % at our level. This is why unsure items belong in the output. It also matches real compliance work: a missed requirement costs more than one extra to review.

What was fitted to the rear lamp, and goes: lamp nouns and R48-specific rules in the scope, matcher and reviewer prompts ("photometry, light sources", "emergency stop signal", "Presence: mandatory", "illuminant, modulation"), regulation and paragraph numbers in prompts, the exemptions post-step (evidence from R10 only), and best-of-N selection by leaderboard score.

## 2. The outcome principle

A UN Regulation states the **outcome** a device or function must achieve: a behaviour or performance, a threshold, and the conditions under which it is measured. It rarely prescribes construction. A spec describes **construction**: parts, materials, layout. Consequences:

1. **Applicability follows function and behaviour, not spec content.** A requirement binds a part because of what the part is and does: its function, its role on the vehicle, what it emits, what it touches, what it is exposed to. The spec almost never states outcomes, so its silence on one is the normal case and never a reason to exclude.
2. **Design facts in the spec have two uses only:** excluding (the spec shows a feature or class is absent, e.g. LED modules rule out filament-lamp provisions) and evidence status (met, not met, evidence needed).
3. **A test's conditions and pass criteria are part of the outcome**, because they define it (an impact speed, a test voltage, a measuring field, an exposure cycle). A test's procedure and equipment are not: how the lab mounts, masks, calibrates or computes, and what the impactor or instrument must be.
4. **The bridge from spec to regulation is a behaviour profile**: what each part does, emits, absorbs, touches and withstands, where it sits, and which attributes decide its class or category.

## 3. The funnel

| Level | Question | Who | Context | When unsure | Change vs pay-to-win |
|---|---|---|---|---|---|
| 0, once per corpus | Which text is a product outcome or rule at all? | Parser, cards, `obligation_extractor` (Haiku) | One provision batch, its definitions; never a product | tag as an outcome condition (kept) | New `role` tag on every obligation (section 4), cached |
| 1 | What does the product do? | `product_analyst` (Sonnet) | Spec, drawing, a domain-neutral behaviour checklist | list under `unknowns` | Behaviour checklist replaces the lamp-flavoured property list |
| 2 | Which regulations govern these behaviours? | `scope_narrower` ×3 independent samples, `recall_auditor`, full-text safety net | Profile, 56 cards, corpus tools | vote (section 6) | Three samples merged in code instead of one draw |
| 3 | Which sections define outcomes for which part? | same scope samples | Tables of contents | keep the section | Domain-neutral section rules |
| 4 | Is this obligation a product outcome or rule? | code, from the role tag | – | keep | Procedure and administrative obligations never reach the matcher |
| 5 | Does this outcome bind this part? | `requirement_matcher` (**Opus**), `match_reviewer` on every batch | Parts with behaviours and facts, card scope, section path, obligations with role and condition | `uncertain`, submitted | Short prompt about applicability only; no domain examples |
| 6 | Cite and check | code | – | – | unchanged: quote on cited page, `validate.py` |

## 4. Role tags (level 0, product-free)

The extractor tags each obligation once. Code keeps the first four and drops the last two before matching.

| Role | Meaning | Kept |
|---|---|---|
| `outcome` | A behaviour or performance the product must achieve: a limit, a criterion, a threshold | yes |
| `outcome_condition` | A condition under which an outcome is defined or measured: test levels, speeds, voltages, fields, exposure cycles, environmental conditioning the product must withstand | yes |
| `design_rule` | A required or forbidden feature, construction, marking, installation position or geometry | yes |
| `permission` | An allowed design or installation option, with its conditions ("may … only if …") | yes |
| `procedure` | How a laboratory carries out a test: preparing, mounting or positioning the sample, masking, set-up, calibration, recording, calculation; the specification of test equipment; alternative test methods and tests only at the manufacturer's request | no |
| `administrative` | Approval application, documents, numbering, communication, conformity-of-production sampling, modifications, transitional provisions | no |

The rule "when unsure, tag `outcome_condition`" keeps the default on the side of recall. The tags replace the long not-applicable list in today's matcher prompt, and they are the same for every product, so they can be audited once per regulation.

## 5. Matcher contract (level 5)

One decision per obligation, ids copied exactly, enforced by the match gate.

- `applicable`: the outcome or rule binds the part through its function, behaviour, role or installation.
- `uncertain`: it concerns the part's own function, but depends on a design choice or optional feature the inputs neither show nor exclude. Submitted.
- `not_applicable`, only with one of these reasons:
  - `other_function`: it is about another device type or function than the part's;
  - `other_class`: a class, category or variant of the device the part cannot be, given its attributes;
  - `other_vehicle`: vehicle categories the product is not for;
  - `shown_absent`: the inputs show the feature it needs is absent (cite the fact).

Spec silence is never a reason. The reviewer flags `silent_spec`, `wrong_function` and `missed`. A disagreement left after the last retry becomes `uncertain`.

## 6. Scope voting (levels 2 and 3)

Three independent scope samples, each with its own gate and recall audit, merged in code:

- A regulation is **kept** when at least 2 of 3 samples keep it (applicable or uncertain). It is `applicable` when at least 2 say applicable, otherwise `uncertain`.
- A regulation kept by only 1 sample is reported as considered, not matched. One wrong regulation can add over a hundred false requirements (R128 on dev: 114, none expected).
- **Sections:** kept when at least 2 of 3 samples chose them (for any part), and given to every part a sample assigned them to; the union only when no section reaches a majority. First built as the union; the dev run showed requirements from 1-of-3 sections at 7 % on expert paragraphs (2 of 3: 37 %, 3 of 3: 64 %), below F2's break-even of about 15 %, so the rule was changed with the user on 2026-10-25.

## 7. Models and cost

| Agent | Model | Effort |
|---|---|---|
| product_analyst, scope_narrower, recall_auditor, output_auditor | `ANTHROPIC_MODEL` (Sonnet) | as today |
| obligation_extractor | `ANTHROPIC_MODEL_FAST` (Haiku) | medium |
| requirement_matcher, match_reviewer | **`ANTHROPIC_MODEL_MATCH`** (new, defaults to `ANTHROPIC_MODEL`; set to Opus) | medium / high |

A fourth tier variable lets one run use Sonnet for scope and Opus for matching, without a replay. Estimated cost per case: $15–25 (three scope samples about $3, extraction under $1, Opus matching with the reviewer on every batch $10–15).

## 8. Guarding against overfitting

- **Prompt test:** no prompt names a regulation number, a paragraph number, or a dev-case product noun (lamp, stop, reversing, reflector, bumper, bezel, photometry, illuminant).
- **Dev must hold:** within one F2 point of 76.9 % on the platform, checked first with the free paragraph proxy, then one paid run.
- **Smoke tests without an answer key:** the mock front bumper and one product outside lighting. Check the regulations chosen, and that the output reads as outcomes and design rules, not lab procedure.
- **No rule for a single paragraph.** A rule enters a prompt only when it describes a kind of text that every UN Regulation has.

## 9. Implementation order

1. Bring over from `main` (fix/precision): the prompt test, `score --policy`, rerun from a step, the precision-recall note.
2. Extractor: `role` tag, `EXTRACTOR_VERSION` x5; code filter before matching.
3. Matcher and reviewer: the contract in section 5, domain-neutral.
4. Product analyst: behaviour checklist.
5. Scope: domain-neutral rules; three samples and the merge in section 6.
6. `ANTHROPIC_MODEL_MATCH` tier.
7. Unit and fake-model integration tests; prompt test passes.
8. Paid, after approval: dev rear lamp, then the mock bumper.

## 10. Open questions

- Should requirement text be rewritten as "the part shall achieve X under Y", or stay close to the source wording? The experts' text stays close to the source; changing it risks the matching on the platform.
- Do cards need a "regulated outcomes" field, so scope matches behaviours to behaviours? Rebuilding 56 cards costs about $5.
