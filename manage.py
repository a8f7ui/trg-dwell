#!/usr/bin/env python3
"""
Administrative commands for a course.

    python manage.py add-instructor <username>   create a teaching-team login
    python manage.py list-instructors            who can log in
    python manage.py load-sample                 load the synthetic sample data
    python manage.py status                      what is currently stored
    python manage.py wipe                        delete ALL participant data
    python manage.py sweep                       delete data past its retention date
    python manage.py audit                       show the log of consequential actions

`wipe` is the teardown control: run it at the end of a course. It asks for
confirmation, and records what it deleted in the audit log.
"""

from __future__ import annotations

import getpass
import sys
from datetime import datetime, timedelta, timezone

from backend import auth, config, db


def cmd_add_instructor(args: list[str]) -> None:
    if not args:
        raise SystemExit("Usage: python manage.py add-instructor <username>")
    username = args[0]
    password = getpass.getpass(f"Password for {username}: ")
    if len(password) < 10:
        raise SystemExit("Please use a password of at least 10 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords did not match.")

    conn = db.connect()
    db.init_db(conn)
    auth.create_instructor(conn, username, password)
    db.audit(conn, "manage.py", "instructor_created", username)
    conn.close()
    print(f"Instructor '{username}' created.")


def cmd_list_instructors(_args: list[str]) -> None:
    conn = db.connect()
    db.init_db(conn)
    rows = conn.execute(
        "SELECT username, created_at FROM instructors ORDER BY username").fetchall()
    conn.close()
    if not rows:
        print("No instructor accounts yet. Create one with:")
        print("  python manage.py add-instructor <username>")
        return
    for r in rows:
        print(f"  {r['username']:20s} created {r['created_at']}")


def cmd_load_sample(_args: list[str]) -> None:
    from backend import load_sample
    result = load_sample.load()
    for key, value in result.items():
        print(f"  {key:14s}: {value}")
    print(f"\nDemo login: {load_sample.DEMO_INSTRUCTOR[0]} / "
          f"{load_sample.DEMO_INSTRUCTOR[1]}")


def cmd_status(_args: list[str]) -> None:
    conn = db.connect()
    db.init_db(conn)
    people = conn.execute("SELECT COUNT(*) AS n FROM participants").fetchone()["n"]
    pings = conn.execute("SELECT COUNT(*) AS n FROM pings").fetchone()["n"]
    span = conn.execute("SELECT MIN(ts) AS a, MAX(ts) AS b FROM pings").fetchone()
    instructors = conn.execute("SELECT COUNT(*) AS n FROM instructors").fetchone()["n"]
    conn.close()
    print(f"  database        : {config.DB_PATH}")
    print(f"  participants    : {people}")
    print(f"  location points : {pings}")
    print(f"  earliest point  : {span['a'] or '—'}")
    print(f"  latest point    : {span['b'] or '—'}")
    print(f"  instructors     : {instructors}")
    print(f"  retention       : {config.RETENTION_DAYS} days")
    print(f"  k-anonymity     : {config.K_ANONYMITY_THRESHOLD}")


def cmd_wipe(_args: list[str]) -> None:
    conn = db.connect()
    db.init_db(conn)
    people = conn.execute("SELECT COUNT(*) AS n FROM participants").fetchone()["n"]
    pings = conn.execute("SELECT COUNT(*) AS n FROM pings").fetchone()["n"]
    print(f"This will permanently delete {people} participants and {pings} location "
          f"points.")
    if input('Type "DELETE ALL DATA" to confirm: ') != "DELETE ALL DATA":
        conn.close()
        raise SystemExit("Cancelled. Nothing was deleted.")
    result = db.wipe_all_data(conn, actor="manage.py")
    conn.close()
    print(f"Deleted {result['participants_deleted']} participants and "
          f"{result['pings_deleted']} location points.")


def cmd_sweep(_args: list[str]) -> None:
    """Delete anything older than the retention window."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=config.RETENTION_DAYS)).isoformat()
    conn = db.connect()
    db.init_db(conn)
    n = conn.execute("SELECT COUNT(*) AS n FROM pings WHERE ts < ?",
                     (cutoff,)).fetchone()["n"]
    conn.execute("DELETE FROM pings WHERE ts < ?", (cutoff,))
    conn.commit()
    db.audit(conn, "manage.py", "retention_sweep",
             f"{n} points older than {cutoff} deleted")
    conn.close()
    print(f"Deleted {n} location points older than {config.RETENTION_DAYS} days.")


def cmd_audit(_args: list[str]) -> None:
    conn = db.connect()
    db.init_db(conn)
    rows = conn.execute(
        "SELECT ts, actor, action, detail FROM audit_log ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    for r in rows:
        print(f"  {r['ts']}  {r['actor']:24s} {r['action']:22s} {r['detail']}")


COMMANDS = {
    "add-instructor": cmd_add_instructor,
    "list-instructors": cmd_list_instructors,
    "load-sample": cmd_load_sample,
    "status": cmd_status,
    "wipe": cmd_wipe,
    "sweep": cmd_sweep,
    "audit": cmd_audit,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        raise SystemExit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
