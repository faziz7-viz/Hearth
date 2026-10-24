import { useEffect, useRef, useState } from 'react'
import { Building2, House, Leaf } from 'lucide-react'
import { TalkPanel } from './components/TalkPanel'
import { VoicePanel } from './components/VoicePanel'
import { RepairCard } from './components/RepairCard'
import { ActivityList } from './components/ActivityList'
import { ApiError, approveDraft, cancelDraft, checkRepair, createDraft, createSession, createVoiceAccess, getSession, getWorkOrders, updateDraft } from './api'
import { approvalDisabledReason, approvalKey, changedDraftFields, draftFields, draftsDiffer, editDraftFields, localDetailsForLocation } from './draftState'
import { checkExamples, emptyCheckFields } from './demoData'
import { mergeVoiceDraft, voiceApprovalReason, voiceDraftContext, voiceLocksForm, voiceStartReason } from './voiceState'
import type { VoiceMode, VoicePhase } from './voiceState'
import type { CheckFields, CheckRequestResult, DraftFields, RepairCategory, RepairDraft, SessionResult, WorkOrder } from './types'

const sessionStorageKey = 'hearth.session-id'
function rememberedSession() {
  try { return localStorage.getItem(sessionStorageKey) } catch { return null }
}
function rememberSession(id: string) {
  try { localStorage.setItem(sessionStorageKey, id) } catch { /* The current session still works if browser storage is disabled. */ }
}
function queryForDraft(draft: RepairDraft, session: SessionResult): CheckFields {
  const property = session.properties.find((item) => item.id === draft.property_id)
  return { property_query: draft.property_id ?? '', unit_label: property?.units.find((item) => item.id === draft.unit_id)?.label ?? '', issue_summary: draft.issue_summary, category: draft.category ?? '' }
}

export default function App() {
  const [fields, setFields] = useState<CheckFields>(emptyCheckFields)
  const [sampleId, setSampleId] = useState('maple')
  const [session, setSession] = useState<SessionResult | null>(null)
  const [draft, setDraft] = useState<RepairDraft | null>(null)
  const [saved, setSaved] = useState<RepairDraft | null>(null)
  const [orders, setOrders] = useState<WorkOrder[]>([])
  const [result, setResult] = useState<CheckRequestResult | null>(null)
  const [busy, setBusy] = useState(true)
  const [stale, setStale] = useState(false)
  const [requestEdited, setRequestEdited] = useState(false)
  const [needsRecheck, setNeedsRecheck] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activityError, setActivityError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<ApiError | null>(null)
  const [recovery, setRecovery] = useState<Partial<DraftFields> | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [generateMessage, setGenerateMessage] = useState(true)
  const [voicePhase, setVoicePhase] = useState<VoicePhase>('restoring')
  const voicePhaseRef = useRef<VoicePhase>('restoring')
  const rawFormDirty = !draft && Boolean(fields.issue_summary.trim() || fields.property_query.trim() || fields.unit_label.trim())
  const cardRef = useRef({ draft, saved, rawFormDirty })
  cardRef.current = { draft, saved, rawFormDirty }
  const voiceSnapshotVersion = useRef(0)
  const dismissedDraftId = useRef<string | null>(null)
  const sessionId = useRef<string | null>(rememberedSession())
  const sessionPromise = useRef<Promise<SessionResult> | null>(null)
  const operation = useRef(false)
  const requestNumber = useRef(0)
  const terminal = draft?.status === 'approved' || draft?.status === 'cancelled'
  const requestLocked = Boolean(saved || terminal)
  const dirty = Boolean(draft && (!saved || draftsDiffer(draft, saved)))
  const voiceLocked = voiceLocksForm(voicePhase)
  const voiceReason = voiceApprovalReason(voicePhase)
  const approvalReason = voiceReason ?? (needsRecheck && !busy && !conflict ? 'Save changes to recheck current records, then review the saved revision.' : approvalDisabledReason(draft, saved, busy, Boolean(conflict)))

  async function ensureSession(): Promise<SessionResult> {
    if (sessionPromise.current) return sessionPromise.current
    sessionPromise.current = (async () => {
      if (!sessionId.current) {
        sessionId.current = (await createSession()).session_id
        rememberSession(sessionId.current)
      }
      let current: SessionResult
      try { current = await getSession(sessionId.current) }
      catch (failure: unknown) {
        if (failure instanceof ApiError && failure.status === 404 && !saved) {
          sessionId.current = null
          try { localStorage.removeItem(sessionStorageKey) } catch { /* Storage may be disabled. */ }
          throw new ApiError('The previous session is no longer available. Try again to open a new session. Your local edits have been kept.', 404, 'unknown_session')
        }
        throw failure
      }
      setSession(current)
      return current
    })().finally(() => { sessionPromise.current = null })
    return sessionPromise.current
  }

  function showFailure(failure: unknown) {
    setError(failure instanceof Error ? failure.message : 'The backend is unavailable. Your edits have been kept.')
    if (failure instanceof ApiError && failure.status === 409) {
      setConflict(failure)
      if (failure.code === 'approval_blocked') setNeedsRecheck(true)
    }
    setAnnouncement('This step could not finish. Your local edits have been kept.')
  }

  function useSavedDraft(current: RepairDraft, catalog = session) {
    cardRef.current = { draft: current, saved: current, rawFormDirty: false }
    setSaved(current)
    setDraft(current)
    setGenerateMessage(false)
    setResult(null)
    setStale(false)
    setRequestEdited(false)
    if (catalog) setFields(queryForDraft(current, catalog))
  }

  async function refreshActivity() {
    const [current, currentOrders] = await Promise.all([ensureSession(), getWorkOrders()])
    setSession(current)
    setOrders(currentOrders)
    setActivityError(null)
  }

  useEffect(() => {
    let active = true
    const initialSnapshotVersion = voiceSnapshotVersion.current
    void (async () => {
      try {
        const current = await ensureSession()
        if (!active) return
        if (current.draft && initialSnapshotVersion === voiceSnapshotVersion.current) useSavedDraft(current.draft, current)
        const currentOrders = await getWorkOrders()
        if (active) setOrders(currentOrders)
      } catch (failure: unknown) {
        if (active) showFailure(failure)
      } finally {
        if (active) setBusy(false)
      }
    })()
    return () => { active = false }
  }, [])

  function changeFields(changes: Partial<CheckFields>) {
    if (requestLocked || busy || voiceLocksForm(voicePhaseRef.current)) return
    requestNumber.current += 1
    setFields((current) => ({ ...current, ...changes }))
    setResult(null)
    setError(null)
    setStale(Boolean(draft || result))
    setRequestEdited(true)
  }

  async function runCheck(input: CheckFields = fields) {
    if (requestLocked || operation.current || voiceLocksForm(voicePhaseRef.current)) return
    operation.current = true
    const thisRequest = ++requestNumber.current
    setBusy(true)
    setError(null)
    setResult(null)
    setStale(false)
    setRequestEdited(true)
    try {
      const currentSession = await ensureSession()
      const response = await checkRepair({ ...input, session_id: currentSession.session_id })
      if (requestNumber.current !== thisRequest) return
      setResult(response)
      if (response.status !== 'error' && response.matched_unit) {
        const unit = response.matched_unit
        const sameUnit = draft?.unit_id === unit.id && draft?.property_id === unit.property_id
        const candidate = response.approved_contractors.find((contractor) => sameUnit && contractor.id === draft?.contractor_id)
        setRequestEdited(false)
        if (!sameUnit) setGenerateMessage(true)
        setDraft({
          id: '', session_id: currentSession.session_id, revision: 0,
          property_id: unit.property_id, unit_id: unit.id, issue_summary: input.issue_summary,
          category: ['plumbing', 'electrical', 'general'].includes(input.category) ? input.category as RepairCategory : null,
          contractor_id: candidate?.id ?? (response.approved_contractors.length === 1 ? response.approved_contractors[0].id : null),
          ...localDetailsForLocation(draft, unit.property_id, unit.id), missing_fields: [], review_reasons: [], evidence: response.evidence,
          status: response.status === 'duplicate_found' ? 'duplicate_found' : response.status === 'needs_human' ? 'needs_human' : 'ready_for_review',
        })
      }
      setAnnouncement(response.events.join('. ') || 'Record check finished.')
    } catch (failure: unknown) {
      if (requestNumber.current === thisRequest) showFailure(failure)
    } finally {
      operation.current = false
      if (requestNumber.current === thisRequest) setBusy(false)
    }
  }

  function loadExample() {
    if (requestLocked || busy || voiceLocksForm(voicePhaseRef.current)) return
    const example = checkExamples.find((item) => item.id === sampleId) ?? checkExamples[0]
    setFields({ ...example.fields })
    void runCheck(example.fields)
  }

  function chooseProperty(id: string) {
    const selected = result?.property_choices.find((property) => property.id === id)
    if (!selected || requestLocked || busy || voiceLocksForm(voicePhaseRef.current)) return
    const next = { ...fields, property_query: selected.id }
    setFields(next)
    void runCheck(next)
  }

  function editDraft(changes: Partial<DraftFields>) {
    if (!draft || terminal || busy || voiceLocksForm(voicePhaseRef.current)) return
    const locationChanged = ('property_id' in changes && changes.property_id !== draft.property_id) || ('unit_id' in changes && changes.unit_id !== draft.unit_id)
    const next = editDraftFields(draft, saved, changes)
    setDraft(next)
    if (!saved && session) setFields(queryForDraft(next, session))
    if (locationChanged && !saved) setGenerateMessage(true)
    if ('contractor_message' in changes) setGenerateMessage(false)
    setResult(null)
    setStale(true)
    if (!conflict) setError(null)
  }

  async function save() {
    if (!draft || terminal || conflict || operation.current || voiceLocksForm(voicePhaseRef.current) || (!saved && (requestEdited || !dirty))) return
    operation.current = true
    setBusy(true)
    setError(null)
    try {
      const currentSession = await ensureSession()
      const payload = draftFields(draft)
      const response = saved
        ? await updateDraft(saved, changedDraftFields(saved, draft))
        : await createDraft(currentSession.session_id, { ...payload, contractor_message: generateMessage ? null : payload.contractor_message })
      useSavedDraft(response, currentSession)
      setRecovery(null)
      setNeedsRecheck(false)
      setAnnouncement(`Draft saved. Review revision ${response.revision} before approving.`)
    } catch (failure: unknown) { showFailure(failure) }
    finally { operation.current = false; setBusy(false) }
  }

  async function approve() {
    // Approval never saves. Both the guard and the request use the last reviewed server snapshot.
    if (!saved || needsRecheck || voiceApprovalReason(voicePhaseRef.current) || approvalDisabledReason(draft, saved, busy, Boolean(conflict)) || operation.current) return
    operation.current = true
    setBusy(true)
    setError(null)
    try {
      const order = await approveDraft(saved, approvalKey(saved))
      useSavedDraft({ ...order.snapshot, status: 'approved' })
      setOrders((current) => [order, ...current.filter((item) => item.id !== order.id)])
      setAnnouncement(`Revision ${order.approved_revision} approved. Work order saved. No message was sent.`)
      void refreshActivity().catch((failure: unknown) => setActivityError(failure instanceof Error ? failure.message : 'Could not refresh activity.'))
    } catch (failure: unknown) { showFailure(failure) }
    finally { operation.current = false; setBusy(false) }
  }

  async function cancel() {
    if (!draft || terminal || busy || conflict || operation.current || voiceLocksForm(voicePhaseRef.current) || (saved && dirty)) return
    if (!saved) {
      setDraft({ ...draft, status: 'cancelled' })
      setResult(null)
      setError(null)
      setStale(false)
      setAnnouncement('Local card discarded. No draft was saved.')
      return
    }
    operation.current = true
    setBusy(true)
    setError(null)
    try {
      const response = await cancelDraft(saved)
      useSavedDraft(response)
      setAnnouncement('Saved draft cancelled. It cannot be approved.')
    } catch (failure: unknown) { showFailure(failure) }
    finally { operation.current = false; setBusy(false) }
  }

  async function loadLatest() {
    if (operation.current || voiceLocksForm(voicePhaseRef.current)) return
    operation.current = true
    setBusy(true)
    try {
      const current = await ensureSession()
      if (!current.draft) throw new Error('No saved draft was returned. Your local edits are still here.')
      if (draft && dirty) setRecovery(changedDraftFields(saved, draft))
      useSavedDraft(current.draft, current)
      setConflict(null)
      setError(null)
      setAnnouncement(`Latest saved revision ${current.draft.revision} loaded. Review it before continuing. Your unsaved edits are kept separately.`)
      void refreshActivity().catch((failure: unknown) => setActivityError(failure instanceof Error ? failure.message : 'Could not refresh activity.'))
    } catch (failure: unknown) { showFailure(failure) }
    finally { operation.current = false; setBusy(false) }
  }

  function reset() {
    if (busy || voiceLocksForm(voicePhaseRef.current) || (saved && !terminal)) return
    dismissedDraftId.current = saved?.id ?? dismissedDraftId.current
    setDraft(null); setSaved(null); setResult(null); setStale(false); setError(null); setConflict(null); setRecovery(null)
    setGenerateMessage(true)
    setRequestEdited(false)
    setNeedsRecheck(false)
    setFields(emptyCheckFields)
    cardRef.current = { draft: null, saved: null, rawFormDirty: false }
    requestAnimationFrame(() => document.getElementById('repair-request')?.focus())
  }

  function retry() {
    if (voiceLocksForm(voicePhaseRef.current)) return
    if (saved || conflict) { void loadLatest(); return }
    if (draft && !requestEdited) { void save(); return }
    if (fields.issue_summary.trim() && fields.unit_label.trim()) { void runCheck(); return }
    setBusy(true)
    setError(null)
    void ensureSession().then((current) => {
      if (current.draft) useSavedDraft(current.draft, current)
      return getWorkOrders()
    }).then(setOrders).catch(showFailure).finally(() => setBusy(false))
  }

  function changeVoicePhase(phase: VoicePhase) {
    voicePhaseRef.current = phase
    setVoicePhase(phase)
  }

  function applyVoiceSnapshot(current: SessionResult) {
    if (sessionId.current && current.session_id !== sessionId.current) return
    voiceSnapshotVersion.current += 1
    setSession(current)
    const merged = mergeVoiceDraft(cardRef.current.draft, cardRef.current.saved, current.draft, cardRef.current.rawFormDirty, dismissedDraftId.current)
    if (merged.conflict) {
      setConflict(new ApiError('The saved draft changed during the conversation. Your unsaved edits are kept. Load and review the latest draft.', 409, 'voice_draft_conflict', current.draft ?? undefined))
      return
    }
    if (merged.changed && merged.draft) {
      useSavedDraft(merged.draft, current)
      setNeedsRecheck(false)
      setAnnouncement(`The assistant saved revision ${merged.draft.revision}. Review the saved card before approving.`)
    }
  }

  async function prepareVoice(mode: VoiceMode) {
    const local = cardRef.current
    const reason = voiceStartReason(local.draft, local.saved, busy || operation.current, Boolean(conflict), 'idle', local.rawFormDirty)
    if (reason) throw new Error(reason)
    try {
      const current = await ensureSession()
      const access = await createVoiceAccess(current.session_id, mode, voiceDraftContext(local.saved))
      return { session_id: current.session_id, access }
    } catch (failure: unknown) {
      if (failure instanceof ApiError && failure.status === 409) showFailure(failure)
      throw failure
    }
  }

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to workspace</a>
      <header className="app-header"><div className="header-inner">
        <div className="flex items-center gap-3"><span className="brand-mark"><House size={23} strokeWidth={1.7} aria-hidden="true" /></span><span className="brand-name">hearth<span>.</span></span><span className="header-divider" /><span className="header-label">Landlord workspace</span></div>
        <div className="flex items-center gap-4"><span className="demo-badge"><span />Demo data</span><span className="profile-avatar" aria-label="Demo landlord account">L</span></div>
      </div></header>
      <main id="main-content" className="workspace">
        <div className="page-intro"><div><p className="eyebrow">A LITTLE CARE GOES A LONG WAY</p><h1>Repairs, taken care of.</h1><p className="intro-description">From the first request to the next step. All in one calm place.</p></div><div className="portfolio-note"><Building2 size={19} strokeWidth={1.5} aria-hidden="true" /><div><strong>{session ? `${session.properties.length} properties. One workspace.` : 'Your property workspace.'}</strong><span>Real database checks · Demo data</span></div></div></div>
        <div className="workspace-grid">
          <TalkPanel canClearRequest={rawFormDirty} onClearRequest={() => { if (!busy && !draft && !voiceLocksForm(voicePhaseRef.current)) { setFields(emptyCheckFields); setRequestEdited(false); setResult(null); setStale(false); setError(null) } }} voiceActive={voiceLocked} voicePanel={<VoicePanel startReason={voiceStartReason(draft, saved, busy, Boolean(conflict), voicePhase, rawFormDirty)} events={session?.events ?? []} prepare={prepareVoice} onSnapshot={applyVoiceSnapshot} onPhaseChange={changeVoicePhase} />} fields={fields} sampleId={sampleId} busy={busy} locked={requestLocked} terminal={terminal} onFieldsChange={changeFields} onSampleChange={setSampleId} onLoadExample={loadExample} onCheck={() => void runCheck()} />
          <RepairCard draft={draft} saved={saved} properties={session?.properties ?? []} contractors={session?.contractors ?? []} result={result} busy={busy || voiceLocked} voiceActive={voiceLocked} onDiscardChanges={() => { if (saved && !busy && !voiceLocksForm(voicePhaseRef.current)) useSavedDraft(saved) }} error={error} stale={stale} dirty={dirty} requestEdited={requestEdited} approvalReason={approvalReason} conflict={conflict} recovery={recovery} generateMessage={generateMessage} onEdit={editDraft} onSave={() => void save()} onApprove={() => void approve()} onCancel={() => void cancel()} onReset={reset} onLoadExample={loadExample} onChoose={chooseProperty} onRetry={retry} onLoadLatest={() => void loadLatest()} onRecover={() => { if (draft && recovery && !terminal && !busy) { editDraft(recovery); setRecovery(null) } }} />
        </div>
        <div className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</div>
        <ActivityList jobs={session?.recent_jobs ?? []} orders={orders} properties={session?.properties ?? []} contractors={session?.contractors ?? []} loaded={Boolean(session)} error={activityError} onRetry={() => { void refreshActivity().catch((failure: unknown) => setActivityError(failure instanceof Error ? failure.message : 'Could not refresh activity.')) }} />
        <footer className="page-footer"><span className="flex items-center gap-2"><Leaf size={15} aria-hidden="true" /> A little more care. A little less admin.</span><span>Demo data · Saved drafts & work orders · No messages sent</span></footer>
      </main>
    </>
  )
}
