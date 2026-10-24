import { CheckCircle2, Info, LoaderCircle } from 'lucide-react'
import type { CheckRequestResult } from '../types'

export function CheckResults({ result, busy, error, stale, onChoose, onRetry }: {
  result: CheckRequestResult | null
  busy: boolean
  error: string | null
  stale: boolean
  onChoose: (propertyId: string) => void
  onRetry: () => void
}) {
  if (busy) return <div className="notice mb-5" role="status"><LoaderCircle className="animate-spin" size={17} aria-hidden="true" /><p>Reading the saved property, repair, and contractor records…</p></div>
  if (error) return <div className="notice mb-5" role="alert"><Info size={17} aria-hidden="true" /><div><strong>Backend unavailable</strong><p>{error}</p><button className="text-button mt-2" onClick={onRetry}>Try again</button></div></div>
  if (stale) return <div className="notice mb-5" role="status"><Info size={17} aria-hidden="true" /><div><strong>Details changed</strong><p>Run Check repair records again. Previous matches and contractor suggestions are no longer current.</p></div></div>
  if (!result) return null

  const heading = {
    matched: 'Records checked', unknown_property: 'Property not found', ambiguous_property: 'Which property did you mean?',
    duplicate_found: 'Possible duplicate repair', needs_human: 'A person needs to review this', error: 'Record check failed',
  }[result.status]
  const explanations = {
    matched: 'The property and unit match. No similar open repair was found.',
    unknown_property: 'No property matches these details. Check the spelling or try another property.',
    ambiguous_property: 'More than one property matches. Choose one below to run the checks for that property.',
    duplicate_found: 'An open repair may already cover this problem. Review it before creating another job.',
    needs_human: result.error_code === 'unknown_unit' ? 'That unit was not found at this property. Check the unit and try again.' : result.error_code === 'safety_concern' ? 'This request may involve an urgent safety concern. Contact a person for help before arranging routine repairs.' : result.error_code === 'no_approved_contractor' ? 'There is no approved contractor for this trade at this property. Ask a person to review the next step.' : 'These records do not support a routine repair with an approved contractor. Review the details with a person.',
    error: 'The check did not finish. Your local details have been kept. Try again.',
  }

  return (
    <div className="check-results mb-6" aria-live="polite">
      <div className={`notice ${result.status === 'matched' ? 'notice-green' : ''}`}>
        {result.status === 'matched' ? <CheckCircle2 size={18} aria-hidden="true" /> : <Info size={18} aria-hidden="true" />}
        <div><strong>{heading}</strong><p>{explanations[result.status]}</p></div>
      </div>
      {result.status === 'ambiguous_property' && <div className="mt-3 flex flex-wrap gap-2">{result.property_choices.map((property) => <button key={property.id} className="secondary-button" onClick={() => onChoose(property.id)}>{property.name}</button>)}</div>}
      {result.status === 'error' && <button className="text-button mt-2" onClick={onRetry}>Try again</button>}
      {result.open_jobs.length > 0 && <ul className="result-records" aria-label="Possible duplicate repairs">{result.open_jobs.map((job) => <li key={job.id}><strong>{job.issue_summary}</strong><span>Open repair · {result.property_choices.find((property) => property.id === job.property_id)?.name} · {result.matched_unit?.label}</span></li>)}</ul>}
      {result.matched_unit && <div className="mt-4"><h3 className="field-label">Approved contractors for this repair</h3>{result.approved_contractors.length ? <ul className="result-records">{result.approved_contractors.map((contractor) => <li key={contractor.id}><strong>{contractor.name} · {contractor.trade}</strong><span>Approved for this property. Availability has not been checked.</span></li>)}</ul> : <p className="text-xs leading-5 text-muted">No approved contractor returned. No replacement has been selected.</p>}</div>}
      {result.events.length > 0 && <ul className="check-events" aria-label="Completed record checks">{result.events.map((event, index) => <li key={`${index}-${event}`}>{event}</li>)}</ul>}
      {result.evidence.length > 0 && <details className="sample-context mt-4"><summary>Database record notes <span>{result.evidence.length} references</span></summary><ul>{result.evidence.map((item, index) => <li key={`${item.source_type}-${item.record_id}-${index}`}>{item.summary}</li>)}</ul></details>}
    </div>
  )
}
