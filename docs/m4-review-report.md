# Milestone 4 independent review — 2026-10-22

Reviewed the temporary conversation access service, four-route gateway, shared draft transaction helpers, browser controller and App integration, and setup scripts/templates. No live account changes or production database mutations were performed. Secret values were not inspected or printed.

## Findings resolved and rechecked

1. **P2 — stale controller cleanup can erase a newer call's recovery marker.** `frontend/src/voiceSession.ts:163` clears the remembered binding without checking ownership. React StrictMode runs a disposed restoration controller and a replacement controller. If the replacement restores and starts a new call before the old revocation completes, the old `remember(null)` removes the new marker. An isolated two-controller reproduction printed the new binding before releasing the old revoke, then `null` after releasing it. This removes reload/pagehide recovery for the newer active call. The frontend owner changed disposed controllers so they cannot write or clear the storage marker while still revoking their own binding. The two-controller regression now passes; rechecked the implementation and full frontend suite.

2. **P2 — transcript locality copy overstates privacy.** `frontend/src/components/VoicePanel.tsx:119` and `frontend/src/voiceSession.ts:169` say the transcript remains only in the current tab. The agent template configures provider retention and ElevenLabs stores conversation transcripts. The frontend owner removed both “only in this tab” claims; rechecked the rendered source strings. The setup owner is also checking explicit transcript deletion configuration. Source: [ElevenLabs retention documentation](https://elevenlabs.io/docs/eleven-agents/customization/privacy/retention).

No unresolved blocking implementation finding remains from this review.

## Verified boundaries

- The public gateway exposes exactly four authenticated POST tools, with docs and other business routes absent.
- Authorization requires the workspace secret, hashed opaque binding, matching pre-issued provider conversation ID, and an unexpired, unrevoked stored capability.
- Session capability is excluded from model-facing draft results and errors.
- Same-draft correction, exact revision, terminal status, and property grounding checks run under the same SQLite write transaction as mutation.
- Active voice capabilities prevent new work-order approval; no voice tool can approve or create a work order.
- Installed ElevenLabs React types and implementation confirm `startSession`/`endSession` return void and `onConnect` supplies `conversationId`; provider cleanup closes pending starts.
- Browser polls reject stale runs, preserve dirty draft edits, and keep approval blocked through revocation and final snapshot failure.
- Scripts keep credential values out of controlled CLI errors and use owner-only local configuration files.

## Validation

- `backend/.venv/bin/python -m pytest backend/tests/test_voice.py backend/tests/test_drafts.py scripts/test_elevenlabs_setup.py -q`: **89 passed, 4 subtests passed**.
- `npm test` in `frontend`: **27 passed** after the findings were fixed.
- Additional isolated Node reproduction confirmed finding 1 without network calls.

## Residual limitation

If the server commits `/api/voice/access` but the browser loses its response, the browser does not know the new `voice_session_id`. Form approval then fails closed until another successful Start/End cycle revokes that capability or its maximum ten-minute lifetime expires. This is a recovery limitation, not an authorization bypass.

Signed access against the live account, real microphone conversation, live webhook execution, and spoken correction acceptance remain **NOT TESTED** by this reviewer.
