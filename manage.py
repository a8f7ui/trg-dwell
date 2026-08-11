#!/usr/bin/env python3
"""
Administrative commands for a course.

    python manage.py check-production               before going live: safety check
    python manage.py add-instructor <username>      create a teaching-team login
    python manage.py remove-instructor <username>   delete a login
    python manage.py list-instructors               who can log in
    python manage.py status                         what is currently stored
    python manage.py where                          where the course is being taught
    python manage.py set-location <place> [...]     move the course to another city
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

from backend import auth, config, course, db


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
    try:
        for r in rows:
            print(f"  {r['ts']}  {r['actor']:24s} {r['action']:22s} {r['detail']}")
    except BrokenPipeError:
        # Piping into `head`, or quitting a pager, closes the output early.
        # That is normal and should not print a traceback at somebody.
        pass


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
    if os.getenv("DWELL_SECRET_KEY"):
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
            f"DWELL_PUBLIC_URL is '{config.PUBLIC_URL}', which is not HTTPS.\n"
            "     Participant tokens and instructor passwords would cross the "
            "network in the clear.\n"
            "     Fix: use the https:// address your host gave you.")
    else:
        warnings.append(
            "DWELL_PUBLIC_URL is not set. Set it to your server's https:// address "
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

    # 5. Is the course anchored where it is actually being taught?
    loc = course.get_location(conn)
    if loc["is_default"]:
        warnings.append(
            "The course location is still the built-in default "
            "(Milwaukee, Wisconsin).\n"
            "     If that is where you are teaching, ignore this. If not, the "
            "dashboard will\n"
            "     open on the wrong city and every time will be shown in the "
            "wrong zone.\n"
            "     Fix: python manage.py set-location \"Your City, State\" "
            "--timezone America/...")
    else:
        good.append(f"Course location is set to {loc['name']} "
                    f"({loc['timezone']}).")

    # 6. Can the database actually be written to?
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


def cmd_where(_args: list[str]) -> None:
    """Where the course is currently anchored."""
    conn = db.connect()
    db.init_db(conn)
    loc = course.get_location(conn)
    conn.close()
    print(f"\n  {loc['name']}")
    print(f"  {loc['lat']}, {loc['lon']}   zoom {loc['zoom']}")
    print(f"  Times shown in {loc['timezone']}")
    if loc["is_default"]:
        print("\n  This is the built-in default, not something anybody chose.")
        print("  If the course is not in Milwaukee, set it:")
        print("      python manage.py set-location \"Cincinnati, Ohio\" "
              "--timezone America/New_York")
    print()


def cmd_set_location(args: list[str]) -> None:
    """
    Move the course. Either look up a place name, or give coordinates.

        python manage.py set-location "Cincinnati, Ohio" \\
            --timezone America/New_York
        python manage.py set-location "Cincinnati" --at 39.1031,-84.5120 \\
            --timezone America/New_York
        python manage.py set-location --reset

    The timezone cannot be looked up from a place name — nothing in a geocoding
    response knows one — so it is asked for rather than guessed. Guessing it
    would show every time in the course an hour out for half the year.
    """
    conn = db.connect()
    db.init_db(conn)

    if "--reset" in args:
        loc = course.reset_location(conn)
        db.audit(conn, "cli", "course_location_set", "reset to default")
        conn.commit()
        conn.close()
        print(f"\n  Reset to {loc['name']} ({loc['timezone']}).\n")
        return

    positional = [a for a in args if not a.startswith("--")]
    flags = {}
    for i, a in enumerate(args):
        if a.startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            flags[a] = args[i + 1]

    if not positional:
        conn.close()
        print(cmd_set_location.__doc__)
        raise SystemExit(1)

    name = positional[0]
    current = course.get_location(conn)
    tz_name = flags.get("--timezone", current["timezone"])

    if "--at" in flags:
        try:
            lat_s, lon_s = flags["--at"].split(",")
            lat, lon = float(lat_s), float(lon_s)
        except ValueError:
            conn.close()
            print("  --at must look like 39.1031,-84.5120")
            raise SystemExit(1)
    else:
        print(f"  Looking up '{name}' ...")
        try:
            results = course.geocode(name)
        except course.LocationError as exc:
            conn.close()
            print(f"\n  {exc}\n")
            print("  To skip the lookup entirely:")
            print(f"      python manage.py set-location \"{name}\" "
                  f"--at LAT,LON --timezone {tz_name}\n")
            raise SystemExit(1)
        # More than one match is normal — there are Cincinnatis in several
        # states. Show them rather than silently taking the first.
        if len(results) > 1:
            print("\n  Several matches. Re-run with --at to pick one:\n")
            for r in results:
                print(f"      --at {r['lat']},{r['lon']}   {r['name']}")
            conn.close()
            print()
            raise SystemExit(1)
        name, lat, lon = results[0]["short_name"], results[0]["lat"], results[0]["lon"]

    try:
        loc = course.set_location(conn, name, lat, lon, tz_name)
    except course.LocationError as exc:
        conn.close()
        print(f"\n  {exc}\n")
        raise SystemExit(1)

    db.audit(conn, "cli", "course_location_set",
             f"{loc['name']} ({loc['lat']}, {loc['lon']})")
    conn.commit()
    conn.close()

    print(f"\n  Course location set to {loc['name']}")
    print(f"  {loc['lat']}, {loc['lon']}   times in {loc['timezone']}")
    if "--timezone" not in flags:
        print(f"\n  Timezone left as {loc['timezone']} — pass --timezone if that "
              f"is wrong for\n  this city, or every time shown will be off.")
    print("\n  The dashboard will open here from now on. To regenerate sample")
    print("  data for the new city:")
    print("      python3 tools/generate_sample_data.py --use-course-location "
          "--out data/sample")
    print("      python -m backend.load_sample\n")


COMMANDS = {
    "add-instructor": cmd_add_instructor,
    "where": cmd_where,
    "set-location": cmd_set_location,
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
