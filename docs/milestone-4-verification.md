# Milestone 4 — actual verification results

Milestone 4 adds ElevenLabs to the existing Hearth interface. Live account setup and speech acceptance are separate from automated tests. **A mocked provider is not a real ElevenLabs conversation.**

## Live setup and acceptance

| Check | Status | Actual result |
| --- | --- | --- |
| Agents account access and credits | PASS (user confirmed) | The user confirmed “Agents is available and I have credits.” |
| Private agent and real webhook configuration | PASS | User saved the API key and dedicated agent ID through hidden local Terminal input. Real API provisioning created/configured the four webhook tools and verified the agent's exact tool IDs and private authentication. The agent is named Hearth Demo. |
| Real temporary conversation access | PASS | The user connected voice conversations; a subsequent browser text test also connected using temporary access and the current app binding. |
| Real speech → four real ElevenLabs tool calls → visible draft | PASS after tunnel fix | The first attempt failed with DNS resolution failure for the old temporary tunnel. After replacing it and updating all four tools, the user spoke a broken door handle request for Willow Place, Unit 2. The completed provider transcript identifies the user turns as audio and all four webhook results as successful. Safari visibly showed saved revision 1, Ben, requested October 29, 2026, and access notes “Just knock.” The user confirmed “works now.” |
| Spoken correction updates the same draft ID | PASS (real speech) | Curtain-rail draft `4b7e5fcb-d408-4376-a68b-a5ce14aabd60` at Willow Place Unit 2 remains unapproved. Voice created revision 1; a form edit created revision 2. A resumed audio conversation called prepare_repair_draft with that same ID, expected_revision 2, and only access_notes changed. It saved revision 3 with “Back door will be left open for entry. Please knock. Availability after 4:00 PM.” The user confirmed the notes changed. |
| Live microphone denial and disconnection | NOT TESTED | Requires the configured live browser flow; simulated error handling does not substitute for this check. |
| Same-agent text conversation | PASS (read tools) | On October 23, the running browser connected to the real agent. Provider execution results show successful lookup_property, check_open_jobs, and lookup_maintenance_context calls. The visible transcript matched Willow Place, Unit 2, returned Ben, and reported no duplicate for a loose bedroom door handle. The request explicitly asked for checks only; no draft or order was created. End revoked the binding. |
| Maple Court retest after tunnel repair | PASS (live text) | The same app-bound agent returned Maple Court Unit 4 from lookup_property and flagged the existing leaking kitchen-tap work order. Exact arguments matched the failed call. |
| Stop after the first technical failure and one requested retry | PASS (live text) | During a controlled gateway outage, exactly two lookup attempts failed. The agent offered the form and invoked end_call; it did not offer or attempt a third retry. The session disconnected and its binding was revoked. |
| End the conversation disconnects | PASS (real speech and live text) | The curtain-rail call contains the audio-source user turn “End the conversation.” followed by successful native end_call. Provider termination says “end_call tool was called.” and the SQLite binding is revoked. The saved draft remains unapproved. Text-mode checks separately verified the screen returning to idle. |
| Goodbye disconnects without clicking End | PASS (real speech) | The user confirmed automatic disconnection. Provider history confirms a successful native end_call and a revoked app binding. Two earlier closing attempts were interrupted by new microphone input; the follow-up fix and its testing limits are recorded below. |
| Corrected draft survives backend restart | PASS | Restarted only the project main API. The complete revision-3 snapshot, all three history entries, and all three work orders matched the pre-restart snapshot exactly. The live session API returned the same saved draft and access notes. |

The first successful live test used **Willow Place, unit 2, broken door handle** (general repairs). There was no existing open job before that test. The user subsequently ended voice and approved revision 1 through the card, so this repair now correctly has a saved work order. The separate curtain-rail test also returned no duplicate and completed the same-draft spoken correction; it remains unapproved.

Successful voice draft: `e5daaa6a-ece5-4c65-8eee-00b0ef13bc01`, revision 1. Its binding was revoked when the call ended. Work-order count stayed two during voice preparation, then increased to three when the user approved the card; no contractor message was sent. The requested date remains a request, not a booking.

## Data baseline

The existing database was backed up to `/tmp/hearth-m4-baseline.sqlite3`. Before M4 verification it contained **3 drafts, 9 draft-history entries, 2 work orders, 5 jobs, and 1 seed marker**. The approved jobs include Maple Court's kitchen tap and Cedar House's bathroom sink. Those records must be preserved.

## Automated and local checks

| Check | Status | Actual result |
| --- | --- | --- |
| Backend and setup tests | PASS | October 23: `backend/.venv/bin/python -m pytest -q`: **141 passed, 11 subtests passed in 1.90s**, exit 0. Includes existing record/draft/approval tests, 45 voice tests, and 10 setup/config cases. Provider access is mocked in the automated integration tests. |
| Frontend state/lifecycle tests | PASS | `npm test`: **28 passed, 0 failed**, exit 0. Covers denial/error callbacks, native agent termination, disconnect, pending access cancellation, bind failure, stale polls, reload recovery, dirty edits, finite duration, and final refresh before approval. These are controlled tests, not a real microphone call. |
| Frontend production build | PASS | `npm run build`: TypeScript and Vite passed, exit 0; 1644 modules. Vite reports a nonblocking bundle-size warning: approximately 886 kB minified / 244 kB gzip including the SDK. |
| Same draft and revisions | PASS (automated) | Authenticated adapter tests create revision 1, correct the same ID to revision 2, reject stale/other-session/terminal drafts, and exercise concurrent/replayed writes using temporary SQLite databases. No work orders are created by the tools. |
| Webhook authorization | PASS | Tests require the workspace secret, opaque binding, and exact provider-issued conversation ID; reject expired/revoked/wrong-session access before body parsing. Token hashes and bindings survive restart. |
| Public HTTPS isolation | PASS | The running Cloudflare gateway returned **401** for unauthenticated POSTs to all four tools. `/api/work-orders`, `/api/drafts/anything/approve`, `/docs`, and `/openapi.json` returned **404**. This proves reachability and isolation, not an ElevenLabs tool call. |
| Unavailable tunnel before Start | PASS | Added a real public gateway preflight before issuing ElevenLabs access: verified HTTPS, no credentials, no redirects, five-second socket timeout, bounded response, expected controlled 401. DNS/TLS/timeout/malformed/unexpected responses fail clearly without provider access or a new binding. In the running browser, stopping only the gateway then clicking Start displayed “Hearth’s voice connection is unavailable. Retry or use the saved repair form.” The form stayed available, binding count stayed four, and restarting the gateway passed the real preflight. |
| Python HTTPS | PASS | Fixed the Python installation's missing default CA-store issue using the operating system trust store with certificate/hostname verification enabled. An unauthenticated official ElevenLabs request reached HTTP 401. No API key was sent in that test. |
| Exact configuration payloads | PASS (offline) | All four rendered tool payloads and the agent PATCH validate against the official current ElevenLabs OpenAPI schema. Live account acceptance remains separate. |
| Existing form fallback | PASS | In the running browser, unconfigured voice clearly showed “Voice setup needed.” The real form check returned Willow Place, Unit 2, no similar open repair, and Ben as the approved general contractor. The unsaved card was discarded; no draft/order was created. |
| Desktop design | PASS | Inspected the running Hearth screen: existing layout, warm neutral/green styling and review card retained; voice/text mode controls and Start/End fit the request panel. |
| Existing SQLite records and restart | PASS | After restarting only the project backend/gateway, every pre-existing property, unit, contractor, approval, job, history, policy, draft, draft-history, work-order, and seed row matched the baseline exactly. Counts remained 3 drafts, 9 history entries, 2 orders, 5 jobs, 1 seed marker. |
| Python dependencies | PASS | `backend/.venv/bin/python -m pip check`: no broken requirements. |
| Independent review | PASS | Two findings were fixed and rechecked: late disposed-controller cleanup clearing a newer recovery marker, and misleading transcript-retention copy. No unresolved blocker reported. See `docs/m4-review-report.md`. |

Known recovery limit: if an access request commits but its HTTP response is lost, the browser may not know the binding ID. Approval fails closed until a new successful Start/End cycle or the binding's maximum ten-minute expiry. Saved draft details remain available.

Milestone 5 is not part of this change.

## October 23 lookup incident: captured evidence

The reported conversation started at **15:38:04 UTC (11:38:04 EDT)**. ElevenLabs recorded two actual `lookup_property` webhook attempts, at 22 and 38 seconds into the call. Both used:

```json
{"query":"Maple Court","unit_label":"4"}
```

Both requested `POST https://essex-someone-bundle-indicate.trycloudflare.com/voice/tools/lookup_property`. Both results had `is_error: true`, `tool_has_been_called: true`, and `error_type: external_server`. The provider's result was HTTP 500; its exact underlying error for both attempts was:

```text
Failed to make the request: DNS resolution failed for "essex-someone-bundle-indicate.trycloudflare.com": lookup essex-someone-bundle-indicate.trycloudflare.com on 169.254.20.10:53: no such host
```

The attempts took 0.027006 and 0.020445 seconds. They ran on ElevenLabs but did not reach the Python lookup function. The previous tunnel process log reports `Register tunnel error from server side error="Unauthorized: Tunnel not found"` repeatedly, including 15:41:31 UTC, before its intentional shutdown at 15:43:06 UTC. This is Cloudflare rejecting the disappeared tunnel, not Hearth rejecting a session.

The local main API logs show successful `POST /api/voice/access` responses (200). The gateway ran with access logs disabled, so historical per-request gateway entries are unavailable. DNS failure before HTTP explains why no backend lookup result exists. Both recorded requests used the correct POST route and exact required field names. Their conversation ID matched the durable binding and the requests occurred before expiry. ElevenLabs redacts the workspace secret and binding token in its history, so their original literal values cannot be reverified from that transcript. Those credentials are not reproduced here. Current real successful calls exercise all three authorization checks with no bypass.

The replacement URL is `https://lee-symposium-refused-compared.trycloudflare.com`; the configured tool URL matches it. The main API, gateway and existing Vite server are running locally. A public preflight verifies the protected gateway before issuing new access. Authentication, session binding, expiry, revision checks and review-card-only approval remain enabled.

The goodbye-only behavior had a separate cause: the native ElevenLabs `end_call` tool was disabled. It is now enabled alongside the same four business webhooks. The prompt permits one explicitly requested technical retry, then ends the call with form fallback after another failure. Missing details, ambiguity and stale-revision corrections are treated separately. Frontend tool-error copy no longer invites open-ended retries.

Live retest from Hearth text conversation: `lookup_property` returned `status: matched` with `maple-court-unit-4`, `Unit 4`, `property_id: maple-court`. `check_open_jobs` correctly returned `duplicate_found` for the existing kitchen tap. Sending “End the conversation” invoked native `end_call`; provider termination reason was `end_call tool was called.`, the app returned to idle, and the SQLite voice binding was revoked. No draft or work order was created by this retest. Spoken termination was subsequently verified separately.

Controlled live failure test: connected a fresh app-bound text conversation, then stopped only Hearth's gateway. The agent's first lookup failed and it offered one retry. Sent “Try the lookup once more.” The second lookup failed; the agent gave form fallback and invoked `end_call` without another retry offer. Provider history contains exactly two failed `lookup_property` results and one successful `end_call`. The app showed “Ready when you are,” disabled End, and revoked the binding. No third attempt was possible in that closed session. Restored the gateway and passed its public preflight. Business records remained four drafts and three work orders (including the user's earlier approved door-handle job).

Goodbye follow-up: removed remaining prompt instructions telling the landlord to end manually. The agent now invokes end_call with any final farewell, and treats “All good,” “That's all,” or “No more changes” after a saved draft as completion. Ordinary thanks during unfinished work does not end the call. Published these instructions to the existing private agent. A real Hearth text conversation sent “Goodbye.”; the assistant replied “Goodbye.”, native end_call terminated the provider session, the binding was revoked, and the screen returned to Ready when you are with End disabled. No manual End click was used. Spoken goodbye was subsequently verified below. The post-save “All good” variation remains NOT TESTED live.

The user subsequently confirmed a saved curtain-rail draft appeared. Provider evidence for the call started October 23 at 19:11:24 UTC (3:11:24 pm EDT) confirms actual audio, successful property/duplicate/maintenance reads, no existing curtain-rail job, and successful prepare_repair_draft for Willow Place Unit 2/Ben with no requested date. Draft `4b7e5fcb-d408-4376-a68b-a5ce14aabd60` was created at revision 1. Unknown property requests returned unknown_property and clarification without changing its property. The audio command “End the conversation” successfully invoked end_call and revoked the binding. Work orders remained three.


## Final speech correction, closing interruption, and persistence

After a form edit saved revision 2, the user resumed voice on the same unapproved curtain-rail draft. The provider records actual audio and this successful tool request:

```json
{"draft_id":"4b7e5fcb-d408-4376-a68b-a5ce14aabd60","expected_revision":2,"fields":{"access_notes":"Back door will be left open for entry. Please knock. Availability after 4:00 PM."}}
```

The result returned the same ID at revision 3. The user confirmed the notes changed. The saved property remains Willow Place, Unit 2, contractor Ben, requested date empty, status ready_for_review. The draft has exactly three history entries: created, edited, edited. No work order was created by the correction.

The user also confirmed Goodbye automatically disconnected. Inspection found an additional closing edge case: at 88 and 107 seconds, the agent selected end_call but new microphone input interrupted its long farewell. Both results were `is_error: true`, `tool_has_been_called: false`, with exact error `Tool execution was abandoned due to user input`. At 112 seconds, the third closing attempt successfully called end_call and revoked the binding.

Fixed only the closing behavior: the native end_call tool now uses `interruption_mode: disable_during_tool_and_turn` and `pre_tool_speech: off`. Its prompt requires one short farewell, without another draft summary or approval reminder. These are supported by the current official OpenAPI schema. All four business webhooks retain `interruption_mode: allow`; authentication and session/revision checks remain enabled. A regression failed before the change and passed afterward. The real account accepted the configuration and a subsequent GET verified it.

Post-fix real Hearth text test: “Goodbye.” produced exactly the short farewell, successful native end_call, provider termination `end_call tool was called.`, a revoked binding, and the visible “Ready when you are” state with End disabled. No manual End click was used. **New microphone audio interrupting the farewell after this latest fix is NOT TESTED live.** The earlier user-confirmed spoken hang-up is a separate PASS, not proof of this interruption edge case.

Finally, restarted only Hearth's main API and compared the complete saved draft, all three revision-history rows, and all three work orders with the pre-restart snapshot: identical. The running API returned revision 3. Reloading the user's Safari Hearth page visibly retained the exact after-4-PM access note, Saved revision 3, Ready for review, editable fields, Save changes, Approve work order, and Cancel draft. The draft was left unapproved. Current database: five drafts, fourteen history rows, three work orders. The latest voice test created no additional order.

Final automated checks: **141 backend/setup tests passed, 11 subtests passed; 28 frontend tests passed; TypeScript/Vite production build passed.** Live microphone denial, an unexpected connection drop with a saved draft, the post-save “All good” phrase, and the latest closing-interruption edge case remain NOT TESTED. Milestone 4 mobile layout was not newly inspected. Milestone 5 remains untouched.
