# Milestone 3 independent review

## Backend verdict

Reviewed the binding contract and Task 1 in `docs/superpowers/plans/2026-10-22-milestone-3.md`, `/tmp/hearth-m3-backend-review.diff`, current backend implementation, draft tests, affected M2 tests, and `docs/m3-backend-report.md`.

**Spec compliance: passes review. Code quality: acceptable. No actionable backend findings.** This verdict applies to the file hashes below, before frontend/integration review. The implementation keeps mutation boundaries explicit and centralizes assessment and revision/status guards without added dependencies.

- `backend/app/drafts.py:201` validates ownership and revision before retry resolution, rejects incompatible keys and cancellation, and rechecks current records under `BEGIN IMMEDIATE`. Order, matching job, key, history, and approved status commit together.
- `backend/app/drafts.py:229` saves the reviewed draft as the work-order snapshot, preserving its strings, evidence, revision, and review status. The current draft transitions separately to approved.
- `backend/app/drafts.py:170` merges only explicitly supplied editable fields and increments revision when content or derived review data changes. No-op saves preserve revision; later edits do not regenerate messages.
- `backend/app/drafts.py:146` handles active-create retry/conflict and terminal-to-new workflow behavior; `:189` makes cancellation terminal and repeated cancellation idempotent.
- `backend/app/store.py:44` adds workflow tables and uniqueness constraints. `:96` applies schema before the existing seed marker check, preserving seeded/custom records and sessions on migration.
- Test coverage includes six simultaneous approvals, distinct-draft duplicate races, rollback after injected insertion failure, stale/terminal conflicts, key conflicts, eligibility/relationship changes, exact snapshots, history, additive migration, and retained read-only check behavior.

## Independent verification

Command run: `PYTHONPATH=. backend/.venv/bin/python /tmp/hearth_m3_review_probe.py` — exit 0.

The isolated temporary-database probe verified:

1. A change to policy evidence followed by an empty PATCH earns a new revision; the old approval fails with `stale_revision`; approval of the refreshed draft preserves the exact saved snapshot.
2. Explicit null contractor-message PATCH is rejected with 422.
3. Ten concurrent approve/cancel races each produce exactly one successful terminal transition. Approved winners have exactly one saved order and cancellation conflicts; cancelled winners have no saved order and approval conflicts.

The implementer's report records 86 passing backend tests; this reviewer read their assertions and did not rerun the unchanged full suite. No live database, server, browser, or source code was modified during this review. Root owns actual process restart and UI integration evidence. Existing deterministic duplicate/safety matching remains bounded by the Milestone 2 rules; this review does not claim general natural-language classification.

## Reviewed snapshot (SHA-256)

| File | SHA-256 |
| --- | --- |
| backend/app/drafts.py | `6225f09773e1b4ffd09d4e52d1e080bbbbf5df7b609f515e14cf859b0b45ca54` |
| backend/app/models.py | `3f5b484d4ea451ec656eaac08bb3763697aacafe69794b9fa334f3a445f24b2c` |
| backend/app/store.py | `a1cab09c6aef53c9f46b1fa79a01275599d8bb94c42ebcd0c03fd1162b81514b` |
| backend/app/main.py | `0684a7e03b67cd93a1c7bceb6e8bfbebc4bfba92bd8d427d236143f85941209a` |
| backend/tests/test_drafts.py | `363fedc526bb99b19d1ccdf00505a9156bd1c92fee8349e778463b6bc99ba0fc` |
| backend/tests/test_workflow.py | `a667b70b46e1427711b90f6fb5f4b5f0789ddf0080d91ff858b1f6da4abcc30e` |
| /tmp/hearth-m3-backend-review.diff | `cbf95a4ae682927cc2babed6174684867c38f85460bafc5bc212673aeee368d6` |

## Frontend/integration verdict

**Spec compliance: passes review after two frontend fixes. Code quality: acceptable. No unresolved actionable findings in the reviewed final source.** The earlier `/tmp/hearth-m3-frontend-review.diff` predates the final fixes; final current-source hashes below define this verdict.

Reviewed `frontend/src`, `frontend/tests/draftState.test.ts`, the provided frontend diff, and `docs/m3-frontend-report.md` against the binding contract and the backend's actual request/response behavior.

Resolved findings:

1. **P2 — failed replacement example could save the previous local card.** Previously, loading another example replaced the request inputs without setting `requestEdited`, so a failed check retained the old card with Save enabled. Current `App.tsx:135` marks every started check as needing a successful match; only the matched response clears it. Verified the actual current `runCheck` and `save` handlers with a mocked failed check: old draft retained, pending flag true, and no create request emitted.
2. **P2 — saved location edits cleared unrelated explicit content.** Previously, the location-change branch cleared date, access notes, and message on a saved draft; Save would then persist that unintended deletion. Current `App.tsx:183` calls `editDraftFields`, which preserves those saved fields and limits location-specific clearing to unsaved local cards. A focused regression test verifies exact strings/date are retained and approval remains blocked until saving.

Review evidence:

- Approval guards are repeated in the UI and handler; payload uses the separate last saved snapshot and stable draft/revision key. Approval performs no implicit save. Dirty, busy, conflicted, unpersisted, mismatched-revision, terminal, and blocked cards cannot be approved.
- Partial save payloads whitelist all eight editable fields and preserve strings. First-save generated message uses null only while the placeholder remains untouched; intentional empty text remains empty.
- Conflicts retain visible edits. Explicit latest-version loading puts only intentional changed fields into recovery; restore is explicit, and approval-blocked errors require a save/recheck after loading. Server conflicts remain authoritative if another tab changes data again.
- Request/example controls are locked while an active saved draft is open. Cancel/approved cards remain until explicit New request. LocalStorage retains the session ID; reload reads the authoritative latest draft and saved orders.
- Work-order details come from `order.snapshot`, include IDs/revision/evidence and exact message/text whitespace, and jobs deduplicate using the shared order/job ID. Requested date and disconnected voice/no-send wording remain clear.
- API route names, editable fields, null-message creation, strict revision requests, structured conflicts, work-order schema, and shared job IDs match the reviewed backend.

Independent commands run after the fixes:

- `node --test --test-name-pattern='saved draft location edits' frontend/tests/draftState.test.ts` — **1 passed, 0 failed**, exit 0.
- `node /tmp/hearth_m3_frontend_probe.mjs` — **passed**, exit 0. This temporary probe extracts the current actual runCheck/save function bodies, strips TypeScript, and executes them with isolated mock state/network responses; no browser/server/DB actions.

The frontend implementer's report records seven passing tests and a passing TypeScript/Vite build. This reviewer did not repeat the unchanged full suite/build. Root separately owns live UI, outage, browser reload, and actual server restart verification; this static/isolated review does not substitute for those checks.

## Final frontend snapshot (SHA-256)

| File | SHA-256 |
| --- | --- |

| frontend/src/App.tsx | `dbbe4939bffa155e89758d825f0c71d76291fd095c7c0969b1a3ec3dbd1197ee` |
| frontend/src/draftState.ts | `4db938845688d2dbe876f0f7d59942bd2b9d34abfdad9796c609e141e8112b98` |
| frontend/src/api.ts | `e8ae96198ae6c5799af66f14b882e628e65892e7d0b2df77ab3f58cda3ead934` |
| frontend/src/types.ts | `b892a9be8f10fb0a324c803305915efa1c7e6ab68a02356e48599e51153841f2` |
| frontend/src/components/RepairCard.tsx | `7034c81277cd6766dd8402242c72aae99a7daeece5a84385b7568497ce410951` |
| frontend/src/components/ActivityList.tsx | `43c1d11977069f969b34207412bd66e95b72826e6b09b6e7fc895756474f6968` |
| frontend/src/components/TalkPanel.tsx | `2a7c05b9b245e88f30c7b1be5bab873b43940c8dd09002876a94d17dd9bbd688` |
| frontend/src/components/CheckResults.tsx | `624e35b2e06aab36e51999f8bfe3f1141eb542c7bb557d60682023d44c5db8a6` |
| frontend/src/index.css | `cb220bd16cd568d15419e58043169def30ca6915e427dc82abc4d93f9c79e909` |
| frontend/tests/draftState.test.ts | `e31ea6a039b9c979ee800f138f7fee27b757c6afdab2084750bbc5acecd17e94` |
| /tmp/hearth-m3-frontend-review.diff | `acb86d76bf4a8fc0b4a865f237fd1952e9b64403b47e7ac8426d6b17e4d14f14` |
