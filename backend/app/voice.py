"""Temporary ElevenLabs access and narrowly scoped, durable voice capabilities.

The random app session UUID is a capability for this local, single-user demo.
Only the separate webhook gateway is intended to be reachable over HTTPS.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest
from http.client import HTTPException
import json
import os
from pathlib import Path
import secrets
import sqlite3
import ssl
from time import sleep, time
from typing import Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request as URLRequest, build_opener, urlopen
from uuid import uuid4

from dotenv import load_dotenv
import truststore
from fastapi import APIRouter, Request
from pydantic import Field, ValidationError

from .drafts import (DraftConflict, DraftWorkflow, TERMINAL_STATUSES, editable_fields,
                     latest_draft, load_draft, require_editable, require_revision)
from .models import (ContractModel, DraftCreateRequest, DraftEditFields, DraftEditRequest,
                     DraftFields, MatchedUnit, RepairCategory)
from .store import Store, is_temporary_read_error, session_events
from .tools import RecordTools, normalize_unit

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
GUIDANCE = "Use returned records only. Correct this same draft using its exact ID and revision. The landlord must end the conversation and review the card to approve; no message has been sent or booking confirmed."


@dataclass(frozen=True)
class VoiceSettings:
    api_key: str = field(default="", repr=False)
    agent_id: str = ""
    webhook_secret: str = field(default="", repr=False)
    public_url: str = ""
    max_seconds: int = 600

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT_ENV, override=False)
        try:
            duration = int(os.getenv("HEARTH_VOICE_MAX_SECONDS", "600"))
        except ValueError:
            duration = 600
        return cls(api_key=os.getenv("ELEVENLABS_API_KEY", "").strip(),
                   agent_id=os.getenv("ELEVENLABS_AGENT_ID", "").strip(),
                   webhook_secret=os.getenv("HEARTH_WEBHOOK_SECRET", "").strip(),
                   public_url=os.getenv("HEARTH_VOICE_PUBLIC_URL", "").strip().rstrip("/"),
                   max_seconds=max(60, min(duration, 600)))

    @property
    def available(self):
        parsed = urlparse(self.public_url)
        return bool(self.api_key and self.agent_id and len(self.webhook_secret) >= 32
                    and parsed.scheme == "https" and parsed.hostname
                    and not parsed.username and not parsed.password
                    and not parsed.query and not parsed.fragment)


def provider_failure():
    return DraftConflict("voice_provider_unavailable", "Conversation access could not be created. Retry or use the saved repair form.", status_code=502)


class NoGatewayRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_public_gateway(settings: VoiceSettings):
    """Verify the public tunnel reaches Hearth before issuing conversation access."""
    try:
        tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        opener = build_opener(HTTPSHandler(context=tls), NoGatewayRedirects())
        request = URLRequest(settings.public_url.rstrip("/") + "/voice/tools/lookup_property",
                             data=b"{}", headers={"Content-Type": "application/json", "Accept": "application/json"},
                             method="POST")
        try:
            with opener.open(request, timeout=5):
                raise ValueError("Unexpected gateway response")
        except HTTPError as error:
            with error:
                if error.code != 401:
                    raise ValueError("Unexpected gateway status")
                raw = error.read(4097)
            if len(raw) > 4096:
                raise ValueError("Gateway response too large")
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("error_code") != "unauthorized_tool":
                raise ValueError("Unexpected gateway error")
    except (URLError, OSError, ValueError, HTTPException):
        raise DraftConflict("voice_gateway_unavailable",
                            "Hearth’s voice connection is unavailable. Retry or use the saved repair form.",
                            status_code=502) from None


def fetch_signed_access(settings: VoiceSettings) -> dict:
    check_public_gateway(settings)
    query = urlencode({"agent_id": settings.agent_id, "include_conversation_id": "true"})
    request = URLRequest(f"https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?{query}",
                         headers={"xi-api-key": settings.api_key, "Accept": "application/json"})
    try:
        # Python.org macOS builds may lack a bundled CA store; use verified
        # operating-system trust without changing global TLS behavior.
        tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with urlopen(request, timeout=5, context=tls) as response:
            raw = response.read(32769)
            if len(raw) > 32768:
                raise ValueError("Response too large")
            result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Invalid access response")
        return result
    except (URLError, OSError, ValueError):
        # Never echo provider bodies, signed URLs, or authorization headers.
        raise provider_failure() from None


def provider_binding(payload: dict) -> tuple[str, str]:
    try:
        signed_url = payload["signed_url"]
        parsed = urlparse(signed_url)
        query_ids = parse_qs(parsed.query).get("conversation_id", [])
        if len(query_ids) > 1:
            raise ValueError("Repeated ID")
        url_id = query_ids[0] if query_ids else None
        body_id = payload.get("conversation_id")
        conversation_id = body_id or url_id
        if body_id and url_id and body_id != url_id:
            raise ValueError("Mismatched ID")
        if (parsed.scheme != "wss" or parsed.hostname != "api.elevenlabs.io"
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or not isinstance(conversation_id, str) or not 1 <= len(conversation_id) <= 200
                or not isinstance(signed_url, str) or len(signed_url) > 16384):
            raise ValueError("Invalid access")
        return signed_url, conversation_id
    except (KeyError, TypeError, ValueError, AttributeError):
        raise provider_failure() from None


class VoiceAccessRequest(ContractModel):
    session_id: str = Field(min_length=1, max_length=100)
    mode: Literal["voice", "text"]
    draft_id: str | None
    expected_revision: int | None = Field(strict=True, ge=1)


class VoiceEndRequest(ContractModel):
    session_id: str = Field(min_length=1, max_length=100)


class VoiceBindRequest(VoiceEndRequest):
    conversation_id: str = Field(min_length=1, max_length=200)


class LookupPropertyRequest(ContractModel):
    query: str = Field(max_length=200)
    unit_label: str = Field(max_length=100)


class OpenJobsRequest(ContractModel):
    unit_id: str = Field(min_length=1, max_length=100)
    category: RepairCategory
    issue_summary: str = Field(min_length=1, max_length=2000)


class MaintenanceRequest(ContractModel):
    unit_id: str = Field(min_length=1, max_length=100)
    category: RepairCategory


class PrepareDraftRequest(ContractModel):
    draft_id: str | None = Field(max_length=100)
    expected_revision: int = Field(strict=True, ge=0)
    fields: DraftFields


def local_browser_only(request: Request):
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    origin = request.headers.get("origin")
    try:
        parsed = urlparse(origin) if origin else None
        valid_origin = parsed is None or (parsed.scheme in {"http", "https"}
            and parsed.hostname in local_hosts and parsed.port in {None, 5173, 8000}
            and not parsed.username and not parsed.password and parsed.path in {"", "/"})
        valid_host = request.url.hostname in local_hosts
    except ValueError:
        valid_origin, valid_host = False, False
    if not valid_origin or not valid_host or request.headers.get("sec-fetch-site") == "cross-site":
        raise DraftConflict("local_access_only", "Start and manage conversations from the local Hearth workspace.", status_code=403)


class VoiceService:
    def __init__(self, store: Store, settings: VoiceSettings, signed_url_provider: Callable = fetch_signed_access):
        self.store, self.settings, self.signed_url_provider = store, settings, signed_url_provider
        self.drafts = DraftWorkflow(store)

    def config(self):
        return {"available": self.settings.available,
                "message": "ElevenLabs is configured. Start a conversation to connect." if self.settings.available else "Voice is not configured yet. Continue with the saved repair form.",
                "max_duration_seconds": self.settings.max_seconds}

    def _access_draft(self, db, request):
        session_events(db, request.session_id)
        draft = latest_draft(db, request.session_id)
        active = draft if draft and draft.status not in TERMINAL_STATUSES else None
        if active:
            if request.draft_id != active.id or request.expected_revision != active.revision:
                raise DraftConflict("stale_revision", "Load the current saved draft before starting the conversation.", active)
        elif request.draft_id is not None or request.expected_revision is not None:
            raise DraftConflict("draft_not_active", "Start a new conversation with no active draft selected.", draft)
        return active

    def access(self, request: VoiceAccessRequest):
        if not self.settings.available:
            raise DraftConflict("voice_not_configured", self.config()["message"], status_code=503)
        self.store.read(lambda db: self._access_draft(db, request))
        try:
            signed_url, conversation_id = provider_binding(self.signed_url_provider(self.settings))
        except DraftConflict:
            raise
        except Exception:
            raise provider_failure() from None
        token, call_id = secrets.token_urlsafe(32), str(uuid4())
        expires = time() + self.settings.max_seconds
        with self.store.write_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            draft = self._access_draft(db, request)
            db.execute("UPDATE voice_sessions SET revoked=1 WHERE session_id=? AND revoked=0", (request.session_id,))
            db.execute("""INSERT INTO voice_sessions
                (id,session_id,binding_hash,conversation_id,draft_id,expires_at,created_at)
                VALUES (?,?,?,?,?,?,?)""", (call_id, request.session_id, sha256(token.encode()).hexdigest(),
                conversation_id, draft.id if draft else None, expires, datetime.now(timezone.utc).isoformat()))
        context = {"current_draft": draft.model_dump(mode="json", exclude={"session_id"}) if draft else None,
                   "guidance": GUIDANCE, "mode": request.mode}
        return {"voice_session_id": call_id, "signed_url": signed_url,
                "expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
                "max_duration_seconds": self.settings.max_seconds,
                "dynamic_variables": {"secret__hearth_binding": token, "hearth_context": json.dumps(context)}}

    def manage(self, call_id: str, request: VoiceEndRequest, *, end=False):
        with self.store.write_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM voice_sessions WHERE id=? AND session_id=?", (call_id, request.session_id)).fetchone()
            if row is None:
                raise DraftConflict("unknown_voice_session", "Conversation not found for this session.", status_code=404)
            if end:
                db.execute("UPDATE voice_sessions SET revoked=1 WHERE id=?", (call_id,))
            elif row["revoked"] or row["expires_at"] <= time():
                raise DraftConflict("voice_expired", "This conversation has ended. Start again to continue.")
            elif not compare_digest(row["conversation_id"].encode(), request.conversation_id.encode()):
                raise DraftConflict("conversation_mismatch", "The connected conversation does not match the issued access. End it and start again.")
        return {"ok": True}

    def _authenticate(self, db, headers):
        supplied = headers.get("x-hearth-webhook-secret", "")
        token = headers.get("x-hearth-binding", "")
        conversation = headers.get("x-elevenlabs-conversation-id", "")
        if (not self.settings.available or not supplied or len(supplied) > 1024
                or not compare_digest(supplied.encode(), self.settings.webhook_secret.encode())
                or not token or len(token) > 200 or not conversation or len(conversation) > 200):
            raise DraftConflict("unauthorized_tool", "Valid conversation authorization is required.", status_code=401)
        row = db.execute("SELECT * FROM voice_sessions WHERE binding_hash=?", (sha256(token.encode()).hexdigest(),)).fetchone()
        if (row is None or row["revoked"] or row["expires_at"] <= time()
                or not compare_digest(row["conversation_id"].encode(), conversation.encode())):
            raise DraftConflict("unauthorized_tool", "Valid conversation authorization is required.", status_code=401)
        return row

    def _current(self, db, binding):
        if binding["draft_id"]:
            return load_draft(db, binding["draft_id"], binding["session_id"])
        current = latest_draft(db, binding["session_id"])
        return current if current and current.status not in TERMINAL_STATUSES else None

    def _events(self, db, binding, events):
        # Preserve factual recent activity without storing transcript or credentials.
        previous = session_events(db, binding["session_id"])
        db.execute("UPDATE sessions SET events_json=? WHERE id=?", (json.dumps((previous + events)[-30:]), binding["session_id"]))

    def _tool_unavailable(self, headers):
        message = "The record check could not finish. Retry or continue with the saved repair form."
        draft = None
        try:
            with self.store.write_connection() as db:
                db.execute("BEGIN IMMEDIATE")
                binding = self._authenticate(db, headers)
                draft = self._current(db, binding)
                self._events(db, binding, [message])
        except (sqlite3.DatabaseError, DraftConflict):
            # A failed database cannot reliably store activity. Preserve the error
            # response without leaking database details or weakening authorization.
            pass
        raise DraftConflict("backend_unavailable", message, draft, status_code=503) from None

    def tool(self, name, request, headers):
        for attempt in range(2):
            try:
                with self.store.write_connection() as db:
                    db.execute("BEGIN IMMEDIATE")
                    binding = self._authenticate(db, headers)
                    return self._run_tool(db, binding, name, request)
            except sqlite3.OperationalError as error:
                if attempt or not is_temporary_read_error(error):
                    self._tool_unavailable(headers)
                sleep(0.05)
            except sqlite3.DatabaseError:
                self._tool_unavailable(headers)
            except DraftConflict as error:
                if error.status_code != 401:
                    with self.store.write_connection() as db:
                        db.execute("BEGIN IMMEDIATE")
                        binding = self._authenticate(db, headers)
                        self._events(db, binding, [error.content["message"]])
                raise

    def _require_grounded_unit(self, db, binding, unit_id):
        if unit_id != binding["grounded_unit_id"]:
            raise DraftConflict("property_lookup_required", "Look up and uniquely identify the property and unit before checking or changing this repair.", self._current(db, binding))

    def _run_tool(self, db, binding, name, request):
        records = RecordTools(db)
        draft = self._current(db, binding)
        result = {"draft": draft.model_dump(mode="json") if draft else None, "guidance": GUIDANCE}
        events = []
        if name == "lookup_property":
            properties = records.lookup_property(request.query, request.unit_label).properties
            matched = None
            if len(properties) == 1:
                units = [u for u in properties[0].units if normalize_unit(u.label) == normalize_unit(request.unit_label)]
                if len(units) == 1:
                    matched = MatchedUnit(**units[0].model_dump(), property_id=properties[0].id)
            status = "matched" if matched else ("unknown_property" if not properties else "ambiguous_property" if len(properties) > 1 else "needs_human")
            db.execute("UPDATE voice_sessions SET grounded_property_id=?,grounded_unit_id=? WHERE id=?", (
                matched.property_id if matched else None, matched.id if matched else None, binding["id"]))
            result.update(status=status, property_choices=[p.model_dump() for p in properties],
                          matched_unit=matched.model_dump() if matched else None)
            events = [f"Property and unit found: {properties[0].name}, {matched.label}."] if matched else ["Property or unit is unresolved. Ask the landlord to identify one property and unit."]
            if not matched:
                result["guidance"] = events[0]
        elif name == "check_open_jobs":
            self._require_grounded_unit(db, binding, request.unit_id)
            jobs = records.check_open_jobs(request.unit_id, request.category, request.issue_summary)
            result.update(open_jobs=[job.model_dump() for job in jobs], status="duplicate_found" if jobs else "matched")
            events = ["Potential duplicate open job found. Review the existing job with a person."] if jobs else ["No matching open job found for these issue details."]
        elif name == "lookup_maintenance_context":
            self._require_grounded_unit(db, binding, request.unit_id)
            context = records.lookup_maintenance_context(request.unit_id, request.category)
            result.update(context.model_dump(mode="json"))
            events = ["Maintenance policy and relevant history checked.",
                      f"{len(context.approved_contractors)} approved contractor(s) found; availability has not been checked."]
        elif name == "prepare_repair_draft":
            if binding["draft_id"]:
                require_editable(draft)
                if request.draft_id != draft.id:
                    raise DraftConflict("bound_draft_mismatch", "Correct the current bound draft using its exact ID and revision.", draft)
                require_revision(draft, request.expected_revision)
                merged = editable_fields(draft) | request.fields.model_dump(exclude_unset=True)
                changes_location = any(key in request.fields.model_fields_set for key in ("property_id", "unit_id"))
                if changes_location and (merged["property_id"] or merged["unit_id"]):
                    self._require_grounded_unit(db, binding, merged["unit_id"])
                    if merged["property_id"] != binding["grounded_property_id"]:
                        raise DraftConflict("property_lookup_required", "Use the property and unit returned by the latest unique lookup.", draft)
                try:
                    edit_fields = DraftEditFields.model_validate(request.fields.model_dump(exclude_unset=True))
                except ValidationError:
                    raise DraftConflict("invalid_request", "Supply valid editable fields. Use an empty message to clear it.", draft, status_code=422) from None
                draft = self.drafts.edit_in_transaction(db, draft.id, DraftEditRequest(session_id=binding["session_id"], expected_revision=request.expected_revision, fields=edit_fields))
            else:
                if request.draft_id is not None or request.expected_revision != 0:
                    raise DraftConflict("bound_draft_mismatch", "A new conversation draft must use null draft ID and revision zero.", draft)
                if draft and draft.status not in TERMINAL_STATUSES:
                    raise DraftConflict("active_draft_exists", "The form created a draft during this conversation. End and start again to resume that draft.", draft)
                if request.fields.property_id or request.fields.unit_id:
                    self._require_grounded_unit(db, binding, request.fields.unit_id)
                    if request.fields.property_id != binding["grounded_property_id"]:
                        raise DraftConflict("property_lookup_required", "Use the property and unit returned by the latest unique lookup.", draft)
                draft = self.drafts.create_in_transaction(db, DraftCreateRequest(session_id=binding["session_id"], fields=request.fields))
                db.execute("UPDATE voice_sessions SET draft_id=? WHERE id=?", (draft.id, binding["id"]))
            result["draft"] = draft.model_dump(mode="json")
            events = [f"Repair draft saved for review (revision {draft.revision})."]
            if draft.review_reasons:
                events.append("Draft requires review: " + ", ".join(draft.review_reasons) + ".")
        else:
            raise ValueError("Unknown internal tool")
        self._events(db, binding, events)
        result["events"] = events
        return result


def voice_router(service: VoiceService):
    router = APIRouter(prefix="/api/voice")

    @router.get("/config")
    def config(request: Request):
        local_browser_only(request)
        return service.config()

    @router.post("/access")
    def access(payload: VoiceAccessRequest, request: Request):
        local_browser_only(request)
        return service.access(payload)

    @router.post("/{call_id}/bind")
    def bind(call_id: str, payload: VoiceBindRequest, request: Request):
        local_browser_only(request)
        return service.manage(call_id, payload)

    @router.post("/{call_id}/end")
    def end(call_id: str, payload: VoiceEndRequest, request: Request):
        local_browser_only(request)
        return service.manage(call_id, payload, end=True)

    return router
