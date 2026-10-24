"""Voice boundaries exercise real routes, durable SQLite state, and the shared workflow."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from http.client import BadStatusLine, IncompleteRead
from io import BytesIO
import json
import sqlite3
import ssl
from threading import Barrier
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.tests.test_drafts import fields, saved, patch, cancel, approve
from backend.tests.test_workflow import new_session


def settings(**overrides):
    from backend.app.voice import VoiceSettings
    return replace(VoiceSettings(api_key="private-key", agent_id="agent_demo", webhook_secret="w" * 40,
                                 public_url="https://gateway.example", max_seconds=600), **overrides)


@contextmanager
def clients(path, configuration=None, provider=None):
    from backend.app.voice_gateway import create_gateway
    config = configuration or settings()
    issue = provider or (lambda _: {"signed_url": "wss://api.elevenlabs.io/v1/convai/conversation?conversation_id=conv_demo&signature=temporary"})
    with TestClient(create_app(path, voice_settings=config, signed_url_provider=issue), base_url="http://127.0.0.1:8000") as api:
        with TestClient(create_gateway(path, voice_settings=config)) as gateway:
            yield api, gateway


@pytest.fixture
def pair(tmp_path):
    with clients(tmp_path / "voice.sqlite3") as value:
        yield value


def access(api, session=None, draft=None, **overrides):
    return api.post("/api/voice/access", json={"session_id": session or new_session(api), "mode": "voice",
        "draft_id": draft["id"] if draft else None, "expected_revision": draft["revision"] if draft else None, **overrides})


def start(api, session=None, draft=None):
    response = access(api, session, draft)
    assert response.status_code == 200, response.text
    return response.json()


def headers(call, **overrides):
    return {"X-Hearth-Webhook-Secret": "w" * 40,
            "X-Hearth-Binding": call["dynamic_variables"]["secret__hearth_binding"],
            "X-ElevenLabs-Conversation-Id": "conv_demo", **overrides}


def tool(gateway, call, name, body, **overrides):
    return gateway.post(f"/voice/tools/{name}", headers=headers(call, **overrides), json=body)


def lookup(gateway, call, **overrides):
    return tool(gateway, call, "lookup_property", {"query": "Maple Court", "unit_label": "4", **overrides})


def prepare(gateway, call, draft=None, changes=None):
    return tool(gateway, call, "prepare_repair_draft", {"draft_id": draft["id"] if draft else None,
        "expected_revision": draft["revision"] if draft else 0, "fields": changes if changes is not None else fields()})


def test_unconfigured_voice_is_graceful_and_local_origin_is_enforced(tmp_path):
    with clients(tmp_path / "empty.sqlite3", settings(api_key="")) as (api, _):
        assert api.get("/api/voice/config").json()["available"] is False
        assert access(api).status_code == 503
        response = api.get("/api/voice/config", headers={"Origin": "https://evil.example"})
        assert response.status_code == 403
        assert api.get("/api/voice/config", headers={"Host": "public.example"}).status_code == 403
        assert api.get("/api/voice/config", headers={"Origin": "http://localhost:5173"}).status_code == 200


@pytest.mark.parametrize("result", [
    {"signed_url": "wss://api.elevenlabs.io/v1/convai/conversation?signature=secret"},
    {"signed_url": "wss://evil.example/?conversation_id=conv_demo"},
    {"signed_url": "wss://api.elevenlabs.io/v1/convai/conversation?conversation_id=conv_demo", "conversation_id": "different"},
])
def test_bad_provider_response_fails_closed_without_creating_binding(tmp_path, result):
    path = tmp_path / "provider.sqlite3"
    with clients(path, provider=lambda _: result) as (api, _):
        response = access(api)
        assert response.status_code == 502
        assert "secret" not in response.text
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT count(*) FROM voice_sessions").fetchone()[0] == 0


@pytest.fixture
def public_gateway_transport(monkeypatch):
    """Keep urllib's real status/redirect handling; replace only external HTTPS I/O."""
    state = {"status": 401, "body": b'{"error_code":"unauthorized_tool","message":"Valid conversation authorization is required."}',
             "requests": []}

    def receive(handler, request):
        state["requests"].append((request, handler._context))
        if "error" in state:
            raise state["error"]
        return HTTPError(request.full_url, state["status"], "Gateway response",
                         {"Location": "https://unexpected.example/redirect"}, BytesIO(state["body"]))

    monkeypatch.setattr(HTTPSHandler, "https_open", receive)
    return state


def test_provider_failure_is_redacted(tmp_path, public_gateway_transport):
    from backend.app.voice import fetch_signed_access
    from unittest.mock import patch as mock_patch
    with mock_patch("backend.app.voice.urlopen", side_effect=URLError("private-key secret upstream body")):
        with clients(tmp_path / "error.sqlite3", provider=fetch_signed_access) as (api, _):
            response = access(api)
            assert response.status_code == 502
            assert response.json()["error_code"] == "voice_provider_unavailable"
            assert "private-key" not in response.text and "upstream body" not in response.text


def test_signed_access_checks_public_gateway_before_issuing_provider_access(monkeypatch, public_gateway_transport):
    from backend.app.voice import fetch_signed_access
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return b'{"signed_url":"wss://api.elevenlabs.io/?signature=temporary","conversation_id":"conv_issued"}'
    def receive(request, timeout, context=None):
        assert len(public_gateway_transport["requests"]) == 1
        captured.update(url=request.full_url, headers=request.headers, timeout=timeout, context=context)
        return Response()
    monkeypatch.setattr("backend.app.voice.urlopen", receive)
    assert fetch_signed_access(settings())["conversation_id"] == "conv_issued"
    assert "include_conversation_id=true" in captured["url"]
    assert captured["headers"]["Xi-api-key"] == "private-key"
    assert captured["timeout"] == 5
    assert captured["context"] is not None
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED
    assert captured["context"].check_hostname is True
    request, context = public_gateway_transport["requests"][0]
    assert request.full_url == "https://gateway.example/voice/tools/lookup_property"
    assert request.method == "POST" and request.data == b"{}"
    assert request.timeout == 5
    assert "private-key" not in str(request.headers) and "w" * 40 not in str(request.headers)
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname is True


@pytest.mark.parametrize("failure", [
    {"error": URLError("private-key DNS resolution failed")},
    {"error": ssl.SSLCertVerificationError("private-key untrusted certificate")},
    {"error": TimeoutError("private-key timed out")},
    {"error": BadStatusLine("private-key invalid HTTP")},
    {"error": IncompleteRead(b"private-key truncated response")},
    {"status": 302},
    {"status": 200},
    {"status": 401, "body": b'{"error_code":"unrelated_service"}'},
    {"status": 401, "body": b"private-key invalid JSON"},
    {"status": 401, "body": b'{"error_code":"unauthorized_tool","extra":"' + b"x" * 4096 + b'"}'},
])
def test_unavailable_public_gateway_blocks_provider_access_without_binding(tmp_path, monkeypatch, public_gateway_transport, failure):
    from backend.app.voice import fetch_signed_access
    public_gateway_transport.update(failure)
    provider_requests = []

    def provider(request, **kwargs):
        provider_requests.append(request.full_url)
        raise URLError("provider must not be contacted")

    monkeypatch.setattr("backend.app.voice.urlopen", provider)
    path = tmp_path / "gateway-unavailable.sqlite3"
    with clients(path, provider=fetch_signed_access) as (api, _):
        response = access(api)
        assert response.status_code == 502
        assert response.json()["error_code"] == "voice_gateway_unavailable"
        assert "form" in response.json()["message"]
        assert "private-key" not in response.text and "unexpected.example" not in response.text
        assert provider_requests == []
        assert len(public_gateway_transport["requests"]) == 1
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT count(*) FROM voice_sessions").fetchone()[0] == 0


def test_session_ownership_access_revision_and_browser_binding(pair):
    api, gateway = pair
    session = new_session(api)
    draft = saved(api, session)
    assert access(api, session).status_code == 409
    assert access(api, session, draft, expected_revision=99).status_code == 409
    other = new_session(api)
    assert access(api, other, draft).status_code == 409
    call = start(api, session, draft)
    assert "private-key" not in json.dumps(call)
    endpoint = f"/api/voice/{call['voice_session_id']}/bind"
    assert api.post(endpoint, json={"session_id": other, "conversation_id": "conv_demo"}).status_code == 404
    assert api.post(endpoint, json={"session_id": session, "conversation_id": "wrong"}).status_code == 409
    assert api.post(endpoint, json={"session_id": session, "conversation_id": "conv_demo"}).json() == {"ok": True}


@pytest.mark.parametrize("override", [
    {"X-Hearth-Webhook-Secret": ""}, {"X-Hearth-Webhook-Secret": "incorrect"},
    {"X-Hearth-Binding": ""}, {"X-Hearth-Binding": "wrong"},
    {"X-ElevenLabs-Conversation-Id": ""}, {"X-ElevenLabs-Conversation-Id": "wrong"},
])
def test_each_gateway_credential_is_required_before_read_or_write(pair, override):
    api, gateway = pair
    call = start(api)
    response = tool(gateway, call, "lookup_property", {"query": "Maple Court", "unit_label": "4"}, **override)
    assert response.status_code == 401
    assert "properties" not in response.json()


def test_lookup_ambiguity_and_record_grounding_prevent_guessed_property(pair):
    api, gateway = pair
    session = new_session(api)
    call = start(api, session)
    result = lookup(gateway, call, query="").json()
    assert result["status"] == "ambiguous_property" and len(result["property_choices"]) == 2
    assert result["matched_unit"] is None and result["guidance"]
    assert prepare(gateway, call).status_code == 409
    result = lookup(gateway, call).json()
    assert result["matched_unit"]["id"] == "maple-court-unit-4"
    assert prepare(gateway, call, changes=fields(property_id="cedar-house", unit_id="cedar-house-unit-4")).status_code == 409
    assert api.get(f"/api/sessions/{session}").json()["draft"] is None
    assert prepare(gateway, call).status_code == 200


def test_four_tools_create_and_correct_same_saved_draft_without_orders(pair):
    api, gateway = pair
    session = new_session(api)
    call = start(api, session)
    assert lookup(gateway, call).status_code == 200
    checked = tool(gateway, call, "check_open_jobs", {"unit_id": "maple-court-unit-4", "category": "plumbing", "issue_summary": "Leaking kitchen tap"}).json()
    assert checked["open_jobs"] == []
    context = tool(gateway, call, "lookup_maintenance_context", {"unit_id": "maple-court-unit-4", "category": "plumbing"}).json()
    assert [c["id"] for c in context["approved_contractors"]] == ["ahmed"]
    response = prepare(gateway, call)
    assert response.status_code == 200, response.text
    draft = response.json()["draft"]
    assert draft["status"] == "ready_for_review" and "session_id" not in draft
    changed = prepare(gateway, call, draft, {"access_notes": "Tenant home after 3 pm"}).json()["draft"]
    assert changed["id"] == draft["id"] and changed["revision"] == 2
    assert changed["access_notes"] == "Tenant home after 3 pm"
    assert api.get(f"/api/sessions/{session}").json()["draft"] == changed | {"session_id": session}
    assert api.get(f"/api/sessions/{session}").json()["events"]
    assert api.get("/api/work-orders").json() == []


def test_invalid_contractor_duplicate_and_safety_use_current_workflow(pair):
    api, gateway = pair
    call = start(api)
    lookup(gateway, call, query="Cedar House")
    draft = prepare(gateway, call, changes=fields(property_id="cedar-house", unit_id="cedar-house-unit-4", issue_summary="Leaking bathroom tap")).json()["draft"]
    assert draft["status"] == "duplicate_found"
    draft = prepare(gateway, call, draft, {"contractor_id": "absent"}).json()["draft"]
    assert "contractor_not_approved" in draft["review_reasons"]
    draft = prepare(gateway, call, draft, {"issue_summary": "There are sparks"}).json()["draft"]
    assert draft["status"] == "needs_human"
    assert api.get("/api/work-orders").json() == []


def test_stale_voice_cannot_overwrite_form_edit_or_terminal_draft(pair):
    api, gateway = pair
    session = new_session(api)
    draft = saved(api, session)
    call = start(api, session, draft)
    changed = patch(api, draft, access_notes="Keep my form edit").json()
    response = prepare(gateway, call, draft, {"access_notes": "Old voice edit"})
    assert response.status_code == 409 and response.json()["draft"] == {k: v for k, v in changed.items() if k != "session_id"}
    cancelled = cancel(api, changed).json()
    for response in [prepare(gateway, call, cancelled, {"access_notes": "Try again"}), prepare(gateway, call)]:
        assert response.status_code == 409
    assert api.get(f"/api/sessions/{session}").json()["draft"] == cancelled


def test_concurrent_create_and_replayed_edit_cannot_duplicate_or_overwrite(pair):
    api, gateway = pair
    session = new_session(api)
    call = start(api, session)
    lookup(gateway, call)
    barrier = Barrier(4)
    def create_once(_):
        barrier.wait()
        return prepare(gateway, call)
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(create_once, range(4)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409]
    draft = next(r.json()["draft"] for r in responses if r.status_code == 200)
    edited = prepare(gateway, call, draft, {"access_notes": "One update"}).json()["draft"]
    retry = prepare(gateway, call, draft, {"access_notes": "Replay"})
    assert retry.status_code == 409 and retry.json()["draft"] == edited
    assert api.get("/api/work-orders").json() == []


def test_new_start_end_expiry_and_restart_enforce_durable_binding(tmp_path):
    path = tmp_path / "durable.sqlite3"
    with clients(path) as (api, gateway):
        session = new_session(api)
        first = start(api, session)
        second = start(api, session)
        assert lookup(gateway, first).status_code == 401
        lookup(gateway, second)
        draft = prepare(gateway, second).json()["draft"] | {"session_id": session}
        assert approve(api, draft).status_code == 409
        with sqlite3.connect(path) as db:
            hashes = [r[0] for r in db.execute("SELECT binding_hash FROM voice_sessions")]
        assert second["dynamic_variables"]["secret__hearth_binding"] not in hashes
    with clients(path) as (api, gateway):
        assert lookup(gateway, second).json()["draft"] == {k: v for k, v in draft.items() if k != "session_id"}
        other = new_session(api)
        endpoint = f"/api/voice/{second['voice_session_id']}/end"
        assert api.post(endpoint, json={"session_id": other}).status_code == 404
        assert api.post(endpoint, json={"session_id": session}).json() == {"ok": True}
        assert lookup(gateway, second).status_code == 401
        third = start(api, session, draft)
        with sqlite3.connect(path) as db:
            db.execute("UPDATE voice_sessions SET expires_at=0 WHERE id=?", (third["voice_session_id"],))
        assert lookup(gateway, third).status_code == 401
        assert api.get(f"/api/sessions/{session}").json()["draft"] == draft
        assert approve(api, draft).status_code == 200


def test_gateway_exposes_exactly_four_tools_and_rejects_authority_fields(pair):
    api, gateway = pair
    call = start(api)
    for path in ["/api/sessions", "/api/drafts", "/api/work-orders", "/docs", "/openapi.json", "/redoc", "/voice/tools/approve"]:
        assert gateway.get(path).status_code == 404
        assert gateway.post(path, json={}).status_code == 404
    for extra in ["session_id", "status", "evidence", "approved"]:
        response = tool(gateway, call, "prepare_repair_draft", {"draft_id": None, "expected_revision": 0, "fields": fields() | {extra: "fake"}})
        assert response.status_code == 422
    assert api.post("/voice/tools/lookup_property", json={}).status_code == 404


@pytest.mark.parametrize("terminal", ["cancelled", "approved"])
def test_new_conversation_does_not_return_previous_terminal_draft(pair, terminal):
    api, gateway = pair
    session = new_session(api)
    old = saved(api, session)
    if terminal == "cancelled":
        cancel(api, old)
    else:
        approve(api, old)
    call = start(api, session)
    assert lookup(gateway, call).json()["draft"] is None
    response = prepare(gateway, call, changes=fields(issue_summary="Blocked bathroom toilet"))
    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["id"] != old["id"] and draft["revision"] == 1


def test_gateway_authenticates_before_parsing_malformed_or_forbidden_body(pair):
    _, gateway = pair
    for body in ['{', '{"session_id":"invented"}']:
        response = gateway.post("/voice/tools/prepare_repair_draft", content=body,
                                headers={"Content-Type": "application/json"})
        assert response.status_code == 401


def test_temporary_tool_read_retries_once_then_reports_failure_and_preserves_draft(pair, monkeypatch):
    from backend.app.tools import RecordTools
    api, gateway = pair
    session = new_session(api)
    draft = saved(api, session)
    call = start(api, session, draft)
    actual = RecordTools.lookup_property
    attempts = []
    def temporary(self, *args):
        attempts.append(1)
        if len(attempts) == 1:
            raise sqlite3.OperationalError("database is locked")
        return actual(self, *args)
    monkeypatch.setattr(RecordTools, "lookup_property", temporary)
    assert lookup(gateway, call).json()["matched_unit"]["id"] == "maple-court-unit-4"
    assert len(attempts) == 2
    attempts.clear()
    def unavailable(self, *args):
        attempts.append(1)
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(RecordTools, "lookup_property", unavailable)
    response = lookup(gateway, call)
    assert response.status_code == 503
    assert response.json()["error_code"] == "backend_unavailable"
    assert len(attempts) == 2
    state = api.get(f"/api/sessions/{session}").json()
    assert state["draft"] == draft
    assert any("could not finish" in event for event in state["events"])
    assert api.get("/api/work-orders").json() == []


def test_approved_bound_draft_cannot_be_replaced_by_voice(pair):
    api, gateway = pair
    session = new_session(api)
    draft = saved(api, session)
    call = start(api, session, draft)
    # Simulate a competing pre-existing process having already approved the draft.
    with sqlite3.connect(api.app.state.store.db_path) as db:
        snapshot = draft | {"status": "approved"}
        db.execute("UPDATE drafts SET status='approved',snapshot_json=? WHERE id=?", (json.dumps(snapshot), draft["id"]))
    for response in [prepare(gateway, call), prepare(gateway, call, draft, {"access_notes": "Change"})]:
        assert response.status_code == 409 and response.json()["error_code"] == "draft_approved"
    assert api.get(f"/api/sessions/{session}").json()["draft"] == snapshot


def test_cross_session_draft_id_and_model_session_fields_are_rejected(pair):
    api, gateway = pair
    first = saved(api)
    second = saved(api)
    call = start(api, first["session_id"], first)
    response = prepare(gateway, call, second, {"access_notes": "Other repair"})
    assert response.status_code == 409 and response.json()["draft"] == {k: v for k, v in first.items() if k != "session_id"}
    response = tool(gateway, call, "prepare_repair_draft", {"draft_id": first["id"], "expected_revision": 1,
        "session_id": second["session_id"], "fields": {"access_notes": "Other"}})
    assert response.status_code == 422
    assert api.get(f"/api/sessions/{second['session_id']}").json()["draft"] == second


def test_access_revalidates_revision_after_provider_call_before_revoking_previous(tmp_path):
    path = tmp_path / "race.sqlite3"
    state = {}
    def issue(_):
        if state.get("draft"):
            patch(state["api"], state["draft"], access_notes="Saved while access was loading")
        return {"signed_url": "wss://api.elevenlabs.io/v1/convai/conversation?conversation_id=conv_demo&signature=temporary"}
    with clients(path, provider=issue) as (api, gateway):
        session = new_session(api)
        old = saved(api, session)
        first = start(api, session, old)
        state.update(api=api, draft=old)
        assert access(api, session, old).status_code == 409
        assert lookup(gateway, first).status_code == 200
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT count(*) FROM voice_sessions").fetchone()[0] == 1


def test_failed_binding_or_draft_write_is_atomic(pair):
    api, gateway = pair
    session = new_session(api)
    call = start(api, session)
    lookup(gateway, call)
    with sqlite3.connect(api.app.state.store.db_path) as db:
        db.execute("CREATE TRIGGER fail_binding BEFORE UPDATE OF draft_id ON voice_sessions BEGIN SELECT RAISE(ABORT,'private failure'); END")
    response = prepare(gateway, call)
    assert response.status_code == 503 and "private failure" not in response.text
    assert api.get(f"/api/sessions/{session}").json()["draft"] is None
    with sqlite3.connect(api.app.state.store.db_path) as db:
        assert db.execute("SELECT count(*) FROM drafts").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM draft_history").fetchone()[0] == 0


@pytest.mark.parametrize("configured,expected", [("5", 60), ("750", 600), ("invalid", 600), ("120", 120)])
def test_environment_duration_stays_within_demo_limit(monkeypatch, tmp_path, configured, expected):
    from backend.app.voice import VoiceSettings
    monkeypatch.setattr("backend.app.voice.ROOT_ENV", tmp_path / "absent.env")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "isolated-test-key")
    monkeypatch.setenv("HEARTH_WEBHOOK_SECRET", "isolated-test-secret" * 3)
    monkeypatch.setenv("HEARTH_VOICE_MAX_SECONDS", configured)
    assert VoiceSettings.from_env().max_seconds == expected


def test_access_accepts_top_level_provider_id_and_exposes_no_permanent_secret(tmp_path):
    response = {"signed_url": "wss://api.elevenlabs.io/v1/convai/conversation?signature=temporary", "conversation_id": "conv_demo"}
    with clients(tmp_path / "top-level.sqlite3", provider=lambda _: response) as (api, gateway):
        call = start(api)
        assert lookup(gateway, call).status_code == 200
        assert "private-key" not in json.dumps(call) and "w" * 40 not in json.dumps(call)


def test_settings_repr_does_not_disclose_private_credentials():
    configured = settings(api_key="test-api-secret", webhook_secret="test-webhook-secret" * 3)
    assert "test-api-secret" not in repr(configured)
    assert "test-webhook-secret" not in repr(configured)


def test_gateway_results_and_errors_do_not_expose_app_session_capability(pair):
    api, gateway = pair
    session = new_session(api)
    draft = saved(api, session)
    call = start(api, session, draft)
    assert session not in lookup(gateway, call).text
    changed = patch(api, draft, access_notes="Form correction").json()
    failed = prepare(gateway, call, draft, {"access_notes": "Stale voice"})
    assert failed.status_code == 409
    assert session not in failed.text
    assert failed.json()["draft"]["id"] == changed["id"]
    assert api.get(f"/api/sessions/{session}").json()["draft"]["session_id"] == session
