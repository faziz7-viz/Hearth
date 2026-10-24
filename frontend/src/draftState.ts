import type { DraftFields, RepairDraft } from './types'

const editableKeys = ['property_id', 'unit_id', 'issue_summary', 'category', 'contractor_id', 'preferred_date', 'access_notes', 'contractor_message'] as const

export function draftFields(draft: RepairDraft): DraftFields {
  return {
    property_id: draft.property_id ?? null, unit_id: draft.unit_id ?? null,
    issue_summary: draft.issue_summary, category: draft.category ?? null,
    contractor_id: draft.contractor_id ?? null, preferred_date: draft.preferred_date || null,
    access_notes: draft.access_notes, contractor_message: draft.contractor_message,
  }
}

export function changedDraftFields(saved: RepairDraft | null, edited: RepairDraft): Partial<DraftFields> {
  const next = draftFields(edited)
  if (!saved) return next
  const previous = draftFields(saved)
  return Object.fromEntries(editableKeys.filter((key) => next[key] !== previous[key]).map((key) => [key, next[key]])) as Partial<DraftFields>
}

export function draftsDiffer(edited: RepairDraft, saved: RepairDraft): boolean {
  return Object.keys(changedDraftFields(saved, edited)).length > 0
}

export function approvalKey(draft: RepairDraft): string {
  return `hearth:${draft.session_id}:${draft.id}:${draft.revision}`
}

export function approvalDisabledReason(edited: RepairDraft | null, saved: RepairDraft | null, busy: boolean, conflict: boolean): string | null {
  if (busy) return 'Please wait for the current step to finish.'
  if (conflict) return 'Load and review the latest saved draft first.'
  if (!edited || !saved) return 'Save draft, then review the saved revision before approval.'
  if (edited.id !== saved.id || edited.revision !== saved.revision) return 'Load and review the latest saved draft first.'
  if (draftsDiffer(edited, saved)) return 'Save changes, then review the saved revision before approval.'
  if (saved.status === 'approved') return 'This work order is already approved.'
  if (saved.status === 'cancelled') return 'This draft was cancelled.'
  if (saved.status !== 'ready_for_review' || saved.missing_fields.length || saved.review_reasons.length) return 'Resolve the saved draft’s missing information or review reasons before approval.'
  return null
}

const reasonLabels: Record<string, string> = {
  safety_concern: 'This issue needs a person to review safety before proceeding.',
  invalid_property_unit: 'Select a unit that belongs to the selected property.',
  unsupported_category: 'This repair trade needs human review.',
  contractor_not_approved: 'Choose a contractor approved for this property and repair trade.',
  duplicate_found: 'A matching open or approved job already exists. Review it before proceeding.',
  unknown_property: 'The property could not be found in the saved records.',
  missing_unit: 'Choose a unit in the selected property.',
}

export const reviewReason = (reason: string) => reasonLabels[reason] ?? reason.replaceAll('_', ' ')

export function localDetailsForLocation(previous: RepairDraft | null, propertyId: string | null | undefined, unitId: string | null | undefined): Pick<DraftFields, 'preferred_date' | 'access_notes' | 'contractor_message'> {
  const sameLocation = previous?.property_id === propertyId && previous?.unit_id === unitId
  return {
    preferred_date: sameLocation ? previous?.preferred_date ?? null : null,
    access_notes: sameLocation ? previous?.access_notes ?? '' : '',
    contractor_message: sameLocation ? previous?.contractor_message ?? '' : '',
  }
}

export function editDraftFields(draft: RepairDraft, saved: RepairDraft | null, changes: Partial<DraftFields>): RepairDraft {
  const locationChanged = ('property_id' in changes && changes.property_id !== draft.property_id) || ('unit_id' in changes && changes.unit_id !== draft.unit_id)
  const localDetails = !saved && locationChanged ? localDetailsForLocation(draft, 'property_id' in changes ? changes.property_id : draft.property_id, 'unit_id' in changes ? changes.unit_id : draft.unit_id) : {}
  // Saved text is deliberate user content. A location edit must keep it visible for review.
  return { ...draft, ...localDetails, ...changes }
}
