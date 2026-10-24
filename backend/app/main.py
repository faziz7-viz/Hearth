"""Local demo API. Run from the project root with uvicorn backend.app.main:app."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .drafts import DraftConflict, DraftWorkflow, latest_draft
from .models import (
    CheckRequestInput, CheckRequestResult, DraftApproveRequest, DraftCreateRequest,
    DraftEditRequest, DraftRevisionRequest, RepairDraft, SessionCreated, SessionState, WorkOrder,
)
from .store import DEFAULT_DB_PATH, Store, UnknownSession, session_events
from .tools import RecordTools
from .workflow import check_request
from .voice import VoiceService, VoiceSettings, fetch_signed_access, voice_router


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    result = CheckRequestResult(status="error", error_code=code, events=[message])
    return JSONResponse(status_code=status_code, content=result.model_dump(mode="json"))


def create_app(db_path: str | Path | None = None, *, voice_settings: VoiceSettings | None = None, signed_url_provider=fetch_signed_access) -> FastAPI:
    settings = voice_settings or VoiceSettings.from_env()
    store = Store(db_path or os.environ.get("REPAIR_DB_PATH", DEFAULT_DB_PATH))
    drafts = DraftWorkflow(store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.initialize()
        yield

    app = FastAPI(title="Landlord Repair Assistant — Demo record checks", lifespan=lifespan)
    app.state.store = store
    app.include_router(voice_router(VoiceService(store, settings, signed_url_provider)))

    def is_draft_route(request: Request) -> bool:
        return request.url.path.startswith(("/api/drafts", "/api/work-orders", "/api/voice"))

    @app.exception_handler(DraftConflict)
    async def draft_conflict_handler(request: Request, error: DraftConflict):
        return JSONResponse(status_code=error.status_code, content=error.content)

    @app.exception_handler(UnknownSession)
    async def unknown_session_handler(request: Request, error: UnknownSession):
        if is_draft_route(request):
            return JSONResponse(status_code=404, content={"error_code": "unknown_session", "message": "Session not found."})
        return error_response(404, "unknown_session", "Session not found. Start a new session, then retry the check.")

    @app.exception_handler(sqlite3.DatabaseError)
    async def database_error_handler(request: Request, error: sqlite3.DatabaseError):
        if is_draft_route(request):
            return JSONResponse(status_code=503, content={
                "error_code": "backend_unavailable", "message": "Saved repair records are unavailable. Retry when the backend is available.",
            })
        return error_response(503, "backend_unavailable", "Record checks are unavailable. Retry after the backend is available.")

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, error: RequestValidationError):
        if is_draft_route(request):
            return JSONResponse(status_code=422, content={
                "error_code": "invalid_request", "message": "Supply valid editable fields, session ID, and the saved revision for updates or approval.",
            })
        return error_response(422, "invalid_request", "The check request is invalid. Supply the structured session, property, unit, category, and issue fields.")

    @app.post("/api/sessions", response_model=SessionCreated, status_code=201)
    def create_session() -> SessionCreated:
        return SessionCreated(session_id=store.create_session())

    @app.get("/api/sessions/{session_id}", response_model=SessionState)
    def read_session(session_id: str) -> SessionState:
        def read_snapshot(db: sqlite3.Connection) -> SessionState:
            events = session_events(db, session_id)
            records = RecordTools(db)
            return SessionState(
                session_id=session_id, draft=latest_draft(db, session_id), events=events, recent_jobs=records.recent_jobs(),
                properties=records.properties(), contractors=records.contractors(),
            )
        return store.read(read_snapshot)

    @app.post("/api/repair-check", response_model=CheckRequestResult)
    def repair_check(request: CheckRequestInput) -> CheckRequestResult:
        result = store.read(lambda db: check_request(db, request))
        # Only session activity is persisted; all business reads use the read snapshot.
        store.save_events(request.session_id, result.events)
        return result

    @app.post("/api/drafts", response_model=RepairDraft)
    def create_draft(request: DraftCreateRequest) -> RepairDraft:
        return drafts.create(request)

    @app.patch("/api/drafts/{draft_id}", response_model=RepairDraft)
    def edit_draft(draft_id: str, request: DraftEditRequest) -> RepairDraft:
        return drafts.edit(draft_id, request)

    @app.post("/api/drafts/{draft_id}/approve", response_model=WorkOrder)
    def approve_draft(draft_id: str, request: DraftApproveRequest) -> WorkOrder:
        return drafts.approve(draft_id, request)

    @app.post("/api/drafts/{draft_id}/cancel", response_model=RepairDraft)
    def cancel_draft(draft_id: str, request: DraftRevisionRequest) -> RepairDraft:
        return drafts.cancel(draft_id, request)

    @app.get("/api/work-orders", response_model=list[WorkOrder])
    def work_orders() -> list[WorkOrder]:
        return drafts.orders()

    return app


app = create_app()
