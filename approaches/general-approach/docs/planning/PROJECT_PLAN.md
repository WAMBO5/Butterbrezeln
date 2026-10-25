# Industrial AI Hackathon Project Plan

**Status:** planning draft for team review  
**Challenge:** Certivity Industrial Agents Hackathon, 24–25 October 2026  
**Primary deliverable:** an end-to-end demo and a valid requirements JSON for the held-out `heldout-front-bumper` case.

## 1. Purpose and success criteria

Turn a product specification and/or exploded view into a concise, reviewable list of engineering obligations that apply to that product. Every submitted obligation must be traceable to an allowed UN Regulation, its exact version, and a page in the supplied PDF.

### Required for the challenge

- Produce a valid main-goal output for `heldout-front-bumper`.
- Cite only regulations listed in `regulations/index.json`, with a valid version label and page number.
- Express one engineering obligation per requirement; retain its conditions and constraints.
- Run a demo end to end from product input to requirements without manual processing steps.
- Show source evidence for each result in the user interface.
- Submit the repository, demo, and organizer-platform answers.

### How success is measured

- The held-out score gives 40% to regulation-, page-, and requirement-level recall/precision. F2 weights recall more heavily, with recall as the tie-breaker.
- The demo and user experience are 20%; the optional version-change sub-goal is 15%; potential impact is 15%; pitch is 10%.
- The brief says not to pad the answer with loosely related obligations. Retrieve broadly to avoid misses, then filter carefully so engineers do not have to remove many false positives.

## 2. Scope and guiding decisions

### MVP scope

- Use the challenge package's fixed corpus and its exact provided PDFs. Do not build a crawler or add a broad external legal corpus.
- Use `regulations/index.json` as the allowlist and version manifest.
- Use precomputed regulation and requirement candidates by product functionality group, then make a product-specific applicability decision at runtime.
- Keep extraction, candidate selection, product adjudication, source checking, JSON validation, and UI review as distinct steps.
- Prioritize the main-goal held-out case. Treat the sub-goal and multi-region comparison as secondary or future work if time is short.

### Source and citation rules

- The supplied PDF for the selected version is the authority for page citations. Keep its page number and paragraph identifier together.
- Distinguish the regulation's base and latest versions. The main-goal benchmark is built on base versions; a page from latest is not interchangeable.
- Keep verbatim provision text separate from any normalized or generated engineering requirement.
- Link each generated requirement to one or more source provisions internally. Select the strongest source for the challenge output's `source` field.
- Treat uncertainty as uncertainty. Do not invent a scope, threshold, value, or citation to make a requirement sound complete.

### Product role and Regulation (EU) 2018/858

The project leaders suggested using Regulation (EU) 2018/858, especially Annex II, to help classify vehicle products and identify relevant regulatory acts. It is a promising routing and applicability reference: it concerns vehicle, system, component, and separate technical-unit approval. Verify the exact Annex II table and the role distinctions before encoding them as rules. The transcript's supplier-versus-assembler interpretation is a hypothesis to verify, not a settled project fact.

For the challenge submission, use 2018/858 only as internal classification context unless the challenge allowlist changes: final citations must come from `regulations/index.json`. Pin the edition/date used for any derived mapping. [Official EUR-Lex text](https://eur-lex.europa.eu/eli/reg/2018/858)

## 3. Current state

- The challenge README, schemas, worked rear-lamp example, and expected output have been reviewed.
- The regulation corpus has been downloaded and checksum-verified: 92 regulation PDFs plus 2 sub-goal PDFs.
- `tools/extract_regulations.py` extracts page-marked raw text into a mirrored `regulations/text/` tree. The current 94 PDFs yielded 5,532 pages of text; the PDFs already had embedded text, so OCR was not needed in this run. The script has an OCR fallback for pages without extractable text.
- Downloaded PDFs and generated regulation text are ignored by Git. Keep them as local, reproducible challenge data; version the extractor and small metadata/code instead.
- The held-out front-bumper case is expected Sunday at 08:00. The brief says held-out uploads close at 13:00 and the pitch begins at 15:00 (event-local time).

## 4. Proposed end-to-end workflow

```mermaid
flowchart TD
    subgraph Prep[One-time data preparation]
        A[Challenge index and PDFs] --> B[Page-preserving text extraction]
        B --> C[Provision records: paragraph, heading path, page, exact text]
        C --> D[Functionality taxonomy and applicability evidence]
        D --> E[Precomputed candidates by function group]
    end

    subgraph Run[Product-specific run]
        F[Specification and exploded view] --> G[Product profile: parts, functions, attributes, unknowns]
        G --> H[Map product to functionality group(s)]
        H --> I[Load precomputed candidate regulations and provisions]
        I --> J[Retrieve broad candidate set: exact terms + semantic matches]
        J --> K[Applicability adjudicator filters candidates using product evidence]
        K --> L[Atomic requirement writer]
        L --> M[Source and version verifier]
        M --> N[Schema validation and submission JSON]
        N --> O[UI: requirements with citations and evidence]
    end

    E --> I
    P[Worked example expected.json] --> Q[Calibration and error analysis]
    N --> Q
    R[Optional: base/latest versions] --> S[Provision diff and requirement change analysis]
```

### Runtime sequence

1. Collect the specification, exploded view, target market/region, vehicle category if known, and manufacturer role if needed.
2. Extract product facts: components, functions, operating context, materials, dimensions, and any explicit standards or constraints. Record which facts came from the text or drawing and which are missing.
3. Map the product to one or more functionality groups and load the precomputed candidate regulations/provisions for those groups.
4. Retrieve a deliberately broad candidate set using exact paragraph/keyword matches plus semantic matching. Keep version and applicability metadata as filters.
5. Have the product-specific adjudicator label each candidate `applicable`, `not_applicable`, or `uncertain`, with a concise reason tied to product evidence and regulation text.
6. Convert applicable provisions into one obligation per output requirement. Preserve scope, conditions, thresholds, units, exceptions, and required state.
7. Verify each source against the allowlist, version label, page marker, and paragraph. Reject unsupported or untraceable requirements.
8. Validate the final JSON and show the result with source evidence in the UI.

## 5. Workstreams and sub-goals

### A. Regulatory data and functionality catalog (one-time preprocessing)

**Goal:** prepare searchable, traceable candidate requirements grouped by function without re-reading the entire corpus for every product.

**Tasks:**

- Confirm the data available for each regulation version and preserve regulation ID, `base`/`latest` role, `version_label`, file name, and checksum.
- Parse the extracted text into provision-level records while retaining exact text, paragraph identifier, heading path, and PDF page.
- Define a compact functionality taxonomy that works across component names and legal wording (for example: exterior lighting, braking, steering, occupant restraint, glazing, bumpers, electrical compatibility).
- For each group, create a high-recall map to candidate regulations and provisions, with evidence and review status. Avoid presenting the candidate map as a final applicability decision.
- Use Regulation (EU) 2018/858 Annex II as a research lead for vehicle/system/component classification after verifying the exact text and role scope.
- Link cross-references between provisions when the referenced text changes how a requirement is read.

**Deliverables:** taxonomy; versioned provision catalog; candidate regulation/provision map; source and extraction metadata.

### B. Product data and functionality classification

**Goal:** convert a spec and optional exploded view into a grounded product profile that can be matched to the catalog.

**Tasks:**

- Extract named parts, assemblies, functions, interactions, attributes, and relevant vehicle/product category.
- Use a vision model for the exploded view to identify visible parts and relationships; reconcile these with the written spec.
- Keep extracted facts linked to the input passage or image region when possible.
- Map each product to functionality group(s); allow multiple groups for multi-function assemblies.
- Track unknown or ambiguous facts rather than filling them in by assumption.

**Deliverables:** product-profile schema; part/function classifier prompt or model; worked-example and held-out-case profiles.

### C. Candidate retrieval, applicability adjudication, and requirement generation

**Goal:** select the relevant obligations for the specific product and produce output that is complete, atomic, and cited.

**Tasks:**

- Build retrieval over provision records with exact-number and lexical search plus semantic search.
- Bias retrieval toward recall, then use the adjudicator to filter candidates using product facts and applicability conditions.
- Require an evidence-based decision for each candidate, including `uncertain` when the input does not support a decision.
- Write one engineering obligation per requirement. Preserve all conditions, exceptions, thresholds, and units present in the source.
- Resolve references to definitions, annexes, or related provisions before finalizing a requirement.
- Verify citation fields against the exact base PDF for main-goal output.
- Keep the optional sub-goal as a separate workflow: align base/latest provisions, identify additions/removals/changes, then map those changes to affected requirements.

**Deliverables:** retrieval and adjudication interfaces; requirement writer; citation verifier; main-goal JSON; optional sub-goal JSON if time permits.

### D. Orchestration, UI, demo, and evaluation

**Goal:** integrate the two streams into a demo that an engineer can follow and that can run without manual data preparation.

**Tasks:**

- Implement the end-to-end run and a clear processing status for each stage.
- Present product profile, matched functionality groups, candidate decisions, final requirements, and source citations.
- Let users open the cited version/page or inspect page-marked extracted text when PDFs are available locally.
- Keep uncertainty and evidence visible; support review without making human intervention a required demo step.
- Calibrate against `cases/dev-rear-lamp/expected.json`; compare regulation, page, and requirement errors separately.
- Run the challenge validator before any upload. Track each held-out output version and avoid replacing the final valid upload with a weaker one.
- Prepare a short demo narrative that shows input, a meaningful applicability decision, a traceable requirement, and known limitations.

**Deliverables:** usable UI; one-command or one-action demo; evaluation notes; submission checklist; pitch/demo script.

## 6. Team of four: suggested ownership

Replace Member A-D with names after the team agrees. Each person owns an output and should pair-review at least one other workstream.

| Owner | Primary focus | First deliverables | Pair review |
|---|---|---|---|
| **Member A - Regulation data** | Text extraction, provision parsing, version metadata, functionality-to-regulation map | Provision schema; catalog for the likely held-out domains; source trace checks | Member C reviews applicability mapping |
| **Member B - Product understanding** | Spec/drawing ingestion, part/function taxonomy, product profile | Product-profile schema; rear-lamp profile; front-bumper profile after release | Member A reviews regulatory terminology |
| **Member C - Matching and evaluation** | Retrieval, adjudicator, atomic requirement generation, validation | Candidate retrieval; decision rubric; expected-example error log | Member D reviews integration behavior |
| **Member D - App and demo** | Astro UI, orchestration, citations, demo flow, pitch | End-to-end screen; API/workflow integration; demo script | Member B reviews product interaction |

**Shared responsibility:** all four review the final held-out output, validate the file, and agree that every submitted requirement has a defensible source. Keep one person as release captain on Sunday; the release captain does not work alone on content review.

## 7. Event-time plan

### Before Sunday 08:00

- Freeze the data contract, product profile, and functionality group IDs.
- Complete one end-to-end run against the worked rear lamp and record main failure modes.
- Ensure generated data is reproducible from the downloaded package; do not require PDFs to be checked into Git.
- Exercise the UI with a sample product and ensure a citation opens the matching page/version.
- Prepare a held-out run checklist and assign a release captain.

### Sunday 08:00-13:00

- **08:00-09:00:** download/unpack held-out material and fetch any newly referenced PDFs; create the product profile and candidate set.
- **09:00-11:00:** run end to end; review high-impact uncertainty, omitted functions, duplicates, wrong versions, and page/paragraph references.
- **11:00-12:00:** validate the candidate JSON, inspect citations, and prepare a safe valid upload.
- **By 13:00:** submit the best supported final output. The brief says the last valid held-out upload counts, so only upload a replacement after checking it is better and valid.
- **13:00-15:00:** freeze the scored artifact; rehearse the demo and prepare evidence/limitations for the pitch.
- **15:00 onward:** pitch if selected.

The times above are a suggested allocation within the brief's stated Sunday deadlines, not extra organizer deadlines.

## 8. Evaluation and quality gates

### Worked-example calibration

- Run `tools/validate.py` on each candidate submission.
- Use `tools/score_local.py` to inspect regulation and page-level matches.
- Compare requirements by obligation, not sentence similarity alone: same subject, action, scope, condition, and constraint.
- Categorize errors: missed regulation/function, missed provision, wrong version/page, merged obligations, unsupported obligation, or applicability error.

### Per-requirement gate

- The regulation appears in `regulations/index.json`.
- Version label is exact and matches the relevant PDF.
- Page is the page in that exact PDF; paragraph is retained where available.
- Text states one actionable obligation and does not add unsupported values.
- Applicability reason cites product facts and relevant legal scope.
- Repeated or overlapping obligations are deduplicated without merging distinct obligations.

### Demonstration gate

- A cold run from product input to result succeeds without editing extracted data by hand.
- The UI makes it clear which facts came from the product and which requirements came from law.
- A reviewer can follow a requirement back to its regulation version, page, and paragraph.
- The team can state what the model does not know and how that uncertainty is handled.

## 9. Deferred ideas and decisions

Keep these out of the critical path unless the MVP is stable:

- Cross-market/regional regulation comparison and a common requirement “envelope” or intersection.
- Matching existing engineering requirements to regulations and reporting compliance gaps.
- An engineering agent that proposes a design/system from requirements, followed by a separate regulatory verification agent.
- Broad external legal datasets, case law, crawling, and additional jurisdictions.
- Full multi-version change impact analysis beyond the provided sub-goal pair.

Open decisions for team review:

1. Which functionality groups are required for the held-out bumper, and which are shared with the sample?
2. Which model/provider is available, affordable, and reliable for vision and adjudication?
3. How should product role (component/system manufacturer vs vehicle/assembly manufacturer) affect candidate scope for this challenge?
4. Should any small derived applicability catalog be versioned? Keep full legal text local/ignored; check the data license and team agreement before checking in excerpts or generated catalogs.
5. Does a user need to choose regions and manufacturer role in the MVP, or are these fixed by the held-out case?
6. Is a human review queue a future product feature, while the challenge demo remains fully automatic?
7. Python tooling will use `uv`; Astro's frontend dependencies should use a JavaScript package manager (for example npm or pnpm). Confirm the choice before setup.

## 10. MVP versus product vision

| Stage | User value | Included capabilities |
|---|---|---|
| **Hackathon MVP** | Find applicable requirements for the held-out component and prove each citation | Fixed UN corpus, one target product/case, functionality-group precomputation, product-specific adjudication, JSON validation, citation UI |
| **Near-term product** | Keep a product's compliance profile current | User-managed products, multiple component roles, human review, saved requirement sets, regulation-version impact alerts |
| **Longer-term vision** | Plan compliance across markets and product lifecycle | Region selection, cross-jurisdiction comparison, shared/stricter “envelope” requirements, change propagation to engineering requirements, controlled integrations |

