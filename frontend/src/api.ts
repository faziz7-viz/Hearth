import type { CheckRequestInput, CheckRequestResult, DraftFields, RepairDraft, SessionResult, WorkOrder } from './types'

export class ApiError extends Error {
  status: number
  code: string
  draft?: RepairDraft
  missingFields: string[]
  reviewReasons: string[]
  constructor(
    message: string,
    status = 0,
    code = 'backend_unavailable',
    draft?: RepairDraft,
    missingFields: string[] = [],
    reviewReasons: string[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.draft = draft
    this.missingFields = missingFields
    this.reviewReasons = reviewReasons
  }
}

async function request<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST'): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    })
  } catch {
    throw new ApiError('Cannot reach the backend. Start the Python server, then try again. Your local edits have been kept. If approval was interrupted, retrying this saved revision is safe.')
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.error_code ? payload : payload?.detail
    const code = detail?.error_code
    const message = detail?.message
    if (response.status >= 500 && path.startsWith('/voice/') && typeof code === 'string' && typeof message === 'string') {
      throw new ApiError(message, response.status, code)
    }
    if (response.status >= 500) {
      throw new ApiError('The backend could not finish this step. Try again. Your local edits have been kept; an interrupted approval can safely be retried.', response.status, code)
    }
    if (response.status === 409) {
      throw new ApiError(message ?? 'The saved draft changed or approval is blocked. Load and review the latest saved draft.', response.status, code ?? 'conflict', detail?.draft, detail?.missing_fields ?? [], detail?.review_reasons ?? [])
    }
    if (response.status === 404) {
      throw new ApiError(message ?? 'This saved record is no longer available. Your local edits have been kept.', response.status, code ?? 'unknown_record')
    }
    throw new ApiError(message ?? 'Check the property, unit, trade, problem, and message fields, then try again.', response.status, code ?? 'invalid_request')
  }
  if (payload === null) throw new ApiError('The backend returned an unreadable response. Try again.')
  return payload as T
}

export const createSession = () => request<{ session_id: string }>('/sessions', {})
export const getSession = (id: string) => request<SessionResult>(`/sessions/${encodeURIComponent(id)}`)
export const checkRepair = (fields: CheckRequestInput) => request<CheckRequestResult>('/repair-check', fields)
export const createDraft = (sessionId: string, fields: Omit<DraftFields, 'contractor_message'> & { contractor_message?: string | null }) => request<RepairDraft>('/drafts', { session_id: sessionId, fields })
export const updateDraft = (draft: RepairDraft, fields: Partial<DraftFields>) => request<RepairDraft>(`/drafts/${encodeURIComponent(draft.id)}`, { session_id: draft.session_id, expected_revision: draft.revision, fields }, 'PATCH')
export const approveDraft = (draft: RepairDraft, idempotencyKey: string) => request<WorkOrder>(`/drafts/${encodeURIComponent(draft.id)}/approve`, { session_id: draft.session_id, expected_revision: draft.revision, idempotency_key: idempotencyKey })
export const cancelDraft = (draft: RepairDraft) => request<RepairDraft>(`/drafts/${encodeURIComponent(draft.id)}/cancel`, { session_id: draft.session_id, expected_revision: draft.revision })
export const getWorkOrders = () => request<WorkOrder[]>('/work-orders')

export const getVoiceConfig = () => request<import('./types').VoiceConfig>('/voice/config')
export const createVoiceAccess = (sessionId: string, mode: 'voice' | 'text', context: { draft_id: string | null; expected_revision: number | null }) => request<import('./types').VoiceAccess>('/voice/access', { session_id: sessionId, mode, ...context })
export const bindVoiceSession = (sessionId: string, voiceId: string, conversationId: string) => request<{ ok: true }>(`/voice/${encodeURIComponent(voiceId)}/bind`, { session_id: sessionId, conversation_id: conversationId })
export const endVoiceSession = (sessionId: string, voiceId: string) => request<{ ok: true }>(`/voice/${encodeURIComponent(voiceId)}/end`, { session_id: sessionId })
