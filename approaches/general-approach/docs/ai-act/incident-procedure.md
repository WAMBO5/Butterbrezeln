# Incident procedure (Art. 73)

An incident is any output that led, or could lead, someone to treat a vehicle component as compliant when it is not. Examples: a missed requirement that reached a released design, a wrong citation that was relied on, or illustrative market data taken as real law.

## When you notice one

1. **Record it.** Note the run id (shown in the UI header and in `manifest.json`), the requirement id or regulation concerned, and what was wrong.
2. **Preserve the run.** Do not edit or delete the run folder. Run `uv run certivity verify <run_dir>` and keep its output: it shows whether the record is intact.
3. **Tell the product owner** the same day, with the record.

## The product owner

1. Reproduces the problem from the run's ledger (`calls/` holds every prompt and output).
2. Decides whether it is a serious incident under Art. 73 together with legal counsel, and reports it to the market surveillance authority within the deadline that applies.
3. Opens a fix: a new test that reproduces the failure, then the change. A change to a prompt or model must not lower the `bench` scores (`technical-file.md`, section 8).
4. Adds the risk and its control to `risk-register.md` if it is new.

## Afterwards

Users of affected runs are told what was wrong and which runs to re-check. The run ids come from the ledger and manifests.
