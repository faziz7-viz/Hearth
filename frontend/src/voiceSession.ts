import { ApiError } from './api.ts'
import type { HookOptions } from '@elevenlabs/react'
import { appendTranscript } from './voiceState.ts'
import type { TranscriptTurn, VoiceMode, VoicePhase } from './voiceState.ts'
import type { SessionResult, VoiceAccess } from './types.ts'

export interface VoiceBinding { session_id: string; voice_session_id: string }
export interface VoiceState {
  phase: VoicePhase
  mode: VoiceMode
  transcript: TranscriptTurn[]
  error: string | null
  notice: string | null
}
interface Dependencies {
  prepare: (mode: VoiceMode) => Promise<{ session_id: string; access: VoiceAccess }>
  bind: (sessionId: string, voiceId: string, conversationId: string) => Promise<unknown>
  revoke: (sessionId: string, voiceId: string) => Promise<unknown>
  snapshot: (sessionId: string) => Promise<SessionResult>
  startSdk: (options: HookOptions) => void
  endSdk: () => void
  remember: (binding: VoiceBinding | null) => void
  onSnapshot: (session: SessionResult) => void
  onChange: (state: VoiceState) => void
}
interface Run {
  binding: VoiceBinding | null
  stopping: boolean
  errorBeforeStop?: string | null
  pollError?: string
  preparation?: Promise<void>
  ending?: Promise<void>
  poll?: ReturnType<typeof setTimeout>
  deadline?: ReturnType<typeof setTimeout>
  startupDeadline?: ReturnType<typeof setTimeout>
}

// Owns request ordering independently of React renders. SDK and network operations are boundaries.
export class VoiceSession {
  state: VoiceState = { phase: 'restoring', mode: 'voice', transcript: [], error: null, notice: null }
  private deps: Dependencies
  private run: Run | null = null
  private disposed = false

  constructor(deps: Dependencies) { this.deps = deps }

  private publish(changes: Partial<VoiceState>) {
    this.state = { ...this.state, ...changes }
    if (!this.disposed) this.deps.onChange(this.state)
  }

  async restore(binding: VoiceBinding | null) {
    if (!binding) { this.publish({ phase: 'idle' }); return }
    this.run = { binding, stopping: false }
    this.publish({ notice: 'An interrupted conversation was found. Loading its saved card.' })
    await this.stop()
  }

  async start(mode: VoiceMode) {
    if (this.state.phase !== 'idle' || this.disposed) return
    const run: Run = { binding: null, stopping: false }
    this.run = run
    this.publish({ phase: 'starting', mode, transcript: [], error: null, notice: 'Connecting securely…' })
    run.preparation = (async () => {
      const { session_id, access } = await this.deps.prepare(mode)
      run.binding = { session_id, voice_session_id: access.voice_session_id }
      if (!this.disposed) this.deps.remember(run.binding)
      if (run.stopping || this.disposed) return
      const maximum = Math.min(600, Math.max(1, access.max_duration_seconds || 600))
      run.deadline = setTimeout(() => {
        this.publish({ notice: 'The conversation time limit was reached. Your saved card is being refreshed.' })
        void this.stop()
      }, maximum * 1000)
      run.startupDeadline = setTimeout(() => {
        this.publish({ error: 'The conversation took too long to connect. Try again or use the form.' })
        void this.stop()
      }, 30000)
      this.deps.startSdk({
        signedUrl: access.signed_url,
        connectionType: 'websocket',
        textOnly: mode === 'text',
        ...(mode === 'text' ? { overrides: { conversation: { textOnly: true } } } : {}),
        dynamicVariables: access.dynamic_variables,
        onConnect: ({ conversationId }) => { void this.connected(run, conversationId) },
        onDisconnect: (details) => {
          if (!this.isCurrent(run)) return
          this.publish(details.reason === 'error'
            ? { error: 'The conversation disconnected. Your saved draft is kept. Reconnect or continue with the form.' }
            : { notice: 'Conversation ended. Loading the latest saved card.' })
          void this.stop()
        },
        onError: (message, context) => {
          if (!this.isCurrent(run)) return
          const denied = /permission|notallowed|microphone|notfound|audio input/i.test(`${message} ${context instanceof Error ? context.name : ''}`)
          this.publish({ error: denied ? 'Microphone access is unavailable. Allow it in your browser and retry, or choose Text conversation. Your saved draft is kept.' : 'The conversation could not finish. Try again or use the form. Your saved draft is kept.' })
          void this.stop()
        },
        onMessage: (event) => {
          if (!this.isCurrent(run)) return
          this.publish({ transcript: appendTranscript(this.state.transcript, { id: `${event.role}:${event.response_id ?? event.event_id}`, role: event.role, text: event.message }) })
        },
        onAgentResponseCorrection: (event) => {
          if (!this.isCurrent(run)) return
          this.publish({ transcript: appendTranscript(this.state.transcript, { id: `agent:${event.response_id ?? event.event_id}`, role: 'agent', text: event.corrected_agent_response }) })
        },
        onAgentToolResponse: (event) => {
          if (!this.isCurrent(run)) return
          if (event.is_error || !event.is_called) this.publish({ error: 'A record check or draft update could not finish. Your saved card is kept. You can end the conversation and continue with the form. Check the saved card before approval.' })
        },
        onUnhandledClientToolCall: () => {
          if (this.isCurrent(run)) this.publish({ error: 'The assistant requested an unavailable tool. End the conversation and use the form; no approval was made.' })
        },
      })
    })()
    try { await run.preparation }
    catch (failure) {
      if (run.stopping) return
      this.publish({ error: failure instanceof ApiError ? failure.message : 'Unable to start the conversation. Check the backend voice setup and try again, or continue with the form.' })
      await this.stop()
    }
  }

  private isCurrent(run: Run) { return this.run === run && !run.stopping && !this.disposed }

  private async connected(run: Run, conversationId: string) {
    if (!this.isCurrent(run) || !run.binding) return
    try {
      await this.deps.bind(run.binding.session_id, run.binding.voice_session_id, conversationId)
      if (!this.isCurrent(run)) return
      clearTimeout(run.startupDeadline)
      this.publish({ phase: 'connected', notice: 'The assistant can check records and prepare this card. End the conversation to review it.' })
      void this.poll(run)
    } catch {
      if (!this.isCurrent(run)) return
      this.publish({ error: 'The conversation could not be linked to this workspace. It has been stopped. Your saved draft is kept.' })
      await this.stop()
    }
  }

  private async poll(run: Run) {
    if (!this.isCurrent(run) || !run.binding) return
    try {
      const snapshot = await this.deps.snapshot(run.binding.session_id)
      if (this.isCurrent(run)) this.deps.onSnapshot(snapshot)
    } catch {
      if (this.isCurrent(run)) {
        run.pollError = 'The saved card could not refresh. Retrying while connected. End the conversation before reviewing or editing.'
        if (!this.state.error || this.state.error === run.pollError) this.publish({ error: run.pollError })
      }
    }
    if (this.isCurrent(run)) run.poll = setTimeout(() => { void this.poll(run) }, 1500)
  }

  stop(): Promise<void> {
    const run = this.run
    if (!run) { this.publish({ phase: 'idle' }); return Promise.resolve() }
    if (run.ending) return run.ending
    if (!run.stopping) run.errorBeforeStop = this.state.error === run.pollError ? null : this.state.error
    run.stopping = true
    clearTimeout(run.poll); clearTimeout(run.deadline); clearTimeout(run.startupDeadline)
    this.publish({ phase: 'ending' })
    this.deps.endSdk()
    run.ending = (async () => {
      // Access may still be arriving when End is clicked; revoke it before final read.
      await run.preparation?.catch(() => {})
      try {
        if (run.binding) {
          await this.deps.revoke(run.binding.session_id, run.binding.voice_session_id)
          if (!this.disposed) this.deps.remember(null)
          this.publish({ phase: 'syncing' })
          const snapshot = await this.deps.snapshot(run.binding.session_id)
          if (!this.disposed) this.deps.onSnapshot(snapshot)
        }
        this.run = null
        this.publish({ phase: 'idle', error: run.errorBeforeStop ?? null, notice: 'Conversation ended. Review the saved card before approving.' })
      } catch {
        this.publish({ phase: 'sync_error', error: 'The conversation could not be fully closed or its latest saved card loaded. Retry ending and refreshing before approval. Your existing card is kept.' })
      } finally { run.ending = undefined }
    })()
    return run.ending
  }

  addText(text: string) {
    this.publish({ transcript: appendTranscript(this.state.transcript, { id: `typed:${Date.now()}:${this.state.transcript.length}`, role: 'user', text }) })
  }

  reportSendFailure() { this.publish({ error: 'Your message could not be sent. Try again, or end the conversation and use the form.' }) }

  dispose() {
    this.disposed = true
    void this.stop()
  }
}
