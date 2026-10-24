"""Milestone 2 read workflow; returns checks only, never a repair draft."""

import re
import sqlite3

from .models import CheckRequestInput, CheckRequestResult, MatchedUnit, RepairEvidence
from .store import session_events
from .tools import RecordTools, normalize, normalize_unit

SAFETY_PATTERN = re.compile(
    r"\b(sparks?|smoke|fire|flooding|gas leak|gas smell|smell (?:of )?gas|burning smell|exposed wires?|carbon monoxide)\b",
    re.IGNORECASE,
)


def check_request(db: sqlite3.Connection, request: CheckRequestInput) -> CheckRequestResult:
    session_events(db, request.session_id)
    if SAFETY_PATTERN.search(request.issue_summary):
        return CheckRequestResult(
            status="needs_human", error_code="safety_concern",
            events=["Possible urgent safety concern. A person must review this request before routine repair coordination."],
        )
    tools = RecordTools(db)
    properties = tools.lookup_property(request.property_query, request.unit_label).properties
    if not properties:
        return CheckRequestResult(
            status="unknown_property", error_code="unknown_property",
            events=["No property matched the supplied property and unit details. Check the property selection."],
        )
    if len(properties) > 1:
        return CheckRequestResult(
            status="ambiguous_property", property_choices=properties, error_code="ambiguous_property",
            events=[f"{len(properties)} properties match. Select a property before checking its jobs."],
        )

    prop = properties[0]
    result = CheckRequestResult(status="matched", property_choices=[prop], events=[f"Property found: {prop.name}."])
    unit = next((unit for unit in prop.units if normalize_unit(unit.label) == normalize_unit(request.unit_label)), None)
    if unit is None:
        result.status = "needs_human"
        result.error_code = "unknown_unit"
        result.events.append("Unit not found at the selected property. Check the unit label with a person.")
        return result
    result.matched_unit = MatchedUnit(**unit.model_dump(), property_id=prop.id)
    result.evidence.append(RepairEvidence(
        source_type="property", record_id=unit.id, summary=f"{prop.name} contains {unit.label}.",
    ))
    result.events.append(f"Unit found: {unit.label}.")
    if not request.issue_summary.strip():
        result.status = "needs_human"
        result.error_code = "missing_issue"
        result.events.append("Issue details are missing. Add the repair details before checking records.")
        return result
    category = normalize(request.category)
    if category not in {"plumbing", "electrical", "general"}:
        result.status = "needs_human"
        result.error_code = "unsupported_category"
        result.events.append("This repair category is unsupported. A person must identify an appropriate approved contractor.")
        return result

    result.open_jobs = tools.check_open_jobs(unit.id, category, request.issue_summary)
    result.events.append("Potential duplicate open job found." if result.open_jobs else "No matching open job found for these issue details.")
    result.evidence.extend(RepairEvidence(
        source_type="open_job", record_id=job.id, summary=f"{job.status.capitalize()} job: {job.issue_summary}.",
    ) for job in result.open_jobs)
    context = tools.lookup_maintenance_context(unit.id, category)
    result.approved_contractors = context.approved_contractors
    result.evidence.extend(context.evidence)
    result.events.append("Maintenance policy and relevant history checked.")
    result.events.append(
        f"{len(context.approved_contractors)} approved contractor(s) found; availability has not been checked."
        if context.approved_contractors else "No approved contractor found for this trade at this property."
    )
    if result.open_jobs:
        result.status = "duplicate_found"
        result.error_code = "duplicate_found"
        result.events.append("Review the existing job with a person before creating another repair.")
    elif not context.approved_contractors:
        result.status = "needs_human"
        result.error_code = "no_approved_contractor"
    return result
