"""Validated record-check and persisted repair workflow API contracts."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RepairCategory = Literal["plumbing", "electrical", "general"]
DraftStatus = Literal[
    "needs_info", "duplicate_found", "needs_human", "ready_for_review", "approved", "cancelled"
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepairEvidence(ContractModel):
    source_type: str
    record_id: str
    summary: str


class RepairDraft(ContractModel):
    id: str
    session_id: str
    revision: int = Field(strict=True, ge=1)
    property_id: str | None = None
    unit_id: str | None = None
    issue_summary: str
    category: RepairCategory | None = None
    contractor_id: str | None = None
    preferred_date: str | None = None
    access_notes: str
    contractor_message: str
    missing_fields: list[str]
    review_reasons: list[str] = Field(default_factory=list)
    evidence: list[RepairEvidence]
    status: DraftStatus


class AgentTurnResult(ContractModel):
    session_id: str
    reply: str
    draft: RepairDraft | None = None
    events: list[str]
    error_code: str | None = None


class WorkOrder(ContractModel):
    id: str
    draft_id: str
    approved_revision: int = Field(strict=True, ge=1)
    snapshot: RepairDraft
    created_at: str


class Unit(ContractModel):
    id: str
    label: str


class MatchedUnit(Unit):
    property_id: str


class Property(ContractModel):
    id: str
    name: str
    units: list[Unit]


class Contractor(ContractModel):
    id: str
    name: str
    trade: RepairCategory
    approved_property_ids: list[str]


class RecentJob(ContractModel):
    id: str
    property_id: str
    unit_id: str
    issue_summary: str
    contractor_id: str
    category: RepairCategory
    status: Literal["open", "completed", "approved"]
    created_at: str


class SessionCreated(ContractModel):
    session_id: str


class SessionState(SessionCreated):
    draft: RepairDraft | None = None
    events: list[str]
    recent_jobs: list[RecentJob]
    properties: list[Property]
    contractors: list[Contractor]


class CheckRequestInput(ContractModel):
    session_id: str = Field(min_length=1, max_length=100)
    property_query: str = Field(max_length=200)
    unit_label: str = Field(max_length=100)
    # Unsupported categories are a useful human-review result, not a parsing failure.
    category: str = Field(max_length=100)
    issue_summary: str = Field(max_length=2000)


class CheckRequestResult(ContractModel):
    status: Literal[
        "matched", "unknown_property", "ambiguous_property", "duplicate_found", "needs_human", "error"
    ]
    property_choices: list[Property] = Field(default_factory=list)
    matched_unit: MatchedUnit | None = None
    open_jobs: list[RecentJob] = Field(default_factory=list)
    approved_contractors: list[Contractor] = Field(default_factory=list)
    evidence: list[RepairEvidence] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    error_code: str | None = None


class PropertyLookupResult(ContractModel):
    properties: list[Property]


class MaintenanceContext(ContractModel):
    evidence: list[RepairEvidence]
    approved_contractors: list[Contractor]


class DraftFields(ContractModel):
    """Only landlord-editable content; defaults also allow incomplete drafts."""

    property_id: str | None = Field(default=None, max_length=100)
    unit_id: str | None = Field(default=None, max_length=100)
    issue_summary: str = Field(default="", max_length=2000)
    category: RepairCategory | None = None
    contractor_id: str | None = Field(default=None, max_length=100)
    preferred_date: str | None = None
    access_notes: str = Field(default="", max_length=4000)
    contractor_message: str | None = Field(default=None, max_length=8000)

    @field_validator("preferred_date")
    @classmethod
    def validate_requested_date(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Requested date must use YYYY-MM-DD.")
        return value


class DraftEditFields(DraftFields):
    # Null generates a message only on creation. Later saves preserve explicit text.
    contractor_message: str = Field(default="", max_length=8000)


class DraftCreateRequest(ContractModel):
    session_id: str = Field(min_length=1, max_length=100)
    fields: DraftFields


class DraftRevisionRequest(ContractModel):
    session_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(strict=True, ge=1)


class DraftEditRequest(DraftRevisionRequest):
    fields: DraftEditFields


class DraftApproveRequest(DraftRevisionRequest):
    idempotency_key: str = Field(min_length=1, max_length=200, pattern=r"\S")
