import assert from 'node:assert/strict'
import test from 'node:test'
import { appendTranscript, mergeVoiceDraft, voiceApprovalReason, voiceStartReason, voiceDraftContext } from '../src/voiceState.ts'
import type { RepairDraft } from '../src/types.ts'

const saved: RepairDraft = { id: 'draft-1', session_id: 'session-1', revision: 3, property_id: 'p1', unit_id: 'u1', issue_summary: 'Leaking tap', category: 'plumbing', contractor_id: 'c1', preferred_date: null, access_notes: 'Knock first', contractor_message: 'Please inspect.', missing_fields: [], review_reasons: [], evidence: [], status: 'ready_for_review' }

test('voice cannot start over an unsaved card, dirty saved revision, or unresolved conflict', () => {
  assert.equal(voiceStartReason(null, null, false, false, 'idle'), null)
  assert.equal(voiceStartReason(saved, saved, false, false, 'idle'), null)
  assert.match(voiceStartReason({ ...saved, id: '', revision: 0 }, null, false, false, 'idle')!, /save|discard/i)
  assert.match(voiceStartReason({ ...saved, access_notes: 'Changed' }, saved, false, false, 'idle')!, /save|discard/i)
  assert.ok(voiceStartReason(saved, saved, false, true, 'idle'))
  assert.ok(voiceStartReason(saved, saved, true, false, 'idle'))
  assert.ok(voiceStartReason(saved, saved, false, false, 'sync_error'))
  assert.ok(voiceStartReason({ ...saved, status: 'cancelled' }, saved, false, false, 'idle'))
})

test('voice access binds active saved ID and revision, while a new request sends nulls', () => {
  assert.deepEqual(voiceDraftContext(saved), { draft_id: 'draft-1', expected_revision: 3 })
  assert.deepEqual(voiceDraftContext(null), { draft_id: null, expected_revision: null })
  assert.deepEqual(voiceDraftContext({ ...saved, status: 'approved' }), { draft_id: null, expected_revision: null })
})

test('polling accepts newer saved details but never overwrites unsaved edits or regresses a revision', () => {
  const newer = { ...saved, revision: 4, access_notes: 'After 3 pm' }
  assert.deepEqual(mergeVoiceDraft(saved, saved, newer), { draft: newer, saved: newer, changed: true, conflict: false })
  const edited = { ...saved, access_notes: 'My unsaved note' }
  assert.deepEqual(mergeVoiceDraft(edited, saved, newer), { draft: edited, saved, changed: false, conflict: true })
  assert.deepEqual(mergeVoiceDraft(newer, newer, saved), { draft: newer, saved: newer, changed: false, conflict: false })
  const local = { ...saved, id: '', revision: 0 }
  assert.deepEqual(mergeVoiceDraft(local, null, newer), { draft: local, saved: null, changed: false, conflict: true })
  assert.equal(mergeVoiceDraft(null, null, newer).draft, newer)
  assert.equal(mergeVoiceDraft(saved, saved, null).draft, saved)
})

test('approval stays blocked until the conversation ends and the final snapshot is loaded', () => {
  for (const phase of ['restoring', 'starting', 'connected', 'ending', 'syncing', 'sync_error'] as const) {
    assert.ok(voiceApprovalReason(phase))
  }
  assert.equal(voiceApprovalReason('idle'), null)
})

test('transcript corrections replace the matching turn and long sessions retain a bounded recent transcript', () => {
  let rows = appendTranscript([], { id: 'agent:1', role: 'agent', text: 'First version' })
  rows = appendTranscript(rows, { id: 'agent:1', role: 'agent', text: 'Corrected version' })
  assert.equal(rows.length, 1)
  assert.equal(rows[0].text, 'Corrected version')
  for (let i = 2; i <= 140; i++) rows = appendTranscript(rows, { id: `user:${i}`, role: 'user', text: `Message ${i}` })
  assert.equal(rows.length, 120)
  assert.equal(rows.at(-1)?.text, 'Message 140')
  assert.equal(appendTranscript(rows, { id: 'empty', role: 'agent', text: '  ' }).length, 120)
})

test('raw form input is preserved before a local card exists and prevents a conversation from replacing it', () => {
  assert.match(voiceStartReason(null, null, false, false, 'idle', true)!, /clear|save/i)
  assert.deepEqual(mergeVoiceDraft(null, null, saved, true), { draft: null, saved: null, changed: false, conflict: true })
})

test('polling a new request does not resurrect the previous completed card before the agent saves a new draft', () => {
  assert.deepEqual(mergeVoiceDraft(null, null, { ...saved, status: 'approved' }, false, 'draft-1'), { draft: null, saved: null, changed: false, conflict: false })
  assert.deepEqual(mergeVoiceDraft(null, null, { ...saved, status: 'cancelled' }, false, 'draft-1'), { draft: null, saved: null, changed: false, conflict: false })
})
