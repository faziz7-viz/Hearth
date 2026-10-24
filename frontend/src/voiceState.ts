import { draftsDiffer } from './draftState.ts'
import type { RepairDraft } from './types.ts'

export type VoicePhase = 'restoring' | 'idle' | 'starting' | 'connected' | 'ending' | 'syncing' | 'sync_error'
export type VoiceMode = 'voice' | 'text'
export interface TranscriptTurn { id: string; role: 'user' | 'agent'; text: string }
export const voiceLocksForm = (phase: VoicePhase) => ['restoring', 'starting', 'connected', 'ending', 'syncing'].includes(phase)

export function voiceStartReason(draft: RepairDraft | null, saved: RepairDraft | null, busy: boolean, conflict: boolean, phase: VoicePhase, rawFormDirty = false): string | null {
  if (phase !== 'idle') return 'Finish the current conversation and refresh its saved card first.'
  if (busy) return 'Wait for the current step to finish.'
  if (conflict) return 'Load and review the latest saved draft first.'
  if (draft?.status === 'approved' || draft?.status === 'cancelled') return 'Choose New request on the card to begin another conversation.'
  if (rawFormDirty) return 'Check and save this request, or clear the form before starting.'
  if (draft && (!saved || draftsDiffer(draft, saved))) return 'Save or discard your unsaved card changes before starting a conversation.'
  return null
}

export function voiceDraftContext(saved: RepairDraft | null) {
  return saved && saved.id && saved.status !== 'approved' && saved.status !== 'cancelled'
    ? { draft_id: saved.id, expected_revision: saved.revision }
    : { draft_id: null, expected_revision: null }
}

export function mergeVoiceDraft(draft: RepairDraft | null, saved: RepairDraft | null, remote: RepairDraft | null, rawFormDirty = false, dismissedDraftId: string | null = null) {
  const unchanged = { draft, saved, changed: false, conflict: false }
  if (!remote || (saved?.id === remote.id && saved.revision > remote.revision)) return unchanged
  if (!saved && remote.id === dismissedDraftId && (remote.status === 'approved' || remote.status === 'cancelled')) return unchanged
  const changed = saved?.id !== remote.id || saved?.revision !== remote.revision || saved?.status !== remote.status
  if (!changed) return unchanged
  if (rawFormDirty || (draft && (!saved || draftsDiffer(draft, saved)))) return { ...unchanged, conflict: true }
  return { draft: remote, saved: remote, changed: true, conflict: false }
}

export function voiceApprovalReason(phase: VoicePhase): string | null {
  if (phase === 'sync_error') return 'Retry ending the conversation and loading its saved card before approval.'
  if (phase !== 'idle') return 'End the conversation and wait for the latest saved card before reviewing.'
  return null
}

export function appendTranscript(turns: TranscriptTurn[], turn: TranscriptTurn): TranscriptTurn[] {
  if (!turn.text.trim()) return turns
  const next = { ...turn, text: turn.text.slice(0, 5000) }
  const index = turns.findIndex((item) => item.id === next.id)
  return (index < 0 ? [...turns, next] : turns.map((item, at) => at === index ? next : item)).slice(-120)
}
