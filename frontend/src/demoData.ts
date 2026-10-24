import type { CheckFields } from './types'

// Example inputs only. All property matches, jobs, history, and contractors come from SQLite.
export const checkExamples: { id: string; label: string; fields: CheckFields }[] = [
  { id: 'maple', label: 'Maple Court · kitchen tap', fields: { property_query: 'Maple Court', unit_label: '4', category: 'plumbing', issue_summary: 'Leaking kitchen tap' } },
  { id: 'cedar', label: 'Cedar House · existing repair', fields: { property_query: 'Cedar House', unit_label: '4', category: 'plumbing', issue_summary: 'Leaking bathroom tap' } },
  { id: 'ambiguous', label: 'Unit 4 · which property?', fields: { property_query: '', unit_label: '4', category: 'plumbing', issue_summary: 'Leaking kitchen tap' } },
  { id: 'unknown', label: 'Unknown property', fields: { property_query: 'Oak Lodge', unit_label: '4', category: 'plumbing', issue_summary: 'Leaking kitchen tap' } },
  { id: 'unavailable', label: 'Willow Place · no approved plumber', fields: { property_query: 'Willow Place', unit_label: '2', category: 'plumbing', issue_summary: 'Leaking kitchen tap' } },
]

export const emptyCheckFields: CheckFields = { property_query: '', unit_label: '', category: 'plumbing', issue_summary: '' }
