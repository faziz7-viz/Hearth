# Milestone 5 — verification complete

Scope: the current build plan's complete-workflow checks and the user's five outstanding live voice checks. Preserve Hearth's design, authentication, session/revision checks, and all saved records. Stop before Milestone 6; Milestone 7 features remain deferred.

Completed October 24, 2026. All requested Milestone 5 acceptance categories passed with the live/simulated distinctions below. Final state: 8 drafts, 22 history rows, 4 work orders, 7 jobs; every pre-existing business row is unchanged. One new wardrobe work order was approved. The final skirting-board draft remains unapproved at revision 2. No active or unrevoked voice bindings remain.

## Baseline and test isolation

Before testing on October 23, 2026, SQLite contained 5 drafts, 14 draft-history rows, 3 work orders, and 6 jobs. A private SQLite backup is at `/tmp/hearth-m5-baseline.sqlite3`. The existing Maple Court kitchen tap, Cedar House bathroom sink, and Willow Place broken door handle work orders must remain unchanged. The unapproved Milestone 4 curtain-rail draft must also remain unchanged.

A separate Safari private window has its own app session. The live happy-path candidate is Maple Court, Unit 4, a loose bedroom wardrobe shelf. Direct read-only checks returned no similar open job and Ben as the approved general contractor. The ordinary Safari window and its saved curtain-rail draft are retained.

Ruling: use a genuinely new repair instead of the plan's original kitchen-tap happy path, because that tap already has a saved work order. This follows the user's explicit preservation instruction.

No Git repository exists in this workspace. Verification uses the existing running project and isolated temporary databases for simulated tests; no extra workflow tools or repository setup are introduced.

## Live checklist

| Check | Status | Evidence |
| --- | --- | --- |
| Microphone permission denied | PASS — real browser | Denied the native Safari prompt, then clicked Start again with permission denied. Hearth displayed “Microphone access is unavailable. Allow it in your browser and retry, or choose Text conversation. Your saved draft is kept.” It returned to Ready when you are with End disabled and the form available. This private test session had no saved draft; same-session saved-draft preservation under denial is covered by simulated lifecycle tests. |
| Unexpected connection loss with saved draft | PASS — live voice/network loss | User switched Wi-Fi off and back on during a real Safari voice call. Provider recorded abnormal disconnect code 1006 without an end_call tool. Hearth displayed its disconnected/saved-draft-kept message and returned to Ready when you are. The same wardrobe draft stayed editable at revision 2, with unchanged notes/date, revoked binding, and no work order created by the drop. |
| New draft and spoken correction during the same call | PASS — live speech/tools | One provider conversation created the hallway-skirting-board draft at revision 1 and updated that same ID with expected revision 1 to saved revision 2. Both prepare tools succeeded. The visible card and SQLite show “After 2:00 p.m., please knock.” The earlier wardrobe resumed-call correction is not used as this evidence. |
| Speak during updated goodbye | PASS — live, user-confirmed overlap | The user confirmed speaking while Hearth was audibly saying goodbye and reported automatic disconnection. Provider history records successful native end_call and both test bindings revoked. Speech overlap itself is confirmed by the user, not inferred from the transcript. |
| All good after save automatically disconnects | PASS — live speech | User said “All good.” Provider recorded a successful native end_call, status done, and termination reason “end_call tool was called.” The app binding was revoked; the user confirmed automatic disconnection. Wardrobe revision 2 stayed saved and unapproved until the later explicit card-approval test. |
| Voice → tools → correction → reviewed approval → reload | PASS — live speech, browser, API | Wardrobe repair was created and corrected through real speech/tools, then exact revision 2 reviewed and approved through Safari. Reload retained its approved card and saved order. Correction used a resumed conversation; the separate skirting-board check proves same-call creation/correction. |
| Exactly one correct work order | PASS — live browser/API | Double-clicked Approve on wardrobe revision 2. Three real approval retries (two same-key, one new-key) returned HTTP 200 and the same order, with snapshot exactly equal to saved reviewed revision 2. Exactly one wardrobe order exists; total orders 3 → 4, all originals unchanged. |
| Desktop and mobile | PASS — browser inspection | Inspected the running desktop layout and Chrome mobile emulation at 390 × 844 and 320 × 844. Request/voice controls, stacked card fields, action buttons, saved orders, and recent jobs fit without horizontal clipping. This is browser emulation, not a physical phone test. |
| Draft-message and requested-date labels | PASS — browser inspection | The card says Requested date, “A request, not a confirmed booking,” and “Editable draft only. Approval saves this exact message; nothing is sent.” Saved orders show “Exact approved details · No messages sent.” |

## Automated and isolated verification

| Check | Status | Actual result |
| --- | --- | --- |
| Backend/setup suite | PASS — automated | Root ran `backend/.venv/bin/python -m pytest -q`: 143 passed, 11 subtests passed in 2.47s, exit 0. Real FastAPI/SQLite behavior in temporary databases; signed provider access is simulated. |
| Frontend lifecycle/state suite | PASS — simulated | Root ran `npm test`: 33 passed, 0 failed/skipped, exit 0. Includes microphone, disconnect, recovery, exact revision, and approval guards. |
| Production build | PASS | Root ran `npm run build`: TypeScript and Vite passed, exit 0, 1644 modules. Existing nonblocking bundle warning: 886.06 kB minified / 243.80 kB gzip. |
| Text ↔ voice handoff | PASS — simulated provider | Two new isolated cases cover the same draft through form revision 1, first mode edit revision 2, form date edit revision 3, second mode edit revision 4, end, exact snapshot approval, and repeated approval returning one order. This does not prove speech recognition or a live same-call correction. |
| Cancellation | PASS — live form/API and automated | Cancelled only the M5 coat-hook test draft through Chrome. UI showed Cancelled and disabled fields; a real approval retry returned HTTP 409 draft_cancelled. Work orders remained 3 during that check. Isolated tests also pass. |
| Repeated/concurrent approvals | PASS — live browser/API and automated | Live double-click plus three HTTP retries returned one wardrobe order with the exact reviewed revision 2. Isolated tests: six simultaneous requests return one order; two competing drafts produce one HTTP 200 and one HTTP 409. |
| Unapproved contractor | PASS — automated | Unknown/wrong-trade contractor saves needs_human; approval returns HTTP 409 approval_blocked / contractor_not_approved. A contractor approval revoked after save also blocks approval. |
| No agent approval | PASS — automated | Gateway approval/API routes are HTTP 404, authority fields HTTP 422, and card approval during an active binding HTTP 409 voice_active. |
| Bounded retry | PASS — automated; prior M4 live evidence retained | Backend temporary-read tests permit two total attempts, then HTTP 503 with draft preserved. M4's real provider text outage test already proved initial attempt plus one requested retry, then native end_call; it was not re-run in M5. |

Backend acceptance cases are in `backend/tests/test_milestone5.py`. Existing cancellation/concurrency/revalidation tests remain in `test_drafts.py`; voice-boundary/retry checks remain in `test_voice.py`.

## Preservation check

At the start, local Vite, main API, and gateway were already running and reused. The real HTTPS gateway preflight passed. No service restart, credential change, database reset, existing order edit, or existing draft cancellation was performed.


## Fresh running-app record and revision checks

These used the actual port-8000 backend and current SQLite records. Read-only HTTP probes and the Chrome repair form agreed:

| Check | Status | Actual result |
| --- | --- | --- |
| Ambiguous Unit 4 | PASS — live form/API | Choose a property; Cedar House and Maple Court offered. HTTP 200 ambiguous_property, no matched unit or contractor. No silent selection. |
| Unknown Juniper Court | PASS — live form/API | Property not found; HTTP 200 unknown_property, no invented property or unit. |
| Cedar bathroom tap | PASS — live form/API | Possible duplicate repair shows existing open leaking bathroom tap and Ahmed. Approval is unavailable on the unsaved duplicate card; isolated approval tests return 409. |
| Willow plumbing without an approved contractor | PASS — live form/API | Needs human review; no replacement selected. HTTP 200 needs_human with no approved contractors. |
| Sparks/burning smell | PASS — live form/API | Needs human review before routine repairs; no repair instructions or booking claim. HTTP 200 needs_human before property matching. |
| New Maple wardrobe-shelf candidate | PASS — read-only API | Maple Court Unit 4, Ben, no similar open repair. Reserved for the user-guided spoken flow. |
| Outdated approval | PASS — live form plus controlled API edit | Chrome saved the separate coat-hook draft at revision 1. A real PATCH emulating another tab saved revision 2. Clicking Approve on visible revision 1 produced “Saved draft needs review” and required Load latest saved draft. No order was created. Loading latest restored revision 2 and the updated access notes. |

The separate coat-hook test draft is `4043f530-ce45-44da-b2fb-381a6edce8de`, Maple Court Unit 4, Ben, issue “Loose hallway coat hook,” revision 2, requested date empty. Access notes: “M5 connection test. Knock before entry. Wait for an answer.” After the connection checks, it was cancelled through Chrome; real API approval was rejected with HTTP 409 draft_cancelled and no order was created. The original curtain-rail draft was not used or modified.

## Live network test and scoped recovery fix

Connected Chrome Text conversation to the real provider with the saved coat-hook draft. Turning Chrome DevTools Network to Offline caused the real HTTP polling request to fail while the established WebSocket remained connected. The card stayed locked for review and retained the saved draft. This is evidence of polling failure, not an unexpected call disconnection.

A targeted console command intended to close only Hearth's provider WebSocket was blocked by Chrome's paste security warning. It did not run; no warning was bypassed and no browser security protection was weakened. Then clicked the normal End control while Offline. The app entered recovery error, kept the card, and blocked approval. Restored No throttling and clicked Retry ending & refresh saved card. It returned to idle with the exact revision-2 draft, enabled review controls, and revoked the binding. Provider history says done / “Client disconnected: 1000,” consistent with manual End, not unexpected transport failure.

That sequence exposed misleading recovery text: the previous failure message remained after successful final refresh. Fixed only `frontend/src/voiceSession.ts` with regression coverage in `frontend/tests/voiceSession.test.ts`. A successful final read now clears resolved closing/polling warnings and retains meaningful microphone, disconnect, or tool-failure explanations. Independent review found the tool-failure-then-poll-failure ordering case; the final guarded polling update and reverse-order regression address it. Regression failures were observed before fixes; the final full frontend suite/build passed. The latest source correction has not yet been rechecked through the live browser: browser automation subsequently returned `cgWindowNotFound` for Chrome.

References used for browser-only fault injection: [Chrome Network reference](https://developer.chrome.com/docs/devtools/network/reference/#offline), [Chrome Console utilities](https://developer.chrome.com/docs/devtools/console/utilities), and [WebSocket close method](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/close). These describe test mechanisms; they do not substitute for observed app results.

## Current checkpoint and remaining actions

Preservation comparison against the M5 baseline passed: every pre-existing row in properties, units, contractors, approvals, jobs, policy, maintenance history, drafts, draft history, work orders, approval keys, and seed markers remains byte-for-byte unchanged. The added coat-hook test draft/history are additive. Work orders remain exactly three; no live M5 approval has occurred. No active voice binding remains; Chrome network throttling was restored to normal before the automation window became unavailable.

The October 23 checkpoint above is historical. The October 24 live tests below completed the outstanding creation/correction in the SAME call and reviewed approval/reload/retry checks, along with All good hang-up, real unexpected connection loss, and user-confirmed speech overlap during goodbye. Milestone 5 is complete. Milestones 6 and 7 were not implemented as part of this verification.

## October 24 — unavailable voice connection restored

The user reported “Hearth’s voice connection is unavailable.” Safari showed that exact preflight error, Ready when you are, and no new draft. The local frontend, API, and authenticated gateway were running. The old Cloudflare quick-tunnel hostname no longer resolved; cloudflared logs repeatedly reported `Unauthorized: Tunnel not found` following a network inactivity timeout. Production `check_public_gateway()` reproduced HTTP 502 `voice_gateway_unavailable`, while the local gateway returned its expected HTTP 401 `unauthorized_tool`. This was a failed public tunnel, not a property lookup or microphone failure. No new provider lookup or wardrobe draft was created by this failed start.

Replaced only Hearth's failed quick-tunnel process, changed the four existing ElevenLabs webhook URLs and the local public URL, and restarted the main API to load that URL. Each tool's method, request schema, authentication headers, other settings, and empty response mocks were verified unchanged. The agent remains private, retains its four tool IDs, and its instructions match the local prompt. The frontend and gateway were reused. No application source change was needed.

Post-fix live HTTP checks: running API issued temporary conversation access with HTTP 200; an authenticated HTTPS `lookup_property` request returned HTTP 200, `matched`, Maple Court / `maple-court-unit-4`; ending that diagnostic binding caused the same credentials to return HTTP 401. This diagnostic used real HTTPS/backend records but no speech or connected provider conversation. All checked pre-existing business rows were unchanged, with 6 drafts, 16 history rows, 3 work orders, and 6 jobs at that checkpoint. Safari was refreshed and showed Start conversation without the error. User speech checks were still pending at that point; their completed results follow below.

## October 24 — live wardrobe draft and All good

The real spoken request created draft `0cba58ca-a6ab-44c1-837b-8e8a529d8ed5`, revision 1, Maple Court Unit 4, “Bedroom wardrobe shelves are loose,” approved general contractor Ben, requested date empty, access “Access by knocking.” Provider conversation `conv_1201m5pzkzknfgzbadbfsktdhdsh` completed real record tools and successful `prepare_repair_draft` with null draft ID / expected revision 0. It later ended natively after the user did not reply; no approval occurred.

Conversation `conv_4501m5pzpswcfjdbtk4bm3gtbfc5` accepted the spoken correction and successfully called `prepare_repair_draft` on that exact ID with expected revision 1 and only changed access notes. SQLite now has revision 2, ready_for_review, notes “After 4:00 p.m. Please knock.” This is resumed-call correction, not the outstanding same-call check. After the user said “All good,” the provider recorded native `end_call`, no tool error, status done, and its app binding was revoked. The user confirmed automatic disconnection. No new work order has been created.

The subsequent live Wi-Fi interruption used `conv_6401m5q03xg7frtrpn0fb6jcf4t5`. Provider metadata recorded `Client disconnected: 1006`; no tool call or normal end_call occurred. Safari displayed “The conversation disconnected. Your saved draft is kept. Reconnect or continue with the form.” Ready when you are, disabled End, editable card, and enabled Approve/Cancel were inspected directly. SQLite confirms the same wardrobe draft is still ready_for_review revision 2, same access note and null requested date; the binding is revoked and order count remains 3. Public gateway preflight still passes after Wi-Fi restoration. This is the required real transport-loss evidence, unlike the earlier Chrome HTTP-only Offline test.

During accessibility inspection, the screen-reader-only saved-revision announcement still instructed the user to end an already ended call. Changed that single App.tsx sentence to “Review the saved card before approving,” keeping the revision notice and all voice/approval guards. Post-change frontend verification: 33 tests passed; TypeScript/Vite production build passed, with the same nonblocking bundle-size warning.

Goodbye test conversations `conv_9901m5q0g90yerfrj0gt01x9qy84` and `conv_3801m5q0gvqsfdevpx0176m78kzg` both finished with native end_call and revoked app bindings. The latter first heard “Goodbye. Wait, one more thing” as one user turn and correctly stayed available; a subsequent standalone goodbye ended it. The user then explicitly confirmed that their attempted interruption overlapped Hearth's audible goodbye and that the call disconnected automatically. This provides live user-confirmed overlap evidence; the transcript alone cannot establish speech that the agent ignored during its uninterruptible closing turn.

Pre-approval checkpoint: the wardrobe draft was still unapproved, ready_for_review revision 2, with the same notes and empty requested date. The coat-hook test draft was cancelled. At that point there were still exactly 3 existing work orders.

## Final approval and reload check

After the user's instruction to finish the two remaining checks, reviewed the visible wardrobe card and double-clicked Approve in Safari. It displayed “Work order saved,” revision 2 approved, no message sent, and four saved orders. Reload retained that approved card and the single wardrobe order. Work order `67fe4802-0982-45b0-8e18-26296fd613bd` has the exact snapshot stored by the revision-2 edit, including null requested date, Ben, the wardrobe issue, and “After 4:00 p.m. Please knock.” Two retries using the original approval key and one with a fresh key each returned HTTP 200 and that same order/snapshot. Exactly one order exists for the wardrobe draft; all baseline business rows and the original three orders remain unchanged.

Fresh checks at this point: backend/setup suite 143 passed and 11 subtests passed (2.17s); frontend suite 33 passed, none failed/skipped; TypeScript/Vite production build passed (same nonblocking bundle warning). Opened New request in Safari for a genuinely new hallway-skirting-board repair, completing the final live check below.

## Final uninterrupted speech check

Conversation `conv_1101m5q8e3g8e85a6nprn9azz5y9` is the only binding for new draft `0b7b5794-f48e-4099-9f2c-75c34631bfd5`. Its completed provider history contains, in order:

1. Successful real `lookup_property` for Maple Court / Unit 4.
2. Successful `check_open_jobs` and `lookup_maintenance_context`, grounding the general-repair draft and approved contractor Ben.
3. Successful `prepare_repair_draft` with null draft ID, expected revision 0, issue “Loose skirting board in the hallway,” empty requested date, and “Access by knocking.”
4. After the user's spoken correction, successful `prepare_repair_draft` with that same draft ID, expected revision 1, and only access notes changed to “After 2:00 p.m., please knock.”
5. Successful native `end_call` after the user indicated no further changes; provider status done, termination reason “end_call tool was called,” app binding revoked.

SQLite has exactly created revision 1 and edited revision 2 for this draft. Safari visibly shows Ready when you are, saved revision 2, the corrected notes, Ben, an empty requested date, and an editable review card. The screen-reader saved-revision notice also now correctly says “Review the saved card before approving.” No skirting-board work order was created; this final draft is left available for review.

Independent final read-only audit compared all 12 business tables with the pre-M5 backup. Zero baseline rows are missing or changed. The wardrobe order is unique and exactly matches its reviewed revision-2 snapshot. Both the active-binding count and total unrevoked-binding count are zero.

## Limits of the evidence

Mobile layout was tested in browser emulation, not on a physical phone. Concurrent approval, revoked-contractor approval, and injected business-tool failures use real isolated FastAPI/SQLite tests with simulated provider access. The exact earlier Chrome HTTP-polling/offline recovery sequence was not repeated after the final recovery-text fix; its regressions pass, and the subsequent real Wi-Fi disconnection verified saved-draft recovery. These limitations do not replace the live speech checks documented above. No message sending, confirmed booking, Milestone 6 deliverable, or Milestone 7 feature is claimed.
