import { ArrowRight, Check, ChevronDown, ClipboardList, LockKeyhole, RotateCcw, Save, X } from 'lucide-react'
import type { CheckRequestResult, Contractor, DraftFields, Property, RepairDraft } from '../types'
import type { ApiError } from '../api'
import { reviewReason } from '../draftState'
import { CheckResults } from './CheckResults'

interface RepairCardProps {
  draft: RepairDraft | null
  saved: RepairDraft | null
  properties: Property[]
  contractors: Contractor[]
  result: CheckRequestResult | null
  voiceActive: boolean
  onDiscardChanges: () => void
  busy: boolean
  error: string | null
  stale: boolean
  dirty: boolean
  requestEdited: boolean
  approvalReason: string | null
  conflict: ApiError | null
  recovery: Partial<DraftFields> | null
  generateMessage: boolean
  onEdit: (changes: Partial<DraftFields>) => void
  onSave: () => void
  onApprove: () => void
  onCancel: () => void
  onReset: () => void
  onLoadExample: () => void
  onChoose: (id: string) => void
  onRetry: () => void
  onLoadLatest: () => void
  onRecover: () => void
}

const statuses: Record<RepairDraft['status'], string> = {
  ready_for_review: 'Ready for review', needs_info: 'Needs information', approved: 'Approved · demo',
  cancelled: 'Cancelled · demo', duplicate_found: 'Existing job', needs_human: 'Needs human review',
}
const fieldNames: Record<string, string> = { property_id: 'Property', unit_id: 'Unit', issue_summary: 'Problem', category: 'Repair trade', contractor_id: 'Contractor', preferred_date: 'Requested date', access_notes: 'Access notes', contractor_message: 'Contractor message' }

export function RepairCard({ draft, saved, properties, contractors, result, busy, voiceActive, onDiscardChanges, error, stale, dirty, requestEdited, approvalReason, conflict, recovery, generateMessage, onEdit, onSave, onApprove, onCancel, onReset, onLoadExample, onChoose, onRetry, onLoadLatest, onRecover }: RepairCardProps) {
  const locked = draft?.status === 'approved' || draft?.status === 'cancelled'
  const unresolved = Boolean(!saved && result && !result.matched_unit && result.status !== 'error')
  const property = properties.find((item) => item.id === draft?.property_id)
  const availableContractors = contractors.filter((item) => item.trade === draft?.category && item.approved_property_ids.includes(draft?.property_id ?? ''))
  const selectedContractor = contractors.find((item) => item.id === draft?.contractor_id)
  const badge = voiceActive ? 'Conversation in progress' : busy ? 'Working…' : conflict ? 'Review latest draft' : error ? 'Step interrupted' : saved && dirty ? 'Unsaved changes' : stale && !saved ? 'Checks run on save' : result?.status === 'ambiguous_property' ? 'Choose a property' : result?.status === 'unknown_property' ? 'Property not found' : draft ? statuses[draft.status] : 'Awaiting a request'

  return (
    <section className="panel repair-panel" aria-labelledby="card-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="section-kicker"><span className="step-number">02</span> THE DETAILS</div>
        <span className={`status-badge ${saved && !dirty && !conflict && !busy && !error && ['ready_for_review', 'approved'].includes(saved.status) ? 'status-green' : ''}`}><span className="status-dot" /> {badge}</span>
      </div>
      <div className="mb-6 mt-5 flex items-start gap-3">
        <ClipboardList size={23} className="mt-1 text-accent" aria-hidden="true" />
        <div><h2 id="card-heading" tabIndex={-1}>Your repair card</h2><p className="mt-2 text-sm text-muted">Save the details. Review them. Approve once.</p></div>
      </div>

      {voiceActive && <p className="notice mb-5">The assistant can update this saved card. End the conversation to edit, review, or approve its latest revision.</p>}
      <CheckResults result={result} busy={busy} error={conflict ? null : error} stale={!saved && stale} onChoose={onChoose} onRetry={onRetry} />
      {conflict && <div className="notice mb-5" role="alert"><div><strong>Saved draft needs review</strong><p>{conflict.message} Your edits are kept in this card.</p>{conflict.reviewReasons.map((reason) => <p key={reason}>{reviewReason(reason)}</p>)}<button className="text-button mt-2" disabled={busy} onClick={onLoadLatest}>Load latest saved draft</button><p className="field-help">Loading keeps unsaved edits separately so you can review the server version first.</p></div></div>}
      {recovery && Object.keys(recovery).length > 0 && <details className="recovery-note mb-5" open><summary>Your unsaved edits are kept</summary><dl>{Object.entries(recovery).map(([key, value]) => <div key={key}><dt>{fieldNames[key] ?? key}</dt><dd className="exact-text">{value || '(empty)'}</dd></div>)}</dl>{draft && !locked && <button className="text-button mt-2" disabled={busy || Boolean(conflict)} onClick={onRecover}>Restore these edits to the card</button>}<p className="field-help">Review the latest version before restoring and saving your changes.</p></details>}

      {!saved && requestEdited && draft && <p className="notice mb-5">The request inputs changed. Check repair records again before saving this local card.</p>}
      {unresolved && draft ? <p className="notice mb-5">Your previous local card is kept. Resolve this request to see its details again.</p> : !draft ? (result || busy || error ? null : (
        <div className="empty-card">
          <div className="paper-illustration" aria-hidden="true"><div className="paper-back" /><div className="paper-front"><ClipboardList size={28} strokeWidth={1.5} /><span /><span /><span /><div className="paper-check"><Check size={16} /></div></div></div>
          <h3>Every repair starts with a request.</h3><p>Load an example to find the property, check open repairs, and see approved contractors.</p>
          <button onClick={onLoadExample} disabled={busy} className="text-button mt-5">Try the example <ArrowRight size={16} aria-hidden="true" /></button>
          <div className="empty-field-hints"><span>Property & unit</span><span>Repair details</span><span>Contractor</span></div>
        </div>
      )) : (
        <div className="card-content">
          {locked && <div className={`notice mb-5 ${draft.status === 'approved' ? 'notice-green' : ''}`} role="status">{draft.status === 'approved' ? <Check size={18} aria-hidden="true" /> : <X size={18} aria-hidden="true" />}<div><strong>{draft.status === 'approved' ? 'Work order saved' : saved ? 'Saved draft cancelled' : 'Local card discarded'}</strong><p>{draft.status === 'approved' ? `Revision ${draft.revision} was approved. Its exact details are saved below. No message was sent.` : saved ? 'This draft cannot be approved. Its saved details stay visible.' : 'No draft was saved. Start a new request when you are ready.'}</p></div></div>}
          <fieldset disabled={locked || busy} className="grid min-w-0 grid-cols-1 gap-x-5 gap-y-5 sm:grid-cols-2">
            <legend className="sr-only">Editable repair details</legend>
            <div>
              <label className="field-label" htmlFor="property">Property <span className="required-mark">*</span></label>
              <div className="select-wrap"><select id="property" className="field" value={draft.property_id ?? ''} onChange={(event) => onEdit({ property_id: event.target.value, unit_id: '' })} required><option value="">Select a property</option>{properties.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={15} aria-hidden="true" /></div>
            </div>
            <div>
              <label className="field-label" htmlFor="unit">Unit <span className="required-mark">*</span></label>
              <div className="select-wrap"><select id="unit" className="field" value={draft.unit_id ?? ''} onChange={(event) => onEdit({ unit_id: event.target.value })} disabled={!property || locked || busy} required><option value="">{property ? 'Select a unit' : 'Choose a property first'}</option>{property?.units.map((unit) => <option key={unit.id} value={unit.id}>{unit.label}</option>)}</select><ChevronDown size={15} aria-hidden="true" /></div>
            </div>
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="problem">Problem <span className="required-mark">*</span></label>
              <textarea id="problem" className="field problem-field" value={draft.issue_summary} onChange={(event) => onEdit({ issue_summary: event.target.value })} rows={2} maxLength={2000} required />
            </div>
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="repair-trade">Repair trade <span className="required-mark">*</span></label>
              <div className="select-wrap"><select id="repair-trade" className="field" value={draft.category ?? ''} onChange={(event) => onEdit({ category: event.target.value ? event.target.value as RepairDraft['category'] : null })}><option value="">Select a repair trade</option><option value="plumbing">Plumbing</option><option value="electrical">Electrical</option><option value="general">General repairs</option></select><ChevronDown size={15} aria-hidden="true" /></div>
            </div>
            <div>
              <label className="field-label" htmlFor="contractor">Contractor <span className="required-mark">*</span></label>
              <div className="select-wrap"><select id="contractor" className="field" value={draft.contractor_id ?? ''} onChange={(event) => onEdit({ contractor_id: event.target.value })} required><option value="">Select a contractor</option>{draft.contractor_id && !availableContractors.some((item) => item.id === draft.contractor_id) && <option value={draft.contractor_id}>{selectedContractor?.name ?? draft.contractor_id} · eligibility needs review</option>}{availableContractors.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.trade}</option>)}</select><ChevronDown size={15} aria-hidden="true" /></div>
              <p className="field-help">Property and trade approvals from saved records. Rechecked on save and approval.</p>
            </div>
            <div>
              <label className="field-label" htmlFor="preferred-date">Requested date <span className="optional-label">Optional</span></label>
              <input id="preferred-date" type="date" className="field" value={draft.preferred_date ?? ''} onChange={(event) => onEdit({ preferred_date: event.target.value })} aria-describedby="date-help" />
              <p id="date-help" className="field-help">A request, not a confirmed booking.</p>
            </div>
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="access-notes">Access notes <span className="optional-label">Optional</span></label>
              <textarea id="access-notes" className="field notes-field" placeholder="e.g. Tenant is home after 3 pm. Please knock." value={draft.access_notes} onChange={(event) => onEdit({ access_notes: event.target.value })} maxLength={2000} rows={2} />
            </div>
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="contractor-message">Contractor message <span className="required-mark">*</span></label>
              <textarea id="contractor-message" className="field notes-field" placeholder={generateMessage ? 'A grounded message will be prepared on first save, or write your own.' : 'Write the message you want to save.'} value={draft.contractor_message} onChange={(event) => onEdit({ contractor_message: event.target.value })} maxLength={5000} rows={4} aria-describedby="message-help" />
              <p id="message-help" className="field-help">Editable draft only. Approval saves this exact message; nothing is sent.</p>
            </div>
          </fieldset>
          <p className="revision-note mt-4" role="status">{saved ? dirty ? `Unsaved changes · Last saved revision ${saved.revision}` : `Saved revision ${saved.revision} · ${locked ? 'Details kept in SQLite' : 'Review these details before approval'}` : 'Unsaved local card · Save draft to keep these details'}</p>
          {!locked && dirty && <p className="field-help">Saving rechecks the current property, unit, contractor, duplicate jobs, and safety.</p>}
          {saved && !locked && (saved.missing_fields.length > 0 || saved.review_reasons.length > 0) && <div className="notice mt-4"><div><strong>Saved revision needs attention</strong>{saved.missing_fields.length > 0 && <p>Missing: {saved.missing_fields.map((field) => fieldNames[field] ?? field.replaceAll('_', ' ')).join(', ')}.</p>}{saved.review_reasons.map((reason) => <p key={reason}>{reviewReason(reason)}</p>)}</div></div>}
          {saved && saved.evidence.length > 0 && <details className="sample-context mt-4"><summary>Saved revision {saved.revision} record notes <span>{saved.evidence.length} references</span></summary><ul>{saved.evidence.map((item, index) => <li key={`${item.source_type}-${item.record_id}-${index}`}>{item.summary}</li>)}</ul></details>}
        </div>
      )}

      <div className="card-footer">
        {locked ? <button className="secondary-button w-full" disabled={busy} onClick={onReset}><RotateCcw size={16} aria-hidden="true" /> New request</button> : <>
          <button type="button" className="secondary-button mb-3 w-full" disabled={!draft || (!saved && (!dirty || requestEdited)) || busy || unresolved || Boolean(conflict)} onClick={onSave}><Save size={16} aria-hidden="true" /> {saved ? 'Save changes' : 'Save draft'}</button>
          {saved && dirty && <button type="button" className="text-button mb-3" disabled={busy || Boolean(conflict)} onClick={onDiscardChanges}>Discard unsaved changes</button>}
          <div className="flex gap-3"><button type="button" className="primary-button flex-1" disabled={Boolean(approvalReason)} aria-describedby="approval-help" onClick={onApprove}><Check size={17} aria-hidden="true" /> Approve work order</button><button type="button" className="secondary-button" disabled={!draft || busy || unresolved || Boolean(conflict) || Boolean(saved && dirty)} onClick={onCancel}>{saved ? 'Cancel draft' : 'Discard local card'}</button></div>
          <p id="approval-help" className="mt-3 text-xs leading-5 text-muted">{approvalReason ?? `Approve exactly saved revision ${saved?.revision}.`}{saved && dirty ? ' Save your changes before cancelling, too.' : ''}</p>
        </>}
        <p className="mt-4 flex items-center justify-center gap-2 text-center text-xs leading-5 text-muted"><LockKeyhole size={13} className="shrink-0" aria-hidden="true" /> No messages sent. Contractor availability has not been checked.</p>
      </div>
    </section>
  )
}
