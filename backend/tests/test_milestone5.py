"""M5 acceptance uses real routes/SQLite and a simulated signed-access provider.

No test here connects to ElevenLabs, changes provider configuration, or opens the
live repairs database. This covers handoff state, not speech recognition or the
agent's decision to call a tool.
"""

import json
import sqlite3

import pytest

from backend.tests.test_drafts import approve, patch, saved
from backend.tests.test_voice import access, clients, lookup, prepare
from backend.tests.test_workflow import new_session


@pytest.mark.parametrize("first_mode,second_mode", [("text", "voice"), ("voice", "text")])
def test_conversation_mode_handoff_preserves_same_draft_through_reviewed_approval(
    tmp_path, first_mode, second_mode,
):
    """Catch a mode switch losing a form edit or approving a different snapshot."""
    path = tmp_path / "milestone5.sqlite3"
    with clients(path) as (api, gateway):
        session = new_session(api)
        original = saved(api, session)

        first_response = access(api, session, original, mode=first_mode)
        assert first_response.status_code == 200, first_response.text
        first = first_response.json()
        first_context = json.loads(first["dynamic_variables"]["hearth_context"])
        assert first_context["mode"] == first_mode
        assert first_context["current_draft"]["id"] == original["id"]
        assert first_context["current_draft"]["revision"] == 1
        assert lookup(gateway, first).status_code == 200
        first_edit = prepare(gateway, first, original, {"access_notes": "Use the side door."})
        assert first_edit.status_code == 200, first_edit.text
        revision_two = first_edit.json()["draft"] | {"session_id": session}
        assert revision_two["id"] == original["id"]
        assert revision_two["revision"] == 2
        assert api.post(f"/api/voice/{first['voice_session_id']}/end", json={"session_id": session}).status_code == 200
        assert lookup(gateway, first).status_code == 401

        form_response = patch(api, revision_two, preferred_date="2026-10-29")
        assert form_response.status_code == 200, form_response.text
        revision_three = form_response.json()
        assert revision_three["revision"] == 3

        second_response = access(api, session, revision_three, mode=second_mode)
        assert second_response.status_code == 200, second_response.text
        second = second_response.json()
        context = json.loads(second["dynamic_variables"]["hearth_context"])
        assert context["mode"] == second_mode
        assert context["current_draft"] == {k: v for k, v in revision_three.items() if k != "session_id"}
        assert lookup(gateway, second).status_code == 200
        second_edit = prepare(gateway, second, revision_three, {"access_notes": "  Knock first.\nAfter 4 pm.  "})
        assert second_edit.status_code == 200, second_edit.text
        reviewed = second_edit.json()["draft"] | {"session_id": session}
        assert reviewed["id"] == original["id"]
        assert reviewed["revision"] == 4
        assert reviewed["preferred_date"] == "2026-10-29"
        assert reviewed["access_notes"] == "  Knock first.\nAfter 4 pm.  "
        assert reviewed["contractor_message"] == original["contractor_message"]
        assert api.get(f"/api/sessions/{session}").json()["draft"] == reviewed
        blocked = approve(api, reviewed)
        assert blocked.status_code == 409
        assert blocked.json()["error_code"] == "voice_active"
        assert api.get("/api/work-orders").json() == []

        assert api.post(f"/api/voice/{second['voice_session_id']}/end", json={"session_id": session}).status_code == 200
        assert lookup(gateway, second).status_code == 401
        response = approve(api, reviewed)
        assert response.status_code == 200, response.text
        order = response.json()
        assert order["snapshot"] == reviewed
        assert order["approved_revision"] == 4
        repeated = approve(api, reviewed, key="repeat-after-mode-handoff")
        assert repeated.status_code == 200
        assert repeated.json() == order
        assert api.get("/api/work-orders").json() == [order]

    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM drafts").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM work_orders").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 4
        assert db.execute("SELECT revision, event_type FROM draft_history ORDER BY id").fetchall() == [
            (1, "created"), (2, "edited"), (3, "edited"), (4, "edited"), (4, "approved"),
        ]
