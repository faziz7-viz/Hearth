# Milestone 2 verification — October 22, 2026

Verified against the running screen at http://127.0.0.1:5173/ and its Python backend on port 8000. No Milestone 3 work was performed.

## Port diagnosis

`lsof` identified Node PID **86114** listening on `127.0.0.1:5173`. Its command was `node /Users/faizaaziz073/MAI/Week3/frontend/node_modules/.bin/vite --host 127.0.0.1`, and its working directory was this project's `frontend/`. The page returned HTTP 200 and displayed the current Hearth app. Reused this server without restarting it.

Backend PID **88344** belonged to this project. It was stopped only for the deliberate outage test and restarted as PID **89695** on port 8000. No unrelated processes were stopped. Both project servers were left running.

## Actual results

| Check | Status | Observed result |
| --- | --- | --- |
| Maple Court, unit 4, leaking kitchen tap | PASS | Load example displayed Maple Court, Unit 4, and approved plumber Ahmed. No matching open repair was returned. |
| Cedar House, unit 4, bathroom tap | PASS | Load example displayed Possible duplicate repair and the existing open Leaking bathroom tap job for Cedar House, Unit 4. |
| Missing or ambiguous property | PASS | Blank property with unit 4 displayed Which property did you mean? with Cedar House and Maple Court choices. No property was selected automatically. Choosing Maple Court explicitly continued the check. Oak Lodge separately displayed Property not found with no fallback. |
| Backend unavailable | PASS | Stopped the confirmed project backend, then clicked Load example from a successful Maple result. The screen switched to Check failed / Backend unavailable, with Try again. Previous contractor selection was labelled recheck required; successful check results disappeared. Restarting the backend and clicking Try again restored the successful result. |
| Load example uses the backend | PASS | Chrome Network showed GET /api/sessions/{id} and POST /api/repair-check, both HTTP 200. The actual repair-check response contained status matched, property ID maple-court, unit ID maple-court-unit-4, an empty open_jobs list, and contractor ID ahmed with plumbing trade. These matched the rendered screen. The same button failed during the real backend outage. Source audit confirmed frontend fixtures contain request inputs only. |
| No work orders; voice disconnected | PASS | Compared all SQLite business rows before and after the browser checks and backend restart: identical. Jobs remained 3 → 3; no draft or work-order table exists. Approve (later) stayed disabled. The microphone was disabled and labelled Voice not connected. |
| Backend tests | PASS | `backend/.venv/bin/python -m pytest backend/tests/test_workflow.py -q` exited 0: 39 passed in 0.51s. Tests used isolated temporary databases. |
| Frontend build | PASS | `npm run build` exited 0, including `tsc --noEmit` and Vite's production build; 1572 modules transformed. |

Business snapshot SHA-256 before and after: `40963f3dc694c3c9297c65e917f834ab20e4c64cace741814113c0ecf6ee2272`. Sessions and their check events are the permitted writes and were excluded from the business snapshot.

No Milestone 2 blockers were found. No application code changes were needed. README startup guidance now explains how to reuse the already-running frontend.
