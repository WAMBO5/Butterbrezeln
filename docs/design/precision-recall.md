# Problem statement: too many requirements, then too few

**Date:** 2026-10-24 · **Case:** worked example `dev-rear-lamp` (190 expected requirements, 4 regulations, 53 pages)

## The problem

The pipeline finds the right regulations and almost every right page, but the number of requirements it submits is hard to get right. The first runs produced far too many requirements: most of them were real obligations of the right regulations, but not ones an engineer would list for this product. The fix overshot: it cut the output so far that recall collapsed. The challenge scores requirements with F2, which weights recall over precision, so neither extreme scores well.

## What the runs show

| Run | Requirements | Regulations P/R | Pages P/R | Requirements P/R (platform) |
|---|---|---|---|---|
| 1 | 1,023 | 1.00 / 1.00 | 0.41 / 1.00 | not uploaded |
| 2 | 695 | 0.80 / 1.00 | 0.47 / 0.98 | not uploaded |
| 3 (strict) | 61 | 1.00 / 1.00 | 0.90 / 0.53 | 73.8% / 23.7% (F2 27.4%) |
| 4 (recalibrated) | 173 | 1.00 / 1.00 | 0.87 / 0.89 | pending |

Runs 1 and 2 were cut short by the budget; run 4 re-ran only matching on run 3's product profile and scope plan.

## Why run 2 had too many

In run 2, 74% of the requirements sat on paragraphs the expected answer never cites, while recall was fine (112 of 121 expected paragraphs cited). The extra requirements came from:

1. **Conditional features kept as "uncertain".** Variable intensity, manufacturer logos, triangular retro-reflectors, fail-safe modes: the spec never mentions them. The matcher was told that a silent spec is never a reason to exclude, and uncertain items were submitted (411 of 695).
2. **Test-lab instructions treated as product requirements.** Apparatus, conditioning and test steps. The expected answer keeps only the pass/fail results.
3. **A wrong regulation kept as uncertain.** R128 (replaceable LED light sources) gave 114 requirements, none expected.
4. **Administrative sections in scope.** Approval procedure, conformity of production and sampling.
5. **The budget ran out.** 254 obligations were never matched and were submitted as uncertain. Matching ran once per part, and the analyst had split the lamp into 10 parts.

## Why run 3 had too few

Two strictness changes at once:

- **The matcher prompt excluded too much.** It selected 14% of the candidates. Its "leave out conditional features" rule also dropped conditional obligations of the lamp's *own* functions ("where the lamp is mounted below 750 mm…"), installation rules (tell-tales, electrical connections) and R10's emission limits (1 submitted, 32 expected).
- **A strict submit policy held back the 51 medium-confidence items,** although they were about as precise as the submitted ones.

With 61 requirements, recall could not exceed 32% even at perfect precision.

## What run 4 changed

- **The matcher selects only obligations that bind the parts,** each with a confidence. The general rules:
  - **Keep:** requirements on the part's own device type and function, its installation, conditional obligations about the part itself, and the limits it must reach in tests.
  - **Leave out:** other device types, add-ons the spec doesn't mention, other vehicle categories, test-lab steps and paperwork.
- **The reviewer checks both directions:** wrong selections and clear misses.
- **Code removes administrative provisions** and matches only applicable regulations.
- **Sections are matched once per group of parts,** not once per part.
- **The submit policy defaults to high and medium confidence.**

## Measuring without uploading

Uploads are limited to 5 per hour, so every change is measured offline first.

- **Regulations and pages:** `industrial-ai-hackathon/tools/score_local.py`. `certivity score <run_dir>` calls it, and every run report shows it. It does not score requirements. Run 4 gets 0.87 / 0.89 on pages but only about 0.64 / 0.58 on requirements, so page scores cannot tune the requirement count. The tool itself says it is for catching gross mistakes, not for tuning.
- **Requirements (estimate):** map every submitted and every expected requirement to its paragraph in the corpus. Matched = the sum over paragraphs of min(expected there, submitted there); precision = matched / submitted, recall = matched / 190. Free, no model calls. Checked against the platform: run 3 is estimated at P 0.754 / R 0.242 / F2 0.280; the platform gave 0.738 / 0.237 / 0.274.
- **Requirements (judge):** `certivity score --judge` asks an LLM to compare meanings. It is paid; use it only to confirm a change the estimate already favours.

| Run | Requirements | P (est.) | R (est.) | F2 (est.) |
|---|---|---|---|---|
| 1 | 1,023 | 0.161 | 0.868 | 0.463 |
| 2 | 695 | 0.233 | 0.853 | 0.557 |
| 3 | 61 | 0.754 | 0.242 | 0.280 (platform 0.274) |
| 4 | 173 | 0.642 | 0.584 | 0.595 |

## What the golden set shows

Run 4's 818 candidate obligations were labelled against the 190 expected requirements: an obligation counts as expected when its paragraph is cited in `expected.json`. That makes about 800 labelled examples for one product.

1. **The section decides most of it.** No expected requirement sits outside the sections about the product's own device types and functions. Inside those sections, 55% of the obligations in the main text are expected and 14% of those in annexes.
2. **Conditional obligations are kept even when the spec does not mention the feature:** logos, replaceable light-source modules, optional lamps, reciprocally incorporated lamps, "where the lamp is mounted below 750 mm". The run 4 matcher prompt tells the model to leave exactly these out.
3. **Markings on the product are kept:** approval-mark placement, the sequential number, the Unique Identifier format, the mounting-side arrow.
4. **Test parameters that define a pass/fail result are kept** (13.5 V test voltage, signal modulation, salt mist at 35 °C, weathering cycles). **Lab logistics are not** (sample groups, masking stray reflections, what to do when results are challenged).
5. **Conformity-of-production tolerances are kept** ("shall not deviate unfavourably by more than 20 per cent"), and so are restrictions phrased as permissions ("may be installed on movable components only if …").
6. **Left out:** other device types; other classes, colours or categories of the same device (S3/S4, amber, Class C–F); other vehicle categories; paperwork for the applicant or the authority.
7. **The expected answer is not exhaustive.** It leaves out some plainly relevant obligations (rear retro-reflector height, reversing-lamp geometric visibility), so precision cannot reach 1.0 and single misses are not worth chasing.

## What F2 implies

F2 rewards a requirement as long as its chance of matching an expected one is above about F2 / 5, roughly 13% at the scores we reach. The data agrees:

- Adding the conditional obligations run 4 dropped (about 45% match) raises the estimated F2 from 0.60 to 0.69.
- Adding all annex test obligations (about 5% match) lowers it to 0.52.

So for each obligation, ask **"is there a positive reason to exclude it?"**, not "is it proven to bind the part?". Medium- and low-confidence items belong in the submission.

## Where run 4 loses recall

| Cause | Expected requirements lost | Fix |
|---|---|---|
| Matcher drops conditional obligations and markings | ~37 | Silence in the spec is not a reason to exclude |
| Lists and tables in one paragraph are not split one row per requirement (R10 6.9.1: 10 expected, 3 extracted) | ~15 | Extractor granularity |
| Extractor drops "may … only if" restrictions | 3 | Extract restrictions phrased as permissions |
| Administrative filter drops conformity-of-production tolerances | 3 | Let tolerance limits through |
| Section never selected (R10 6.10 "Exceptions") | 2 | Section selection |
| Parser labels a marking provision as administrative | 1 | Parser kind |

Estimated F2: run 4 is 0.60; adding markings and conditional obligations gives 0.70. If the matcher kept every expected-paragraph obligation that is not about another subject, it would reach about 0.81.

## Adjustments for run 5

1. **Classify by exclusion, not by inclusion.** In a relevant section every obligation is included by default. The matcher may exclude one only by naming a reason from a closed list, together with the words that prove it:
   - another device type;
   - another class, colour or category of the same device;
   - another vehicle category;
   - the spec states the opposite (silence does not count);
   - lab procedure;
   - paperwork.

   It also tags the obligation's role: requirement, conditional requirement, test parameter or pass criterion. Code turns reason and role into a match probability, using a table calibrated on the worked example, and submits everything above about 13%. A prompt-only version (reverse the silence rule, keep markings and test parameters, submit every confidence level) is the quick fallback.
2. **Keep markings on the product** and **test parameters that define a pass criterion**; drop lab logistics.
3. **Submit every confidence level** that passes the threshold; the strict policy goes.
4. **Extractor:** one requirement per list item or table row; extract "may … only if" restrictions.
5. **Administrative filter:** let conformity-of-production tolerance limits through.
6. **Section selection:** include the exceptions and general provisions of a cross-cutting regulation that applies.

Each adjustment is measured on its own with the requirement estimate before the next one.

## Guarding against overfitting

All tuning so far uses one worked example; the held-out case (a front bumper) decides the ranking.

- **Prompts stay general.** A test fails if any agent prompt names a regulation, a paragraph or a count target. It caught two leaks, both since removed.
- **One change at a time.** Run 4 changed only the matcher; the profile and scope were reused from run 3.
- **Gains must hold across regulations.** In run 4, recall rose in all four regulations: R10 3% → 44%, R148 25% → 51%, R150 26% → 62%, R48 34% → 71%.
- **Exclusion reasons name no regulation.** They describe kinds of mismatch (device, class, vehicle category, lab, paperwork), so they carry over to a product under different regulations.
- **Leave one regulation out.** Calibrate the probability table on three regulations and check it on the fourth before trusting it.

## Open questions

- **What does the platform score run 4 at?** It's the first run aimed at the middle. The offline estimate is P 0.64 / R 0.58 / F2 0.60.
- **The held-out front bumper probably falls under whole-vehicle regulations** (external projections, protective devices, pedestrian safety), whose requirements are mostly test pass criteria. Keeping pass criteria and the parameters that define them matters even more there.
- **R48 is the least precise** (57% of its requirements on expected paragraphs). Its installation rules attract neighbouring lamp functions.
- **Does the calibration carry over to a product with no lighting at all?** Only the held-out case will tell.
