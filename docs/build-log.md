# Build log

## October 22, 2026 — Milestone 1

Prompt: Read the supplied plan and implement Milestone 1 only in React, TypeScript, Vite, and Tailwind CSS. Build one landlord workspace with a request box, Load example, disconnected voice control, editable repair card, demo approval/cancellation, and recent jobs. Use fictional plan records, verify the app, and provide a local preview.

Scope: One local screen; React state only. No backend, model, microphone permission, ElevenLabs integration, messages, bookings, or persistent work orders.

Design: Hearth workspace, warm ivory background, forest-green accent, request panel on the left, repair card on the right, recent jobs below, stacked on mobile.

Implementation sequence:
1. Define the plan's TypeScript contract and fictional records.
2. Build the responsive interface and local demo transitions.
3. Run type checking and production build; inspect and exercise desktop and mobile layouts.
4. Record results and give one learner check, then stop.

Decisions:
- The supplied plan already contains the approved design and explicit implementation request, so use it directly.
- This directory had no existing application or Git repository. Create `frontend/` here; keep the original plan and copy it to the requested documentation path.
- Check installed Node and official Vite/Tailwind setup documentation before dependency installation; retain the npm lockfile.
- Use browser interaction checks for this reversible interface milestone, as requested; do not add tests that repeat static markup.
- Custom text creates a manually completed demo card. It does not imply agent parsing or live record checks.

Implementation: complete for Milestone 1. Later milestones remain untouched.

Iterations:
- First type check identified a missing Vite CSS type declaration. Added `src/vite-env.d.ts`; the subsequent check and production build passed.
- Review identified low-contrast supporting text and an approval path that regenerated an unseen message. Darkened helper text, and changed approval to preserve the existing draft snapshot exactly (apart from its approved status).

Verification performed:
- Runtime: Node 25.9.0, npm 11.12.1. Installed React 19.3.1, Vite 8.3.5, TypeScript 7.0.2, and Tailwind CSS 4.3.3. `package-lock.json` retained.
- `npm install`: passed, audit reported zero vulnerabilities.
- `npm run build` (includes `tsc --noEmit`): passed after the configuration fix and again after review changes.
- Local preview HTTP check: 200 at `http://127.0.0.1:5173/`.
- Chrome desktop: empty card, sample loading, request text, sample contractor, and all six editable fields displayed correctly.
- Clearing Problem produced Needs information and disabled Approve; restoring the text re-enabled it.
- Access notes were edited and retained. Preferred date was entered using the keyboard as October 24, 2026; its value remained `2026-10-24` after approval.
- Approval added one job per draft and locked the card with its exact visible date and access notes. Repeat approval protection was checked in code (status guard and draft-ID deduplication).
- Custom request text was copied to Problem, leaving property, unit, and contractor unresolved. Cancellation locked this card and left the job count unchanged.
- Chrome responsive preview at 390 × 844: request panel and repair card stacked; fields, date input, notes, and demo controls fit without clipping. Recent jobs switch to a compact stacked layout.
- Browser console showed no application errors during inspection.
- Voice remained disabled throughout. No microphone permission, messages, bookings, or backend calls occurred.
- A fresh read-only code review was completed; both reported findings were addressed.

Learner check: click Load example, type “Tenant is home after 3 pm.” in Access notes, then click Approve (demo). Check the note remains visible and one new demo job appears.

Handoff: local Vite preview left running. Refreshing clears local edits and approvals. Stop after this first screen.


## October 22, 2026 — Milestone 2

Prompt: Read the revised plan and implement Milestone 2 only. Keep the React design, add Python/FastAPI and SQLite, seed fictional records once, connect Load example to actual record checks, and show unknown, ambiguous, duplicate, and backend-error results. Keep repair checks read-only and voice disconnected. LangChain is no longer required.

Scope: Existing React interface plus validated backend routes and persistent fictional records. No draft saving, work-order approval, contractor actions, model API, or ElevenLabs integration. Seed initialization and session records are allowed by the revised plan.

Implementation:
- Added validated Python models, FastAPI session/check routes, a SQLite store, and three read tools for property/unit lookup, duplicate checks, and maintenance context with approved contractors.
- Seeded the plan's three properties, units, contractors, three jobs, maintenance history, and policies. The fixture transaction and version marker ensure initialization happens once without overwriting records on restart.
- Used property and unit IDs explicitly. Ambiguous matches require a user choice; unknown names and units never fall back to a property. Duplicate detection considers issue details as well as unit and trade.
- Added one bounded retry for temporary SQLite read failures. Queries use read-only connections; no draft, order, or contractor mutation route exists.
- Replaced frontend business fixtures with example request inputs and a typed backend client. Recent jobs, matches, evidence, and contractors now come from SQLite.
- Kept the existing layout, colors, editable local card, and disconnected microphone. Added an example selector, structured request fields, visible check results, and retry controls. Approve (later) remains disabled; Cancel (local) affects only local state.
- Saved startup and screen-testing instructions in README.md. Marked only Milestones 1 and 2 complete in the documentation copy of the revised plan.

Iterations and review:
- Backend behavior tests were written before the implementation; the initial run had 31 failures and one passing test.
- Independent backend review found that urgent requests could reach lookup before human review. Added three regression cases, observed failures, and moved the safety check before business lookups.
- Frontend review found that an ambiguous result discarded local notes. Reproduced it in Chrome, preserved the previous local card while unresolved, and confirmed notes reappear after explicitly selecting the same property/unit.
- Changing a card's property or unit now clears location-specific notes and preferred date. Editing lookup fields invalidates old check results so stale contractors are not presented as newly checked.

Verification:
- `backend/.venv/bin/python -m pytest backend/tests/test_workflow.py -q`: 39 passed. The full backend test suite also passed, and installed Python dependencies passed `pip check`.
- `npm run build` in frontend: passed, including TypeScript checking and the Vite production build.
- Tests cover seed-once preservation and rollback, session routes, unknown and ambiguous matches, explicit selection, duplicate and unrelated issues, unsupported trades, urgent-review routing, validation, bounded retries, read-only business records, and absence of later-milestone mutation endpoints.
- Chrome desktop: Maple Court returned Unit 4, Ahmed, no duplicate, and maintenance evidence. Cedar House returned the existing bathroom-tap repair. Unit 4 alone required a property choice. Oak Lodge showed Property not found. Willow Place showed no approved plumber and no invented replacement.
- Stopped the actual backend, triggered a check, and observed Backend unavailable while the local note remained. Restarted the server and used Try again successfully; the note was still present. The browser's expected failed network request was from this deliberate outage test.
- After a real backend restart, SQLite still held exactly three properties, three units, three contractors, three jobs, one maintenance-history entry, and one seed-version marker.
- Chrome at 390 × 844: request fields, results, local card, controls, and recent jobs stacked cleanly without horizontal clipping.
- Voice remained disconnected, approval remained disabled, and checks did not create repair records or send messages.

Handoff: frontend at http://127.0.0.1:5173/ and backend at http://127.0.0.1:8000/ left running. Choose an example, then click Load example to inspect the real database result. Stop at Milestone 2; later milestones remain untouched.

## October 22, 2026 — Port conflict and Milestone 2 re-verification

The reported port conflict came from this project's existing Vite process, PID 86114. Confirmed its command, working directory, HTTP response, and live screen; reused it without restarting. Re-ran all requested screen checks, inspected the real HTTP response in Chrome Network, deliberately stopped and restarted only the project backend, and compared SQLite business rows before/after. All six requested checks passed; jobs stayed at three and voice stayed disconnected. Backend tests: 39 passed in 0.51s. Frontend production build and TypeScript check passed. No code blockers were found; README now explains reusing an existing server. Full evidence is in `docs/milestone-2-verification.md`. Stopped before Milestone 3.

## October 22, 2026 — Milestone 3

Prompt: Implement saved editable repair drafts and approval only. Preserve Hearth's design and working checks. Keep one draft ID across revisions; approve the exact reviewed revision; validate required details, eligibility, safety, and duplicates; reject stale or cancelled drafts; make approval retries return one order; persist through reload/restart. Keep voice disconnected, messages unsent, and dates requested rather than booked.

Implementation: additive SQLite draft/history/order/key tables; validated create/edit/cancel/approve routes and work-order listing. Approval uses one transaction for revalidation, immutable snapshot, unique order, corresponding job, and status history. React separates local edits from the saved revision, uses explicit Save draft/Save changes, disables approval while dirty or blocked, restores the session on reload, and displays saved order details. No new integration dependencies or Milestone 4 features.

Test-first sequence: new backend tests initially failed on missing draft routes; implementation passed 86 total tests. Obsolete M2 assertions about absent tables/routes were replaced while retaining read-only-check behavior assertions. Frontend state guards and exact-content/conflict logic were exercised with seven Node tests. Independent review identified failed-check/local-card mismatch and saved-location text loss; both were fixed and verified before completion.

Live verification: saved draft revision 1, edited notes/date/message to revision 2, simulated another tab creating revision 3, and observed the screen reject outdated approval. Explicitly loaded latest, edited/saved revision 4, then approved it. The whole saved snapshot exactly matched the reviewed draft. Three approval retries returned the same order. Reload showed the saved details. A second duplicate-blocked draft and the approved order survived a real project-backend restart unchanged. Cancelled the second draft, confirmed HTTP 409 on attempted approval, and reloaded to verify the cancelled state. Backend outage produced a clear error while preserving the card. Mobile inspection at 390 × 844 passed.

Final checks: bare backend pytest **86 passed in 1.26s**; frontend state tests **7 passed**; TypeScript and Vite production build passed. Final database contains two test drafts (one approved, one cancelled), seven history events, one saved work order, and four total jobs. No records were reset and no contractor message was sent. Detailed evidence: `docs/milestone-3-verification.md`.

Learner check: open the preview and expand Saved work orders to inspect the approved date, notes, and message after reloading. For a new draft, use New request; change the issue to a different repair such as Blocked bathroom sink before saving, because the tested kitchen tap now correctly flags its saved job as a possible duplicate.

Handoff: reuse Vite at http://127.0.0.1:5173/; backend remains running on port 8000. README updated. Stop before Milestone 4.


## October 22, 2026 — Milestone 4 code and local verification

Implemented the current ElevenLabs React SDK (1.19.1) with ConversationProvider, explicit voice/text Start and End, status, transcript, bounded duration, safe polling, and preserved form/draft state. Added local temporary access and a separate four-tool gateway, provider-issued conversation ID binding, hashed expiring capabilities in SQLite, atomic same-draft corrections, and backend End-before-Approve protection. Approval, contractor dispatch, and booking confirmation are absent from the agent tools. Existing Hearth styling and M2/M3 workflow remain.

Prepared a grounded agent prompt, exact four webhook payloads/private-agent settings, hidden local configuration entry, and explicit safe-retry provisioning. All five rendered payloads validated against the current official ElevenLabs OpenAPI schema. Local secrets are excluded from source; only the authenticated port-8001 gateway is exposed through the temporary HTTPS tunnel.

Local verification: 128 backend/setup tests plus 4 subtests passed; 27 frontend tests passed; TypeScript/Vite build passed with a nonblocking SDK bundle-size warning; pip check passed. The public gateway returned401 without credentials for all four tools and404 for approval/work-order/docs routes. The browser form returned Willow Place Unit2, Ben, and no duplicate for a loose bedroom door handle; no draft/order was saved. All pre-existing business rows and both saved work orders survived backend/gateway restart unchanged.

Review fixed stale restoration cleanup that could erase a newer binding marker, previous terminal drafts reappearing during a new call, preservation of unsaved raw form input, and inaccurate transcript privacy wording. Python HTTPS uses the OS trust store with validation enabled. An initially generated unused webhook secret exposed in a failing test repr was rotated locally before use; settings repr and isolated test configuration were corrected. No ElevenLabs API key was present during that incident.

Account setup is being guided one action at a time. The user confirmed Agents access and credits and created a dedicated Hearth Demo agent. Live account provisioning, actual speech, and spoken correction remain NOT TESTED until performed. Full current results are recorded in docs/milestone-4-verification.md. Milestone5 has not started.

## October 23, 2026 — Milestone 4 live connection repair

The user connected voice but reported failed record tools. Actual ElevenLabs conversation results showed lookup_property failing before Hearth with DNS resolution failure for the old quick-tunnel hostname. The local backend and gateway were healthy. Restarted only Hearth's tunnel, saved its new origin locally, and updated the four existing tools without replacing credentials or records.

A real browser text conversation then successfully called lookup_property, check_open_jobs, and lookup_maintenance_context. Its visible response matched Willow Place Unit 2, returned Ben, and found no duplicate bedroom-door-handle repair. The read-only test explicitly requested no draft; End revoked its binding. Business counts remain three drafts, nine draft-history rows, two work orders, and five jobs.

Added public gateway preflight before signed-access issuance to catch DNS/TLS/HTTP failures before starting a call. It sends no credentials, verifies system-trust HTTPS, blocks redirects, limits response size/time, and requires Hearth's controlled unauthorized response. Test-first regression coverage includes DNS, TLS, timeout, redirect, unexpected status/body, and malformed/truncated HTTP. The running UI also displayed the clear connection error during a deliberate gateway outage; no binding was created and the form stayed available. Restored only the project services and rechecked the live public preflight.

Fresh final tests: 140 backend/setup tests plus 11 subtests passed in 1.95s; 27 frontend tests passed; TypeScript and Vite build passed with the existing bundle-size warning. Speech-to-draft retry and same-draft spoken correction remain pending; they are not claimed from text or mocked tests. Milestone 5 remains untouched.

## October 23, 2026 — Milestone 4 lookup/retry/end investigation

Inspected the exact failed conversation: two lookup_property attempts sent query Maple Court and unit_label 4 using the documented POST route. Both provider results were HTTP500 external_server with DNS no-such-host for the old tunnel. Correlated with old cloudflared logs reporting Unauthorized: Tunnel not found; backend access issuance succeeded. The provider redacts both secret headers, so historical literal credential equality cannot be rechecked, but the recorded conversation ID matched its unexpired binding. Current actual tool calls pass unchanged authorization. Detailed redacted arguments/results/errors are in docs/milestone-4-verification.md.

Separate causes: native end_call was disabled, and technical retry instructions/copy did not enforce a single requested retry. Enabled only native end_call alongside the existing four repair webhooks; added immediate termination on end requests and termination/form fallback after the permitted retry fails. Business ambiguity, missing details and stale revisions remain recoverable. Removed the frontend tool-error invitation to repeatedly retry.

Live Hearth text checks passed: Maple Court Unit4 returned and its existing tap job was flagged; sending End the conversation invoked native end_call and revoked the binding. A deliberate gateway outage produced exactly two failed lookup calls, followed by native termination with no third offer or attempt. Restored the project gateway and verified the public preflight. No new draft or work order resulted. The new curtain-rail candidate at Willow Place Unit2 has no duplicate. User microphone correction and spoken end tests are pending, not inferred from the text checks.

Verification: 140 backend/setup tests and11subtests passed;28frontend tests passed;TypeScript/Vitebuild passed with the existing bundle-size warning. Current official OpenAPI accepted the rendered agent PATCH, and the real configured private agent has four repair tools plus native end_call. No authentication/session protections were removed and no Milestone5 work was added.


## October 23, 2026 — Milestone 4 speech acceptance completed

The user created a curtain-rail repair at Willow Place Unit 2 through real speech and four successful tools, with no duplicate job. After a local form edit, a resumed audio conversation updated only the access notes to availability after 4 PM using the same draft ID and expected_revision 2; SQLite saved revision 3. The user confirmed the visible change. The draft remains unapproved and work orders remain three.

The user confirmed automatic spoken Goodbye disconnection. Provider history also exposed two earlier end_call attempts abandoned by user audio during a long farewell. Restricted only native end_call with the officially supported disable_during_tool_and_turn interruption setting, pre_tool_speech off, and a one-sentence farewell. Kept business tools interruptible and all authentication/session/revision checks enabled. New config regression verified red then green; real private agent updated and read back. A fresh Hearth text conversation said Goodbye, invoked successful end_call, revoked its binding, and returned to Ready when you are. The new microphone-interruption edge case remains NOT TESTED live.

Restarted only the project main API; revision 3, all three draft-history entries and all three orders were unchanged. Reloaded the user's Safari Hearth screen and verified the same notes, saved revision 3, and editable review-card controls. Latest checks: 141 backend/setup tests plus 11 subtests passed; 28 frontend tests and TypeScript/Vite build passed. Full evidence and remaining NOT TESTED items are in docs/milestone-4-verification.md. Stopped before Milestone 5.


## October 23, 2026 — Milestone 5 verification started

Read the current plan and M4 verification; backed up the existing SQLite database and preserved all prior rows. Reused the existing frontend/API/gateway. Opened a separate private Safari test session. Real microphone denial returned clear fallback and an available form. Fresh live form/API checks passed ambiguity, unknown property, Cedar duplicate, no eligible contractor, urgent human review, and a genuinely new Maple wardrobe-shelf candidate. Saved a separate coat-hook draft for failure checks; a controlled second-tab API edit made the UI reject an outdated approval. No new work order was created.

Desktop plus 390px and 320px mobile emulation retained the existing layout and truthful message/date labels. A real text provider session with Chrome Offline demonstrated polling failure and saved-card preservation; the established WebSocket did not drop, so unexpected connection loss is not claimed. Manual End while Offline blocked approval until online recovery revoked the binding and loaded revision 2. Chrome's security warning prevented a forced-socket console test; it was not bypassed. Network settings were restored.

Fixed stale recovery messages with failing-then-passing lifecycle regressions, including both tool/poll error orderings identified by independent review. Added two isolated backend text↔voice handoff acceptance cases. Root verification: 143 backend/setup tests plus 11 subtests passed; 33 frontend tests and production build passed. Browser automation later reported cgWindowNotFound, so the latest copy fix still needs a live recheck. Detailed PASS/NOT TESTED distinctions are in docs/milestone-5-verification.md.

User-guided SAME-call speech correction, All good, interrupted farewell, actual unexpected call loss, and new reviewed approval/reload remain pending. M5 is in progress; M6 and M7 were not started.
## October 24, 2026 — Milestone 5 connection recovery

Investigated the reported unavailable voice connection before changing configuration. The local services were healthy; Cloudflare's temporary tunnel had disappeared (`Unauthorized: Tunnel not found`, then DNS failure). Replaced that tunnel, updated only the four existing tool URLs and local public URL, and restarted the main API. Verified real authenticated HTTPS lookup returns Maple Court Unit 4, revoked binding returns 401, private agent/authentication remain enabled, and saved business records are unchanged. No source changes; live speech acceptance is still pending in `docs/milestone-5-verification.md`.

## October 24, 2026 — Milestone 5 completed

Completed the user-guided live checks: microphone denial, unexpected Wi-Fi disconnection with unchanged editable saved draft, All good automatic hang-up, and automatic hang-up despite user-confirmed speech overlap during goodbye. Created the wardrobe draft through real voice/tools, corrected its notes in a resumed call, then reviewed revision 2 and double-clicked Approve through Safari. Reload and three real approval retries retained exactly one order with the exact reviewed snapshot. Cancelled only the separate coat-hook test draft and confirmed approval returns 409 draft_cancelled.

The final uninterrupted speech test created the new hallway-skirting-board draft at revision 1 and corrected its access notes to “After 2:00 p.m., please knock” at revision 2 in the SAME provider conversation. Both prepare tools succeeded, the same draft ID remained, the visible card updated, and native end_call disconnected. This draft remains unapproved for review. Fixed one misleading screen-reader announcement to avoid asking the user to end an already ended call; no new state or feature was added.

Final checks: 143 backend/setup tests plus 11 subtests passed; 33 frontend tests and TypeScript/Vite production build passed. Independent read-only comparison found zero altered or missing pre-existing business rows. Final counts: 8 drafts, 22 history rows, 4 work orders, 7 jobs, one seed marker, zero active/unrevoked voice bindings. Live versus simulated evidence and remaining test-environment limitations are recorded in `docs/milestone-5-verification.md`. M5 is complete; M6 submission preparation is next, and M7 features remain deferred.

## October 24, 2026 — Milestone 6 local submission package

Scope: prepare the README, Google Doc source, a 4:30 demonstration script, and a safe local Git package. Use completed Milestone 5 evidence and preserve all saved records. Actual Google Doc creation, recording, GitHub publication, and course submission remain pending; no Milestone 7 features were added.

Finished `README.md` with architecture, reproducible setup commands, all environment variables, service startup, temporary tunnel verification/renewal, fictional data, approval boundaries, and limitations. Prepared `docs/submission-overview.md` from existing records without inventing customer feedback, savings, or results. Prepared `docs/demo-script.md` with eight contiguous slots totaling 270 seconds. Independent review caught a narration gap that could end the call before correction; the final script corrects immediately after draft creation and narrates the records after disconnecting.

The overview includes these exact excerpts from the user's milestone prompts in the project conversation, rather than presenting earlier build-log summaries as verbatim chat:

- Milestone 1: “Build a polished React web app using TypeScript, Vite, and Tailwind CSS.”
- Milestone 3: “Approval must save the exact revision the landlord reviewed. Reject outdated or cancelled drafts.”
- Milestone 4: “Keep approval exclusively in the existing review card. The voice agent cannot approve, send messages, or confirm bookings.”
- Milestone 5: “Report PASS, FAIL, or NOT TESTED, distinguishing live checks from simulated tests.”

Read-only preparation found no matching blind/cord draft or job for the proposed Maple Court Unit 4 dining-room blind-cord repair, and confirmed Ben's general-repair approval. The script requires a freshness recheck before recording and preserves both original orders and unapproved test cards. This candidate has not been demonstrated in a new live speech recording; that remains NOT TESTED.

The README tunnel preflight exposed another expired temporary hostname while the gateway remained healthy. Restarted only Hearth's tunnel, updated the existing four provider tool URLs and local configuration, and restarted the main API. Authentication, tool schemas, agent instructions, voice/model settings, and repair data were retained. Fresh checks passed: controlled unauthenticated lookup response, public `/docs` and `/api/work-orders` both 404, frontend/API both 200. These checks establish connectivity, not a new real ElevenLabs conversation; no paid call was started for M6.

Created the local `main` Git repository and prepared 68 source/documentation files. Updated `.gitignore` for credentials, databases/journals, local setup state, logs, dependencies, caches, coverage, and build output; `.env.example` contains blank credentials and safe instructions. No remote was configured or push performed. A private backup and complete read-only comparison of all 14 database tables found zero changes: 8 drafts, 22 history rows, 4 work orders, and 7 jobs remained.

Verification of an exported staged source tree, without the local `.env` or saved database:

- Backend/setup: **143 tests plus 11 subtests passed** (using the existing pinned Python environment).
- Fresh frontend `npm ci`: passed, followed by **33 frontend tests passed**.
- TypeScript and Vite production build: passed; existing nonblocking 886.06 kB / 243.80 kB gzip bundle warning remains.
- Fresh-seed FastAPI smoke: Maple Court Unit 4 and Ahmed returned, zero work orders, voice correctly unavailable without credentials. The first ad-hoc smoke assertion used a nested field instead of the documented flat `matched_unit.id`; corrected the smoke harness, with no application change.
- Documentation: all 34 checked local links resolve; the demo timeline totals 270 seconds.
- Git package: all 68 staged files passed the actual local-credential/session-capability scan with zero findings; no forbidden local/generated files were staged, ignore-rule checks passed, and `git diff --cached --check` was clean.

Existing M5 live outcomes remain attributed to `docs/milestone-5-verification.md`. No new microphone, recording, physical-phone, or hosted-deployment result is claimed for this packaging milestone.

## October 24, 2026 — GitHub publication

The user selected `https://github.com/faziz7-viz/Hearth`. Confirmed the public repository was empty and the connected account had write access. A fresh independent audit of all 68 committed files found no actual local credentials, app-session capabilities, voice-binding hashes, databases, logs, generated dependencies/output, or local provider setup state. All exclusion probes passed, and `.env.example` retained blank credential fields.

Connected `origin` and pushed the prepared commit `4592e93` to `main` without forcing or replacing any remote history. Updated the README with clone instructions and the repository link, and marked only the GitHub publication task complete in both plan copies. The application code and saved records were not changed. Existing clean-export test/build results above still apply; these follow-up changes are documentation only. Google Doc creation, video recording, and course submission remain pending; Milestone 7 stays deferred.
