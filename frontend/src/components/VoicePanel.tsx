import { useEffect, useRef, useState } from 'react'
import { useConversation } from '@elevenlabs/react'
import { Headphones, LoaderCircle, MessageSquareText, Mic, Send, Square } from 'lucide-react'
import { bindVoiceSession, endVoiceSession, getSession, getVoiceConfig } from '../api'
import { VoiceSession } from '../voiceSession'
import type { VoiceBinding, VoiceState } from '../voiceSession'
import type { VoiceMode, VoicePhase } from '../voiceState'
import type { SessionResult, VoiceAccess, VoiceConfig } from '../types'

const bindingKey = 'hearth.voice-binding'
function rememberedBinding(): VoiceBinding | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(bindingKey) ?? 'null')
    return typeof value?.session_id === 'string' && typeof value?.voice_session_id === 'string' ? value : null
  } catch { return null }
}
function rememberBinding(binding: VoiceBinding | null) {
  try {
    if (binding) sessionStorage.setItem(bindingKey, JSON.stringify(binding))
    else sessionStorage.removeItem(bindingKey)
  } catch { /* The backend still expires and checks every binding. */ }
}
interface VoicePanelProps {
  startReason: string | null
  events: string[]
  prepare: (mode: VoiceMode) => Promise<{ session_id: string; access: VoiceAccess }>
  onSnapshot: (session: SessionResult) => void
  onPhaseChange: (phase: VoicePhase) => void
}

export function VoicePanel(props: VoicePanelProps) {
  const conversation = useConversation()
  const latest = useRef({ props, conversation })
  latest.current = { props, conversation }
  const controller = useRef<VoiceSession | null>(null)
  const [state, setState] = useState<VoiceState>({ phase: 'restoring', mode: 'voice', transcript: [], error: null, notice: null })
  const [mode, setMode] = useState<VoiceMode>('voice')
  const [config, setConfig] = useState<VoiceConfig | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const transcript = useRef<HTMLDivElement>(null)

  async function loadConfig() {
    setConfigError(null)
    try { setConfig(await getVoiceConfig()) }
    catch { setConfigError('Voice setup could not be checked. Start the backend and retry. The repair form is still available.') }
  }

  useEffect(() => {
    const session = new VoiceSession({
      prepare: (nextMode) => latest.current.props.prepare(nextMode),
      bind: bindVoiceSession,
      revoke: endVoiceSession,
      snapshot: getSession,
      startSdk: (options) => latest.current.conversation.startSession(options),
      endSdk: () => latest.current.conversation.endSession(),
      remember: rememberBinding,
      onSnapshot: (value) => latest.current.props.onSnapshot(value),
      onChange: (value) => { setState(value); latest.current.props.onPhaseChange(value.phase) },
    })
    controller.current = session
    void session.restore(rememberedBinding())
    void loadConfig()
    const closeOnPageLeave = () => {
      const binding = rememberedBinding()
      if (binding) navigator.sendBeacon(`/api/voice/${encodeURIComponent(binding.voice_session_id)}/end`, new Blob([JSON.stringify({ session_id: binding.session_id })], { type: 'application/json' }))
    }
    window.addEventListener('pagehide', closeOnPageLeave)
    return () => { window.removeEventListener('pagehide', closeOnPageLeave); session.dispose() }
  }, [])

  useEffect(() => {
    const box = transcript.current
    if (box) box.scrollTop = box.scrollHeight
  }, [state.transcript])

  const running = state.phase === 'starting' || state.phase === 'connected'
  const working = ['restoring', 'ending', 'syncing'].includes(state.phase)
  const ready = state.phase === 'connected' && conversation.status === 'connected'
  const status = state.phase === 'connected'
    ? state.mode === 'text' ? 'Connected · Text conversation' : conversation.isSpeaking ? 'Connected · Speaking' : conversation.isListening ? 'Connected · Listening' : 'Connected'
    : state.phase === 'starting' ? 'Connecting…'
    : state.phase === 'ending' ? 'Ending conversation…'
    : state.phase === 'syncing' || state.phase === 'restoring' ? 'Loading saved card…'
    : state.phase === 'sync_error' ? 'Saved card needs a refresh'
    : config?.available ? 'Ready when you are' : config ? 'Voice setup needed' : 'Checking voice setup…'
  const sdkClosing = state.phase === 'idle' && (conversation.status === 'connecting' || conversation.status === 'connected')
  const disabled = !config?.available || Boolean(props.startReason) || state.phase !== 'idle' || sdkClosing

  function sendMessage() {
    const text = message.trim()
    if (!text || !ready) return
    try {
      conversation.sendUserMessage(text)
      controller.current?.addText(text)
      setMessage('')
    } catch { controller.current?.reportSendFailure() }
  }

  return (
    <section className="conversation-panel" aria-labelledby="conversation-heading">
      <div className="conversation-heading"><div className="conversation-icon"><Headphones size={20} aria-hidden="true" /></div><div><h3 id="conversation-heading">Talk it through.</h3><p>One assistant. The same repair card.</p></div></div>
      <div className={`conversation-status ${ready ? 'is-connected' : ''}`} role="status"><span className="status-dot" />{sdkClosing ? 'Closing audio connection…' : status}</div>
      <div className="conversation-modes" role="group" aria-label="Conversation mode">
        <button type="button" aria-pressed={mode === 'voice'} disabled={state.phase !== 'idle'} onClick={() => setMode('voice')}><Mic size={15} aria-hidden="true" /> Voice conversation</button>
        <button type="button" aria-pressed={mode === 'text'} disabled={state.phase !== 'idle'} onClick={() => setMode('text')}><MessageSquareText size={15} aria-hidden="true" /> Text conversation</button>
      </div>
      <div className="conversation-controls">
        <button type="button" className="primary-button" disabled={disabled} aria-describedby="conversation-help" onClick={() => { setMessage(''); void controller.current?.start(mode) }}>{state.phase === 'starting' ? <LoaderCircle size={16} className="animate-spin" aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />} Start {mode === 'voice' ? 'conversation' : 'text conversation'}</button>
        <button type="button" className="secondary-button" disabled={!running} onClick={() => void controller.current?.stop()}><Square size={13} aria-hidden="true" /> End</button>
      </div>
      <p id="conversation-help" className="field-help">{props.startReason ?? (mode === 'voice' ? 'Your microphone is used only after Start. The assistant checks saved records and prepares a draft.' : 'Chat with the same ElevenLabs assistant without microphone access.')}</p>
      {sdkClosing && <p className="field-help">Dismiss any open browser microphone prompt before starting again. You can use the repair form now.</p>}
      {config && !config.available && <p className="notice mt-4">{config.message} You can continue with the repair form below.</p>}
      {configError && <div className="notice mt-4" role="alert"><div><p>{configError}</p><button className="text-button mt-2" onClick={() => void loadConfig()}>Retry voice setup check</button></div></div>}
      {config && !config.available && <button className="text-button mt-2" onClick={() => void loadConfig()}>Check setup again</button>}
      {state.error && <p className="notice mt-4" role="alert">{state.error}</p>}
      {state.phase === 'sync_error' && <button type="button" className="secondary-button mt-3 w-full" onClick={() => void controller.current?.stop()}>Retry ending & refresh saved card</button>}
      {working && <p className="field-help" role="status">Please wait. The saved card stays protected until this step finishes.</p>}
      {state.notice && <p className="field-help">{state.notice}</p>}
      {(running || state.transcript.length > 0) && <div className="transcript-wrap"><div className="transcript-heading"><span>LIVE TRANSCRIPT</span><span>Recent 120 turns</span></div><div ref={transcript} className="transcript" role="log" aria-label="Conversation transcript" aria-live="polite" aria-relevant="additions text">{state.transcript.length ? state.transcript.map((turn) => <div key={turn.id} className={`transcript-turn turn-${turn.role}`}><strong>{turn.role === 'user' ? 'You' : 'Hearth assistant'}</strong><p>{turn.text}</p></div>) : <p className="transcript-empty">{state.mode === 'text' ? 'Type your repair request below once connected.' : 'Your conversation will appear here once connected.'}</p>}</div></div>}
      {state.mode === 'text' && running && <form className="conversation-composer" onSubmit={(event) => { event.preventDefault(); sendMessage() }}><label className="field-label" htmlFor="conversation-message">Message the assistant</label><div><input id="conversation-message" className="field" value={message} maxLength={2000} disabled={!ready} onChange={(event) => { setMessage(event.target.value); if (ready) conversation.sendUserActivity() }} placeholder="Describe the repair or change a detail…" /><button type="submit" className="primary-button" disabled={!ready || !message.trim()} aria-label="Send message"><Send size={17} aria-hidden="true" /></button></div></form>}
      {props.events.length > 0 && (running || state.transcript.length > 0) && <details className="conversation-events"><summary>Saved record activity</summary><ul>{props.events.slice(-8).map((event, index) => <li key={`${index}-${event}`}>{event}</li>)}</ul></details>}
      <p className="conversation-boundary">End the conversation, then review and approve on the card. No messages sent. Up to {Math.min(config?.max_duration_seconds ?? 600, 600) / 60} minutes per conversation.</p>
    </section>
  )
}
