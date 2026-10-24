"""Public HTTPS tunnel target: exactly four authenticated draft/read tools.

Run on 127.0.0.1:8001. Never tunnel the main API or frontend.
"""
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .drafts import DraftConflict
from .store import DEFAULT_DB_PATH, Store
from .voice import (LookupPropertyRequest, MaintenanceRequest, OpenJobsRequest,
                    PrepareDraftRequest, VoiceService, VoiceSettings)


def tool_response(content: dict) -> dict:
    """The model needs the draft ID/revision, never the local session capability."""
    if content.get("draft"):
        return content | {"draft": {key: value for key, value in content["draft"].items() if key != "session_id"}}
    return content


def create_gateway(db_path: str | Path | None = None, *, voice_settings: VoiceSettings | None = None):
    settings = voice_settings or VoiceSettings.from_env()
    store = Store(db_path or os.environ.get("REPAIR_DB_PATH", DEFAULT_DB_PATH))
    service = VoiceService(store, settings)

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        yield

    app = FastAPI(title="Hearth voice tools", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def authenticate_before_body(request, call_next):
        if request.method == "POST" and request.url.path in {
            "/voice/tools/lookup_property", "/voice/tools/check_open_jobs",
            "/voice/tools/lookup_maintenance_context", "/voice/tools/prepare_repair_draft",
        }:
            try:
                await run_in_threadpool(lambda: store.read(lambda db: service._authenticate(db, request.headers)))
            except DraftConflict as error:
                return JSONResponse(status_code=error.status_code, content=tool_response(error.content))
            except sqlite3.DatabaseError:
                return JSONResponse(status_code=503, content={"error_code": "backend_unavailable",
                    "message": "The record check could not finish. Retry or continue with the saved repair form."})
        return await call_next(request)

    @app.exception_handler(DraftConflict)
    async def conflict(request, error):
        return JSONResponse(status_code=error.status_code, content=tool_response(error.content))

    @app.exception_handler(RequestValidationError)
    async def validation(request, error):
        return JSONResponse(status_code=422, content={"error_code": "invalid_request",
            "message": "Supply only the documented editable tool fields. Obtain draft ID and revision from the latest tool result."})

    @app.exception_handler(sqlite3.DatabaseError)
    async def database_error(request, error):
        return JSONResponse(status_code=503, content={"error_code": "backend_unavailable",
            "message": "The record check could not finish. Retry or continue with the saved repair form."})

    @app.post("/voice/tools/lookup_property")
    def lookup_property(payload: LookupPropertyRequest, request: Request):
        return tool_response(service.tool("lookup_property", payload, request.headers))

    @app.post("/voice/tools/check_open_jobs")
    def check_open_jobs(payload: OpenJobsRequest, request: Request):
        return tool_response(service.tool("check_open_jobs", payload, request.headers))

    @app.post("/voice/tools/lookup_maintenance_context")
    def lookup_maintenance_context(payload: MaintenanceRequest, request: Request):
        return tool_response(service.tool("lookup_maintenance_context", payload, request.headers))

    @app.post("/voice/tools/prepare_repair_draft")
    def prepare_repair_draft(payload: PrepareDraftRequest, request: Request):
        return tool_response(service.tool("prepare_repair_draft", payload, request.headers))

    return app


app = create_gateway()
