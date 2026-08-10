"""
Database schema and helpers.

Design notes that matter for privacy:

* There is no column anywhere for a participant's name, email address or phone
  number. Participants are identified by a random ID generated on their own
  device. The dashboard shows "Participant 03", not a person.
* There is no column for a street address. Earlier prototypes of this idea
  reverse-geocoded coordinates into postal addresses; that is exactly the
  behaviour this course teaches people to be wary of, so the backend does not
  do it. Stops are described by the *type* of place nearby, never by address.
* Deleting a participant cascades to their location data. Withdrawal is a real
  delete, not a flag.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA = """
PRAGMA journal_mode = WAL;

-- One row per person taking part. No names, no contact details.
CREATE TABLE IF NOT EXISTS participants (
    participant_id   TEXT PRIMARY KEY,
    display_label    TEXT NOT NULL,
    device_model     TEXT,
    os_name          TEXT,
    os_version       TEXT,
    screen_w         INTEGER,
    screen_h         INTEGER,
    timezone         TEXT,
    language         TEXT,
    joined_at        TEXT NOT NULL,
    consent_version  TEXT,
    consented_at     TEXT,
    withdrawn_at     TEXT,
    last_seen_at     TEXT,
    -- SHA-256 of the token held by that participant's phone. Storing the hash
    -- rather than the token means a stolen database file cannot be used to
    -- impersonate anybody's device.
    token_hash       TEXT UNIQUE
);

-- Location points. Note the absence of an address column.
CREATE TABLE IF NOT EXISTS pings (
    ping_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id TEXT NOT NULL
                   REFERENCES participants(participant_id) ON DELETE CASCADE,
    session_id     TEXT,
    ts             TEXT NOT NULL,
    lat            REAL NOT NULL,
    lon            REAL NOT NULL,
    accuracy_m     REAL,
    battery_pct    INTEGER,
    connection     TEXT,
    -- 'background' or 'foreground'. Recorded so a participant can be told what
    -- proportion of what the app knows about them was gathered while they were
    -- not looking at it. That figure is the single most persuasive number in
    -- the whole daily reveal.
    collection_mode TEXT,
    received_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pings_participant_ts ON pings(participant_id, ts);
CREATE INDEX IF NOT EXISTS idx_pings_ts ON pings(ts);

-- Reference data about places. In the sample dataset these are invented; in a
-- real deployment they come from OpenStreetMap. Used only to say "there is a
-- cafe here", never to identify a person.
CREATE TABLE IF NOT EXISTS places (
    poi_id TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    kind   TEXT NOT NULL,
    lat    REAL NOT NULL,
    lon    REAL NOT NULL
);

-- Instructor logins. Passwords are stored as scrypt hashes, never in the clear.
CREATE TABLE IF NOT EXISTS instructors (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- A record of consequential actions: withdrawals, wipes, logins. So that
-- "we deleted the data" is a checkable claim rather than a promise.
CREATE TABLE IF NOT EXISTS audit_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,
    actor  TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=0)
    conn.row_factory = sqlite3.Row
    # Without this, SQLite silently ignores the cascade deletes that make
    # withdrawal actually remove a participant's location history.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Add columns introduced after a database was first created.

    `CREATE TABLE IF NOT EXISTS` silently leaves an existing table alone, so
    without this an older course.db would fail with a confusing "no such column"
    error rather than simply working.
    """
    expected = {
        "pings": {"collection_mode": "TEXT"},
        "participants": {"token_hash": "TEXT"},
    }
    for table, columns in expected.items():
        present = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, coltype in columns.items():
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")


def audit(conn: sqlite3.Connection, actor: str, action: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (ts, actor, action, detail) VALUES (?, ?, ?, ?)",
        (now_iso(), actor, action, detail),
    )
    conn.commit()


def delete_participant(conn: sqlite3.Connection, participant_id: str, actor: str) -> int:
    """
    Remove a participant and every location point they contributed.

    Returns the number of location points deleted, so the caller can tell the
    person exactly what was removed rather than just saying "done".
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM pings WHERE participant_id = ?", (participant_id,)
    ).fetchone()
    ping_count = row["n"] if row else 0
    conn.execute("DELETE FROM pings WHERE participant_id = ?", (participant_id,))
    conn.execute("DELETE FROM participants WHERE participant_id = ?", (participant_id,))
    conn.commit()
    audit(conn, actor, "delete_participant",
          f"{participant_id}: {ping_count} location points deleted")
    return ping_count


def wipe_all_data(conn: sqlite3.Connection, actor: str) -> dict:
    """Teardown control: remove all participant data at the end of a course."""
    pings = conn.execute("SELECT COUNT(*) AS n FROM pings").fetchone()["n"]
    people = conn.execute("SELECT COUNT(*) AS n FROM participants").fetchone()["n"]
    conn.execute("DELETE FROM pings")
    conn.execute("DELETE FROM participants")
    conn.commit()
    audit(conn, actor, "wipe_all_data",
          f"{people} participants and {pings} location points deleted")
    return {"participants_deleted": people, "pings_deleted": pings}
