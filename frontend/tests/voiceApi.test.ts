import assert from 'node:assert/strict'
import test from 'node:test'
import { ApiError, createVoiceAccess } from '../src/api.ts'

test('voice setup errors preserve the controlled backend message and error code', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ error_code: 'voice_not_configured', message: 'Voice is not configured. Add the server settings first.' }), { status: 503, headers: { 'Content-Type': 'application/json' } }))
  await assert.rejects(createVoiceAccess('s1', 'text', { draft_id: null, expected_revision: null }), (failure: unknown) => {
    assert.ok(failure instanceof ApiError)
    assert.equal(failure.status, 503)
    assert.equal(failure.code, 'voice_not_configured')
    assert.equal(failure.message, 'Voice is not configured. Add the server settings first.')
    return true
  })
})
