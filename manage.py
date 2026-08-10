#!/usr/bin/env python3
"""
Administrative commands for a course.

    python manage.py check-production               before going live: safety check
    python manage.py add-instructor <username>      create a teaching-team login
    python manage.py remove-instructor <username>   delete a login
    python manage.py list-instructors               who can log in
    python manage.py status                         what is currently stored
    python manage.py load-sample                    load the synthetic sample data
    python manage.py wipe                           delete ALL participant data
    python manage.py sweep                          delete data past its retention date
    python manage.py audit                          log of consequential actions

`wipe` is the teardown control: run it at the end of a course. It asks for
confirmation, and records what it deleted in the audit log.
"""

from __future__ import annotations

import getpass
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def cmd_check_production(_args: list[str]) -> None:
    """
    Check the things that are dangerous to get wrong on a public server.

    Written to be run by somebody who is not a developer, so every failure says
    what to do about it rather than only what is wrong.
    """
    from backend import load_sample

    problems: list[str] = []
    warnings: list[str] = []
    good: list[str] = []

    conn = db.connect()
    db.init_db(conn)

    # 1. Is there a real instructor account, and is the demo one gone?
    rows = conn.execute("SELECT username FROM instructors").fetchall()
    names = [r["username"] for r in rows]
    demo_user = load_sample.DEMO_INSTRUCTOR[0]
    if not names:
        problems.append(
            "There are no instructor accounts, so nobody can log in.\n"
            "     Fix: python manage.py add-instructor <your-name>")
    if demo_user in names:
        if auth.check_instructor(conn, demo_user, load_sample.DEMO_INSTRUCTOR[1]):
            problems.append(
                f"The demo account '{demo_user}' still exists WITH ITS PUBLISHED\n"
                f"     PASSWORD. Anyone who has read this project on GitHub can log in\n"
                f"     and watch your participants.\n"
                f"     Fix: python manage.py remove-instructor {demo_user}")
        else:
            warnings.append(
                f"An account named '{demo_user}' exists. Its password has been "
                f"changed, so this is not urgent, but a distinctive name is better.")
    if names and demo_user not in names:
        good.append(f"Instructor accounts exist ({', '.join(names)}) and none is the demo.")

    # 2. Is the session secret a real one?
    if os.getenv("WYPK_SECRET_KEY"):
        good.append("Session secret is set from the environment.")
    else:
        key_file = Path(config.DB_PATH).parent / "secret_key"
        if key_file.exists():
            good.append(f"Session secret was generated and stored at {key_file}.")
        else:
            warnings.append(
                "No session secret yet. One will be generated automatically the "
                "first time the server starts.")

    # 3. HTTPS
    if config.PUBLIC_URL.startswith("https://"):
        good.append(f"Public address is HTTPS ({config.PUBLIC_URL}); "
                    f"login cookies will be marked HTTPS-only.")
    elif config.PUBLIC_URL:
        problems.append(
            f"WYPK_PUBLIC_URL is '{config.PUBLIC_URL}', which is not HTTPS.\n"
            "     Participant tokens and instructor passwords would cross the "
            "network in the clear.\n"
            "     Fix: use the https:// address your host gave you.")
    else:
        warnings.append(
            "WYPK_PUBLIC_URL is not set. Set it to your server's https:// address "
            "so login cookies are marked HTTPS-only.")

    # 4. Is there sample data sitting in what is meant to be a real course?
    sample = conn.execute(
        "SELECT COUNT(*) AS n FROM participants WHERE consent_version = 'sample-data-v1'"
    ).fetchone()["n"]
    if sample:
        warnings.append(
            f"{sample} synthetic sample participants are still loaded. Real "
            f"participants would be mixed in with invented ones.\n"
            f"     Fix: python manage.py wipe")
    else:
        good.append("No synthetic sample data is loaded.")

    # 5. Can the database actually be written to?
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS _writecheck (x INTEGER)")
        conn.execute("DROP TABLE _writecheck")
        conn.commit()
        good.append(f"Database is writable at {config.DB_PATH}.")
    except Exception as exc:
        problems.append(f"The database cannot be written to: {exc}")

    conn.close()

    for line in good:
        print(f"  OK       {line}")
    for line in warnings:
        print(f"  WARNING  {line}")
    for line in problems:
        print(f"  PROBLEM  {line}")

    print()
    if problems:
        print(f"{len(problems)} problem(s) must be fixed before real participants "
              f"use this server.")
        raise SystemExit(1)
    print("No blocking problems found.")


def cmd_remove_instructor(args: list[str]) -> None:
    if not args:
        raise SystemExit("Usage: python manage.py remove-instructor <username>")
    conn = db.connect()
    db.init_db(conn)
    cur = conn.execute("DELETE FROM instructors WHERE username = ?", (args[0],))
    conn.commit()
    db.audit(conn, "manage.py", "instructor_removed", args[0])
    conn.close()
    print(f"Removed {cur.rowcount} account(s) named '{args[0]}'.")


COMMANDS = {
    "add-instructor": cmd_add_instructor,
    "remove-instructor": cmd_remove_instructor,
    "check-production": cmd_check_production,
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
