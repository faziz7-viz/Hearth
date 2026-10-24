"""Integration checks use a real temporary SQLite database for every test."""

from contextlib import contextmanager
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "repairs.sqlite3"


@pytest.fixture
def client(db_path):
    with TestClient(create_app(db_path=db_path)) as connection:
        yield connection


def new_session(client):
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return response.json()["session_id"]


def check(client, session_id=None, **overrides):
    payload = {
        "session_id": session_id or new_session(client),
        "property_query": "Maple Court",
        "unit_label": "4",
        "category": "plumbing",
        "issue_summary": "Leaking kitchen tap",
    }
    payload.update(overrides)
    return client.post("/api/repair-check", json=payload)


def test_session_persists_catalog_and_latest_activity_without_a_draft(client, db_path):
    session_id = new_session(client)
    first = client.get(f"/api/sessions/{session_id}")
    assert first.status_code == 200
    data = first.json()
    assert data["draft"] is None
    assert data["events"] == []
    assert {p["id"] for p in data["properties"]} == {
        "maple-court", "cedar-house", "willow-place"
    }
    assert len(data["recent_jobs"]) == 3
    assert {c["id"] for c in data["contractors"]} == {"ahmed", "lea", "ben"}
    result = check(client, session_id).json()
    with TestClient(create_app(db_path=db_path)) as restarted:
        stored = restarted.get(f"/api/sessions/{session_id}").json()
    assert stored["events"] == result["events"]
    assert stored["draft"] is None


def test_happy_path_uses_saved_property_history_policy_and_approved_plumber(client):
    response = check(client)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "matched"
    assert result["error_code"] is None
    assert result["matched_unit"] == {
        "id": "maple-court-unit-4", "property_id": "maple-court", "label": "Unit 4"
    }
    assert result["open_jobs"] == []
    assert [c["id"] for c in result["approved_contractors"]] == ["ahmed"]
    evidence_ids = {item["record_id"] for item in result["evidence"]}
    assert "demo-history-maple-kitchen-tap" in evidence_ids
    assert "demo-maintenance-policy" in evidence_ids
    assert "ahmed" in evidence_ids
    assert result["events"]


@pytest.mark.parametrize("query", ["", "   "])
def test_unit_four_returns_both_properties_without_selecting_one(client, query):
    result = check(client, property_query=query, unit_label="Unit 4").json()
    assert result["status"] == "ambiguous_property"
    assert {p["id"] for p in result["property_choices"]} == {"maple-court", "cedar-house"}
    assert result["matched_unit"] is None
    assert result["open_jobs"] == []
    assert result["approved_contractors"] == []


@pytest.mark.parametrize("query", ["maple-court", " MAPLE   COURT ", "maple"])
def test_property_id_exact_name_and_literal_partial_match(client, query):
    result = check(client, property_query=query).json()
    assert result["status"] == "matched"
    assert result["matched_unit"]["property_id"] == "maple-court"


@pytest.mark.parametrize("query", ["Missing Building", "%", "_", "' OR 1=1 --"])
def test_unknown_property_does_not_treat_query_as_sql_pattern(client, query):
    result = check(client, property_query=query).json()
    assert result["status"] == "unknown_property"
    assert result["matched_unit"] is None
    assert result["approved_contractors"] == []


def test_unknown_unit_is_not_substituted(client):
    result = check(client, unit_label="40").json()
    assert result["status"] == "needs_human"
    assert result["error_code"] == "unknown_unit"
    assert result["matched_unit"] is None


def test_cedar_bathroom_tap_matches_existing_open_job(client):
    result = check(
        client, property_query="cedar-house", issue_summary="The bathroom tap is leaking"
    ).json()
    assert result["status"] == "duplicate_found"
    assert [job["id"] for job in result["open_jobs"]] == ["demo-job-cedar-bathroom-tap"]
    assert any(e["record_id"] == "demo-job-cedar-bathroom-tap" for e in result["evidence"])


@pytest.mark.parametrize("summary", ["Leaking kitchen tap", "Blocked bathroom toilet", "Leaking bathroom pipe"])
def test_unrelated_open_job_in_same_unit_and_trade_is_not_duplicate(client, summary):
    result = check(client, property_query="Cedar House", issue_summary=summary).json()
    assert result["status"] == "matched"
    assert result["open_jobs"] == []


@pytest.mark.parametrize(
    ("category", "contractor"), [("electrical", "lea"), ("general", "ben")]
)
def test_supported_trades_return_explicit_approved_contractor(client, category, contractor):
    result = check(client, category=category, issue_summary="Routine repair").json()
    assert result["status"] == "matched"
    assert [c["id"] for c in result["approved_contractors"]] == [contractor]


def test_unsupported_trade_requires_human_without_inventing_contractor(client):
    result = check(client, category="roofing").json()
    assert result["status"] == "needs_human"
    assert result["error_code"] == "unsupported_category"
    assert result["approved_contractors"] == []


def test_supported_trade_with_no_property_approval_requires_human(client):
    result = check(client, property_query="Willow Place", unit_label="2").json()
    assert result["status"] == "needs_human"
    assert result["error_code"] == "no_approved_contractor"
    assert result["approved_contractors"] == []


def test_safety_concern_requires_human_and_no_repair_instructions(client):
    result = check(client, category="electrical", issue_summary="Sparks and a burning smell").json()
    assert result["status"] == "needs_human"
    assert result["error_code"] == "safety_concern"
    assert result["approved_contractors"] == []


@pytest.mark.parametrize("overrides", [
    {"property_query": ""}, {"property_query": "Missing Building"}, {"unit_label": "404"}
])
def test_safety_routing_precedes_property_or_unit_clarification(client, overrides):
    result = check(client, issue_summary="Sparks and a burning smell", **overrides).json()
    assert result["status"] == "needs_human"
    assert result["error_code"] == "safety_concern"
    assert result["property_choices"] == []
    assert result["matched_unit"] is None
    assert result["open_jobs"] == []
    assert result["approved_contractors"] == []


def test_empty_issue_requires_information(client):
    result = check(client, issue_summary="  ").json()
    assert result["status"] == "needs_human"
    assert result["error_code"] == "missing_issue"


def test_unknown_session_has_structured_errors(client):
    read = client.get("/api/sessions/missing-session")
    assert read.status_code == 404
    assert read.json()["error_code"] == "unknown_session"
    response = check(client, session_id="missing-session")
    assert response.status_code == 404
    assert response.json()["status"] == "error"
    assert response.json()["error_code"] == "unknown_session"


def test_malformed_request_has_structured_error_and_does_not_create_session(client, db_path):
    response = client.post("/api/repair-check", json={"property_query": 42})
    assert response.status_code == 422
    assert response.json()["status"] == "error"
    assert response.json()["error_code"] == "invalid_request"
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def business_snapshot(db_path):
    with sqlite3.connect(db_path) as db:
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sessions' ORDER BY name"
        )]
        return {table: db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall() for table in tables}


def test_checks_do_not_mutate_business_records_or_create_drafts_and_orders(client, db_path):
    before = business_snapshot(db_path)
    for overrides in [
        {}, {"property_query": ""}, {"property_query": "missing"},
        {"property_query": "Cedar House", "issue_summary": "Leaking bathroom tap"},
        {"category": "roofing"},
    ]:
        assert check(client, **overrides).status_code == 200
    assert business_snapshot(db_path) == before
    assert before["drafts"] == []
    assert before["work_orders"] == []
    assert before["draft_history"] == []


def test_seed_initialization_does_not_restore_deleted_or_overwrite_edited_records(client, db_path):
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE properties SET name='Maple Court Updated' WHERE id='maple-court'")
        db.execute("DELETE FROM jobs WHERE id='demo-job-maple-hallway-light'")
    with TestClient(create_app(db_path=db_path)) as restarted:
        result = restarted.get(f"/api/sessions/{new_session(restarted)}").json()
    assert next(p for p in result["properties"] if p["id"] == "maple-court")["name"] == "Maple Court Updated"
    assert len(result["recent_jobs"]) == 2


def test_business_read_connection_enforces_query_only(client, db_path):
    store = client.app.state.store
    with store.read_connection() as db:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("DELETE FROM jobs")
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 3


def inject_read_failure(monkeypatch, store, failures, error_message):
    original = store.read_connection
    state = {"attempts": 0}

    @contextmanager
    def flaky_connection():
        state["attempts"] += 1
        if state["attempts"] <= failures:
            raise sqlite3.OperationalError(error_message)
        with original() as db:
            yield db

    monkeypatch.setattr(store, "read_connection", flaky_connection)
    return state


def test_one_temporary_read_failure_retries_and_returns_real_records(client, monkeypatch):
    session_id = new_session(client)
    attempts = inject_read_failure(monkeypatch, client.app.state.store, 1, "database is locked")
    response = check(client, session_id)
    assert response.status_code == 200
    assert response.json()["status"] == "matched"
    assert response.json()["approved_contractors"][0]["id"] == "ahmed"
    assert attempts["attempts"] == 2


def test_persistent_temporary_failure_stops_after_one_retry(client, monkeypatch):
    session_id = new_session(client)
    attempts = inject_read_failure(monkeypatch, client.app.state.store, 3, "database is locked")
    response = check(client, session_id)
    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["error_code"] == "backend_unavailable"
    assert response.json()["approved_contractors"] == []
    assert attempts["attempts"] == 2


def test_non_temporary_database_failure_is_not_retried(client, monkeypatch):
    session_id = new_session(client)
    attempts = inject_read_failure(monkeypatch, client.app.state.store, 3, "no such table: properties")
    response = check(client, session_id)
    assert response.status_code == 503
    assert response.json()["error_code"] == "backend_unavailable"
    assert attempts["attempts"] == 1


def test_ambiguous_and_unknown_lookups_do_not_retry(client, monkeypatch):
    session_id = new_session(client)
    attempts = inject_read_failure(monkeypatch, client.app.state.store, 0, "")
    assert check(client, session_id, property_query="").json()["status"] == "ambiguous_property"
    assert attempts["attempts"] == 1
    assert check(client, session_id, property_query="Missing").json()["status"] == "unknown_property"
    assert attempts["attempts"] == 2


def test_persisted_workflow_routes_validate_requests_without_writes(client):
    for path in ["/api/drafts", "/api/drafts/example/approve"]:
        response = client.post(path, json={})
        assert response.status_code == 422
        assert response.json()["error_code"] == "invalid_request"
    assert client.get("/api/work-orders").json() == []


def test_seed_failure_rolls_back_records_and_marker_together(db_path, tmp_path, monkeypatch):
    from backend.app import store as store_module

    original_seed = store_module.SEED_PATH
    seed = json.loads(original_seed.read_text())
    seed["contractors"].append(seed["contractors"][0])
    invalid_seed = tmp_path / "invalid-seed.json"
    invalid_seed.write_text(json.dumps(seed))
    monkeypatch.setattr(store_module, "SEED_PATH", invalid_seed)
    with pytest.raises(sqlite3.IntegrityError):
        store_module.Store(db_path).initialize()
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    monkeypatch.setattr(store_module, "SEED_PATH", original_seed)
    with TestClient(create_app(db_path=db_path)) as client:
        assert check(client).json()["status"] == "matched"


def test_exact_property_match_wins_over_partial_name_collision(client, db_path):
    with sqlite3.connect(db_path) as db:
        db.execute("INSERT INTO properties VALUES ('maple-annex', 'Maple Court Annex')")
        db.execute("INSERT INTO units VALUES ('maple-annex-unit-4', 'maple-annex', 'Unit 4')")
    result = check(client, property_query="Maple Court").json()
    assert result["status"] == "matched"
    assert [prop["id"] for prop in result["property_choices"]] == ["maple-court"]
    assert check(client, property_query="maple").json()["status"] == "ambiguous_property"


def test_read_retry_budget_is_shared_across_different_tools(client, monkeypatch):
    from backend.app.tools import RecordTools

    session_id = new_session(client)
    original_jobs = RecordTools.check_open_jobs
    calls = {"jobs": 0, "context": 0}

    def fail_jobs_once(self, *args):
        calls["jobs"] += 1
        if calls["jobs"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return original_jobs(self, *args)

    def fail_context(self, *args):
        calls["context"] += 1
        raise sqlite3.OperationalError("database table is locked")

    monkeypatch.setattr(RecordTools, "check_open_jobs", fail_jobs_once)
    monkeypatch.setattr(RecordTools, "lookup_maintenance_context", fail_context)
    response = check(client, session_id)
    assert response.status_code == 503
    assert response.json()["error_code"] == "backend_unavailable"
    assert calls == {"jobs": 2, "context": 1}
    assert client.get(f"/api/sessions/{session_id}").json()["events"] == []


def test_invalid_request_and_unknown_session_do_not_retry(client, monkeypatch):
    attempts = inject_read_failure(monkeypatch, client.app.state.store, 0, "")
    assert client.post("/api/repair-check", json={}).status_code == 422
    assert attempts["attempts"] == 0
    assert check(client, session_id="missing-session").status_code == 404
    assert attempts["attempts"] == 1
