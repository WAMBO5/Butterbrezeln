# Challenge package

This folder is where the pipeline expects its regulation corpus and product cases. The package Certivity provided for the Industrial Agents Hackathon (product cases, sub-goal inputs, the regulation index and the regulation texts Certivity rendered for the event) is licensed for use in the hackathon only, so it is **not included** in this repository.

What is kept here:

| Path | What | Licence |
| --- | --- | --- |
| `tools/validate.py` | Checks a `submission.json` against the schema and the regulation index | MIT (`LICENSE`) |
| `tools/score_local.py` | Offline regulation- and page-level score against a case's `expected.json` | MIT |
| `tools/fetch_regulations.py` | Downloads the regulation PDFs listed in the index, checksum-verified | MIT |
| `schemas/` | JSON Schemas of the main-goal and sub-goal submission formats | MIT |

## Bringing your own corpus

Place the package (or any corpus in the same layout) here, then build the catalog:

```text
industrial-ai-hackathon/
├── regulations/
│   ├── index.json                      # every citable regulation: base (and latest) version, file names, checksums
│   ├── text/<UN_Rxx>/<base|latest>/    # page-preserving text, one "=== PDF page N ===" marker per page
│   └── pdf/                            # optional: lets the UI open each citation on its PDF page
├── cases/<case>/spec.md                # plus exploded_view.png; expected.json enables scoring
└── subgoal/                            # optional: version-change inputs
```

```bash
./certivity general-approach build-corpus           # free: parses the texts into data/
./certivity general-approach doctor                 # checks key, models, corpus, catalog, cards
```

Synthetic product cases that run against any corpus ship with the repository: `testdata/fake-cases/` (LED headlamp, high-mounted stop lamp, side indicator) and `approaches/general-approach/tools/evalkit/mockcases/mock-front-bumper/`.
