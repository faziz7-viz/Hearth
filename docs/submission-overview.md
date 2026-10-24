# Hearth — Landlord Repair Assistant

**Submission overview · Prepared October 24, 2026**

Hearth turns a landlord's spoken or typed repair request into a checked, editable draft. The landlord reviews the saved details and decides whether to approve a work order. The app uses real database checks and a live ElevenLabs conversation with clearly labelled fictional demo data.

This is Markdown prepared for a Google Doc. The results below come from the completed Milestone 5 verification. Code and documentation are published at [faziz7-viz/Hearth](https://github.com/faziz7-viz/Hearth); the Google Doc upload, video recording, and course submission remain pending.

## Problem and intended value

A landlord coordinating repairs needs to identify the right property and unit, check whether a job already exists, find an approved contractor, and collect access details. Hearth brings those steps into one workspace. The landlord is the intended buyer and daily user; tenants do not need a new app.

The intended benefit is less administrative effort and fewer missed details or duplicate requests. This project demonstrates the workflow; its evidence does not establish customer adoption, measured time savings, or willingness to pay. Those remain business assumptions to test. The approved scope is recorded in the [build plan](superpowers/plans/2026-10-22-landlord-repair-assistant.md).

## What the landlord does

1. **Describe the repair.** Start a voice or text conversation, or use the independent repair form. Loading an example fills structured inputs and checks saved records; it is not a simulated AI response.
2. **Resolve uncertainty.** Hearth asks which property is meant when “Unit 4” matches more than one. Unknown records, possible duplicates, missing contractor approval, and urgent safety concerns prevent routine approval.
3. **Prepare and correct the draft.** The assistant checks records and saves a draft. A spoken correction updates the same draft. The screen refreshes with the saved details and tool activity.
4. **Review the saved version.** End the conversation, inspect the repair card, and edit the issue, contractor, requested date, access notes, or contractor message. Save changes before approving.
5. **Approve or cancel.** Only the landlord's card control can approve. Approval saves the exact reviewed version as one work order. Cancelled drafts cannot be approved. Saved details remain after reload.

A contractor message is always an editable **draft**: nothing is sent. A **requested date** is not a confirmed booking, and Hearth does not check contractor availability. Spoken agreement, “All good,” or ending a call never approves a repair.

## Interface decisions

The existing Hearth interface uses a warm ivory background, dark text, and a restrained forest-green accent. On desktop, the request area sits beside the editable repair card, with saved orders and recent jobs below. On narrow screens these sections stack vertically.

Visible labels, saved-revision notices, database evidence, connection status, and disabled approval states explain what has happened and what needs attention. The “Demo data” label stays visible. Supporting text was darkened after an early contrast review, and keyboard focus indicators and reduced-motion styling are present. These choices support a calm, readable review process; they are not claims of a formal accessibility certification. Design history is in the [build log](build-log.md), with the implemented styles in [index.css](../frontend/src/index.css).

## Data and architecture

The fictional records cover Maple Court, Cedar House, and Willow Place; their units; approved contractors Ahmed, Lea, and Ben; jobs; maintenance history; and policies. Maple Court and Cedar House both have a Unit 4 to demonstrate ambiguity. Records seed once, and later saved drafts and orders remain in SQLite instead of being reset for demonstrations.

| Part | Role |
| --- | --- |
| React, TypeScript, Vite, Tailwind CSS | The browser workspace, repair card, conversation controls, and responsive styling. |
| Python and FastAPI | Validate requests, check business rules, save drafts, and handle human approval. |
| SQLite | Store fictional business records, sessions, draft revisions, and approved work-order snapshots. |
| ElevenLabs Agents | Conduct live voice or text conversations and select the four business tools. The build uses the current SDK integration recorded for the project, `@elevenlabs/react` 1.19.1, with `ConversationProvider`. |
| Separate authenticated tool gateway | Let ElevenLabs call the Python business functions through a temporary HTTPS tunnel. Approval routes stay outside this gateway. |

The browser talks to the local FastAPI app, which reads and writes SQLite. ElevenLabs reaches only the tool gateway. Private API credentials stay on the server; the browser receives temporary conversation access. The structured form remains usable independently of ElevenLabs. No LangChain or custom LangGraph workflow is used. See the [README](../README.md), [frontend dependencies](../frontend/package.json), and [gateway](../backend/app/voice_gateway.py).

The four real business tools are:

| Tool | What it does |
| --- | --- |
| `lookup_property` | Finds a property and unit; returns ambiguity or missing-record results instead of guessing. |
| `check_open_jobs` | Checks the matched unit, trade, and issue for a possible duplicate repair. |
| `lookup_maintenance_context` | Returns relevant history, policy, and approved contractors. |
| `prepare_repair_draft` | Creates or corrects the saved draft after backend validation. It cannot approve or dispatch work. |

ElevenLabs' native `end_call` is separate from these four business tools and only ends the conversation. The [agent instructions](elevenlabs-agent-prompt.md) require business facts to come from tools and technical failures to receive at most one explicitly requested retry.

## Keeping the right draft and approval

**App session:** The browser remembers a local session ID so the form, text conversation, voice conversation, and saved draft refer to the same workflow. Saved business state lives in SQLite. A new conversation receives the current draft; it does not assume earlier spoken history persists.

**Temporary conversation binding:** The backend links a provider-issued conversation ID to that app session and draft. Tool calls must pass a shared secret and a temporary, expiring binding token, stored as a hash. A model cannot choose an unrelated session. Ending a conversation revokes its binding. The app refreshes the final saved card before allowing review and approval.

**Draft revisions:** A draft keeps one ID while each save advances its revision. A correction supplies the expected revision. If another edit has made it stale, the backend rejects the overwrite or approval and requires review of the latest saved version.

**Human approval:** The agent has no approval tool. The backend blocks approval during an active conversation and rechecks required details, contractor eligibility, duplicates, and safety concerns. It saves the approved snapshot in one database transaction. Retry keys and unique constraints make repeated approval return the same order, rather than another order. Implementation is in [voice.py](../backend/app/voice.py) and [drafts.py](../backend/app/drafts.py).

## AI-assisted development and lessons

**Codex** was the AI coding assistant used for implementation, debugging, review, tests, and documentation. ElevenLabs is the application's conversation service. No other AI coding tool is claimed.

The build progressed through a local screen, database checks, saved drafts and approval, voice integration, and complete-workflow verification. These are exact excerpts from the user's milestone prompts in the project conversation, also recorded in the Milestone 6 entry of the [build log](build-log.md):

- **Milestone 1:** “Build a polished React web app using TypeScript, Vite, and Tailwind CSS.”
- **Milestone 3:** “Approval must save the exact revision the landlord reviewed. Reject outdated or cancelled drafts.”
- **Milestone 4:** “Keep approval exclusively in the existing review card. The voice agent cannot approve, send messages, or confirm bookings.”
- **Milestone 5:** “Report PASS, FAIL, or NOT TESTED, distinguishing live checks from simulated tests.”

The iteration summaries below paraphrase the recorded work:

| Observation | Change and lesson |
| --- | --- |
| Early approval could regenerate an unseen message. | Preserve the reviewed snapshot exactly. Approval must apply to what the person saw. |
| An ambiguous property result discarded local notes. | Preserve the local card while unresolved. Clarification should not erase useful input. |
| Urgent requests could reach routine lookups first. | Move human-review routing before those lookups and add regression cases. |
| Live tools failed despite healthy local services. | Provider evidence identified an expired tunnel hostname. Add a public gateway check before starting a call; test the whole connection path. |
| Long farewells were interrupted before disconnection. | Use a short farewell and protect only native `end_call` from interruption. Verify actual hang-up with the user. |
| Recovery text could remain after a successful refresh. | Add failing-then-passing lifecycle regressions. An accurate saved draft also needs an accurate status message. |

The main lesson was to separate a working simulation from a verified live interaction. Text success did not prove microphone behavior; an HTTP polling failure did not prove a disconnected voice call; and a correction in a resumed call did not prove correction during the same call.

## Verified results

The authoritative [Milestone 5 verification](milestone-5-verification.md) completed on October 24, 2026. These are recorded results, not newly rerun tests for this overview.

| Area | Evidence |
| --- | --- |
| Automated checks | **143 backend/setup tests plus 11 subtests passed; 33 frontend tests passed.** TypeScript and the Vite production build passed. A nonblocking SDK bundle-size warning remains. |
| Record checks | Live form/API checks passed ambiguity, unknown property, possible duplicate, no approved contractor, and urgent human review. |
| Same-call correction | Real speech created the hallway-skirting-board draft at revision 1 and corrected the same ID to revision 2 during one conversation. The visible notes became “After 2:00 p.m., please knock.” This draft remains unapproved. |
| Approval and reload | The separate wardrobe draft was created and corrected through real speech, using a resumed call for its correction. Revision 2 was reviewed and approved through Safari. A double-click and three API retries produced exactly one order with the exact reviewed snapshot, retained after reload. |
| Voice failures and ending | Real microphone denial showed fallback; a real Wi-Fi drop preserved the editable saved draft. “All good” ended the call. The user confirmed automatic disconnection despite speaking during the audible goodbye; transcript evidence alone does not establish that overlap. |
| Preservation | The final audit found no missing or changed pre-existing business rows. Final totals: **8 drafts, 22 history rows, 4 work orders, 7 jobs**, and zero active or unrevoked voice bindings. |

## Limits and next validation

- This is a local, single-landlord demonstration using fictional records, not a deployed multi-user service.
- The temporary HTTPS tunnel can expire. Voice needs working connectivity, ElevenLabs Agents access, and available credits; the independent form remains the fallback.
- Duplicate detection uses deterministic word matching and flags possible duplicates for review. It is not a semantic guarantee.
- Unsaved browser edits are temporary. Saved drafts and approved orders persist; new calls resume saved details rather than earlier spoken history.
- Layout passed desktop inspection and browser emulation at 390 × 844 and 320 × 844. **Physical-phone testing remains NOT TESTED.**
- Concurrency, revoked-contractor approval, and injected tool-failure cases use isolated real FastAPI/SQLite tests with simulated provider access. Microphone denial was tested in a session without a saved draft; saved-draft preservation for denial is covered by simulated lifecycle tests.
- The exact earlier Chrome HTTP-polling/offline recovery sequence was not repeated after its final text fix. Regression tests passed, and subsequent live Wi-Fi loss verified saved-draft recovery.
- Message sending, confirmed bookings, additional features, and measured business value remain outside the demonstrated scope. The Google Doc upload, recording, and course submission are still separate steps.

The next product validation would observe landlords completing real coordination tasks and measure effort and error rates. It should test the intended business benefit before claiming savings.
