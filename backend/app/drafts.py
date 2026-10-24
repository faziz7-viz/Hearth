"""Persisted draft workflow. Every mutation validates under one SQLite write lock."""

from datetime import datetime, timezone
import sqlite3
from time import time
from uuid import uuid4

from .models import (
    DraftApproveRequest, DraftCreateRequest, DraftEditRequest, DraftFields,
    DraftRevisionRequest, RepairDraft, RepairEvidence, WorkOrder,
)
from .store import Store, session_events
from .tools import RecordTools
from .workflow import SAFETY_PATTERN

TERMINAL_STATUSES = {"approved", "cancelled"}
REQUIRED_FIELDS = (
    "property_id", "unit_id", "issue_summary", "category", "contractor_id", "contractor_message",
)


class DraftConflict(Exception):
    def __init__(self, code: str, message: str, draft: RepairDraft | None = None, *,
                 status_code: int = 409, missing_fields: list[str] | None = None,
                 review_reasons: list[str] | None = None):
        self.status_code = status_code
        self.content = {"error_code": code, "message": message}
        if draft is not None:
            self.content["draft"] = draft.model_dump(mode="json")
        if missing_fields is not None:
            self.content["missing_fields"] = missing_fields
        if review_reasons is not None:
            self.content["review_reasons"] = review_reasons
        super().__init__(message)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_draft(db: sqlite3.Connection, session_id: str) -> RepairDraft | None:
    row = db.execute(
        "SELECT snapshot_json FROM drafts WHERE session_id=? ORDER BY rowid DESC LIMIT 1", (session_id,),
    ).fetchone()
    return RepairDraft.model_validate_json(row["snapshot_json"]) if row else None


def load_draft(db: sqlite3.Connection, draft_id: str, session_id: str) -> RepairDraft:
    row = db.execute("SELECT snapshot_json FROM drafts WHERE id=? AND session_id=?", (draft_id, session_id)).fetchone()
    if row is None:
        raise DraftConflict("unknown_draft", "Draft not found for this session.", status_code=404)
    return RepairDraft.model_validate_json(row["snapshot_json"])


def require_revision(draft: RepairDraft, expected_revision: int) -> None:
    if draft.revision != expected_revision:
        raise DraftConflict("stale_revision", "The saved draft changed. Load and review the latest revision.", draft)


def require_editable(draft: RepairDraft) -> None:
    if draft.status in TERMINAL_STATUSES:
        raise DraftConflict(f"draft_{draft.status}", f"This draft is already {draft.status}.", draft)


def editable_fields(draft: RepairDraft) -> dict:
    return draft.model_dump(include=set(DraftFields.model_fields))


def generated_message(db: sqlite3.Connection, fields: dict) -> str:
    if not fields["issue_summary"].strip():
        return ""
    row = db.execute(
        """SELECT p.name, u.label FROM properties p JOIN units u ON u.property_id=p.id
           WHERE p.id=? AND u.id=?""", (fields["property_id"], fields["unit_id"]),
    ).fetchone()
    location = f" for {row['name']}, {row['label']}" if row else ""
    return f"Please review this repair request{location}: {fields['issue_summary']}"


def assess(db: sqlite3.Connection, fields: dict) -> dict:
    """Compute review data from current records without altering editable content."""
    missing = [name for name in REQUIRED_FIELDS if not fields.get(name) or not fields[name].strip()]
    reasons: list[str] = []
    evidence: list[RepairEvidence] = []
    if any(SAFETY_PATTERN.search(fields[name]) for name in ("issue_summary", "access_notes", "contractor_message")):
        reasons.append("safety_concern")
    prop = db.execute("SELECT name FROM properties WHERE id=?", (fields["property_id"],)).fetchone()
    if fields["property_id"] and prop is None:
        reasons.append("unknown_property")
    unit = db.execute("SELECT property_id, label FROM units WHERE id=?", (fields["unit_id"],)).fetchone()
    valid_unit = prop is not None and unit is not None and unit["property_id"] == fields["property_id"]
    if fields["unit_id"] and (unit is None or (fields["property_id"] and not valid_unit)):
        reasons.append("invalid_property_unit")
    if valid_unit:
        evidence.append(RepairEvidence(
            source_type="property", record_id=fields["unit_id"],
            summary=f"{prop['name']} contains {unit['label']}.",
        ))
        tools = RecordTools(db)
        context = tools.lookup_maintenance_context(fields["unit_id"], fields["category"])
        evidence.extend(context.evidence)
        if fields["contractor_id"] and fields["category"] and fields["contractor_id"] not in {
            contractor.id for contractor in context.approved_contractors
        }:
            reasons.append("contractor_not_approved")
        if fields["category"] and fields["issue_summary"].strip():
            duplicates = tools.check_open_jobs(fields["unit_id"], fields["category"], fields["issue_summary"])
            if duplicates:
                reasons.append("duplicate_found")
                evidence.extend(RepairEvidence(
                    source_type="open_job", record_id=job.id,
                    summary=f"{job.status.capitalize()} job: {job.issue_summary}.",
                ) for job in duplicates)
    if "safety_concern" in reasons:
        status = "needs_human"
    elif missing:
        status = "needs_info"
    elif "duplicate_found" in reasons:
        status = "duplicate_found"
    elif reasons:
        status = "needs_human"
    else:
        status = "ready_for_review"
    return {"missing_fields": missing, "review_reasons": reasons, "evidence": evidence, "status": status}


def persist(db: sqlite3.Connection, draft: RepairDraft, event_type: str) -> None:
    serialized = draft.model_dump_json()
    db.execute("UPDATE drafts SET revision=?, status=?, snapshot_json=? WHERE id=?", (
        draft.revision, draft.status, serialized, draft.id,
    ))
    db.execute("""INSERT INTO draft_history (draft_id, revision, event_type, snapshot_json, created_at)
                  VALUES (?, ?, ?, ?, ?)""", (draft.id, draft.revision, event_type, serialized, now()))


def order_from_row(row: sqlite3.Row) -> WorkOrder:
    return WorkOrder(
        id=row["id"], draft_id=row["draft_id"], approved_revision=row["approved_revision"],
        snapshot=RepairDraft.model_validate_json(row["snapshot_json"]), created_at=row["created_at"],
    )


class DraftWorkflow:
    def __init__(self, store: Store):
        self.store = store

    def create(self, request: DraftCreateRequest) -> RepairDraft:
        with self.store.write_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            return self.create_in_transaction(db, request)

    def create_in_transaction(self, db: sqlite3.Connection, request: DraftCreateRequest) -> RepairDraft:
        session_events(db, request.session_id)
        fields = request.fields.model_dump()
        current = latest_draft(db, request.session_id)
        if current is not None and current.status not in TERMINAL_STATUSES:
            if fields["contractor_message"] is None:
                fields["contractor_message"] = current.contractor_message
            if fields == editable_fields(current):
                return current
            raise DraftConflict("active_draft_exists", "Finish or cancel the active draft before starting another request.", current)
        if fields["contractor_message"] is None:
            fields["contractor_message"] = generated_message(db, fields)
        draft = RepairDraft(
            id=str(uuid4()), session_id=request.session_id, revision=1,
            **fields, **assess(db, fields),
        )
        db.execute("INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?)", (
            draft.id, draft.session_id, draft.revision, draft.status, draft.model_dump_json(), now(),
        ))
        persist(db, draft, "created")
        return draft

    def edit(self, draft_id: str, request: DraftEditRequest) -> RepairDraft:
        with self.store.write_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            return self.edit_in_transaction(db, draft_id, request)

    def edit_in_transaction(self, db: sqlite3.Connection, draft_id: str, request: DraftEditRequest) -> RepairDraft:
        draft = load_draft(db, draft_id, request.session_id)
        require_revision(draft, request.expected_revision)
        require_editable(draft)
        fields = editable_fields(draft) | request.fields.model_dump(exclude_unset=True)
        updated = RepairDraft(
            id=draft.id, session_id=draft.session_id, revision=draft.revision,
            **fields, **assess(db, fields),
        )
        if updated == draft:
            return draft
        # Derived evidence/status is part of the reviewed snapshot, so a changed
        # recheck also earns a revision even when editable text is unchanged.
        updated.revision += 1
        persist(db, updated, "edited")
        return updated

    def cancel(self, draft_id: str, request: DraftRevisionRequest) -> RepairDraft:
        with self.store.write_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            draft = load_draft(db, draft_id, request.session_id)
            require_revision(draft, request.expected_revision)
            if draft.status == "cancelled":
                return draft
            require_editable(draft)
            cancelled = draft.model_copy(update={"status": "cancelled"})
            persist(db, cancelled, "cancelled")
            return cancelled

    def approve(self, draft_id: str, request: DraftApproveRequest) -> WorkOrder:
        with self.store.write_connection() as db:
            # Serialize validation, order insertion, duplicate-job insertion and status
            # change. A second writer sees either the whole first approval or none.
            db.execute("BEGIN IMMEDIATE")
            draft = load_draft(db, draft_id, request.session_id)
            require_revision(draft, request.expected_revision)
            previous_key = db.execute("SELECT draft_id, revision FROM approval_keys WHERE idempotency_key=?", (
                request.idempotency_key,
            )).fetchone()
            if previous_key is not None and (previous_key["draft_id"], previous_key["revision"]) != (draft.id, draft.revision):
                raise DraftConflict("idempotency_conflict", "This approval key belongs to a different draft or revision.", draft)
            if draft.status == "cancelled":
                require_editable(draft)
            row = db.execute("SELECT * FROM work_orders WHERE draft_id=?", (draft.id,)).fetchone()
            if row is not None:
                order = order_from_row(row)
                db.execute("INSERT OR IGNORE INTO approval_keys VALUES (?, ?, ?, ?)", (
                    request.idempotency_key, draft.id, draft.revision, order.id,
                ))
                return order
            require_editable(draft)
            if db.execute(
                "SELECT 1 FROM voice_sessions WHERE session_id=? AND revoked=0 AND expires_at>? LIMIT 1",
                (draft.session_id, time()),
            ).fetchone():
                raise DraftConflict("voice_active", "End the conversation, then review the saved draft before approval.", draft)
            checked = assess(db, editable_fields(draft))
            if checked["status"] != "ready_for_review" or draft.status != "ready_for_review":
                raise DraftConflict(
                    "approval_blocked", "Current records require changes or human review before approval. Save and review the draft again.",
                    draft, missing_fields=checked["missing_fields"], review_reasons=checked["review_reasons"],
                )
            order = WorkOrder(
                id=str(uuid4()), draft_id=draft.id, approved_revision=draft.revision,
                snapshot=draft, created_at=now(),
            )
            db.execute("INSERT INTO work_orders VALUES (?, ?, ?, ?, ?)", (
                order.id, draft.id, draft.revision, draft.model_dump_json(), order.created_at,
            ))
            # The shared ID explicitly links the catalog job and the saved order.
            db.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                order.id, draft.property_id, draft.unit_id, draft.issue_summary,
                draft.contractor_id, draft.category, "approved", order.created_at,
            ))
            db.execute("INSERT INTO approval_keys VALUES (?, ?, ?, ?)", (
                request.idempotency_key, draft.id, draft.revision, order.id,
            ))
            persist(db, draft.model_copy(update={"status": "approved"}), "approved")
            return order

    def orders(self) -> list[WorkOrder]:
        return self.store.read(lambda db: [order_from_row(row) for row in db.execute(
            "SELECT * FROM work_orders ORDER BY created_at DESC, id",
        )])
