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
-- The index on local_day is created after the migration, not here: on a
-- database made before that column existed this script runs first, and an
-- index over a column that is not there yet is an error that would stop the
-- server starting at all.

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

-- Public infrastructure that can observe a person: cameras, plate readers,
-- mapped Wi-Fi, card terminals, transit gates. Describes PLACES, never people.
-- Used to show how a phone trail becomes corroborated — and therefore
-- undeniable — when other sources agree with it.
CREATE TABLE IF NOT EXISTS environment_features (
    feature_id TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    lat        REAL NOT NULL,
    lon        REAL NOT NULL,
    name       TEXT,
    source     TEXT
);

CREATE INDEX IF NOT EXISTS idx_env_kind ON environment_features(kind);

-- Instructor logins. Passwords are stored as scrypt hashes, never in the clear.
CREATE TABLE IF NOT EXISTS instructors (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- Failed login attempts, used to slow down password guessing. Without this,
-- somebody could try passwords against the instructor login as fast as the
-- network allows, and that login opens a map of where participants have been.
CREATE TABLE IF NOT EXISTS login_attempts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    username TEXT,
    ip       TEXT,
    ok       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_ts ON login_attempts(ts);

-- Instance settings that outlive a restart: currently the course location.
-- Deliberately key/value rather than a column per setting, because the
-- alternative is a migration every time the course needs to know one more
-- thing about itself.
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    updated TEXT NOT NULL
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
    # A generous busy timeout rather than the default five seconds. A whole
    # room registering at once is the normal case here, not an edge one — the
    # facilitator's guide tells them to install the app together — and a
    # participant whose registration fails is a participant who never joins.
    conn = sqlite3.connect(path, detect_types=0, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Without this, SQLite silently ignores the cascade deletes that make
    # withdrawal actually remove a participant's location history.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


# Which database files have had their schema checked in this process.
#
# Every request opens a connection, and it used to run the whole schema
# script, the migration and the index creation each time. That is wasted work
# on almost every request, and worse than wasted on the first few: switching
# the journal mode needs an exclusive lock, so thirty phones registering
# together against a new database fought over it and some got "database is
# locked" — which reaches the participant as a registration that simply failed.
#
# Keyed by path rather than a single flag, because the tests open several
# throwaway databases inside one process and each needs its own first time.
_SCHEMA_CHECKED: set[str] = set()


def init_db(conn: sqlite3.Connection, force: bool = False) -> None:
    """
    Make sure this database has the current schema.

    Cheap to call: after the first time for a given file in a given process it
    does nothing. `force` is for tests that want the work repeated.
    """
    path = _path_of(conn)
    if not force and path in _SCHEMA_CHECKED:
        return

    conn.executescript(SCHEMA)
    added = _migrate(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pings_local_day "
                 "ON pings(participant_id, local_day)")
    conn.commit()

    # Write-ahead logging lets readers carry on while somebody is writing,
    # which is what a live map does all day. Set here rather than in the schema
    # script so it is attempted once, when contention is least likely, and
    # tolerated if another connection is mid-write.
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass

    if "pings.local_day" in added:
        # The column has just appeared on a database that already holds points,
        # so every one of them has a NULL day. Fill them in once, here, rather
        # than leaving the reveal to quietly show nothing for older data.
        from . import course
        backfill_local_days(conn, course.get_location(conn)["timezone"])

    _SCHEMA_CHECKED.add(path)


def _path_of(conn: sqlite3.Connection) -> str:
    """The file a connection is attached to, or "" for in-memory ones."""
    try:
        for row in conn.execute("PRAGMA database_list"):
            if row[1] == "main":
                return str(row[2] or "")
    except sqlite3.Error:
        pass
    return ""


def _migrate(conn: sqlite3.Connection) -> set[str]:
    """
    Add columns introduced after a database was first created.

    `CREATE TABLE IF NOT EXISTS` silently leaves an existing table alone, so
    without this an older course.db would fail with a confusing "no such column"
    error rather than simply working.

    Returns the "table.column" names actually added, so a caller can do the
    one-off work that a new column implies.
    """
    added: set[str] = set()
    expected = {
        # The calendar date this point falls on *in the course's timezone*.
        #
        # Everything that groups by day reads this rather than slicing the
        # timestamp text. A phone sends UTC, so slicing gave UTC days: in
        # Milwaukee that filed everything after 19:00 under tomorrow, and the
        # 20:30 evening reveal showed about ninety minutes. It never surfaced in
        # testing because the sample generator writes local-offset timestamps
        # whose first ten characters happen to be the local date.
        "pings": {"collection_mode": "TEXT", "local_day": "TEXT"},
        "participants": {"token_hash": "TEXT"},
    }
    for table, columns in expected.items():
        present = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, coltype in columns.items():
            if name not in present:
                try:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
                except sqlite3.OperationalError as exc:
                    # Another connection added it between the check and the
                    # ALTER. Harmless, and it must not be an error: every
                    # request opens a connection and runs this, so on a fresh
                    # database a room registering together races here, and the
                    # losers were answering 500 to people trying to join.
                    if "duplicate column name" not in str(exc).lower():
                        raise
                else:
                    added.add(f"{table}.{name}")
    return added


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


# --------------------------------------------------------------------------
# Course-local days
# --------------------------------------------------------------------------

def local_day(ts: str | datetime, tz_name: str) -> str:
    """
    The calendar date a moment falls on where the course is happening.

    This exists because a day is a local idea and a timestamp is not. Phones
    send UTC; a course in Milwaukee runs on Central time; and the difference is
    the whole evening. Getting it wrong splits every participant's day at 19:00
    and makes the evening reveal — the centrepiece of the week — show the last
    ninety minutes of it.

    DST is handled by zoneinfo rather than a fixed offset, so a course spanning
    the change still gets correct days on both sides of it.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if isinstance(ts, str):
        try:
            moment = datetime.fromisoformat(ts)
        except ValueError:
            return ts[:10]
    else:
        moment = ts
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = timezone.utc
    return moment.astimezone(zone).date().isoformat()


def backfill_local_days(conn: sqlite3.Connection, tz_name: str) -> int:
    """
    Fill in local_day for rows recorded before this column existed, and for any
    row whose timezone has since changed.

    Run whenever the course location is set, because moving a course to another
    timezone changes which day every existing point belongs to.
    """
    rows = conn.execute("SELECT ping_id, ts, local_day FROM pings").fetchall()
    updates = []
    for row in rows:
        correct = local_day(row["ts"], tz_name)
        if row["local_day"] != correct:
            updates.append((correct, row["ping_id"]))
    if updates:
        conn.executemany(
            "UPDATE pings SET local_day = ? WHERE ping_id = ?", updates)
        conn.commit()
    return len(updates)
