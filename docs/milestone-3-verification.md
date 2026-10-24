# Milestone 3 — actual verification results

Verified October 22, 2026 against the existing Hearth frontend on `http://127.0.0.1:5173/` and the project FastAPI backend on port 8000. No Milestone 4 implementation, voice connection, or message sending.

| Check | Status | Actual result |
| --- | --- | --- |
| Editable saved draft | PASS | Loaded Maple Court, Unit 4, with Ahmed using real checks; saved revision 1. Edited requested date to 2026-11-03, access notes, and a two-line contractor message. Approval disabled while edits were unsaved. Saving produced revision 2 with the same draft ID. |
| Outdated approval | PASS | A separate real PATCH simulated another tab saving revision 3 while the screen displayed revision 2. Clicking Approve produced a stale-revision conflict, disabled further approval, and required Load latest saved draft. No work order was created. Loading latest showed the newer note. |
| Exact reviewed approval | PASS | Edited the note again, saved and reviewed revision 4, then approved through the screen. Compared the entire returned work-order snapshot against the pre-approval JSON: exactly equal, including requested date, notes, message, evidence, and revision. |
| Repeated approval | PASS | Three real HTTP retries (two with the original key, one with another retry key) returned the same work order and identical response. Count remained one work order and four total jobs (three seed jobs plus the approved job). An outdated revision-2 retry still returned HTTP 409 stale_revision. |
| Validation and duplicates | PASS | A fresh Maple Court kitchen-tap check found the newly approved job. Saving another draft reported duplicate_found; approval was disabled. Direct HTTP approval also returned 409 approval_blocked with duplicate_found. Backend tests additionally cover missing details, unknown/wrong contractor, revoked approval, changed trade or property/unit relationship, safety, and duplicates introduced after saving. |
| Page reload | PASS | Reload restored the approved card and one saved work order. Expanding saved details showed the exact revision-4 date, notes, and custom message. |
| Backend restart | PASS | Saved a second, unfinished duplicate-blocked draft. Stopped and restarted only the project backend. Compared every draft, history, work-order, and job row before/after: unchanged. Live session/order endpoints and a browser reload restored both the unfinished draft and the approved order. |
| Cancellation | PASS | Cancel draft persisted the cancelled state and locked the card. A subsequent real approval request returned 409 draft_cancelled. Another browser reload retained cancellation. No additional order was created. |
| Backend outage | PASS | Attempted Save changes while the backend was stopped. The screen showed Backend unavailable and preserved the current draft. It resumed after restart/reload. |
| Existing records and seed | PASS | Additive migration preserved all business records and all pre-existing sessions. Seed marker remains one. Browser hot reload created additional permitted sessions; no fixtures were replaced. |
| Design and scope | PASS | Existing Hearth layout retained. At 390 × 844, message fields, requested-date label, controls, saved order cards, and expanded details fit. Voice remains disabled and labelled Voice not connected. Date explicitly says it is not a confirmed booking; messages remain drafts. |
| Backend test suite | PASS | `backend/.venv/bin/python -m pytest -q`: **86 passed in 1.26s**, exit 0. Includes the 39 record-check tests and 47 draft/approval cases, using temporary databases. |
| Frontend state tests | PASS | `npm test`: **7 passed, 0 failed**, exit 0. Covers dirty/stale/blocked approval guards, retry keys, exact payloads, conflict recovery, and location-edit preservation. |
| Frontend build | PASS | `npm run build`: TypeScript check and Vite production build passed, exit 0; 1573 modules transformed. |

## Saved verification records

- Approved draft: `e97f3fed-4b1f-41f0-be88-e154bc24d912`, approved content revision **4**.
- Work order: `adcfd51a-d9d8-46b5-8133-791364c92476`.
- Cancelled test draft: `f3c5685b-38f4-40ca-a65b-94e3e8716860`.
- Final live counts: **2 drafts, 7 history events, 1 work order, 4 jobs, 1 seed version**. Approval/cancellation are lifecycle history events; they retain the content revision they acted on.
- Exact approved access notes: “Tenant is home after 3 pm. Please knock.”
- Exact approved message:

```text
Hi Ahmed, please inspect the leaking kitchen tap at Maple Court, unit 4.
Please confirm whether the requested date works.
```

The work order was intentionally left saved. A new request for the same kitchen tap should now report a possible duplicate.

## Review and fixes

Independent review found and verified fixes for two frontend cases: a failed replacement check could otherwise leave an old local card saveable, and changing a saved draft's location could otherwise clear its date, notes, and custom message. Failed checks now block saving an unrelated old card. Saved location edits preserve exact user text and require save/review. No unresolved actionable review findings remained.

The backend review also independently exercised evidence-only revision changes and ten approve/cancel races against temporary SQLite databases. Exactly one terminal action won each race, with a consistent work-order count.

Frontend PID 86114 was reused throughout. Final project backend PID 93507 was left running on port 8000. Startup and learner instructions are in `README.md`. Milestone 4 remains untouched.
