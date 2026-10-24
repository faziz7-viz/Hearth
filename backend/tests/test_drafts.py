"""Persisted workflow contract using isolated real SQLite databases and API calls."""

from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.store import Store
from backend.tests.test_workflow import business_snapshot, check, new_session


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "drafts.sqlite3"


@pytest.fixture
def client(db_path):
    with TestClient(create_app(db_path)) as connection:
        yield connection


def fields(**overrides):
    result = {
        "property_id": "maple-court", "unit_id": "maple-court-unit-4",
        "category": "plumbing", "issue_summary": "Leaking kitchen tap",
        "contractor_id": "ahmed", "preferred_date": None,
        "access_notes": "Call before arrival.", "contractor_message": "Please inspect the kitchen tap.\nThanks!  ",
    }
    return result | overrides


def create(client, session_id=None, **overrides):
    return client.post("/api/drafts", json={
        "session_id": session_id or new_session(client), "fields": fields(**overrides),
    })


def saved(client, session_id=None, **overrides):
    response = create(client, session_id, **overrides)
    assert response.status_code == 200, response.text
    return response.json()


def patch(client, draft, **changes):
    return client.patch(f"/api/drafts/{draft['id']}", json={
        "session_id": draft["session_id"], "expected_revision": draft["revision"], "fields": changes,
    })


def approve(client, draft, key="first-key", **overrides):
    return client.post(f"/api/drafts/{draft['id']}/approve", json={
        "session_id": draft["session_id"], "expected_revision": draft["revision"],
        "idempotency_key": key, **overrides,
    })


def cancel(client, draft):
    return client.post(f"/api/drafts/{draft['id']}/cancel", json={
        "session_id": draft["session_id"], "expected_revision": draft["revision"],
    })


def assert_conflict(response, code):
    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == code
    assert response.json()["message"]


def test_save_edit_exact_snapshot_and_restart_preserve_user_text(client, db_path):
    draft = saved(client)
    assert draft["revision"] == 1
    assert draft["status"] == "ready_for_review"
    assert draft["missing_fields"] == [] and draft["review_reasons"] == []
    assert {e["record_id"] for e in draft["evidence"]} >= {
        "demo-history-maple-kitchen-tap", "demo-maintenance-policy", "ahmed", "maple-court-unit-4",
    }
    changes = {"issue_summary": " Kitchen tap leak, constant.  ", "access_notes": "  Ring bell\nWait outside. ",
               "preferred_date": "2026-11-04", "contractor_message": " Hello Ahmed,\nPlease inspect.  "}
    response = patch(client, draft, **changes)
    assert response.status_code == 200
    edited = response.json()
    assert edited["id"] == draft["id"] and edited["revision"] == 2
    for name, value in changes.items():
        assert edited[name] == value
    assert patch(client, edited, **changes).json() == edited
    response = approve(client, edited)
    assert response.status_code == 200, response.text
    order = response.json()
    assert order["snapshot"] == edited
    assert order["approved_revision"] == 2 and order["draft_id"] == draft["id"]
    with TestClient(create_app(db_path)) as restarted:
        current = restarted.get(f"/api/sessions/{draft['session_id']}").json()["draft"]
        assert current == edited | {"status": "approved"}
        assert restarted.get("/api/work-orders").json() == [order]
    with sqlite3.connect(db_path) as db:
        job = db.execute("SELECT issue_summary, status FROM jobs WHERE id = ?", (order["id"],)).fetchone()
        assert job == (changes["issue_summary"], "approved")
        snapshots = [json.loads(row[0]) for row in db.execute(
            "SELECT snapshot_json FROM draft_history WHERE draft_id=? AND event_type IN ('created','edited') ORDER BY id", (draft["id"],)
        )]
        assert snapshots == [draft, edited]


def test_create_retry_returns_existing_without_overwriting_active_draft(client):
    session = new_session(client)
    draft = saved(client, session)
    assert create(client, session).json() == draft
    response = create(client, session, access_notes="Changed request")
    assert_conflict(response, "active_draft_exists")
    assert response.json()["draft"] == draft
    assert client.get(f"/api/sessions/{session}").json()["draft"] == draft


def test_message_generated_once_when_omitted_or_null_and_preserved_on_edit(client):
    session = new_session(client)
    payload = fields()
    payload.pop("contractor_message")
    response = client.post("/api/drafts", json={"session_id": session, "fields": payload})
    assert response.status_code == 200
    draft = response.json()
    assert "Leaking kitchen tap" in draft["contractor_message"]
    assert "Maple Court" in draft["contractor_message"]
    assert "Unit 4" in draft["contractor_message"]
    retry = client.post("/api/drafts", json={"session_id": session, "fields": payload | {"contractor_message": None}})
    assert retry.json() == draft
    edited = patch(client, draft, issue_summary="Bathroom sink leak").json()
    assert edited["contractor_message"] == draft["contractor_message"]
    empty = patch(client, edited, contractor_message="").json()
    assert empty["contractor_message"] == "" and "contractor_message" in empty["missing_fields"]


@pytest.mark.parametrize("name,value", [
    ("issue_summary", "  "), ("contractor_message", ""), ("property_id", None),
    ("unit_id", None), ("category", None), ("contractor_id", None),
])
def test_missing_fields_can_be_saved_but_not_approved(client, name, value):
    draft = saved(client, **{name: value})
    assert name in draft["missing_fields"]
    assert draft["status"] == "needs_info"
    response = approve(client, draft)
    assert_conflict(response, "approval_blocked")
    assert name in response.json()["missing_fields"]
    assert client.get("/api/work-orders").json() == []


@pytest.mark.parametrize("overrides,reason", [
    ({"property_id": "absent"}, "unknown_property"),
    ({"unit_id": "absent"}, "invalid_property_unit"),
    ({"unit_id": "cedar-house-unit-4"}, "invalid_property_unit"),
    ({"contractor_id": "lea"}, "contractor_not_approved"),
    ({"contractor_id": "absent"}, "contractor_not_approved"),
    ({"issue_summary": "Sparks at the socket"}, "safety_concern"),
    ({"access_notes": "Beware exposed wires"}, "safety_concern"),
    ({"contractor_message": "Investigate a gas smell"}, "safety_concern"),
    ({"property_id": "cedar-house", "unit_id": "cedar-house-unit-4", "issue_summary": "Leaking bathroom tap"}, "duplicate_found"),
])
def test_invalid_or_unsafe_drafts_are_saved_for_review_and_blocked(client, overrides, reason):
    draft = saved(client, **overrides)
    assert reason in draft["review_reasons"]
    assert draft["status"] in {"needs_human", "duplicate_found"}
    response = approve(client, draft)
    assert_conflict(response, "approval_blocked")
    assert reason in response.json()["review_reasons"]


@pytest.mark.parametrize("mutation,reason", [
    ("DELETE FROM contractor_approvals WHERE contractor_id='ahmed' AND property_id='maple-court'", "contractor_not_approved"),
    ("UPDATE contractors SET trade='electrical' WHERE id='ahmed'", "contractor_not_approved"),
    ("UPDATE units SET property_id='cedar-house' WHERE id='maple-court-unit-4'", "invalid_property_unit"),
    ("INSERT INTO jobs VALUES ('late-job', 'maple-court', 'maple-court-unit-4', 'Leaking kitchen tap', 'ahmed', 'plumbing', 'open', '2026-10-22')", "duplicate_found"),
])
def test_approval_revalidates_records_changed_after_save(client, db_path, mutation, reason):
    draft = saved(client)
    with sqlite3.connect(db_path) as db:
        db.execute(mutation)
    response = approve(client, draft)
    assert_conflict(response, "approval_blocked")
    assert reason in response.json()["review_reasons"]
    assert client.get("/api/work-orders").json() == []


def test_old_tab_cannot_edit_approve_or_cancel_newer_revision(client):
    old = saved(client)
    newer = patch(client, old, access_notes="Use side door").json()
    for response in [patch(client, old, access_notes="Old tab"), approve(client, old), cancel(client, old)]:
        assert_conflict(response, "stale_revision")
        assert response.json()["draft"] == newer
    assert client.get("/api/work-orders").json() == []


def test_cancellation_is_terminal_and_latest_session_can_start_new_workflow(client, db_path):
    draft = saved(client)
    response = cancel(client, draft)
    assert response.status_code == 200
    cancelled = response.json()
    assert cancelled["status"] == "cancelled"
    assert cancel(client, cancelled).json() == cancelled
    assert_conflict(approve(client, cancelled), "draft_cancelled")
    assert_conflict(patch(client, cancelled, access_notes="Try again"), "draft_cancelled")
    assert client.get(f"/api/sessions/{draft['session_id']}").json()["draft"] == cancelled
    new = saved(client, draft["session_id"])
    assert new["id"] != draft["id"] and new["revision"] == 1
    assert client.get(f"/api/sessions/{draft['session_id']}").json()["draft"] == new
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM draft_history WHERE draft_id=? AND event_type='cancelled'", (draft["id"],)).fetchone()[0] == 1


def test_approval_is_idempotent_but_cannot_edit_cancel_or_approve_old_revision(client):
    draft = saved(client)
    revised = patch(client, draft, access_notes="Edited").json()
    first = approve(client, revised).json()
    assert approve(client, revised).json() == first
    assert approve(client, revised, key="retry-key").json() == first
    assert_conflict(approve(client, draft), "stale_revision")
    assert_conflict(patch(client, revised, access_notes="Changed"), "draft_approved")
    assert_conflict(cancel(client, revised), "draft_approved")
    assert client.get("/api/work-orders").json() == [first]


def test_idempotency_key_cannot_be_reused_for_another_draft_including_retry_keys(client):
    first = saved(client)
    order = approve(client, first, key="one").json()
    assert approve(client, first, key="retry").json() == order
    second = saved(client, issue_summary="Blocked bathroom toilet")
    for key in ["one", "retry"]:
        assert_conflict(approve(client, second, key=key), "idempotency_conflict")
    assert len(client.get("/api/work-orders").json()) == 1


@pytest.mark.parametrize("route", ["edit", "approve", "cancel"])
def test_draft_ownership_and_unknown_ids_are_not_bypassed(client, route):
    draft = saved(client)
    other = draft | {"session_id": new_session(client)}
    unknown = draft | {"id": "unknown"}
    action = {"edit": lambda d: patch(client, d, access_notes="Other"), "approve": lambda d: approve(client, d), "cancel": lambda d: cancel(client, d)}[route]
    for invalid in [other, unknown]:
        response = action(invalid)
        assert response.status_code == 404
        assert response.json()["error_code"] == "unknown_draft"


@pytest.mark.parametrize("forbidden", ["revision", "id", "session_id", "status", "evidence", "missing_fields", "review_reasons"])
def test_client_cannot_supply_server_owned_draft_fields(client, forbidden):
    session = new_session(client)
    response = client.post("/api/drafts", json={"session_id": session, "fields": fields() | {forbidden: "fake"}})
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_request"
    assert client.get(f"/api/sessions/{session}").json()["draft"] is None
    draft = saved(client, session)
    response = patch(client, draft, **{forbidden: "fake"})
    assert response.status_code == 422
    assert client.get(f"/api/sessions/{session}").json()["draft"] == draft


@pytest.mark.parametrize("name,value", [("category", "roofing"), ("issue_summary", None), ("access_notes", None), ("issue_summary", 12), ("preferred_date", "not-a-date"), ("preferred_date", "2026-02-30")])
def test_malformed_fields_fail_without_draft_writes(client, name, value):
    session = new_session(client)
    response = create(client, session, **{name: value})
    assert response.status_code == 422
    assert client.get(f"/api/sessions/{session}").json()["draft"] is None


def test_empty_date_is_optional_and_patch_does_not_regenerate_message(client):
    draft = saved(client, preferred_date="")
    assert draft["preferred_date"] is None
    edited = patch(client, draft, access_notes="").json()
    assert edited["access_notes"] == ""
    assert edited["contractor_message"] == draft["contractor_message"]
    assert edited["status"] == "ready_for_review"


def test_parallel_approvals_for_one_draft_create_one_immutable_order(client, db_path):
    draft = saved(client)
    barrier = Barrier(6)
    def attempt(index):
        barrier.wait()
        return approve(client, draft, key=f"parallel-{index}")
    with ThreadPoolExecutor(max_workers=6) as executor:
        responses = list(executor.map(attempt, range(6)))
    assert [r.status_code for r in responses] == [200] * 6
    assert len({r.json()["id"] for r in responses}) == 1
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM work_orders").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 4


def test_parallel_distinct_drafts_for_same_issue_cannot_create_duplicate_jobs(client, db_path):
    drafts = [saved(client), saved(client)]
    barrier = Barrier(2)
    def attempt(index):
        barrier.wait()
        return approve(client, drafts[index], key=f"race-{index}")
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(attempt, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    blocked = next(r for r in responses if r.status_code == 409)
    assert_conflict(blocked, "approval_blocked")
    assert "duplicate_found" in blocked.json()["review_reasons"]
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 4


def test_failure_during_order_insert_rolls_back_status_order_and_job(client, db_path):
    draft = saved(client)
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TRIGGER fail_new_job BEFORE INSERT ON jobs BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
    response = approve(client, draft)
    assert response.status_code == 503
    assert response.json()["error_code"] == "backend_unavailable"
    assert client.get(f"/api/sessions/{draft['session_id']}").json()["draft"] == draft
    assert client.get("/api/work-orders").json() == []
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 3
        db.execute("DROP TRIGGER fail_new_job")
    assert approve(client, draft).status_code == 200


def test_additive_migration_preserves_existing_records_and_read_checks(client, db_path):
    session = new_session(client)
    check(client, session)
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE properties SET name='Custom Maple' WHERE id='maple-court'")
        db.execute("DELETE FROM jobs WHERE id='demo-job-maple-hallway-light'")
        before_events = db.execute("SELECT events_json FROM sessions WHERE id=?", (session,)).fetchone()[0]
        # Simulate an M2 database with no persisted workflow tables.
        for table in ["approval_keys", "work_orders", "draft_history", "drafts"]:
            db.execute(f'DROP TABLE IF EXISTS "{table}"')
    Store(db_path).initialize()
    state = client.get(f"/api/sessions/{session}").json()
    assert state["events"] == json.loads(before_events)
    assert next(p for p in state["properties"] if p["id"] == "maple-court")["name"] == "Custom Maple"
    assert len(state["recent_jobs"]) == 2
    before = business_snapshot(db_path)
    assert check(client, session, property_query="maple-court").status_code == 200
    assert business_snapshot(db_path) == before
