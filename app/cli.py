"""`certivity` command line (design spec section 10.3). Paid commands run only when asked."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.config.settings import Settings, load_settings

REAR_LAMP = "cases/dev-rear-lamp"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="certivity", description="Product spec → cited UN-regulation requirements")
    parser.add_argument("--fake-llm", action="store_true", help="scripted stand-in model, no API calls")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="check key, models, corpus and catalog (free)")
    doctor.add_argument("--ping", action="store_true", help="one tiny paid call per model tier")
    build = sub.add_parser("build-corpus", help="parse the corpus (free); --cards / --prefill are paid")
    for flag in ("--cards", "--prefill", "--force", "--extract-missing"):
        build.add_argument(flag, action="store_true")
    run = sub.add_parser("run", help="run the pipeline on a case folder (paid)")
    run.add_argument("case_dir")
    run.add_argument("--markets", default="", help="comma-separated market ids")
    run.add_argument("--mode", choices=("benchmark", "assisted"), default="benchmark")
    run.add_argument("--out", default=None, help="run directory")
    score = sub.add_parser("score", help="validate and score a run (free; --judge is paid)")
    score.add_argument("run_dir")
    score.add_argument("--expected", default=None)
    score.add_argument("--judge", action="store_true", help="requirement-level estimate with an LLM judge (paid)")
    sub.add_parser("bench", help="run + score on the rear-lamp case (paid)")
    verify = sub.add_parser("verify", help="check the ledger chain and replay a run (free)")
    verify.add_argument("run_dir")
    sub.add_parser("technical-file", help="regenerate the measured parts of docs/ai-act (free)")
    subgoal = sub.add_parser("subgoal", help="which old requirements change in the new version (paid)")
    subgoal.add_argument("subgoal_dir")
    markets = sub.add_parser("markets", help="market profiles")
    markets_sub = markets.add_subparsers(dest="markets_command", required=True)
    markets_sub.add_parser("list", help="list the market profiles (free)")
    add = markets_sub.add_parser("add", help="build a market profile from cited source files (paid)")
    add.add_argument("name")
    add.add_argument("--source", action="append", required=True, help="a source document (repeatable)")
    serve = sub.add_parser("serve", help="FastAPI service and UI on localhost (paid when runs are started)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="127.0.0.1")
    signoff = sub.add_parser("signoff", help="record a named sign-off for a reviewed run (free)")
    signoff.add_argument("run_dir")
    signoff.add_argument("--reviewer", required=True)
    signoff.add_argument("--statement", default="I reviewed the requirements of this run and accept them.")
    return parser


def _store(settings: Settings):
    from app.pipeline.main import RunDeps

    return RunDeps.load(settings)


def _register_fakes(settings: Settings, deps) -> None:
    from app.testing.fake_llm import register_responders
    from app.testing.responders import build_fake_responders

    register_responders(build_fake_responders(settings, deps.store))


def cmd_doctor(args, settings: Settings) -> int:
    print(f"API key: {'set' if settings.api_key_present else 'missing'}")
    print(f"models: judgment={settings.model_judgment} fast={settings.model_fast} review={settings.model_review} "
          f"match={settings.model_match}")
    texts = list(settings.text_root.rglob("*.txt")) if settings.text_root.exists() else []
    print(f"corpus text: {len(texts)} files")
    built = settings.catalog_path.exists()
    print(f"catalog: {'built' if built else 'missing'}")
    print(f"cards: {len(list(settings.cards_dir.glob('*.json'))) if settings.cards_dir.exists() else 0}")
    if not settings.api_key_present and not settings.fake_llm:
        return 1
    if args.ping:
        from app.pipeline.ping import ping

        deps = _store(settings)
        if settings.fake_llm:
            _register_fakes(settings, deps)
        first = deps.store.provisions(deps.base_versions[0].regulation, deps.base_versions[0].version_label)[0]
        from app.tools.corpus_tools import bind_store

        bind_store(deps.store)
        rows = asyncio.run(ping(settings, first.provision_id))
        for row in rows:
            status = "ok" if row.get("ok") else f"FAILED: {row.get('error', 'unexpected verdict')}"
            print(f"ping {row['tier']:<8} tool={row['tool']:<14} {row.get('model', '?')}: {status}"
                  + (f" ({row['latency_s']} s, {row['tokens']}, ${row['cost_usd']})" if row.get("ok") else ""))
        return 0 if all(r.get("ok") for r in rows) else 1
    return 0


def cmd_build_corpus(args, settings: Settings) -> int:
    from app.pipeline.corpus import build_corpus

    if settings.fake_llm:
        _register_fakes(settings, _store(settings))
    report = asyncio.run(build_corpus(settings, cards=args.cards, prefill=args.prefill, force=args.force,
                                      extract_missing=args.extract_missing))
    s = report.stats
    print(f"parsed: {len(s.parsed)} · unchanged: {len(s.unchanged)} · missing text: {len(s.missing)}")
    for m in s.missing:
        print(f"  missing: {m}")
    if report.extracted:
        print(f"extracted from PDF: {', '.join(report.extracted)}")
    if args.cards:
        print(f"cards written: {len(report.cards_written)} · failed: {len(report.cards_failed)} · "
              f"unresolved: {len(report.cards_unresolved)}")
        for f in report.cards_failed:
            print(f"  card failed: {f}")
    if args.prefill:
        print(f"obligations pre-filled: {report.prefilled}")
    if args.cards or args.prefill:
        print(f"cost: ${report.cost_usd:.4f}")
    return 0


def _print_run(res) -> None:
    print(f"run: {res.run_dir}")
    print(f"status: {res.status}" + (f" (checkpoint {res.checkpoint})" if res.checkpoint else ""))
    if res.submission_path:
        n = len(json.loads(Path(res.submission_path).read_text())["requirements"])
        print(f"submission: {res.submission_path} ({n} requirements)")
    print("validate.py: no problems" if not res.validation_problems else
          "validate.py problems:\n" + "\n".join(f"  {p}" for p in res.validation_problems))
    if res.partial:
        print("Partial run: budget reached")
    if res.missing_texts:
        print(f"missing texts: {', '.join(res.missing_texts)}")
    print(f"cost: ${res.cost_usd:.4f}")


def _run(settings: Settings, case_dir: Path, markets: list[str], mode: str, out: str | None):
    from app.matching.case_loader import CaseError
    from app.pipeline.main import run_case

    deps = _store(settings)
    if settings.fake_llm:
        _register_fakes(settings, deps)
    try:
        return asyncio.run(run_case(case_dir, markets=markets, mode=mode, settings=settings,
                                    run_dir=Path(out) if out else None, deps=deps))
    except CaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def cmd_run(args, settings: Settings) -> int:
    markets = [m.strip() for m in args.markets.split(",") if m.strip()]
    res = _run(settings, Path(args.case_dir), markets, args.mode, args.out)
    if res is None:
        return 2
    _print_run(res)
    return 0 if not res.validation_problems else 1


def _score(settings: Settings, run_dir: Path, expected: Path | None, judge: bool) -> int:
    from app.eval.funnel import funnel_metrics, render_funnel
    from app.matching.submission import validate_submission
    from app.pipeline.state import RunState

    submission = json.loads((run_dir / "submission.json").read_text(encoding="utf-8"))
    problems = validate_submission(submission, settings)
    print("validate.py: no problems" if not problems else "validate.py problems:\n" + "\n".join(problems))
    state = RunState.load(run_dir)
    expected = expected or Path(state.case_dir) / "expected.json"
    if not expected.exists():
        print("no expected.json for this case: regulation and page scores are not available")
        return 0 if not problems else 1
    deps = _store(settings)
    report = funnel_metrics(run_dir, expected, deps.store, settings)
    print(json.dumps(report.final_score, indent=1))
    print(render_funnel(report))
    if judge:
        from app.eval.judge import judge_requirements
        from app.llm import LLM, Budget, load_prices
        from app.pipeline.calls import bind_call

        llm = LLM(settings, budget=Budget(settings.max_cost_usd, load_prices(settings.prices_path)))
        result = asyncio.run(judge_requirements(run_dir, expected, settings, bind_call(llm, None)))
        print(f"requirement judge: matched: {result.matched} · precision {result.precision:.3f} · "
              f"recall {result.recall:.3f} · cost ${llm.budget.spent_usd:.4f}")
    return 0 if not problems else 1


def cmd_score(args, settings: Settings) -> int:
    return _score(settings, Path(args.run_dir), Path(args.expected) if args.expected else None, args.judge)


def cmd_bench(args, settings: Settings) -> int:
    res = _run(settings, settings.challenge_dir / REAR_LAMP, [], "benchmark", None)
    if res is None:
        return 2
    _print_run(res)
    return _score(settings, Path(res.run_dir), None, False)


def cmd_verify(args, settings: Settings) -> int:
    from app.compliance.replay import replay

    problems = replay(Path(args.run_dir), _store(settings).store, settings)
    print("verify: ledger chain intact and the run replays exactly" if not problems else
          "verify problems:\n" + "\n".join(f"  {p}" for p in problems))
    return 0 if not problems else 1


def cmd_signoff(args, settings: Settings) -> int:
    from app.compliance.oversight import OversightError, sign_off

    try:
        s = sign_off(Path(args.run_dir), args.reviewer, args.statement)
    except OversightError as exc:
        print(f"sign-off refused: {exc}", file=sys.stderr)
        return 1
    print(f"signed off by {s.reviewer} at {s.ts}; the export now counts as reviewed")
    return 0


def cmd_markets(args, settings: Settings) -> int:
    from app.pipeline.markets import available_profiles

    deps = _store(settings)
    regulations = sorted({v.regulation for v in deps.versions})
    if args.markets_command == "list":
        for p in available_profiles(settings, regulations):
            applied = sum(1 for r in p.rules if r.status != "not_applied")
            print(f"{p.market_id}: {p.name}{' (illustrative)' if p.illustrative else ''} — {applied} regulations applied"
                  f"{', rules outside the corpus' if p.outside_corpus else ''}")
        return 0
    from app.compliance.ledger import Ledger
    from app.llm import LLM, Budget, load_prices
    from app.markets.onboarding import OnboardingError, onboard_market
    from app.pipeline.calls import bind_call
    from app.pipeline.main import new_run_id

    if settings.fake_llm:
        _register_fakes(settings, deps)
    ledger = Ledger(settings.data_dir / "market_runs" / new_run_id(args.name.replace(" ", "_")))
    llm = LLM(settings, budget=Budget(settings.max_cost_usd, load_prices(settings.prices_path)))
    try:
        profile = asyncio.run(onboard_market(args.name, [Path(s) for s in args.source], settings,
                                             bind_call(llm, ledger), ledger))
    except OnboardingError as exc:
        print(f"onboarding failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {settings.markets_dir / (profile.market_id + '.yaml')}: {len(profile.rules)} rules, "
          f"{len(profile.outside_corpus)} outside the corpus{', illustrative' if profile.illustrative else ''}")
    return 0


def cmd_subgoal(args, settings: Settings) -> int:
    from app.pipeline.subgoal import run_subgoal

    if settings.fake_llm:
        _register_fakes(settings, _store(settings))
    path = asyncio.run(run_subgoal(Path(args.subgoal_dir), settings))
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = json.loads((path.parent / "validation.json").read_text(encoding="utf-8"))["problems"]
    counts = {k: sum(1 for c in data["changes"] if c["change"] == k) for k in ("modified", "removed", "added")}
    print(f"changes: {path} ({counts['modified']} modified, {counts['removed']} removed, {counts['added']} added)")
    print("validate.py --requirements-old: no problems" if not problems else "validate.py problems:\n" + "\n".join(problems))
    return 0 if not problems else 1


def cmd_technical_file(args, settings: Settings) -> int:
    from app.compliance.technical_file import bench_runs, update_technical_file

    runs = bench_runs(settings)
    if not runs:
        print("no finished benchmark run of the rear lamp yet: run `certivity bench` first", file=sys.stderr)
        return 1
    for path in update_technical_file(settings, runs):
        print(f"updated {path}")
    return 0


def cmd_serve(args, settings: Settings) -> int:
    import uvicorn

    from server.main import create_app

    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")
    return 0


COMMANDS = {"doctor": cmd_doctor, "build-corpus": cmd_build_corpus, "run": cmd_run, "score": cmd_score,
            "bench": cmd_bench, "verify": cmd_verify, "signoff": cmd_signoff, "serve": cmd_serve,
            "markets": cmd_markets, "subgoal": cmd_subgoal, "technical-file": cmd_technical_file}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(fake_llm=args.fake_llm)
    return COMMANDS[args.command](args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
