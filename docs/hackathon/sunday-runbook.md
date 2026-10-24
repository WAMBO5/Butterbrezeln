# Sunday runbook: held-out case `heldout-front-bumper`

Held-out inputs are released **08:00**. Uploads close **13:00**. For the held-out case the **last valid upload counts**, not the best one.
Ranking metric: **F2** at the regulation, page and requirement levels (recall weighted over precision; recall breaks ties).

Who does what (sessions on this Mac):
- **brezel-1c**: `app/` pipeline (`certivity run`), all platform uploads (5 valid per hour per challenge, shared by the team).
- **brezel-6c**: the "lane" (`lane.py`, LLM subscription) and the sub-goal (`subgoal-heldout`).
- **brezel-78**: scoring, variant files, this runbook, the API-key tally (global cap $100).

## 0. Saturday night (before sleeping)

- [ ] Freeze the best dev configuration of each lane and write down its dev scores in `data/scoreboard.md`.
- [ ] Download every PDF while the links still work (free):
      `cd industrial-ai-hackathon && python3 tools/fetch_regulations.py` (goes to `regulations/pdf/…`).
- [ ] `uv run pytest` passes in the main checkout, and `uv run certivity doctor` shows the key, 56 cards and the catalog.
- [ ] Note the money left on the API key. A held-out pipeline run in full cost mode needs about $15–20.

## 1. 08:00 Get the held-out package

The brief (p.3) says the held-out case comes as a **second zip whose link is shown on screen at 08:00**; the README says it's added to the upstream repo. Try the zip first: unzip it into `industrial-ai-hackathon/` (same layout) and check with `diff -rq`.

Fallback, the upstream repo. `industrial-ai-hackathon/` is a vendored copy inside our repo, not its own clone, so `git pull` there does nothing. Fetch upstream and copy in what changed:

```bash
cd /Users/Mo/Documents/Brezel/Butterbrezeln
rm -rf /tmp/hack-up && git clone --depth 1 https://github.com/Certivity/industrial-ai-hackathon /tmp/hack-up
diff -rq /tmp/hack-up industrial-ai-hackathon -x .git -x pdf -x text -x __pycache__ | head -50   # see exactly what is new
rsync -a /tmp/hack-up/cases/ industrial-ai-hackathon/cases/
rsync -a /tmp/hack-up/subgoal/ industrial-ai-hackathon/subgoal/
cp /tmp/hack-up/regulations/index.json industrial-ai-hackathon/regulations/index.json   # only if it changed
rsync -a /tmp/hack-up/tools/ /tmp/hack-up/schemas/ industrial-ai-hackathon/ --relative 2>/dev/null || true  # only if they changed
```

Check right away:
- [ ] `ls industrial-ai-hackathon/cases/heldout-front-bumper/` shows `spec.md` and/or a drawing. Read the spec: parts, vehicle category, functions, and any lamps, sensors or radar.
- [ ] Did `regulations/index.json` change (new regulations, new versions)? If so, do step 2 in full.

## 2. Corpus for any new regulations

```bash
cd industrial-ai-hackathon && python3 tools/fetch_regulations.py && cd ..   # new PDFs, incl. sub-goal old/new
uv run certivity build-corpus --extract-missing --cards                    # text for new PDFs, cards only for new regulations (paid, cents)
uv run certivity doctor
```
- [ ] Every regulation in the new index has a text file and a card (`data/cards/`).
- [ ] Parse spot check on the regulations the bumper will use. Every numbered paragraph should become a provision; none should span many pages. brezel-78 has the check script.

## 3. Runs (in parallel)

| Lane | Command | Owner | Cost |
|---|---|---|---|
| Pipeline | `CERTIVITY_MAX_COST_USD=30 CERTIVITY_COST_MODE=<frozen> uv run certivity run industrial-ai-hackathon/cases/heldout-front-bumper`. The budget must be set, or the run gets cut off like the 19:35 one. Output: `data/runs/<id>/submission.json`, team_id from `.env` (team-04). | brezel-1c | API key, ~$15–30 |
| Lane | `cd <scratch> && python3 lane.py /Users/Mo/Documents/Brezel/Butterbrezeln/industrial-ai-hackathon/cases/heldout-front-bumper --out runs/heldout-v1` (~15–25 min). Its own catalog snapshot must be rebuilt after `build-corpus --extract-missing` whenever index.json or the text files change; brezel-6c does that. | brezel-6c | subscription |
| Sub-goal | `scratchpad/subgoal/run.sh <case>` (alignment, ~2 s), then brezel-6c's judgment pass, then `run.sh <case> build` (gates + `validate.py --strict`). Dev calibration: no transitional provisions; flag an old requirement only when its own provision text changed (dev: 7/7 modified/removed with the right change type, 16/17 added found by paragraph; `subgoal-dev.v2.json`). | brezel-6c | subscription |

Then, for each output:
```bash
uv run python industrial-ai-hackathon/tools/validate.py <submission.json>          # must pass
uv run python tools/evalkit/check_heldout.py <submission.json>   # brezel-78: case_id, team_id, base versions, allowlist, duplicates
```
- [ ] `case_id` is `heldout-front-bumper`, `team_id` is `team-04`, every `source.version` is the **base** `version_label`, and every requirement has a page and a paragraph.

## 4. Uploads: use the platform's scores as the loop

Every valid upload shows its headline scores (regulation, page and requirement levels). With 5 uploads per hour from about 09:00 to 12:45 we get up to ~18 uploads. Use them:

1. **~09:00 Safety net:** upload the first valid file (the better lane on dev). From then on a result always counts.
2. **Variants:** compare whole, independently built variants and keep the best:
   - **ensemble first** (best on dev: judge 0.755 vs 0.738 / 0.717 for the single lanes): `python3 tools/evalkit/ensemble.py ens.json <pipeline submission> <lane submission> --case heldout-front-bumper --team team-04`, which keeps pipeline requirements whose paragraph the lane also cites and fills lane requirements for uncited paragraphs inside sections the pipeline covers;
   - lane vs. pipeline alone (plain unions scored worse on dev);
   - with vs. without "uncertain" requirements.
   We decide which regulations to include **by reasoning, not by probing**. Do not upload two files that differ only by one regulation in order to read its regulation-level P/R. That probes the hidden golden set; whether to do it at all is our user's call (flagged), not part of this plan.
   F2 = 5·matched / (4·n_gold + n_submitted). An extra requirement pays off when its chance of matching is above F2/5, so when in doubt, include. That's why borderline regulations (GTR 9 next to R127; R48/R10 when the bumper carries lamps or sensors) go in as "uncertain" by default.
3. **Sub-goal too:** upload `subgoal-heldout` as soon as it validates. It's a separate challenge with its own 5-per-hour quota, worth 15% of the jury score. The last valid upload counts there as well.
4. **GTR 9 vs R127, decided by reasoning:** include GTR 9 as uncertain. Their bumper sections are near-identical text (5.1.1: Jaccard 0.90). Including it wrongly costs about 0.02 F2; leaving it out wrongly costs about 0.10.
5. **Final upload by 12:30 at the latest:** re-upload the best file seen so far, even if it was already uploaded. **Never let a worse file be the last upload.** Write down which file is final and its scores.

## 5. Before the pitch (15:00)

- [ ] Final held-out scores and dev scores in `data/scoreboard.md`, with where we're weak and how we measured it (the brief asks for this).
- [ ] The UI demo runs on the held-out case from input to requirements, with every requirement linking to its source page.
