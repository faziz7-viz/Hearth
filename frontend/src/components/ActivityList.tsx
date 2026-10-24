import { Check, Droplets, History, Lightbulb, Wrench } from 'lucide-react'
import type { Contractor, Property, RecentJob, WorkOrder } from '../types'

const jobIcons = { plumbing: Droplets, electrical: Lightbulb, general: Wrench }
const dates = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' })

export function ActivityList({ jobs, orders, properties, contractors, loaded, error, onRetry }: { jobs: RecentJob[]; orders: WorkOrder[]; properties: Property[]; contractors: Contractor[]; loaded: boolean; error: string | null; onRetry: () => void }) {
  const orderIds = new Set(orders.map((order) => order.id))
  const otherJobs = jobs.filter((job) => !orderIds.has(job.id))

  return (
    <section className="recent-section" aria-labelledby="recent-heading">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><Check size={19} className="text-accent" aria-hidden="true" /><h2 id="orders-heading">Saved work orders</h2><span className="count-badge">{orders.length}</span></div>
        <span className="text-xs text-muted">Exact approved details · No messages sent</span>
      </div>
      {error && <div className="notice mb-4" role="alert"><div><strong>Activity could not refresh</strong><p>{error}</p><button className="text-button" onClick={onRetry}>Refresh saved activity</button></div></div>}
      <ul className="saved-orders" aria-labelledby="orders-heading">{orders.map((order) => {
        const snapshot = order.snapshot
        const property = properties.find((item) => item.id === snapshot.property_id)
        const unit = property?.units.find((item) => item.id === snapshot.unit_id)
        const contractor = contractors.find((item) => item.id === snapshot.contractor_id)
        return <li key={order.id}><details className="saved-order"><summary><div><strong>{snapshot.issue_summary}</strong><span>{property?.name ?? snapshot.property_id} · {unit?.label ?? snapshot.unit_id}</span></div><span className="order-review-label">View saved details · Revision {order.approved_revision}</span></summary>
          <div className="order-details"><p className="field-help">Immutable snapshot of the saved revision reviewed at approval. Requested date is not a booking.</p>
            <dl className="order-fields">
              <div><dt>Work order</dt><dd>{order.id}</dd></div><div><dt>Approved revision</dt><dd>{order.approved_revision}</dd></div>
              <div><dt>Draft</dt><dd>{order.draft_id}</dd></div><div><dt>Approved on</dt><dd><time dateTime={order.created_at}>{new Date(order.created_at).toLocaleString()}</time></dd></div>
              <div><dt>Property</dt><dd>{property?.name ?? snapshot.property_id} · {snapshot.property_id}</dd></div><div><dt>Unit</dt><dd>{unit?.label ?? snapshot.unit_id} · {snapshot.unit_id}</dd></div>
              <div><dt>Repair trade</dt><dd>{snapshot.category ?? 'None'}</dd></div><div><dt>Contractor</dt><dd>{contractor?.name ?? snapshot.contractor_id} · {snapshot.contractor_id}</dd></div>
              <div><dt>Requested date</dt><dd>{snapshot.preferred_date || 'No date requested'}</dd></div><div><dt>Status at approval</dt><dd>{snapshot.status}</dd></div>
              <div className="order-wide"><dt>Problem</dt><dd className="exact-text">{snapshot.issue_summary}</dd></div>
              <div className="order-wide"><dt>Access notes</dt><dd className="exact-text">{snapshot.access_notes || 'No access notes'}</dd></div>
              <div className="order-wide"><dt>Saved contractor message</dt><dd className="exact-text saved-message">{snapshot.contractor_message}</dd></div>
            </dl>
            {snapshot.evidence.length > 0 && <details className="sample-context mt-4"><summary>Record evidence saved at approval <span>{snapshot.evidence.length} references</span></summary><ul>{snapshot.evidence.map((item, index) => <li key={`${item.record_id}-${index}`}>{item.summary} ({item.source_type}: {item.record_id})</li>)}</ul></details>}
          </div>
        </details></li>
      })}</ul>
      {orders.length === 0 && <p className="empty-orders">{loaded ? 'Approved work orders will be kept here with their exact saved details.' : 'Waiting for saved work orders from the backend.'}</p>}
      <div className="mb-5 mt-8 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><History size={19} className="text-accent" aria-hidden="true" /><h2 id="recent-heading">Recent jobs</h2><span className="count-badge">{otherJobs.length}</span></div>
        <span className="text-xs text-muted">{loaded ? 'Fictional records from SQLite' : 'Waiting for backend records'}</span>
      </div>
      <div className="jobs-table">
        <div className="job-row job-header" aria-hidden="true"><span>REPAIR</span><span>PROPERTY</span><span>CONTRACTOR</span><span>STATUS</span><span>CREATED</span></div>
        <ul aria-label="Recent demo jobs">
          {otherJobs.map((job) => {
            const Icon = jobIcons[job.category]
            const property = properties.find((item) => item.id === job.property_id)
            const unit = property?.units.find((item) => item.id === job.unit_id)
            const contractor = contractors.find((item) => item.id === job.contractor_id)
            return (
              <li key={job.id} className="job-row">
                <div className="job-title"><span className="job-icon"><Icon size={18} strokeWidth={1.6} aria-hidden="true" /></span><div><h3>{job.issue_summary}</h3><span className="job-mobile-subtitle">{property?.name} · {unit?.label}</span></div></div>
                <div className="job-property"><p>{property?.name}</p><span>{unit?.label}</span></div>
                <div className="job-contractor"><span className="contractor-avatar" aria-hidden="true">{contractor?.name.slice(0, 1)}</span><span>{contractor?.name}</span></div>
                <div className="job-status"><span className={`status-badge ${job.status === 'approved' ? 'status-green' : ''}`}>
                  {job.status === 'completed' ? <Check size={12} aria-hidden="true" /> : <span className="status-dot" />}
                  {job.status === 'approved' ? 'Approved · demo' : job.status === 'open' ? 'Open' : 'Completed'}
                </span></div>
                <time className="job-date" dateTime={job.created_at}>{dates.format(new Date(job.created_at))}</time>
              </li>
            )
          })}
        </ul>
        {otherJobs.length === 0 && <p className="p-6 text-sm text-muted">{loaded ? 'No other jobs in the saved records.' : 'Connect the backend to load recent jobs. No sample fallback is shown.'}</p>}
      </div>
    </section>
  )
}
