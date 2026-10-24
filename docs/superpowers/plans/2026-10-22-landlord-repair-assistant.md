# Landlord Repair Assistant Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans when those skills are available. Implement one milestone at a time and demonstrate its result before starting the next. Do not install extra workflow tools solely to follow this plan.

**Goal:** Help a landlord turn a spoken repair request into a checked, editable work order that is saved only after approval.

**Architecture:** A React web app provides the call screen, a text fallback, an editable repair card, and approval controls. ElevenLabs Agents conducts the conversation and selects business tools. Those tools call a Python API directly to check records and prepare drafts. SQLite stores business records, drafts, and approved work orders.

**Tech stack:** React, TypeScript, Vite, Tailwind CSS, Python, FastAPI, SQLite, and the ElevenLabs React SDK. This version does not require LangChain or a custom LangGraph workflow.

**Spec:** The approved product idea is recorded in the Design brief section of this file. Put this file in the project as `docs/superpowers/plans/2026-10-22-landlord-repair-assistant.md`.

## How to use this plan

Milestone 5 verification is complete. Preserve the existing interface and saved records; Milestones 6 and 7 have not started. At each milestone, the agent must show what works, give one short test for the learner, and record changes in the build log. Use this revised plan in place of the earlier version that added LangChain.

The milestone sections retain the build plan; actual Milestone 5 results are linked below. The dates below are planning targets.

## Design brief

The landlord is the buyer and daily user. The application helps with repair coordination across properties. The tenant does not need to use a new app.

Example request:

> At Maple Court, unit 4 has a leaking kitchen tap. Check for an open job, find our approved plumber, and prepare the work order.

The agent finds the correct unit, checks existing jobs, reads maintenance history, and finds an approved contractor. It asks one focused question if essential information is missing. It produces a repair draft and contractor message for the landlord to edit.

The landlord can say, "Use Ahmed instead," or change the preferred date. These changes update the same draft. A preferred date is a request; it does not establish contractor availability or a booking.

The landlord reviews the exact draft and clicks Approve. The backend saves that revision as a work order. The contractor message remains a draft. Show "Approved — message ready to send"; do not claim it was sent or that a contractor confirmed attendance.

The proposed business benefit is less time spent collecting details and coordinating repairs. Test that benefit; do not invent measured savings or willingness to pay.

## Global constraints

- Build for a landlord. Use a React interface. Do not use Streamlit.
- Use ElevenLabs Agents with callable business tools in the completed project. The Python backend supplies the tools directly.
- Use ElevenLabs for a real browser voice conversation in the completed project.
- Use fictional records clearly labelled "Demo data."
- Keep API keys in server environment variables and out of frontend code, chat, and Git.
- Keep the first version to one landlord account and one repair workflow.
- Use text input as a fallback and for easier testing.
- Save an approved work order only through a separate approval endpoint.
- The agent cannot approve its own draft.
- Do not send contractor messages, transfer money, or claim a confirmed booking.
- Route urgent safety concerns to a person. Do not provide repair instructions.
- Use one shared session ID for text, voice, follow-up questions, and the current draft.
- Tell the learner whether a screen is using fixtures, live tools, or a live model.
- Check current official documentation before installing integrations; commit dependency lockfiles.

## Review focus

1. A spoken "unit 4" could match two properties. Ask which property before selecting one.
2. A landlord can edit the draft after the agent produces it. Save the reviewed revision exactly; reject stale approvals.
3. Repeated approval clicks or network retries must return the same work order, not create duplicates.
4. An open repair or unavailable contractor must change the proposed action. Do not silently create another job or invent an alternative.
5. Microphone denial, a lost connection, or a failed lookup must leave a clear next action and preserve the current draft.

## Data contract

Define these shapes before building the interface. Mirror them in TypeScript and Python.

- `RepairDraft`: `id`, `session_id`, integer `revision`, optional `property_id`, optional `unit_id`, `issue_summary`, optional `category`, optional `contractor_id`, optional `preferred_date`, `access_notes`, `contractor_message`, `missing_fields`, `evidence`, and `status`.
- `category`: `plumbing | electrical | general`, or null when not established.
- `status`: `needs_info | duplicate_found | needs_human | ready_for_review | approved | cancelled`.
- `evidence`: an array of objects containing `source_type`, `record_id`, and `summary`.
- `AgentTurnResult`: `session_id`, `reply`, optional `draft`, `events`, and optional `error_code`.
- `CheckRequestInput`: `session_id`, `property_query`, `unit_label`, `category`, and `issue_summary`. Milestone 2 sends these structured fields from the example fixture; it does not parse arbitrary natural language.
- `CheckRequestResult`: `status`, `property_choices`, optional `matched_unit`, `open_jobs`, `approved_contractors`, `evidence`, `events`, and optional `error_code`. Use `matched | unknown_property | ambiguous_property | duplicate_found | needs_human | error` for this check status.
- `events`: factual tool activity such as "Property found" or "Open job found." Do not expose hidden reasoning or fabricate completed checks.
- `WorkOrder`: `id`, `draft_id`, `approved_revision`, the reviewed draft snapshot, and `created_at`.

An empty preferred date is allowed. An unresolved property, unit, issue, contractor, duplicate, or safety concern prevents normal approval.

### Fictional fixtures

Create three properties: Maple Court, Cedar House, and Willow Place. Maple Court and Cedar House both contain a unit 4, so ambiguity can be demonstrated.

Use three fictional contractors with explicit trade and approved-property fields. Include Ahmed for plumbing, Lea for electrical work, and Ben for general repairs. Do not add real contact details.

Seed one open bathroom-tap repair at Cedar House unit 4. In a fresh seed, the kitchen-tap repair at Maple Court unit 4 has no existing open job. The current saved local database already contains an approved kitchen-tap order, so that request correctly returns a duplicate. M5 used a new Maple Court wardrobe repair for approval and a separate new hallway-skirting-board repair for same-call creation/correction, preserving existing records. Keep policy and repair history short.

## File structure

- `frontend/src/App.tsx`: the single workspace.
- `frontend/src/types.ts`: the shared frontend data contract.
- `frontend/src/demoData.ts`: explicit fixtures for the first screen.
- `frontend/src/components/TalkPanel.tsx`: text, microphone, connection status, and transcript.
- `frontend/src/components/RepairCard.tsx`: editable fields, evidence, and approval controls.
- `frontend/src/components/ActivityList.tsx`: tool results and job list.
- `frontend/src/api.ts`: typed backend calls.
- `backend/app/main.py`: HTTP endpoints.
- `backend/app/models.py`: validated request and response models.
- `backend/app/store.py`: SQLite access and approval transactions.
- `backend/app/tools.py`: record lookups and duplicate checks.
- `backend/app/workflow.py`: deterministic repair checks, draft validation, and tool result assembly.
- `docs/elevenlabs-agent-prompt.md`: the ElevenLabs agent's instructions and tool sequence.
- `backend/app/voice.py`: ElevenLabs session access and webhook adapter.
- `backend/data/seed.json`: fictional business records.
- `backend/tests/test_workflow.py`: meaningful workflow and approval tests.
- `docs/build-log.md`: actual coding prompts, iterations, and observations.
- `docs/demo-script.md`: the final demonstration outline.
- `README.md`, `.env.example`, and `.gitignore`: setup and environment guidance.

## Milestone 1 — Build the first screen

**Deliverable:** A working local React screen using explicit demo data.

**Interfaces:** Define `RepairDraft`, `AgentTurnResult`, and `WorkOrder` in `frontend/src/types.ts`. Build UI components around these shapes so later API wiring does not require a redesign.

- [x] Create the frontend and check the installed runtime before selecting dependency versions.
- [x] Add a calm, polished workspace: warm neutral background, dark text, one restrained accent colour, readable type, and clear spacing.
- [x] Put the request area on the left, editable repair card on the right, and recent jobs below. Stack these sections on small screens.
- [x] Add a labelled text box, "Load example", and a microphone control labelled "Voice not connected."
- [x] Make Load example populate the Maple Court fixture. Do not pretend the fixture was generated by an agent.
- [x] Allow the learner to edit the preferred date and access notes.
- [x] Provide explicit demo Approve and Cancel behaviour. Keep all effects local and visibly labelled as demo actions.
- [x] Show empty, loaded, needs-information, and cancelled states. Include useful focus states and keyboard navigation.
- [x] Run the frontend build and type checks. Inspect desktop and narrow-screen layouts; do not add tests that merely repeat static markup.
- [x] Add a build-log entry and provide the local preview URL.

**Learner check:** Load the example, change access notes, and see the change on the card. The microphone must not claim to be listening.

**Milestone 1 checkpoint:** the learner can load and edit a sample card. Do not rebuild this screen when continuing.

## Milestone 2 — Make record checks work

**Deliverable:** A Python API that returns real results from the fictional records.

**Interfaces:**
- `lookup_property(query: str) -> PropertyLookupResult`, including zero, one, or multiple matches.
- `check_open_jobs(unit_id: str, category: str, issue_summary: str) -> list[JobMatch]`.
- `lookup_maintenance_context(unit_id: str, category: str) -> MaintenanceContext`, including policy, history, and approved contractors.
- `POST /api/sessions` creates a session.
- `GET /api/sessions/{session_id}` returns the current draft and recent activity.
- `POST /api/repair-check` accepts `CheckRequestInput` and returns `CheckRequestResult`.

- [x] Mirror the TypeScript contract in validated Python models and load the seed records into SQLite.
- [x] Add meaningful tests: ambiguous unit 4 returns multiple choices; the Cedar House request finds its open job; an unsupported trade does not invent a contractor.
- [x] Implement the three read tools and HTTP routes.
- [x] Connect Load example to `POST /api/repair-check` using structured fixture fields. Display results returned by the backend in the existing interface.
- [x] Match property and unit IDs explicitly. Use the issue details when finding potential duplicate jobs; an unrelated open job is not automatically a duplicate.
- [x] Provide visible unknown-property, ambiguous-property, duplicate, and unavailable-backend states. Require selection when there are multiple property matches.
- [x] Keep this step read-only with respect to repair drafts, work orders, and contractor actions. Seed initialization and session records are allowed. Retain the disconnected microphone.
- [x] Retry a temporary read failure once, then return a clear structured failure.
- [x] Run `python -m pytest backend/tests/test_workflow.py -q` and verify the expected outcomes.
- [x] Document how to start the frontend and backend together.

**Learner check:** Inspect the Cedar House sample and see the existing job.

## Milestone 3 — Save reviewed drafts and approvals

**Deliverable:** The existing form can create and edit a checked draft, then save the exact approved revision as a work order. This milestone is a structured form workflow; natural conversation is added in Milestone 4.

**Interfaces:**
- `prepare_repair_draft(session_id: str, fields: DraftFields) -> RepairDraft`. `DraftFields` contains the editable business fields from `RepairDraft`; the backend owns IDs, revision, evidence, missing fields, and status.
- `POST /api/drafts` accepts `session_id` and `fields` and returns the checked draft.
- `PATCH /api/drafts/{draft_id}` accepts edited fields and `expected_revision`.
- `POST /api/drafts/{draft_id}/approve` accepts `expected_revision` and an `idempotency_key`.
- `POST /api/drafts/{draft_id}/cancel` prevents approval of that draft.
- `GET /api/work-orders` supplies the job list.

- [x] Implement the draft-preparation function using the record checks from Milestone 2. Generate evidence from actual tool results, not user-supplied claims.
- [x] Persist sessions, drafts, and approved jobs in SQLite. Store one current draft per repair workflow, retaining its ID across edits.
- [x] Return missing fields or review reasons as structured data. Use clear form errors before attempting approval.
- [x] Validate property, unit, category, and contractor IDs against saved records before presenting a draft as ready.
- [x] Keep the approval endpoint outside the agent tool list. Revalidate the edited revision and duplicate status before saving.
- [x] Save approval in a transaction with one work order per draft. Repeated approval returns the original order ID.
- [x] Reject stale or cancelled approvals. Editing a draft changes its revision and invalidates earlier approval attempts.
- [x] Add tests for exact edited content, stale revision rejection, repeated approval, cancellation, and an unknown contractor.
- [x] Connect the real API to the screen. Record actual tool results in the activity list.
- [x] Run the tests and complete one draft-to-approval flow through the existing screen. This milestone does not need a model API key.

**Learner check:** Load the example, select Ahmed, and add that the tenant is home after 3 pm. Approve the updated draft, reload the page, and verify exactly one saved job.

## Milestone 4 — Connect ElevenLabs voice

**Deliverable:** A real browser conversation using the same business logic and draft.

**Interfaces:** ElevenLabs calls four authenticated webhook tools: `lookup_property`, `check_open_jobs`, `lookup_maintenance_context`, and `prepare_repair_draft`. These use the existing Python functions directly. The browser reads draft changes from the same session through the existing session endpoint.

- [ ] Confirm the user's credit grant and account support ElevenLabs Agents. Do not assume a text-to-speech credit grant covers every product.
- [ ] Add the current ElevenLabs React SDK with a ConversationProvider, explicit Start/End controls, microphone permission handling, and live transcript events.
- [ ] Generate temporary conversation access on the backend. Keep private keys on the server.
- [ ] Configure the four business webhook tools. Keep work-order approval out of this tool list; preparing a draft does not approve or dispatch a repair.
- [ ] Write the ElevenLabs agent instructions: identify the property, ask one question for missing information, check open jobs, retrieve the relevant policy and approved contractor, and prepare the draft. Use tool results for all business facts.
- [ ] Require the agent to correct and update the existing draft when the landlord changes a detail. A stale draft or invalid contractor must produce a clarification instead of a fabricated result.
- [ ] Use ElevenLabs conversation context during the live session and SQLite for durable business state. On a new conversation, load the existing draft when resuming; do not assume spoken history survives a disconnected session.
- [ ] Connect free-text conversation through the same ElevenLabs agent in text mode when needed. The structured form from Milestone 3 remains available independently of voice.
- [ ] Bind each call to the app's existing session. Do not trust a model-invented session ID or accept an unrelated session.
- [ ] The webhook needs a reachable HTTPS backend. Configure a development tunnel or deployment for fictional demo data, with a server-validated shared secret. Verify connectivity early, before visual polish.
- [ ] Let the frontend poll its current session during an active call to refresh the draft and tool activity.
- [ ] Use bounded webhook timeouts, one retry for temporary read failures, and a finite conversation duration. On failure, state that the check could not finish and offer a retry or the existing form.
- [ ] Do not expose work-order approval as a voice tool. Approval stays on the reviewed card.
- [ ] Test a correction during the same call, microphone denial, and a disconnected call. The current saved draft must remain accessible.

**Learner check:** Speak the Maple Court example, answer a follow-up, change one detail, and approve the resulting card.

## Milestone 5 — Verify the complete workflow

**Deliverable:** A reliable demonstration with honest evidence.

- [x] Happy path: Maple Court request produces a grounded draft and one approved job.
- [x] Ambiguity: "unit 4" prompts for the property.
- [x] Duplicate: Cedar House tap request shows the existing job and does not silently create another.
- [x] Contractor failure: an unknown or unapproved contractor triggers clarification or human review.
- [x] Tool failure: one bounded retry, then a clear error and a usable draft or next action.
- [x] Human control: edit, reject, cancel, and repeated approval all behave correctly.
- [x] Voice continuity: text and voice changes use the same session and draft.
- [x] Unsupported urgency: stop the routine workflow and show human review.
- [x] Run backend tests and the frontend production build. Fix failures that affect this scope.
- [x] Check labels. A draft message must not appear as sent; a requested date must not appear as booked.

**Verified October 24, 2026:** [Actual Milestone 5 results](../../milestone-5-verification.md) distinguish live speech/browser/API checks from simulated-provider tests and retained M4 retry evidence. Same-call creation/correction and the separate wardrobe revision-2 approval, one-order retry, and reload checks passed; original records were preserved. Latest checks: 143 backend/setup tests and 11 subtests passed; 33 frontend tests and the production build passed. From the project root, `backend/.venv/bin/python -m pytest -q` includes the setup suite. Milestones 6 and 7 remain deferred.

Record actual pass/fail results. Do not invent results or time saved.

## Milestone 6 — Prepare the submission

**Deliverable:** GitHub repository, Google Doc, and a video of five minutes or less.

**Local submission package prepared October 24, 2026:** the [Google Doc source](../../submission-overview.md) and [4:30 recording script](../../demo-script.md) are ready. A local Git repository excludes secrets, databases, logs, and generated files. Creating/uploading the Google Doc, recording the video, selecting/publishing to GitHub, and course submission remain separate steps; this preparation does not mark those complete. Milestone 7 remains deferred.

- [x] Finish the README with setup commands, required keys, demo data, architecture, and current limitations.
- [ ] Prepare the Google Doc from the build log: overview, data, coding prompts, iterations, observations, and actual test results.
- [ ] Record a short live demonstration: landlord problem, voice request, visible record checks, edited approval, saved work order, and one failure case.
- [ ] Put the code in the user's chosen GitHub repository. Check that secrets and generated databases are excluded.
- [ ] Submit through the course form after the user reviews the final materials.

The handout gives Sunday, October 25, 2026 as the Builder of the Week deadline and does not state a cutoff time. Aim to finish and record on Saturday, October 24. The separate certification deadline is November 11.

Submission form: https://forms.gle/waBYFkkf5xxmcouV9

## Documentation for coding agents

These sources establish the library capabilities. The application design above is our implementation plan.

- Course LangChain and LangGraph examples: https://github.com/The-Gen-Academy/Mastering-Agentic-AI-Week3-Session1/blob/main/langgraph/README.md
- ElevenLabs Agents overview: https://elevenlabs.io/docs/eleven-agents/overview
- ElevenLabs React SDK: https://elevenlabs.io/docs/eleven-agents/libraries/react
- ElevenLabs webhook tools: https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools
- ElevenLabs authentication: https://elevenlabs.io/docs/eleven-agents/customization/authentication
- Assignment requirements: the user-supplied Copy of Week 3 Project Handout (Oct 2026).docx.
