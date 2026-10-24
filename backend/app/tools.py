"""Deterministic record reads; no models, external services, or business writes."""

import re
import sqlite3

from .models import (
    Contractor, MaintenanceContext, Property, PropertyLookupResult, RecentJob, RepairEvidence
)


def normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_unit(value: str) -> str:
    return re.sub(r"^unit\s+", "", normalize(value))


def issue_tokens(summary: str) -> set[str]:
    aliases = {
        "faucet": "tap", "faucets": "tap", "taps": "tap", "leaking": "leak", "leaks": "leak",
        "dripping": "leak", "drip": "leak", "blocked": "block", "clogged": "block",
        "lights": "light", "pipes": "pipe", "doors": "door", "sockets": "socket",
    }
    stopwords = {"a", "an", "the", "is", "has", "at", "in", "of", "and", "to", "with", "repair", "please"}
    return {aliases.get(word, word) for word in re.findall(r"[a-z0-9]+", summary.casefold())} - stopwords


def related_issue(requested: str, existing: str) -> bool:
    """Conservative potential duplicates from explicit issue words, not trade alone.

    Different named rooms or fixtures prevent a match. For known fixtures, require
    another shared detail (room or symptom). This small lexical rule is deliberately
    not a general natural-language repair classifier.
    """
    left, right = issue_tokens(requested), issue_tokens(existing)
    if not left or not right:
        return False
    if left == right:
        return True
    rooms = {"kitchen", "bathroom", "hallway", "bedroom", "living", "balcony", "garage"}
    fixtures = {"tap", "toilet", "sink", "pipe", "shower", "radiator", "light", "socket", "switch", "door", "cupboard", "window"}
    for group in (rooms, fixtures):
        left_features, right_features = left & group, right & group
        if left_features and right_features and not left_features & right_features:
            return False
    common = left & right
    if common & fixtures:
        return len(common) >= 2
    return len(common) >= 2 and len(common) / len(left | right) >= 0.6


class RecordTools:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def properties(self) -> list[Property]:
        units = self.db.execute("SELECT id, property_id, label FROM units ORDER BY id").fetchall()
        return [Property(
            id=row["id"], name=row["name"],
            units=[{"id": unit["id"], "label": unit["label"]} for unit in units if unit["property_id"] == row["id"]],
        ) for row in self.db.execute("SELECT id, name FROM properties ORDER BY name")]

    def contractors(self) -> list[Contractor]:
        approvals = self.db.execute("SELECT contractor_id, property_id FROM contractor_approvals ORDER BY property_id").fetchall()
        return [Contractor(
            **dict(row), approved_property_ids=[
                approval["property_id"] for approval in approvals if approval["contractor_id"] == row["id"]
            ],
        ) for row in self.db.execute("SELECT id, name, trade FROM contractors ORDER BY name")]

    def recent_jobs(self) -> list[RecentJob]:
        return [RecentJob(**dict(row)) for row in self.db.execute("SELECT * FROM jobs ORDER BY created_at DESC, id")]

    def lookup_property(self, query: str, unit_label: str = "") -> PropertyLookupResult:
        properties = self.properties()
        query = normalize(query)
        if query:
            exact = [prop for prop in properties if query in {normalize(prop.id), normalize(prop.name)}]
            # Literal Python substring matching does not interpret SQL % or _ patterns.
            matches = exact or [prop for prop in properties if query in normalize(prop.name)]
        elif normalize_unit(unit_label):
            matches = [prop for prop in properties if any(
                normalize_unit(unit.label) == normalize_unit(unit_label) for unit in prop.units
            )]
        else:
            matches = properties
        return PropertyLookupResult(properties=matches)

    def check_open_jobs(self, unit_id: str, category: str, issue_summary: str) -> list[RecentJob]:
        rows = self.db.execute(
            "SELECT * FROM jobs WHERE unit_id = ? AND category = ? AND status IN ('open', 'approved') ORDER BY created_at DESC, id",
            (unit_id, category),
        )
        return [RecentJob(**dict(row)) for row in rows if related_issue(issue_summary, row["issue_summary"])]

    def lookup_maintenance_context(self, unit_id: str, category: str) -> MaintenanceContext:
        unit = self.db.execute("SELECT property_id FROM units WHERE id = ?", (unit_id,)).fetchone()
        if unit is None:
            return MaintenanceContext(evidence=[], approved_contractors=[])
        evidence = [RepairEvidence(source_type="policy", record_id=row["id"], summary=row["summary"])
                    for row in self.db.execute("SELECT id, summary FROM policies ORDER BY id")]
        evidence.extend(RepairEvidence(source_type="maintenance_history", record_id=row["id"], summary=row["summary"])
                        for row in self.db.execute(
                            "SELECT id, summary FROM maintenance_history WHERE unit_id = ? AND category = ? ORDER BY id",
                            (unit_id, category),
                        ))
        approved = [contractor for contractor in self.contractors()
                    if contractor.trade == category and unit["property_id"] in contractor.approved_property_ids]
        evidence.extend(RepairEvidence(
            source_type="contractor", record_id=contractor.id,
            summary=f"{contractor.name} is approved for {category} at this property. Availability has not been checked.",
        ) for contractor in approved)
        return MaintenanceContext(evidence=evidence, approved_contractors=approved)
