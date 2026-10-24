# Milestone 3 frontend report

Implemented Task 2 against `docs/superpowers/plans/2026-10-22-milestone-3.md` on 2026-10-22.

## Workflow and decisions

- React keeps the editable card and last authoritative saved RepairDraft separately. Local cards use revision 0, clearly labelled unsaved; revisions are assigned only by the backend. Saving patches only changed editable business fields. Exact user whitespace and message content are preserved.
- Explicit **Save draft** creates the persisted draft. **Save changes** patches it and reruns real checks. A clean saved card can also be saved to refresh changed eligibility, duplicate, or safety records. Neither operation runs as part of approval.
- **Approve work order** requires the same draft/revision, no unsaved changes, ready status, no missing fields/review reasons, no unresolved conflict, and no operation in progress. The handler independently repeats the guard. A synchronous operation ref prevents duplicate clicks before React updates the buttons.
- Approval uses the deterministic key `hearth:<session>:<draft>:<revision>`, stable across network retries and reload. Approval responses add the returned immutable WorkOrder directly, then refresh authoritative activity.
- Contractor message is editable. An untouched new blank placeholder sends null on first save so the backend generates a grounded message once. Typing and then clearing sends the intentional empty string. Later saves never request regeneration. The API still uses preferred_date; the interface says **Requested date** and explains that it is not a booking.
- Cancel applies to a clean saved revision. Unsaved local cards can be explicitly discarded. Saved approved/cancelled workflows stay visible until **New request**. The request/example panel is locked while a saved workflow is open and explains how to finish it.
- The session ID is stored under localStorage key `hearth.session-id`; reload fetches the authoritative session/latest draft and work orders. No local fake business results are substituted on outage. Unsaved edits remain temporary browser state.
- A 409 conflict preserves the visible local card and blocks mutations. **Load latest saved draft** explicitly loads/reviews the current server version, keeping only intentionally changed fields in a separate recovery panel. Restoring is explicit; unrelated newer fields survive. Terminal versions retain the recovery text for copying. **New request** clears recovery.
- An approval_blocked response additionally requires an explicit save/recheck before another approval after loading latest, because the backend deliberately preserves the original saved snapshot when current records invalidate approval.
- Request-panel edits require a successful real check before the old local card can be saved. Editing the card synchronizes local lookup inputs; backend checks rerun on save. A failed local save retries the save instead of replacing edits with older check inputs.
- Rechecking the same property/unit preserves date, notes, and edited message. A different checked property/unit clears these location-specific details for an unsaved local card. Editing the location of a saved draft preserves all exact date/notes/message content, makes the form dirty, and requires saving and review. The location-change behavior has a regression test.
- Saved orders show expandable exact snapshot problem, notes, contractor message, date, IDs, approved revision, status at approval, and evidence. Recent jobs exclude IDs represented by saved orders, using the backend's shared job/order ID contract.
- Existing Hearth styling, real `/repair-check` examples, missing/ambiguous property choices, safety/duplicate results, and **Voice not connected** remain. No message sending, recording, model, or integration dependencies were added.

## Verification

- `npm test --prefix frontend`: **7 passed, 0 failed** (Node v25.9.0; native TypeScript Node test runner, available on recent Node releases).
- `npm run build --prefix frontend`: **passed**. Includes strict TypeScript `tsc --noEmit` and Vite production build (1573 transformed modules).
- Tests cover approval eligibility including wrong revisions and terminal states; stable/different retry keys; editable-field payload whitelist and exact strings; optional date/dirty normalization; intentional edit conflict recovery; location-specific local detail preservation/clearing; and preservation of deliberate saved date/notes/message during a saved draft location edit.
- Red/green was observed for missing helper behavior, the wrong-revision approval guard, and the location carryover regression. No static markup tests were added.
- No browser, server, or database was controlled or modified by the frontend implementer. Root owns the live browser workflow, backend restart checks, and integration review. These static/unit checks do not replace that live verification.
