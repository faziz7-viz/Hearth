import assert from 'node:assert/strict'
import test from 'node:test'
import { VoiceSession } from '../src/voiceSession.ts'
import type { HookOptions } from '@elevenlabs/react'
import type { VoiceAccess, SessionResult } from '../src/types.ts'

const access: VoiceAccess = { voice_session_id: 'v1', signed_url: 'wss://example.invalid/signed', expires_at: '2026-11-01T00:00:00Z', max_duration_seconds: 600, dynamic_variables: { secret__hearth_binding: 'opaque', hearth_context: 'Grounded context' } }
const snapshot: SessionResult = { session_id: 's1', draft: null, events: ['Checked property'], recent_jobs: [], properties: [], contractors: [] }
const tick = () => new Promise<void>((resolve) => setImmediate(resolve))
function setup(overrides: Record<string, unknown> = {}) {
  const calls: string[] = []
  let sdk: HookOptions | undefined
  let stored: { session_id: string; voice_session_id: string } | null = null
  let latest: SessionResult | null = null
  const controller = new VoiceSession({
    prepare: async () => ({ session_id: 's1', access }),
    bind: async (_session: string, _voice: string, conversation: string) => { calls.push(`bind:${conversation}`) },
    revoke: async () => { calls.push('revoke') },
    snapshot: async () => { calls.push('snapshot'); return snapshot },
    startSdk: (options: HookOptions) => { sdk = options },
    endSdk: () => { calls.push('end-sdk') },
    remember: (binding: typeof stored) => { stored = binding },
    onSnapshot: (value: SessionResult) => { latest = value },
    onChange: () => {},
    ...overrides,
  })
  return { controller, calls, sdk: () => sdk!, stored: () => stored, latest: () => latest }
}

test('text fallback uses private WebSocket access without a microphone and binds the SDK conversation ID', async () => {
  const f = setup()
  await f.controller.restore(null)
  await f.controller.start('text')
  assert.equal(f.controller.state.phase, 'starting')
  assert.equal(f.sdk().signedUrl, access.signed_url)
  assert.equal(f.sdk().connectionType, 'websocket')
  assert.equal(f.sdk().textOnly, true)
  assert.deepEqual(f.sdk().overrides, { conversation: { textOnly: true } })
  assert.deepEqual(f.stored(), { session_id: 's1', voice_session_id: 'v1' })
  f.sdk().onConnect?.({ conversationId: 'real-sdk-id' })
  await tick()
  assert.equal(f.controller.state.phase, 'connected')
  assert.ok(f.calls.includes('bind:real-sdk-id'))
  await f.controller.stop()
  assert.equal(f.controller.state.phase, 'idle')
  assert.equal(f.stored(), null)
})

test('microphone denial ends and revokes access, keeps a clear error, and refreshes the saved card', async () => {
  const f = setup()
  await f.controller.restore(null)
  await f.controller.start('voice')
  f.sdk().onError?.('Permission denied', new DOMException('Permission denied', 'NotAllowedError'))
  await tick()
  assert.equal(f.controller.state.phase, 'idle')
  assert.match(f.controller.state.error!, /microphone/i)
  assert.ok(f.calls.includes('revoke'))
  assert.equal(f.latest(), snapshot)
})

test('ending while access is pending revokes the eventual binding and never starts the SDK', async () => {
  let release!: (value: { session_id: string; access: VoiceAccess }) => void
  const pending = new Promise<{ session_id: string; access: VoiceAccess }>((resolve) => { release = resolve })
  const f = setup({ prepare: () => pending })
  await f.controller.restore(null)
  const starting = f.controller.start('voice')
  const stopping = f.controller.stop()
  release({ session_id: 's1', access })
  await Promise.all([starting, stopping])
  assert.equal(f.sdk(), undefined)
  assert.ok(f.calls.includes('revoke'))
  assert.equal(f.controller.state.phase, 'idle')
})

test('reload recovery revokes the remembered binding before publishing an approval-ready phase', async () => {
  const f = setup()
  assert.equal(f.controller.state.phase, 'restoring')
  await f.controller.restore({ session_id: 's1', voice_session_id: 'old-call' })
  assert.deepEqual(f.calls, ['end-sdk', 'revoke', 'snapshot'])
  assert.equal(f.controller.state.phase, 'idle')
  assert.equal(f.latest(), snapshot)
})

test('failed revocation blocks approval until a successful retry and final snapshot', async () => {
  let failure = true
  const f = setup({ revoke: async () => { if (failure) throw new Error('Offline') } })
  await f.controller.restore({ session_id: 's1', voice_session_id: 'old-call' })
  assert.equal(f.controller.state.phase, 'sync_error')
  assert.match(f.controller.state.error!, /retry/i)
  assert.equal(f.latest(), null)
  failure = false
  await f.controller.stop()
  assert.equal(f.controller.state.phase, 'idle')
  assert.equal(f.controller.state.error, null)
  assert.equal(f.latest(), snapshot)
})

for (const failure of ['microphone', 'disconnect'] as const) {
  test(`successful close recovery restores the ${failure} explanation and saved draft`, async () => {
    let offline = true
    const savedSnapshot: SessionResult = {
      ...snapshot,
      draft: { id: 'saved-draft', session_id: 's1', revision: 3, property_id: 'p1', unit_id: 'u1', issue_summary: 'Loose curtain rail', category: 'general', contractor_id: 'c1', preferred_date: null, access_notes: 'After 4 pm. Please knock.', contractor_message: 'Please inspect the curtain rail.', missing_fields: [], review_reasons: [], evidence: [], status: 'ready_for_review' },
    }
    const f = setup({
      revoke: async () => { if (offline) throw new Error('Offline') },
      snapshot: async () => savedSnapshot,
    })
    await f.controller.restore(null)
    await f.controller.start('voice')
    if (failure === 'microphone') {
      f.sdk().onError?.('Permission denied', new DOMException('Permission denied', 'NotAllowedError'))
    } else {
      f.sdk().onConnect?.({ conversationId: 'real-id' })
      await tick()
      f.sdk().onDisconnect?.({ reason: 'error', message: 'Connection lost', context: { type: 'close' } })
    }
    await tick()
    assert.equal(f.controller.state.phase, 'sync_error')
    await f.controller.stop()
    assert.equal(f.controller.state.phase, 'sync_error')
    offline = false
    await f.controller.stop()
    assert.equal(f.controller.state.phase, 'idle')
    assert.match(f.controller.state.error!, failure === 'microphone' ? /microphone/i : /disconnected/i)
    assert.match(f.controller.state.error!, /saved draft is kept/i)
    assert.doesNotMatch(f.controller.state.error!, /retry ending/i)
    assert.equal(f.latest()?.draft?.id, 'saved-draft')
    assert.equal(f.latest()?.draft?.revision, 3)
    assert.equal(f.latest()?.draft?.access_notes, 'After 4 pm. Please knock.')
  })
}

for (const toolFailure of ['none', 'before-poll', 'after-poll'] as const) {
  const name = toolFailure === 'none' ? 'successful close recovery clears a resolved polling error and keeps the saved revision' : `a tool failure ${toolFailure === 'before-poll' ? 'before' : 'after'} a polling error survives successful close recovery`
  test(name, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] })
    let offline = false
    const savedSnapshot: SessionResult = {
      ...snapshot,
      draft: { id: 'saved-draft', session_id: 's1', revision: 2, property_id: 'p1', unit_id: 'u1', issue_summary: 'Loose curtain rail', category: 'general', contractor_id: 'c1', preferred_date: null, access_notes: 'After 4 pm. Please knock.', contractor_message: 'Please inspect the curtain rail.', missing_fields: [], review_reasons: [], evidence: [], status: 'ready_for_review' },
    }
    const f = setup({
      revoke: async () => { if (offline) throw new Error('Offline') },
      snapshot: async () => { if (offline) throw new Error('Offline'); return savedSnapshot },
    })
    await f.controller.restore(null)
    await f.controller.start('text')
    f.sdk().onConnect?.({ conversationId: 'real-id' })
    await tick()
    assert.equal(f.latest()?.draft?.revision, 2)
    if (toolFailure === 'before-poll') f.sdk().onAgentToolResponse?.({ tool_name: 'prepare_repair_draft', tool_call_id: 'tc1', tool_type: 'webhook', is_error: true, is_called: true, event_id: 1 })
    offline = true
    t.mock.timers.tick(1500)
    await tick()
    assert.equal(f.controller.state.phase, 'connected')
    if (toolFailure !== 'before-poll') assert.match(f.controller.state.error!, /saved card could not refresh/i)
    if (toolFailure === 'after-poll') f.sdk().onAgentToolResponse?.({ tool_name: 'prepare_repair_draft', tool_call_id: 'tc1', tool_type: 'webhook', is_error: true, is_called: true, event_id: 1 })
    await f.controller.stop()
    assert.equal(f.controller.state.phase, 'sync_error')
    offline = false
    await f.controller.stop()
    assert.equal(f.controller.state.phase, 'idle')
    if (toolFailure !== 'none') assert.match(f.controller.state.error!, /record check or draft update could not finish/i)
    else assert.equal(f.controller.state.error, null)
    assert.equal(f.latest()?.draft?.id, 'saved-draft')
    assert.equal(f.latest()?.draft?.revision, 2)
    assert.equal(f.latest()?.draft?.access_notes, 'After 4 pm. Please knock.')
  })
}

test('a delayed active poll cannot replace the final snapshot after ending', async () => {
  let release!: (value: SessionResult) => void
  let reads = 0
  const f = setup({ snapshot: async () => { reads++; return reads === 1 ? new Promise<SessionResult>((resolve) => { release = resolve }) : snapshot } })
  await f.controller.restore(null)
  await f.controller.start('voice')
  f.sdk().onConnect?.({ conversationId: 'real-id' })
  await tick()
  await f.controller.stop()
  release({ ...snapshot, events: ['Stale poll'] })
  await tick()
  assert.deepEqual(f.latest()?.events, ['Checked property'])
  assert.equal(f.controller.state.phase, 'idle')
})

test('a failed business tool is surfaced without inventing success or discarding the saved card', async (t) => {
  const f = setup()
  t.after(() => f.controller.stop())
  await f.controller.restore(null)
  await f.controller.start('text')
  f.sdk().onAgentToolResponse?.({ tool_name: 'prepare_repair_draft', tool_call_id: 'tc1', tool_type: 'webhook', is_error: true, is_called: true, event_id: 1 })
  assert.match(f.controller.state.error!, /could not finish/i)
  assert.doesNotMatch(f.controller.state.error!, /ask.*retry/i)
  assert.match(f.controller.state.error!, /saved card.*kept/i)
  await f.controller.stop()
})

test('the native agent end-call disconnect revokes access once and refreshes the saved card', async () => {
  const f = setup()
  await f.controller.restore(null)
  await f.controller.start('voice')
  f.sdk().onConnect?.({ conversationId: 'real-id' })
  await tick()
  f.sdk().onDisconnect?.({ reason: 'agent', context: { type: 'end_call', reason: 'User asked to end the conversation' } })
  await tick()
  assert.equal(f.controller.state.phase, 'idle')
  assert.equal(f.controller.state.error, null)
  assert.equal(f.stored(), null)
  assert.equal(f.calls.filter((call) => call === 'revoke').length, 1)
  assert.equal(f.latest(), snapshot)
})

test('a failed bind stops the SDK, revokes the binding, and never starts active polling', async () => {
  const f = setup({ bind: async () => { throw new Error('Wrong conversation') } })
  await f.controller.restore(null)
  await f.controller.start('voice')
  f.sdk().onConnect?.({ conversationId: 'rejected-id' })
  await tick()
  assert.deepEqual(f.calls, ['end-sdk', 'revoke', 'snapshot'])
  assert.equal(f.controller.state.phase, 'idle')
  assert.match(f.controller.state.error!, /linked/i)
})

test('a disconnect refreshes the saved card and ignores later transcript callbacks from that call', async () => {
  const f = setup()
  await f.controller.restore(null)
  await f.controller.start('voice')
  f.sdk().onConnect?.({ conversationId: 'real-id' })
  await tick()
  f.sdk().onMessage?.({ source: 'user', role: 'user', message: 'The tap is leaking.', event_id: 1 })
  f.sdk().onDisconnect?.({ reason: 'error', message: 'private provider context', context: { type: 'close' } })
  await tick()
  f.sdk().onMessage?.({ source: 'ai', role: 'agent', message: 'Stale message', event_id: 2 })
  assert.equal(f.controller.state.phase, 'idle')
  assert.equal(f.controller.state.transcript.length, 1)
  assert.match(f.controller.state.error!, /disconnected/i)
  assert.doesNotMatch(f.controller.state.error!, /private provider context/)
  assert.equal(f.latest(), snapshot)
})

test('a final read failure keeps approval blocked even after successful revocation', async () => {
  let failing = true
  const f = setup({ snapshot: async () => { if (failing) throw new Error('Offline'); return snapshot } })
  await f.controller.restore({ session_id: 's1', voice_session_id: 'old-call' })
  assert.equal(f.controller.state.phase, 'sync_error')
  assert.equal(f.latest(), null)
  failing = false
  await f.controller.stop()
  assert.equal(f.controller.state.phase, 'idle')
  assert.equal(f.controller.state.error, null)
  assert.equal(f.latest(), snapshot)
})

test('the conversation stops at its finite duration and revokes access', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = setup({ prepare: async () => ({ session_id: 's1', access: { ...access, max_duration_seconds: 2 } }) })
  await f.controller.restore(null)
  await f.controller.start('text')
  f.sdk().onConnect?.({ conversationId: 'real-id' })
  await tick()
  t.mock.timers.tick(2000)
  await tick()
  assert.equal(f.controller.state.phase, 'idle')
  assert.ok(f.calls.includes('revoke'))
})

test('a disposed reload recovery cannot erase the next conversation’s remembered binding', async () => {
  let release!: () => void
  let stored: { session_id: string; voice_session_id: string } | null = { session_id: 's1', voice_session_id: 'old-call' }
  const remember = (binding: typeof stored) => { stored = binding }
  const old = setup({ remember, revoke: () => new Promise<void>((resolve) => { release = resolve }) })
  const restoring = old.controller.restore(stored)
  await tick()
  old.controller.dispose()
  const current = setup({ remember })
  await current.controller.restore(stored)
  await current.controller.start('text')
  release()
  await restoring
  const rememberedAfterOldRecovery = stored
  await current.controller.stop()
  assert.deepEqual(rememberedAfterOldRecovery, { session_id: 's1', voice_session_id: 'v1' })
})
