export type RepairCategory = 'plumbing' | 'electrical' | 'general';

export type DraftStatus =
  | 'needs_info'
  | 'duplicate_found'
  | 'needs_human'
  | 'ready_for_review'
  | 'approved'
  | 'cancelled';

export interface RepairEvidence {
  source_type: string;
  record_id: string;
  summary: string;
}

export interface RepairDraft {
  id: string;
  session_id: string;
  revision: number;
  property_id?: string | null;
  unit_id?: string | null;
  issue_summary: string;
  category?: RepairCategory | null;
  contractor_id?: string | null;
  preferred_date?: string | null;
  access_notes: string;
  contractor_message: string;
  missing_fields: string[];
  review_reasons: string[];
  evidence: RepairEvidence[];
  status: DraftStatus;
}

export interface AgentTurnResult {
  session_id: string;
  reply: string;
  draft?: RepairDraft | null;
  events: string[];
  error_code?: string | null;
}

export interface WorkOrder {
  id: string;
  draft_id: string;
  approved_revision: number;
  snapshot: RepairDraft;
  created_at: string;
}

export interface Property {
  id: string;
  name: string;
  units: { id: string; label: string }[];
}

export interface Contractor {
  id: string;
  name: string;
  trade: RepairCategory;
  approved_property_ids: string[];
}

export interface RecentJob {
  id: string;
  property_id: string;
  unit_id: string;
  issue_summary: string;
  contractor_id: string;
  category: RepairCategory;
  status: 'open' | 'completed' | 'approved';
  created_at: string;
}

export interface CheckFields {
  property_query: string;
  unit_label: string;
  category: string;
  issue_summary: string;
}

export interface CheckRequestInput extends CheckFields {
  session_id: string;
}

export type CheckStatus = 'matched' | 'unknown_property' | 'ambiguous_property' | 'duplicate_found' | 'needs_human' | 'error';

export interface CheckRequestResult {
  status: CheckStatus;
  property_choices: Property[];
  matched_unit: { id: string; property_id: string; label: string } | null;
  open_jobs: RecentJob[];
  approved_contractors: Contractor[];
  evidence: RepairEvidence[];
  events: string[];
  error_code?: string | null;
}

export interface SessionResult {
  session_id: string;
  draft: RepairDraft | null;
  events: string[];
  recent_jobs: RecentJob[];
  properties: Property[];
  contractors: Contractor[];
}

export type DraftFields = Pick<RepairDraft,
  'property_id' | 'unit_id' | 'issue_summary' | 'category' | 'contractor_id' |
  'preferred_date' | 'access_notes' | 'contractor_message'>;

export interface VoiceConfig {
  available: boolean;
  message: string;
  max_duration_seconds: number;
}

export interface VoiceAccess {
  voice_session_id: string;
  signed_url: string;
  expires_at: string;
  max_duration_seconds: number;
  dynamic_variables: { secret__hearth_binding: string; hearth_context: string };
}
