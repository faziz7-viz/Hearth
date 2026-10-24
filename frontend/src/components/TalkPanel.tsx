import { ArrowRight, ArrowUpRight, ChevronDown, LoaderCircle, MessageSquareText, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { checkExamples } from '../demoData'
import type { CheckFields } from '../types'

interface TalkPanelProps {
  voicePanel: ReactNode
  voiceActive: boolean
  canClearRequest: boolean
  onClearRequest: () => void
  fields: CheckFields
  sampleId: string
  busy: boolean
  locked: boolean
  terminal: boolean
  onFieldsChange: (changes: Partial<CheckFields>) => void
  onSampleChange: (id: string) => void
  onLoadExample: () => void
  onCheck: () => void
}

export function TalkPanel({ voicePanel, voiceActive, canClearRequest, onClearRequest, fields, sampleId, busy, locked, terminal, onFieldsChange, onSampleChange, onLoadExample, onCheck }: TalkPanelProps) {
  return (
    <div className="flex min-w-0 flex-col gap-5">
      <section className="panel request-panel" aria-labelledby="request-heading">
        <div className="section-kicker"><span className="step-number">01</span> THE REQUEST</div>
        <div className="mt-5 flex items-start gap-3">
          <MessageSquareText size={23} className="mt-1 text-accent" aria-hidden="true" />
          <div><h2 id="request-heading">What needs a little care?</h2><p className="mt-2 text-sm leading-6 text-muted">Check the records before taking the next step.</p></div>
        </div>
        {voicePanel}
        <div className="form-divider"><span>OR USE THE REPAIR FORM</span></div>
        {voiceActive && <p className="notice mt-5">End the conversation to edit the form or review the repair card.</p>}
        {locked && <p className="notice mt-5">{terminal ? 'This request is finished. Choose New request on the repair card to begin another.' : 'A saved draft is open. Edit its repair card, then approve or cancel it before starting another request.'}</p>}
        <form onSubmit={(event) => { event.preventDefault(); onCheck() }} className="mt-7">
          <fieldset disabled={busy || locked || voiceActive}>
            <legend className="sr-only">Repair record check</legend>
            <div className="sample-picker">
              <label htmlFor="sample-request" className="field-label">Example to load</label>
              <div className="flex items-center gap-3">
                <div className="select-wrap min-w-0 flex-1"><select id="sample-request" className="field" value={sampleId} onChange={(event) => onSampleChange(event.target.value)}>{checkExamples.map((example) => <option key={example.id} value={example.id}>{example.label}</option>)}</select><ChevronDown size={15} aria-hidden="true" /></div>
                <button type="button" onClick={onLoadExample} className="example-button shrink-0"><Sparkles size={14} aria-hidden="true" /> Load example</button>
              </div>
            </div>
            <label htmlFor="repair-request" className="field-label mt-5">Problem</label>
            <textarea id="repair-request" className="request-input" placeholder="e.g. Leaking kitchen tap" value={fields.issue_summary} onChange={(event) => onFieldsChange({ issue_summary: event.target.value })} aria-describedby="request-help" maxLength={2000} required />
            <p id="request-help" className="mt-3 text-xs leading-5 text-muted">Enter the property and unit below. This step checks records; it does not interpret a conversation.</p>
            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div><label htmlFor="property-query" className="field-label">Property name</label><input id="property-query" className="field" value={fields.property_query} onChange={(event) => onFieldsChange({ property_query: event.target.value })} placeholder="e.g. Maple Court" maxLength={200} /><p className="field-help">Leave blank to find the unit’s property.</p></div>
              <div><label htmlFor="unit-query" className="field-label">Unit</label><input id="unit-query" className="field" value={fields.unit_label} onChange={(event) => onFieldsChange({ unit_label: event.target.value })} placeholder="e.g. 4" maxLength={40} required /></div>
              <div className="sm:col-span-2"><label htmlFor="trade-query" className="field-label">Repair trade</label><div className="select-wrap"><select id="trade-query" className="field" value={fields.category} onChange={(event) => onFieldsChange({ category: event.target.value })}><option value="plumbing">Plumbing</option><option value="electrical">Electrical</option><option value="general">General repairs</option><option value="roofing">Roofing (unsupported)</option></select><ChevronDown size={15} aria-hidden="true" /></div></div>
            </div>
            <button className="primary-button mt-6 w-full" type="submit" disabled={busy || !fields.issue_summary.trim() || !fields.unit_label.trim()}>{busy ? <><LoaderCircle size={17} className="animate-spin" aria-hidden="true" /> Checking records…</> : <>Check repair records <ArrowRight size={17} aria-hidden="true" /></>}</button>
            {canClearRequest && <button type="button" className="text-button mt-3" onClick={onClearRequest}>Clear form</button>}
          </fieldset>
        </form>
      </section>
      <aside className="example-note" aria-labelledby="example-heading">
        <div className="mb-3 flex items-center justify-between"><h3 id="example-heading" className="section-kicker">REAL CHECKS. FICTIONAL RECORDS.</h3><ArrowUpRight size={18} className="shrink-0 text-accent" aria-hidden="true" /></div>
        <p className="example-quote">“At Maple Court, unit 4 has a leaking kitchen tap. Find our approved plumber and prepare a work order.”</p>
        <p className="mt-4 text-xs leading-5 text-muted">We check the saved records. Save a draft, review its exact details, then approve a work order. No message is sent.</p>
      </aside>
    </div>
  )
}
