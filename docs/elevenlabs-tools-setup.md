# Hearth Milestone 4: ElevenLabs setup

Follow **one step at a time**. The assistant should give the next step only after you
confirm the current one. Never paste an API key or webhook secret into chat.

## First action: confirm the account

Open [ElevenLabs Agents](https://elevenlabs.io/app/agents). Confirm that you can create
an agent and that your account has Agents call minutes/credits available. Check the
Agents allowance and any model costs in your account; a text-to-speech grant alone is
not evidence that an Agents call is covered. No subscription purchase is needed to
prepare Hearth's code. [Official Agents pricing](https://elevenlabs.io/pricing/agents)

Stop here until access and allowance are confirmed. The remaining sections are the
setup reference for the next guided actions.

## Subsequent guided actions

1. Create a **new blank agent dedicated to Hearth**. Choose an available voice and a
   model supporting tool calls in your account. Do not use an existing production agent.
2. Prepare local configuration from the project directory:
   `backend/.venv/bin/python scripts/elevenlabs_setup.py init`.
   This preserves existing values and generates a random webhook secret in `.env`.
3. Create an ElevenLabs API key with the Agents permissions needed to read/configure
   this agent, manage its tools/workspace secret, and issue conversation access.
   Enter it in your own terminal using:
   `backend/.venv/bin/python scripts/elevenlabs_setup.py set ELEVENLABS_API_KEY`.
   Input is hidden. The key is never written to frontend code.
4. Save the dedicated agent ID the same way:
   `backend/.venv/bin/python scripts/elevenlabs_setup.py set ELEVENLABS_AGENT_ID`.
5. Check API access without changing the account:
   `backend/.venv/bin/python scripts/elevenlabs_provision.py check-agent`.
   This does not verify credit eligibility; that remains the account-screen check.
6. Start the webhook gateway and HTTPS tunnel as described below. Save the tunnel
   origin locally with `scripts/elevenlabs_setup.py set HEARTH_VOICE_PUBLIC_URL` using
   the same Python command prefix. Restart the backend and gateway after config changes.
7. Review the configuration files below, then run the explicit provisioning command:

   ```sh
   backend/.venv/bin/python scripts/elevenlabs_provision.py provision --dedicated-agent-id YOUR_AGENT_ID
   ```

   `YOUR_AGENT_ID` is an ID, not an API key. It must match the locally saved agent ID.
   This uploads the shared secret from `.env`, creates or updates the four tools, and
   replaces the dedicated agent's prompt/tool settings. It keeps the agent's chosen
   voice and model. Its saved setup state allows retries to reuse previously created
   tools. No external configuration changes happen during `init`, `check`, or rendering.
8. Open Hearth at <http://127.0.0.1:5173/> and perform the live check below. Start
   conversations from Hearth, because the dashboard preview has no authorized app binding.

The local presence check is `backend/.venv/bin/python scripts/elevenlabs_setup.py check`.
It reports “configured” or “missing” and does not display values. Keep `.env` private.

## Gateway and tunnel

Run these in separate project terminals, or let the assistant start them after setup:

```sh
backend/.venv/bin/python -m uvicorn backend.app.voice_gateway:app --host 127.0.0.1 --port 8001
```

```sh
cloudflared tunnel --url http://127.0.0.1:8001
```

The public HTTPS address must point to **8001 only**. Port 8001 exposes four authenticated
tool routes. Keep the frontend on 5173 and the main API on 8000 local. Do not tunnel them.
The gateway rejects missing/incorrect authorization before reading tool request fields.
It has no public approval, session, work-order, Swagger, or OpenAPI routes.

A quick tunnel's hostname can change after restarting it. Update `HEARTH_VOICE_PUBLIC_URL`,
restart Hearth's backend/gateway, and rerun the same provision command to update tool URLs.
Do not delete the database or setup state.

If the agent reports that record calls cannot connect, a running `cloudflared` process
alone does not prove its temporary hostname still works. The first live test encountered
a DNS failure after the original tunnel had been left running overnight. Restart only
Hearth's tunnel, update the local URL, and reprovision the existing tools as above. API
keys and the agent ID do not need to be entered again.

Before starting a paid call, check through the public URL: an unauthenticated POST to
`/voice/tools/lookup_property` must return 401; `/api/work-orders` and `/docs` must return
404. These checks prove tunnel isolation, not a live agent conversation.

Hearth also checks the public lookup route automatically before requesting temporary
conversation access. If the tunnel cannot be reached or returns an unexpected response,
Start shows a clear connection error and leaves the form available. This check sends no
credentials and creates no conversation binding. It checks connectivity from this
computer; a real agent tool call is still needed to verify ElevenLabs' network path.

## Exact tool configuration

The machine-readable files are:

- `docs/elevenlabs-tools.template.json`: four `POST /v1/convai/tools` bodies. `tool_config`
  is the API envelope. Use the same body for `PATCH /v1/convai/tools/{tool_id}`.
- `docs/elevenlabs-agent.template.json`: dedicated-agent `PATCH /v1/convai/agents/{agent_id}`
  body, with only the four tool IDs attached.
- `docs/elevenlabs-agent-prompt.md`: the full agent system prompt.

All four repair tools use POST, JSON bodies, immediate execution, a 20-second timeout, visible
controlled tool errors, and no redirects or mocked responses. Tool calls are sequential.
The agent also enables ElevenLabs' native `end_call` system action. It disconnects the
conversation when the landlord asks to end, and after the single permitted retry fails.
It has no repair-writing or approval authority. The SDK's disconnect callback revokes
Hearth's binding and reloads the saved card. A farewell by itself is not sufficient.

| Tool | Gateway path | Required request fields |
| --- | --- | --- |
| `lookup_property` | `/voice/tools/lookup_property` | `query`, `unit_label` |
| `check_open_jobs` | `/voice/tools/check_open_jobs` | `unit_id`, `category`, `issue_summary` |
| `lookup_maintenance_context` | `/voice/tools/lookup_maintenance_context` | `unit_id`, `category` |
| `prepare_repair_draft` | `/voice/tools/prepare_repair_draft` | `draft_id`, `expected_revision`, `fields` |

Every tool has these exact header sources:

```json
{
  "X-Hearth-Webhook-Secret": {"secret_id": "YOUR_WORKSPACE_SECRET_ID"},
  "X-Hearth-Binding": {"variable_name": "secret__hearth_binding"},
  "X-ElevenLabs-Conversation-Id": {"variable_name": "system__conversation_id"}
}
```

`secret_id` references an ElevenLabs workspace secret; it is not the secret's value.
`variable_name` is the current header-reference field, distinct from a body parameter's
`dynamic_variable` field. The binding token is header-only and never included in the
prompt. The backend chooses its app session and validates expiry, revocation, and the
exact prebound ElevenLabs conversation ID. The model cannot supply a session ID.

A new draft uses `draft_id: null`, `expected_revision: 0`. Corrections use the last returned
draft ID/revision and only changed editable `fields`. Any stale, cancelled, or approved
draft is rejected. Missing details, eligible contractors, history, and duplicate matches
come from Hearth's SQLite records. The agent must uniquely look up a unit in the current
conversation before using it, including when resuming a saved draft.

The agent requires signed access and permits only the text-only conversation override.
ElevenLabs documents signed access and origin allowlists as alternative modes, so its
allowlist stays empty. Hearth's local access endpoint checks the browser origin/host.
Prompt/tool overrides are disabled. Calls are limited
to 600 seconds (or a smaller configured value), one concurrent conversation, and 20 daily
calls. No call recording is requested; transcript/PII deletion is explicitly enabled
with seven-day retention for new conversations. ElevenLabs processes the audio and
stores conversation transcripts under those settings. The
same agent supports the app's voice and text modes. The ordinary form works independently.
For technical read failures, the prompt allows one retry only after an explicit request.
If that retry fails, it offers the form and invokes `end_call`, including when the user
is silent. Unknown/ambiguous properties and stale revisions remain clarification cases.

To render reviewable JSON without contacting ElevenLabs:

```sh
backend/.venv/bin/python scripts/elevenlabs_config.py --public-url https://YOUR_GATEWAY_HOST --secret-id YOUR_WORKSPACE_SECRET_ID
```

Supply `--tool-ids` followed by the four returned IDs in the table's order to also render
`agent.patch.json`. Output defaults to `/tmp/hearth-elevenlabs-config`. No API key or
secret value is included in those JSON files. The provision helper fills the same
templates automatically and saves only setup IDs/fingerprint in
`backend/data/elevenlabs-setup.json` with private file permissions.

## Live check, after account setup

Use a repair that has **no existing open job**. The original Willow Place door-handle
example now has a saved work order in the verified local workspace. Use the fresh
candidate and preservation steps in [the demo script](demo-script.md), and recheck
the records before recording or repeating it.

1. Start voice and allow the microphone. Say that request. Answer any one-at-a-time
   clarification. Expect actual lookup, duplicate, and maintenance tool activity.
2. The review card should show the explicitly requested property/unit and returned approved contractor,
   and a saved draft ID/revision. It must not show a new work order.
3. Say: “Change the access notes to: the tenant is home after 4 pm.” Expect the **same
   draft ID**, a higher revision, and that exact correction on the visible card.
4. End voice. Review the card. Its Approve control remains the only way to approve;
   a spoken “approve it” must not create a work order or send the contractor message.
5. Reload to confirm the saved draft remains. Also test microphone denial and an
   interrupted call: the error should be clear and the saved form should still work.

Do not mark any of those as PASS from mocked calls or unit tests. Real microphone,
agent tool execution, visible update, and spoken correction must be verified separately.
The October 23 live sequence passed; see [actual results](milestone-4-verification.md).
Milestone 5 subsequently passed live microphone denial, unexpected disconnection,
same-call creation/correction, and the remaining checks; see [M5 evidence](milestone-5-verification.md).

The native end_call tool uses `interruption_mode: disable_during_tool_and_turn` and
`pre_tool_speech: off` so its short closing turn can finish. Business tools remain
interruptible. Post-fix text hang-up passed, and M5 later recorded automatic
disconnection with user-confirmed microphone speech overlapping the closing turn.

## Sources and offline validation

Configuration checked against the current [official OpenAPI schema](https://api.elevenlabs.io/openapi.json),
[Create/update tool API](https://elevenlabs.io/docs/api-reference/tools/create),
[Update agent API](https://elevenlabs.io/docs/api-reference/agents/update), and
[workspace secret API](https://elevenlabs.io/docs/api-reference/workspace/secrets/create).
All four rendered tool payloads and the agent PATCH passed JSON Schema validation on
2026-10-22. This validates schema shape, not account acceptance or live speech.

Header-only bindings follow [secret dynamic variables](https://elevenlabs.io/docs/eleven-agents/customization/personalization/dynamic-variables).
Signed access is configured according to [agent authentication](https://elevenlabs.io/docs/eleven-agents/customization/authentication).
Temporary access uses the [signed URL endpoint](https://elevenlabs.io/docs/api-reference/conversations/get-signed-url)
with `include_conversation_id=true`. The backend requires the returned prebound ID and
fails closed if it is missing. Never log a signed URL or binding token.

Run local setup/config tests with:

```sh
backend/.venv/bin/python -m unittest discover -s scripts -p 'test_elevenlabs_*.py' -v
```
