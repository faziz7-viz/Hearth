# Milestone 3 backend implementation report

Implemented Task 1 in `backend/app/models.py`, `store.py`, `main.py`, new `drafts.py`, `backend/tests/test_drafts.py`, and two obsolete assertions in `test_workflow.py`. No dependencies were added. No server was restarted, browser controlled, or live `backend/data/repairs.sqlite3` opened/written by this work.

## Contract and decisions

- Draft creation, partial edits, approval, cancellation, saved-order listing, and latest-session-draft retrieval are implemented. Errors from draft/order routes use structured `error_code` and `message`; M2 check errors retain their existing shape.
- `RepairDraft.category` retains the supported union; unsupported draft categories receive 422. The M2 check still accepts unsupported categories and returns human review.
- Editable strings are preserved exactly. A valid optional date must use YYYY-MM-DD; empty date normalizes to null. Missing/null contractor message generates a grounded message once on creation. Empty string remains missing information. PATCH never regenerates a message and rejects explicit null for that text field.
- Required fields are property, unit, issue summary, category, contractor, and contractor message. Date and access notes are optional. Review reasons are stable codes: `safety_concern`, `unknown_property`, `invalid_property_unit`, `contractor_not_approved`, and `duplicate_found`. Safety screening includes issue text, access notes, and message.
- PATCH rechecks records. True no-op saves preserve revision. Any changed reviewed snapshot, including changed evidence/status after a record recheck, increments revision. This prevents two different reviewed snapshots sharing a revision. Approval and cancellation change terminal status without changing content revision; history records each transition.
- WorkOrder.snapshot is the exact saved pre-approval RepairDraft, including ready-for-review status, revision, whitespace, and evidence. Approval does not replace its evidence with freshly computed evidence. It separately checks current records under the write lock. Current draft becomes approved. Matching approved `jobs.id` equals `WorkOrder.id`, allowing precise frontend deduplication.
- Every mutation runs within `BEGIN IMMEDIATE`; SQLite enforces one active draft per session and one work order per draft. Approval revalidates current property/unit relationship, contractor trade/property approval, required fields, safety, and duplicate jobs before inserting order, matching job, retry key, history, and status atomically. Competing writers wait up to five seconds, then either see the first commit or return backend unavailable if SQLite remains locked.
- A successful retry of the same draft/revision returns the original order, including with a fresh key. Every successful retry key is bound to that order and cannot approve another draft/revision. Revision checking precedes retries, so an old revision cannot return a newer order.
- Tables/indexes are additive and created before the seed-version check. Existing seed records and sessions are retained without reseeding. History is append-only in application code; saved order snapshots have no update route.

## Test-first evidence

Command: `backend/.venv/bin/python -m pytest backend/tests/test_drafts.py -q`

Initial RED: **46 failed, 1 passed**. The failed cases returned 404 because persisted routes did not yet exist. The passing case checked the existing additive initialization/read-check foundation. After implementation: **47 passed**.

First full suite: **84 passed, 2 failed**. Both failures were obsolete M2 assumptions: `test_checks_do_not_mutate_business_records_or_create_draft_tables` asserted draft tables did not exist, and `test_milestone_three_write_endpoints_are_unavailable` asserted the new routes returned 404. Updated these to assert checks leave business records/draft history/orders unchanged and malformed new-route requests perform no writes.

Final command: `backend/.venv/bin/python -m pytest -q`

Result: **86 passed in 1.03s**. All tests use temporary databases. Coverage includes exact edited approval snapshot; stable ID/revision; create retries/conflicts; one-time generated messages; missing and malformed fields; field ownership validation; safety; eligibility and relationship changes after saving; newly inserted duplicate; stale edit/approve/cancel; terminal cancellation; retry keys; six parallel approvals of one draft; simultaneous distinct-draft duplicate race; transaction rollback after an injected job-insert failure; saved revision history; reload/recreated-app persistence; additive M2 migration; existing seed preservation and read-only M2 checks.

## Remaining integration

Root owns server/browser integration, independent review, actual process restart persistence, and final beginner instructions. Unit/API coverage recreates the FastAPI application and reopens the SQLite file; no claim of an actual live-server restart is made here. No Milestone 4 integration, booking, or messaging was added.
