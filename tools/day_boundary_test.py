#!/usr/bin/env python3
"""
Days belong to the course, not to UTC.

    python3 tools/day_boundary_test.py

Checks the parts of that claim which have nothing to do with the network, so
they can be tested without starting a server: the migration of a database made
before the course knew about local days, what happens when a course moves to
another timezone, and daylight saving.

The fault being guarded against
-------------------------------
A phone reports UTC. A course happens somewhere. Milwaukee is five hours behind
UTC in September, so a day that runs until 21:00 there spans two UTC dates —
and the backend used to take the day from the first ten characters of the
timestamp. One day of somebody's life arrived as two, and the evening reveal,
which shows the most recent day, showed only what happened after 19:00.

Runs entirely on a temporary database. Nothing real is touched.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

failures: list[str] = []


def check(name: str, got, expected) -> None:
    if got == expected:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}\n          expected {expected!r}\n          got      {got!r}")
        failures.append(name)


def build_old_database(path: Path) -> None:
    """A course.db as the version before local days would have written it."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE participants (
            participant_id TEXT PRIMARY KEY, display_label TEXT NOT NULL,
            device_model TEXT, os_name TEXT, os_version TEXT, screen_w INTEGER,
            screen_h INTEGER, timezone TEXT, language TEXT, joined_at TEXT NOT NULL,
            consent_version TEXT, consented_at TEXT, withdrawn_at TEXT,
            last_seen_at TEXT);
        CREATE TABLE pings (
            ping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT NOT NULL, session_id TEXT, ts TEXT NOT NULL,
            lat REAL NOT NULL, lon REAL NOT NULL, accuracy_m REAL,
            battery_pct INTEGER, connection TEXT, received_at TEXT NOT NULL);
    """)
    conn.execute("INSERT INTO participants (participant_id, display_label, joined_at) "
                 "VALUES ('p_001', 'Participant 01', '2026-09-15T08:00:00+00:00')")
    # Afternoon and two evening points. In Milwaukee all three are Tuesday the
    # 15th; in UTC the last two are already Wednesday the 16th.
    for ts in ("2026-09-15T16:00:00+00:00",
               "2026-09-16T01:30:00+00:00",
               "2026-09-16T02:40:00+00:00"):
        conn.execute("INSERT INTO pings (participant_id, ts, lat, lon, received_at) "
                     "VALUES ('p_001', ?, 43.0389, -87.9065, ?)", (ts, ts))
    conn.commit()
    conn.close()


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="dwell-days-"))
    db_path = work / "course.db"
    os.environ["DWELL_DB"] = str(db_path)

    from backend import course, db

    print("\n  Days belong to the course, not to UTC\n")
    try:
        build_old_database(db_path)
        conn = db.connect(db_path)

        # Opening an older database should add the column and fill it in. If it
        # did not, every point already collected would have no day at all.
        db.init_db(conn)
        days = sorted({r["local_day"] for r in
                       conn.execute("SELECT local_day FROM pings")})
        check("an older database is migrated and its days filled in",
              days, ["2026-09-15"])

        # Moving the course changes which day the existing points belong to.
        course.set_location(conn, "Berlin, Germany", 52.52, 13.405, "Europe/Berlin")
        days = sorted({r["local_day"] for r in
                       conn.execute("SELECT local_day FROM pings")})
        check("moving the course to Berlin re-files the days",
              days, ["2026-09-15", "2026-09-16"])

        course.reset_location(conn)
        days = sorted({r["local_day"] for r in
                       conn.execute("SELECT local_day FROM pings")})
        check("resetting the location puts them back", days, ["2026-09-15"])

        # Daylight saving, either side of the change. A fixed -6 offset would
        # get the first of these wrong.
        check("the day before the clocks change (CDT, UTC-5)",
              db.local_day("2026-10-31T04:30:00+00:00", "America/Chicago"),
              "2026-10-30")
        check("the day after the clocks change (CST, UTC-6)",
              db.local_day("2026-11-02T04:30:00+00:00", "America/Chicago"),
              "2026-11-01")

        # A timestamp with no zone marker is treated as UTC, which is what a
        # phone means by it. A timestamp that is not a timestamp falls back to
        # its first ten characters rather than raising, because losing one
        # malformed point is better than losing the request it arrived in.
        check("a bare timestamp is read as UTC",
              db.local_day("2026-09-16T01:30:00", "America/Chicago"), "2026-09-15")
        check("an unparseable timestamp does not raise",
              db.local_day("not-a-timestamp", "America/Chicago"), "not-a-time")
        check("an unknown timezone falls back to UTC rather than failing",
              db.local_day("2026-09-16T01:30:00+00:00", "Mars/Olympus"),
              "2026-09-16")

        conn.close()
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if failures:
        print(f"  {len(failures)} check(s) FAILED\n")
        return 1
    print("  All day-boundary checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
