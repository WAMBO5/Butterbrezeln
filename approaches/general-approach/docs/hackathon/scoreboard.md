# Dev-case scoreboard (rear lamp)

F2 = 5PR/(4P+R), the ranking metric. req(judge): Opus on the subscription, one-to-one; req(para): free paragraph-pairing upper bound.

| when | label | n | reg F2 | page F2 (P/R) | req(para) F2 (P/R) | req(judge) F2 (P/R) | file |
|---|---|---|---|---|---|---|---|
| Sat 21:03 | lane dev-v1 (noR26) | 423 | 1.000 | 0.864 (0.56/1.00) | 0.655 (0.37/0.82) | 0.638 (0.36/0.79) | `<scratch>` |
| Sat 21:08 | lane dev-v2 | 417 | 1.000 | 0.873 (0.58/1.00) | 0.705 (0.40/0.87) | 0.671 (0.38/0.83) | `<scratch>` |
| Sat 19:35 | team platform upload (reported by brezel-1c; platform numbers, not our judge) | 695 | F2 of P 0.80/R 1.00 | P 0.47/R 0.98 | – | **0.498** (0.21/0.76) platform | not on this Mac |
| Sat 21:12 | lane dev-v3 filtered | 334 | 1.000 | 0.868 (0.66/0.94) | 0.690 (0.45/0.79) | 0.681 (0.45/0.78) | `<scratch>` |
| Sat 21:16 | lane dev-v4 (R10/R148 rerun, frozen) | 344 | 1.000 | 0.885 (0.67/0.96) | 0.702 (0.45/0.82) | 0.693 (0.44/0.81) | `<scratch>` |
| Sat 21:17 | pipeline run 1 (reduced, $5.87) | 525 | 0.952 | 0.853 (0.65/0.92) | 0.638 (0.31/0.86) | 0.638 (0.31/0.86) | `/Users/Mo/Documents/Brezel/Butterbrezeln/data/runs/20261024T190247148189Z-dev-rear-lamp/submission.json` |
| Sat 21:25 | lane dev-v6 (frozen prompts) | 360 | 1.000 | 0.897 (0.67/0.98) | 0.701 (0.44/0.83) | 0.683 (0.42/0.81) | `<scratch>` |
| Sat 21:35 | pipeline run 2 ($5.36) | 405 | 1.000 | 0.894 (0.79/0.92) | 0.704 (0.40/0.86) | 0.678 (0.39/0.83) | `/Users/Mo/Documents/Brezel/Butterbrezeln/data/runs/20261024T191745221212Z-dev-rear-lamp/submission.json` |
| Sat 21:41 | lane dev-v7 (frozen for Sunday) | 363 | 1.000 | 0.871 (0.63/0.96) | 0.726 (0.45/0.86) | 0.717 (0.44/0.85) | `<scratch>` |
| Sat 21:57 | pipeline run 3 ($4.04; platform 0.710) | 310 | 1.000 | 0.910 (0.80/0.94) | 0.729 (0.50/0.82) | 0.738 (0.51/0.83) | `/Users/Mo/Documents/Brezel/Butterbrezeln/data/runs/20261024T193837298327Z-dev-rear-lamp/submission.json` |
| Sat 21:59 | ensemble run3∩v7 + fill | 320 | 1.000 | 0.905 (0.84/0.92) | 0.750 (0.51/0.85) | 0.755 (0.51/0.86) | `variants/ens_run3_v7.json` |
| Sat 22:03 | pipeline run 4 ($3.00) | 354 | 1.000 | 0.913 (0.76/0.96) | 0.754 (0.47/0.88) | 0.763 (0.48/0.89) | `/Users/Mo/Documents/Brezel/Butterbrezeln/data/runs/20261024T195657700496Z-dev-rear-lamp/submission.json` |
| Sat 22:03 | ensemble run4∩v7 + fill | 347 | 1.000 | 0.896 (0.80/0.92) | 0.772 (0.49/0.90) | 0.781 (0.50/0.91) | `variants/ens_run4_v7.json` |

## Platform scores (dev uploads, ground truth)

| upload | n | req F2 (P/R) platform | matched platform vs our judge | pages P/R | regs |
|---|---|---|---|---|---|
| lane dev-v7 (21:51) | 363 | **0.686** (0.424/0.811) | 154 vs 161 (0.96×) | 0.631/0.962 | 1.00 |
| lane dev-v4 | 344 | 0.657 (0.422/0.763) | 145 vs 153 (0.95×) | 0.671/0.962 | 1.00 |
| pipeline run 1 | 525 | 0.595 (0.291/0.805) | 153 vs 164 (0.93×) | 0.650/0.925 | P 0.80 / R 1.00 |
| pipeline run 2 ($5.36) | 405 | 0.652 (0.375/0.800) | 152 vs 158 (0.96×) | 0.788/0.925 | 1.00 |
| teammates 20:54 | 173 | 0.525 (0.566/0.516) | – | – | – |
| teammates 20:50 ("Butterbrezeln" team_id) | 223 | 0.524 (0.462/0.542) | – | – | – |

**Calibration:** the platform matches about 4–7% fewer pairs than our judge (×0.93–0.96), and the ranking between files is preserved. Read our judge's F2 minus about 0.03–0.04 as the platform estimate.
