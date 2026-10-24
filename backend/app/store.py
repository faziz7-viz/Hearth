"""Additive SQLite initialization and scoped read/write connections."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from time import sleep
from typing import TypeVar
from uuid import uuid4

T = TypeVar("T")
SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed.json"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "repairs.sqlite3"

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS seed_versions (version TEXT PRIMARY KEY)",
    "CREATE TABLE IF NOT EXISTS properties (id TEXT PRIMARY KEY, name TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS units (
        id TEXT PRIMARY KEY, property_id TEXT NOT NULL REFERENCES properties(id), label TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS contractors (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, trade TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS contractor_approvals (
        contractor_id TEXT REFERENCES contractors(id), property_id TEXT REFERENCES properties(id),
        PRIMARY KEY (contractor_id, property_id)
    )""",
    """CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, property_id TEXT NOT NULL REFERENCES properties(id),
        unit_id TEXT NOT NULL REFERENCES units(id), issue_summary TEXT NOT NULL,
        contractor_id TEXT NOT NULL REFERENCES contractors(id), category TEXT NOT NULL,
        status TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    "CREATE TABLE IF NOT EXISTS policies (id TEXT PRIMARY KEY, summary TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS maintenance_history (
        id TEXT PRIMARY KEY, property_id TEXT NOT NULL REFERENCES properties(id),
        unit_id TEXT NOT NULL REFERENCES units(id), category TEXT NOT NULL, summary TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, events_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS drafts (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
        revision INTEGER NOT NULL CHECK (revision >= 1), status TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE UNIQUE INDEX IF NOT EXISTS one_active_draft_per_session ON drafts(session_id)
        WHERE status NOT IN ('approved', 'cancelled')""",
    """CREATE TABLE IF NOT EXISTS draft_history (
        id INTEGER PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES drafts(id),
        revision INTEGER NOT NULL, event_type TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS work_orders (
        id TEXT PRIMARY KEY, draft_id TEXT NOT NULL UNIQUE REFERENCES drafts(id),
        approved_revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS approval_keys (
        idempotency_key TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES drafts(id),
        revision INTEGER NOT NULL, work_order_id TEXT NOT NULL REFERENCES work_orders(id)
    )""",
    """CREATE TABLE IF NOT EXISTS voice_sessions (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
        binding_hash TEXT NOT NULL UNIQUE, conversation_id TEXT NOT NULL,
        draft_id TEXT, expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
        grounded_property_id TEXT, grounded_unit_id TEXT, created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS voice_session_owner ON voice_sessions(session_id, revoked)",
)


class UnknownSession(Exception):
    pass


def is_temporary_read_error(error: sqlite3.OperationalError) -> bool:
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        return code & 0xFF in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
    return str(error).lower() in {
        "database is locked", "database is busy", "database table is locked", "database schema is locked"
    }


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @contextmanager
    def write_connection(self) -> Iterator[sqlite3.Connection]:
        # A competing approval waits for the first writer, then revalidates its commit.
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        seed = json.loads(SEED_PATH.read_text())
        # Serialize first starts. The marker and every seed record commit together.
        with self.write_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for statement in SCHEMA:
                db.execute(statement)
            if db.execute("SELECT 1 FROM seed_versions WHERE version = ?", (seed["seed_version"],)).fetchone():
                return
            for prop in seed["properties"]:
                db.execute("INSERT INTO properties VALUES (?, ?)", (prop["id"], prop["name"]))
                for unit in prop["units"]:
                    db.execute("INSERT INTO units VALUES (?, ?, ?)", (unit["id"], prop["id"], unit["label"]))
            for contractor in seed["contractors"]:
                db.execute("INSERT INTO contractors VALUES (?, ?, ?)", (
                    contractor["id"], contractor["name"], contractor["trade"]
                ))
                db.executemany("INSERT INTO contractor_approvals VALUES (?, ?)", [
                    (contractor["id"], property_id) for property_id in contractor["approved_property_ids"]
                ])
            db.executemany("""INSERT INTO jobs VALUES (
                :id, :property_id, :unit_id, :issue_summary, :contractor_id, :category, :status, :created_at
            )""", seed["jobs"])
            db.executemany("INSERT INTO policies VALUES (:id, :summary)", seed["policies"])
            db.executemany("""INSERT INTO maintenance_history VALUES (
                :id, :property_id, :unit_id, :category, :summary
            )""", seed["maintenance_history"])
            db.execute("INSERT INTO seed_versions VALUES (?)", (seed["seed_version"],))

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        # URI mode prevents accidentally recreating a missing database during a check.
        db = sqlite3.connect(f"{self.db_path.resolve().as_uri()}?mode=ro", uri=True, timeout=0.1)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA query_only = ON")
            db.execute("BEGIN")
            yield db
        finally:
            db.close()

    def read(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        # One retry for the entire snapshot, never one retry per tool.
        for attempt in range(2):
            try:
                with self.read_connection() as db:
                    return operation(db)
            except sqlite3.OperationalError as error:
                if attempt == 1 or not is_temporary_read_error(error):
                    raise
                sleep(0.05)
        raise AssertionError("unreachable")

    def create_session(self) -> str:
        session_id = str(uuid4())
        with self.write_connection() as db:
            db.execute("INSERT INTO sessions (id, created_at) VALUES (?, ?)", (
                session_id, datetime.now(timezone.utc).isoformat()
            ))
        return session_id

    def save_events(self, session_id: str, events: list[str]) -> None:
        with self.write_connection() as db:
            cursor = db.execute("UPDATE sessions SET events_json = ? WHERE id = ?", (
                json.dumps(events), session_id
            ))
            if cursor.rowcount != 1:
                raise UnknownSession(session_id)


def session_events(db: sqlite3.Connection, session_id: str) -> list[str]:
    session = db.execute("SELECT events_json FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise UnknownSession(session_id)
    return json.loads(session["events_json"])
