"""FastAPI service (design spec section 10.4): runs, sources, oversight and traceability."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.compliance.ledger import Ledger
from app.compliance.oversight import HumanAction, OversightError, export_status, open_items, sign_off, validate_actions
from app.compliance.provenance import UNREVIEWED_LABEL
from app.config.settings import Settings, load_settings
from app.corpus.parser import squash
from app.matching.case_loader import CaseError
from app.pipeline.main import RunDeps
from server.runs import FINISHED, RunManager

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


class RunBody(BaseModel):
    case_dir: str
    markets: list[str] = []
    mode: str = "benchmark"


class ActionBody(BaseModel):
    action: str
    target_id: str | None = None
    reason: str | None = None
    payload: dict | None = None


class CheckpointBody(BaseModel):
    reviewer: str
    actions: list[ActionBody]


class StopBody(BaseModel):
    reviewer: str = "reviewer"
    reason: str = "stopped from the UI"


class MarketsBody(BaseModel):
    markets: list[str]


class SignoffBody(BaseModel):
    reviewer: str
    statement: str = "I reviewed the requirements of this run and accept them."


def _summary(state, manager: RunManager) -> dict:
    run_dir = manager.run_dir(state.run_id)
    review = export_status(run_dir)
    return {
        "run_id": state.run_id, "case_id": state.case_id, "case_dir": state.case_dir, "mode": state.mode,
        "markets": state.markets, "status": state.status, "step": state.step, "checkpoint": state.checkpoint,
        "checkpoint_errors": state.checkpoint_errors, "started_at": state.started_at,
        "finished_at": state.finished_at, "error": state.error, "partial": state.partial, "stopped": state.stopped,
        "profile": state.profile.model_dump() if state.profile else None,
        "plan": state.plan.model_dump() if state.plan else None, "safety_hits": state.safety_hits,
        "requirements": [r.model_dump() for r in state.requirements], "stage_counts": state.stage_counts,
        "held_back": [r.model_dump() for r in state.held_back],
        "quotes": {r.id: state.obligations[r.obligation_ids[0]].quote for r in [*state.requirements, *state.held_back]
                   if r.obligation_ids and r.obligation_ids[0] in state.obligations},
        "cost": state.cost, "validation_problems": state.validation_problems, "score": state.score,
        "give_ups": state.give_ups, "markets_result": state.markets_result,
        "open_items": open_items(state.requirements, state.give_ups, state.human_actions),
        "human_actions": state.human_actions, "review_status": review,
        "label": UNREVIEWED_LABEL if review == "unreviewed" else None, "missing_texts": state.missing_texts,
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    holder: dict[str, RunManager] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        deps = RunDeps.load(settings)
        if settings.fake_llm:
            from app.testing.fake_llm import register_responders
            from app.testing.responders import build_fake_responders

            register_responders(build_fake_responders(settings, deps.store))
        holder["m"] = RunManager(settings, deps)
        yield
        for task in holder["m"].tasks.values():
            task.cancel()

    app = FastAPI(title="Certivity requirements engine", lifespan=lifespan)
    # The built UI is served from this origin; only the Astro dev server needs CORS. A wildcard would let
    # any website start paid runs on this machine.
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4321", "http://127.0.0.1:4321"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    def manager() -> RunManager:
        return holder["m"]

    def state_or_404(run_id: str):
        try:
            return manager().state(run_id)
        except KeyError:
            raise HTTPException(404, f"unknown run {run_id}")

    def run_file(run_id: str, name: str) -> Path:
        state_or_404(run_id)
        path = manager().run_dir(run_id) / name
        if not path.exists():
            raise HTTPException(404, f"{name} is not written yet")
        return path

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "fake_llm": settings.fake_llm}

    @app.get("/cases")
    def cases() -> list[dict]:
        root = settings.cases_dir
        return [{"case_id": d.name, "case_dir": str(d), "has_expected": (d / "expected.json").exists(),
                 "files": sorted(p.name for p in d.iterdir() if p.is_file() and p.name != "expected.json")}
                for d in sorted(root.iterdir()) if d.is_dir()] if root.exists() else []

    @app.post("/runs")
    async def post_run(body: RunBody) -> dict:
        if body.mode not in ("benchmark", "assisted"):
            raise HTTPException(400, "mode must be benchmark or assisted")
        try:
            return {"run_id": manager().start(Path(body.case_dir), body.markets, body.mode)}
        except CaseError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/runs/upload")
    async def post_upload(files: list[UploadFile] = File(...), case_id: str = Form("upload"),
                          mode: str = Form("benchmark"), markets: str = Form("")) -> dict:
        saved = [(f.filename or "file", await f.read()) for f in files]
        case_dir = manager().save_upload(case_id, saved)
        try:
            return {"run_id": manager().start(case_dir, [m for m in markets.split(",") if m], mode)}
        except CaseError as exc:
            manager().delete_upload(case_dir)
            raise HTTPException(400, str(exc))

    @app.get("/runs")
    def list_runs() -> list[dict]:
        return [{"run_id": s.run_id, "case_id": s.case_id, "mode": s.mode, "status": s.status,
                 "checkpoint": s.checkpoint, "started_at": s.started_at, "requirements": len(s.requirements),
                 "cost_usd": (s.cost or {}).get("spent_usd", 0.0), "partial": s.partial}
                for s in manager().list_runs()]

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        return _summary(state_or_404(run_id), manager())

    @app.get("/runs/{run_id}/events")
    async def events(run_id: str) -> StreamingResponse:
        state_or_404(run_id)
        trace = manager().run_dir(run_id) / "trace.jsonl"

        async def stream():
            sent = 0
            idle = 0
            while True:
                lines = trace.read_text(encoding="utf-8").splitlines() if trace.exists() else []
                for line in lines[sent:]:
                    yield f"data: {line}\n\n"
                new = len(lines) - sent
                sent = len(lines)
                status = manager().state(run_id).status
                if status in (*FINISHED, "awaiting_review") and new == 0:
                    yield f"data: {json.dumps({'event': 'status', 'status': status})}\n\n"
                    return
                idle = 0 if new else idle + 1
                if idle and idle % 30 == 0:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.3)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/runs/{run_id}/submission.json")
    def submission(run_id: str) -> FileResponse:
        return FileResponse(run_file(run_id, "submission.json"), media_type="application/json",
                            filename=f"{run_id}-submission.json")

    @app.get("/runs/{run_id}/report", response_class=PlainTextResponse)
    def report(run_id: str) -> str:
        return run_file(run_id, "report.md").read_text(encoding="utf-8")

    @app.get("/runs/{run_id}/requirements/{rid}/lineage")
    def lineage(run_id: str, rid: str) -> dict:
        state = state_or_404(run_id)
        for lin in state.lineage:
            if lin.requirement_id == rid:
                return lin.model_dump()
        raise HTTPException(404, f"unknown requirement {rid}")

    @app.get("/runs/{run_id}/manifest")
    def manifest(run_id: str) -> JSONResponse:
        return JSONResponse(json.loads(run_file(run_id, "manifest.json").read_text(encoding="utf-8")))

    @app.get("/runs/{run_id}/provenance.json")
    def provenance_file(run_id: str) -> JSONResponse:
        return JSONResponse(json.loads(run_file(run_id, "submission.provenance.json").read_text(encoding="utf-8")))

    @app.get("/runs/{run_id}/ledger")
    def ledger(run_id: str) -> list[dict]:
        state_or_404(run_id)
        return [r.model_dump() for r in Ledger(manager().run_dir(run_id)).records()]

    @app.get("/runs/{run_id}/checkpoints")
    def checkpoints(run_id: str) -> dict:
        s = state_or_404(run_id)
        excluded = [d.model_dump() for d in s.plan.decisions if d.state == "not_applicable"] if s.plan else []
        return {"status": s.status, "checkpoint": s.checkpoint, "errors": s.checkpoint_errors,
                "profile": s.profile.model_dump() if s.profile else None,
                "plan": s.plan.model_dump() if s.plan else None, "excluded": excluded,
                "safety_hits": s.safety_hits, "open_items": open_items(s.requirements, s.give_ups, s.human_actions),
                "requirements": [r.model_dump() for r in s.requirements], "give_ups": s.give_ups}

    @app.post("/runs/{run_id}/checkpoints/{checkpoint}", status_code=202)
    async def resume(run_id: str, checkpoint: str, body: CheckpointBody) -> dict:
        state_or_404(run_id)
        now = datetime.now(timezone.utc).isoformat()
        actions = [HumanAction(checkpoint=checkpoint, reviewer=body.reviewer, ts=now, **a.model_dump())
                   for a in body.actions]
        errors = validate_actions(actions)
        if errors:
            raise HTTPException(422, {"errors": errors})
        try:
            manager().resume(run_id, checkpoint, actions)
        except OversightError as exc:
            raise HTTPException(409, str(exc))
        return {"status": "resuming"}

    @app.post("/runs/{run_id}/stop", status_code=202)
    async def stop(run_id: str, body: StopBody) -> dict:
        state_or_404(run_id)
        try:
            await manager().stop(run_id, body.reviewer, body.reason)
        except OversightError as exc:
            raise HTTPException(409, str(exc))
        return {"status": "stopping"}

    @app.post("/runs/{run_id}/signoff")
    def signoff(run_id: str, body: SignoffBody) -> dict:
        state_or_404(run_id)
        try:
            return sign_off(manager().run_dir(run_id), body.reviewer, body.statement).model_dump()
        except OversightError as exc:
            raise HTTPException(409, str(exc))

    @app.get("/provisions/{provision_id:path}")
    def provision(provision_id: str) -> dict:
        p = manager().deps.store.get(provision_id)
        if p is None:
            raise HTTPException(404, f"unknown provision {provision_id}")
        return p.model_dump()

    @app.get("/pages/{regulation}/{version}/{page}")
    def page(regulation: str, version: str, page: int, quote: str | None = None) -> dict:
        store = manager().deps.store
        text = store.page_text(regulation, version, page)
        if text is None:
            raise HTTPException(404, f"no page {page} in {regulation} {version}")
        return {"regulation": regulation, "version": version, "page": page, "text": text,
                "pages": store.page_count(regulation, version), "highlight": _highlight(text, quote)}

    @app.get("/markets")
    def markets() -> list[dict]:
        from app.pipeline.markets import available_profiles

        regulations = sorted({v.regulation for v in manager().deps.versions})
        return [p.model_dump() for p in available_profiles(settings, regulations)]

    @app.post("/markets")
    async def onboard(name: str = Form(...), files: list[UploadFile] = File(...)) -> dict:
        from app.compliance.ledger import Ledger
        from app.llm import LLM, Budget, load_prices
        from app.markets.onboarding import OnboardingError, onboard_market
        from app.pipeline.calls import bind_call
        from app.pipeline.main import new_run_id

        upload = manager().save_upload(f"market-{name}", [(f.filename or "source.md", await f.read()) for f in files])
        ledger = Ledger(settings.data_dir / "market_runs" / new_run_id(upload.name))
        llm = LLM(settings, budget=Budget(settings.max_cost_usd, load_prices(settings.prices_path)))
        try:
            profile = await onboard_market(name, sorted(upload.iterdir()), settings, bind_call(llm, ledger), ledger)
        except OnboardingError as exc:
            raise HTTPException(422, str(exc))
        return profile.model_dump()

    @app.post("/runs/{run_id}/markets", status_code=202)
    async def rerun_markets(run_id: str, body: MarketsBody) -> dict:
        state = state_or_404(run_id)
        if state.status != "done":
            raise HTTPException(409, f"the run is {state.status}; markets can be re-run on a finished run")
        manager().rerun_markets(run_id, body.markets)
        return {"status": "running markets"}

    if WEB_DIST.exists():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    else:
        @app.get("/", response_class=HTMLResponse)
        def index() -> str:
            return ("<h1>Certivity requirements engine</h1><p>The UI is not built yet: run "
                    "<code>cd web && npm install && npm run build</code>. API docs: <a href='/docs'>/docs</a>.</p>")

    return app


def _highlight(text: str, quote: str | None) -> list[int] | None:
    """[start, end] character offsets of `quote` in `text`, ignoring whitespace and case."""
    if not quote:
        return None
    target = squash(quote)
    if not target:
        return None
    index_map = [i for i, ch in enumerate(text) if not ch.isspace()]
    squashed = squash(text)
    if len(squashed) != len(index_map):  # NFKC changed the length (ligatures); fall back to a plain search
        start = text.lower().find(quote.lower()[:40])
        return [start, start + len(quote)] if start >= 0 else None
    pos = squashed.find(target)
    if pos < 0:
        return None
    return [index_map[pos], index_map[pos + len(target) - 1] + 1]
