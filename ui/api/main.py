"""FastAPI layer between the web UI and the requirements backend. Run it from ui/:

    uv run uvicorn api.main:app --reload --reload-dir api --port 8010                    # finished pipeline runs (default)
    BACKEND_MODE=mock uv run uvicorn api.main:app --reload --reload-dir api --port 8010  # golden files, offline demo
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import countries as country_data
from . import pipeline_runs
from .assess import ask_country
from .backend_client import NO_RUN
from .config import BACKEND_MODE, CASES_DIR, PDF_DIR, PIPELINE_ROOT, ROOT
from .models import AskRequest, DecisionRequest, QAEntry, RunResult, TraceEvent
from .runs import RunState, RunStore

app = FastAPI(title="Butterbrezeln Compliance API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
store = RunStore()


def _run(run_id: str) -> RunState:
    state = store.get(run_id)
    if state is None:
        raise HTTPException(404, f"Run {run_id} nicht gefunden")
    return state


@app.get("/api/health")
def health() -> dict:
    finished = [r for r in pipeline_runs.runs() if r.finished] if BACKEND_MODE == "runs" else []
    return {
        "backend_mode": BACKEND_MODE,
        "llm": {"available": store.llm.available, "model": store.llm.model, "reason": store.llm.disabled_reason},
        "countries_loaded": len(country_data.countries_data().get("countries", {})),
        "pipeline": {"root": str(PIPELINE_ROOT), "finished_runs": len(finished),
                     "cases": sorted({r.case_id for r in finished})} if BACKEND_MODE == "runs" else None,
    }


@app.get("/api/countries")
def countries() -> dict:
    return country_data.listing()


def _example_dirs() -> dict[str, Path]:
    """Cases whose spec can be loaded with one click: in runs mode only those with a finished run."""
    if BACKEND_MODE == "runs":
        return pipeline_runs.cases_with_runs()
    return {p.parent.name: p.parent for p in sorted(CASES_DIR.glob("*/spec.md"))}


@app.get("/api/examples")
def examples() -> list[str]:
    return sorted(_example_dirs(), key=lambda case: (not case.startswith("heldout"), case))  # held-out first


@app.get("/api/examples/{case}", response_class=PlainTextResponse)
def example(case: str) -> str:
    folder = _example_dirs().get(case)
    if folder is None:
        raise HTTPException(404, f"Beispiel {case} nicht gefunden")
    return (folder / "spec.md").read_text(encoding="utf-8")


@app.get("/api/examples/{case}/image")
def example_image(case: str) -> FileResponse:
    folder = _example_dirs().get(case)
    images = sorted(folder.glob("*.png")) if folder else []
    if not images:
        raise HTTPException(404, f"Keine Zeichnung für {case}")
    return FileResponse(images[0], media_type="image/png")


@app.post("/api/runs")
async def create_run(spec: UploadFile = File(...), countries: str = Form(...),
                     image: UploadFile | None = File(None)) -> dict:
    text = (await spec.read()).decode("utf-8", errors="replace")
    if not text.strip():
        raise HTTPException(400, "spec.md ist leer")
    selected = [c.strip().upper() for c in countries.split(",") if c.strip()]
    if not selected:
        raise HTTPException(400, "Mindestens ein Land auswählen")
    if BACKEND_MODE == "runs" and pipeline_runs.match(text) is None:
        raise HTTPException(409, NO_RUN)
    image_bytes = await image.read() if image is not None else None
    state = store.start(spec.filename or "spec.md", text, image_bytes or None, selected)
    return {"run_id": state.result.run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> RunResult:
    return _run(run_id).result


@app.get("/api/runs/{run_id}/image")
def run_image(run_id: str) -> FileResponse:
    path = _run(run_id).dir / "image.png"
    if not path.is_file():
        raise HTTPException(404, "Keine Zeichnung hochgeladen")
    return FileResponse(path, media_type="image/png")


@app.get("/api/runs/{run_id}/trace")
def get_trace(run_id: str) -> list[TraceEvent]:
    state = _run(run_id)
    with state.lock:
        return list(state.events.values())


@app.get("/api/runs/{run_id}/events")
async def stream_events(run_id: str) -> StreamingResponse:
    state = _run(run_id)

    async def gen():
        sent = 0
        while True:
            with state.lock:
                pending = state.stream[sent:]
                finished = state.result.status != "running"
            for event in pending:
                yield f"event: step\ndata: {event.model_dump_json()}\n\n"
            sent += len(pending)
            if finished and not pending:
                yield f"event: done\ndata: {state.result.status}\n\n"
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/runs/{run_id}/countries/{iso3}/ask")
def ask(run_id: str, iso3: str, body: AskRequest) -> QAEntry:
    state = _run(run_id)
    iso3 = iso3.upper()
    if iso3 not in state.result.verdicts:
        raise HTTPException(404, f"{iso3} wurde in diesem Run nicht bewertet")
    if not body.question.strip():
        raise HTTPException(400, "Frage ist leer")
    entry = ask_country(state.result, state.spec, iso3, body.question.strip(), store.llm, state.trace)
    with state.lock:
        state.result.qa.append(entry)
    state.save()
    return entry


@app.patch("/api/runs/{run_id}/suggestions/{suggestion_id}")
def decide(run_id: str, suggestion_id: str, body: DecisionRequest) -> dict:
    state = _run(run_id)
    for verdict in state.result.verdicts.values():
        for suggestion in verdict.suggestions:
            if suggestion.id == suggestion_id:
                event = state.trace.record(
                    "human_review", f"Vorschlag {body.decision}: {suggestion_id}",
                    inputs_summary=suggestion.change, outputs_summary=body.note or "",
                    tags={"country": suggestion.country, "suggestion": suggestion_id},
                )
                with state.lock:
                    suggestion.decision = body.decision
                    suggestion.trace_ids.append(event.id)
                state.save()
                return suggestion.model_dump()
    raise HTTPException(404, f"Vorschlag {suggestion_id} nicht gefunden")


@app.get("/api/sources/pdf/{slug}/{role}/{filename}")
def source_pdf(slug: str, role: str, filename: str) -> FileResponse:
    path = (PDF_DIR / slug / role / filename).resolve()
    if PDF_DIR.resolve() not in path.parents or path.suffix.lower() != ".pdf" or not path.is_file():
        raise HTTPException(404, "PDF nicht vorhanden – industrial-ai-hackathon/tools/fetch_regulations.py ausführen")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{filename}"'})


_DIST = ROOT / "web" / "dist"
if _DIST.is_dir():  # serve the built UI from the same origin for the demo
    app.mount("/", StaticFiles(directory=Path(_DIST), html=True), name="web")
