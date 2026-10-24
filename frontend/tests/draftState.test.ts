import assert from 'node:assert/strict'
import test from 'node:test'
import { approvalKey, approvalDisabledReason, draftFields, draftsDiffer, changedDraftFields } from '../src/draftState.ts'
import type { RepairDraft } from '../src/types.ts'

const saved: RepairDraft = {
  id: 'draft-1', session_id: 'session-1', revision: 3, property_id: 'p1', unit_id: 'u1',
  issue_summary: 'Leaking tap', category: 'plumbing', contractor_id: 'c1', preferred_date: null,
  access_notes: '  Knock first.\n', contractor_message: 'Please inspect the tap.\nThank you.',
  missing_fields: [], review_reasons: [], evidence: [{ source_type: 'property', record_id: 'p1', summary: 'Matched property' }],
  status: 'ready_for_review',
}

// These cases catch accidental approval of local/dirty/conflicted/busy/blocked cards.
test('only a clean ready persisted revision can be approved', () => {
  assert.equal(approvalDisabledReason(saved, saved, false, false), null)
  assert.match(approvalDisabledReason(saved, null, false, false)!, /save/i)
  assert.ok(approvalDisabledReason({ ...saved, revision: 2 }, saved, false, false))
  assert.ok(approvalDisabledReason({ ...saved, id: 'other-draft' }, saved, false, false))
  assert.match(approvalDisabledReason({ ...saved, contractor_message: 'changed' }, saved, false, false)!, /save/i)
  assert.match(approvalDisabledReason(saved, saved, true, false)!, /wait/i)
  assert.match(approvalDisabledReason(saved, saved, false, true)!, /latest/i)
  for (const status of ['cancelled', 'approved', 'needs_human', 'needs_info', 'duplicate_found'] as const) {
    assert.ok(approvalDisabledReason({ ...saved, status }, { ...saved, status }, false, false))
  }
  assert.ok(approvalDisabledReason({ ...saved, missing_fields: ['contractor_message'] }, { ...saved, missing_fields: ['contractor_message'] }, false, false))
  assert.ok(approvalDisabledReason({ ...saved, review_reasons: ['safety_concern'] }, { ...saved, review_reasons: ['safety_concern'] }, false, false))
})

test('approval retries use the same key, while another draft or revision cannot reuse it', () => {
  assert.equal(approvalKey(saved), approvalKey({ ...saved }))
  assert.notEqual(approvalKey(saved), approvalKey({ ...saved, revision: 4 }))
  assert.notEqual(approvalKey(saved), approvalKey({ ...saved, id: 'draft-2' }))
})

test('payload strips server-owned fields and preserves exact user strings', () => {
  assert.deepEqual(draftFields(saved), {
    property_id: 'p1', unit_id: 'u1', issue_summary: 'Leaking tap', category: 'plumbing',
    contractor_id: 'c1', preferred_date: null, access_notes: '  Knock first.\n',
    contractor_message: 'Please inspect the tap.\nThank you.',
  })
  assert.equal(draftFields({ ...saved, contractor_message: '' }).contractor_message, '')
})

test('dirty comparison normalizes an empty optional date but preserves whitespace edits', () => {
  assert.equal(draftsDiffer({ ...saved, preferred_date: '' }, saved), false)
  assert.equal(draftsDiffer({ ...saved, access_notes: 'Knock first.' }, saved), true)
  assert.equal(draftsDiffer({ ...saved, revision: 4, evidence: [] }, saved), false)
})

test('conflict recovery keeps only intentional edits so unrelated newer fields survive', () => {
  const local = { ...saved, contractor_message: '  My exact edited message\n', preferred_date: '2026-11-03' }
  const changes = changedDraftFields(saved, local)
  assert.deepEqual(changes, { preferred_date: '2026-11-03', contractor_message: '  My exact edited message\n' })
  const latest = { ...saved, revision: 4, access_notes: 'New server note' }
  const restored = { ...latest, ...changes }
  assert.equal(restored.access_notes, 'New server note')
  assert.equal(restored.contractor_message, '  My exact edited message\n')
  assert.ok(approvalDisabledReason(restored, latest, false, false))
})

test('local rechecks preserve notes and edited message only for the same property and unit', async () => {
  const { localDetailsForLocation } = await import('../src/draftState.ts')
  assert.deepEqual(localDetailsForLocation(saved, 'p1', 'u1'), {
    preferred_date: null, access_notes: '  Knock first.\n', contractor_message: 'Please inspect the tap.\nThank you.',
  })
  assert.deepEqual(localDetailsForLocation(saved, 'p2', 'u2'), {
    preferred_date: null, access_notes: '', contractor_message: '',
  })
  assert.deepEqual(localDetailsForLocation(saved, 'p2', 'u1'), {
    preferred_date: null, access_notes: '', contractor_message: '',
  })
})

test('saved draft location edits preserve exact requested date, notes, and custom message for review', async () => {
  const { editDraftFields } = await import('../src/draftState.ts')
  const current = { ...saved, preferred_date: '2026-11-03' }
  const moved = editDraftFields(current, saved, { property_id: 'p2', unit_id: 'u2' })
  assert.equal(moved.preferred_date, '2026-11-03')
  assert.equal(moved.access_notes, '  Knock first.\n')
  assert.equal(moved.contractor_message, 'Please inspect the tap.\nThank you.')
  assert.ok(approvalDisabledReason(moved, saved, false, false))
  assert.deepEqual(editDraftFields(current, null, { property_id: 'p2', unit_id: 'u2' }).access_notes, '')
})
