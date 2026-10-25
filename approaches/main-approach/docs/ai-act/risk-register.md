# Risk register (Art. 9)

Each risk maps to a control that is built into the pipeline and checked by a test or a measurement. The register is reviewed at every release; the owner signs the review date.

| Risk | Control in the system | Evidence | Owner | Last review |
| --- | --- | --- | --- | --- |
| A requirement is missed (recall) | Every regulation in the index gets an explicit decision; `recall_auditor` reviews every exclusion with code-run full-text search hits; uncertain items are kept, not dropped; checkpoints C2 and C3 in assisted mode | `scope_gate` tests; funnel metrics in every `bench` run (golden regulations kept, golden pages in sections) | Engineering lead | 2026-10-24 |
| A citation is wrong or invented | Citations come from the parsed corpus only; the output gate checks regulation, base version, page, paragraph and that the quote is on the cited page ±1; requirements that fail are dropped and logged | `test_assemble.py`, `test_output.py`; `certivity verify` replays the gates | Engineering lead | 2026-10-24 |
| A requirement is listed that does not apply | `match_reviewer` checks the matcher; C3 review in assisted mode; precision measured per release | Page precision in `bench`; requirement judge on request | Engineering lead | 2026-10-24 |
| Automation bias | Assisted mode: excluded regulations shown with reasons, open items first, nothing pre-approved, reasons required for overrides, named sign-off; benchmark output labelled unreviewed | `test_assisted.py`; UI review screens | Product owner | 2026-10-24 |
| An outdated regulation version is used | Version labels and text checksums in every manifest; base and latest versions kept apart; citations only to the base version | Manifest `corpus` block | Engineering lead | 2026-10-24 |
| Illustrative market data is taken as real law | Made-up market names, `illustrative` flag, banner on every market screen; `market_onboarding` refuses uncited claims | `test_onboarding.py`; UI banner | Product owner | 2026-10-24 |
| Prompt injection through input documents | Spec and drawing text sit inside marked data blocks and the agents are told to ignore instructions in them; tools are read-only; every output passes code gates; no input can trigger an external action | `test_profile.py::test_injection_stays_data` | Engineering lead | 2026-10-24 |
| Cost runaway | Per-run budget guard (`CERTIVITY_MAX_COST_USD`); a blocked call ends the run as partial, flagged in the report | `test_plugins.py`, `test_main_fake.py` | Engineering lead | 2026-10-24 |
| The API key leaks | Read from the environment only; never printed, logged, or written to ledger, manifest, trace or report; redaction on every write | `test_ledger.py`, `test_cli.py`, `test_plugins.py` | Engineering lead | 2026-10-24 |
