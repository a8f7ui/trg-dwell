"""
Load the synthetic sample data into a local database, so the backend and
dashboard can be developed and demonstrated with nothing real involved.

    .venv/bin/python -m backend.load_sample                 practice data only
    .venv/bin/python -m backend.load_sample --with-login    ...and a sign-in

On the sign-in
--------------
This used to create an account called `instructor` whose password was written
in this file, and it did so by default — so every path that loaded practice
data, including the one-command laptop demo, put a credential published on
GitHub onto whatever machine it ran on. That is fine on a laptop and quietly
disastrous on anything reachable from outside, and the difference between the
two is not visible from inside this function.

Now no password that appears in this repository is ever written to a database.
`--with-login` generates a fresh random one and prints it once; without the
flag, no account is created at all. `manage.py add-instructor` remains the way
to make a real one.
"""

from __future__ import annotations

import argparse
import csv
import json
import secrets
import sys
from pathlib import Path

from . import auth, config, course, db

SAMPLE_DIR = config.BASE_DIR / "data" / "sample"

# The username the practice sign-in uses. Generic on purpose — it is meant to
# be recognisable as "not a real person's account".
DEMO_USERNAME = "instructor"

# The credential earlier versions of this file created. Never created any more;
# kept only so `manage.py check-production` can recognise a database made by one
# of those versions and say so. Removing it would not remove the account from
# anybody's server — it would only stop us noticing it.
PUBLISHED_DEMO_LOGIN = ("instructor", "demo-password")


def make_demo_login(conn, password: str | None = None) -> str:
    """
    Create the practice sign-in with a password nobody else knows.

    Returns the password, which is the only time it exists in readable form —
    it is stored as a scrypt hash, so it cannot be recovered afterwards. Callers
    print it; nothing writes it to a file.
    """
    password = password or secrets.token_urlsafe(12)
    auth.create_instructor(conn, DEMO_USERNAME, password)
    db.audit(conn, "load_sample", "instructor_created",
             f"{DEMO_USERNAME} (practice sign-in, generated password)")
    return password

# Every participant invented by the generator carries this, and nothing else
# ever does. It is the only reliable way to tell a synthetic row from a real
# phone that registered.
SAMPLE_CONSENT_VERSION = "sample-data-v1"


class RealDataPresent(Exception):
    """Refusal to overwrite a database that belongs to a real course."""


def real_participant_count(conn) -> int:
    """How many participants came from an actual phone rather than the generator."""
    return conn.execute(
        "SELECT COUNT(*) AS n FROM participants "
        "WHERE consent_version IS NULL OR consent_version != ?",
        (SAMPLE_CONSENT_VERSION,)).fetchone()["n"]


def load(sample_dir: Path = SAMPLE_DIR, reset: bool = True,
         with_demo_login: bool = False, demo_password: str | None = None) -> dict:
    """
    Load the synthetic teaching data.

    `reset` wipes participants and their points first, which is correct for a
    demo and catastrophic for a course. Somebody once ran the setup command on a
    live server between the install links going out and the first upload
    arriving; three registered participants became zero, and an account whose
    password is published in this repository appeared on the server.

    So this now refuses, loudly, if the database holds anybody who registered
    from a real phone. Counting location points was the original test and it is
    not good enough: a participant exists from the moment they consent, which is
    hours before their first upload.

    `with_demo_login` defaults to off, and is the other half of the same story:
    creating a sign-in should be something a caller asks for, not something that
    happens because it forgot to say no. When asked for, the password is
    generated unless one is supplied, and returned under `demo_password`.
    """
    if not (sample_dir / "pings.csv").exists():
        raise SystemExit(
            f"No sample data found in {sample_dir}.\n"
            f"Generate it first:\n"
            f"  python3 tools/generate_sample_data.py --out data/sample")

    conn = db.connect()
    db.init_db(conn)

    if reset:
        real = real_participant_count(conn)
        if real:
            conn.close()
            raise RealDataPresent(
                f"This database has {real} participant(s) who registered from a "
                f"real phone.\n"
                f"Loading the example data would delete them and everything they "
                f"have collected.\n\n"
                f"Nothing has been changed.\n\n"
                f"If you genuinely want to erase this course and start over, use "
                f"the wipe control\non the dashboard's Data & teardown screen, or "
                f"run:  .venv/bin/python manage.py wipe")

    if reset:
        conn.execute("DELETE FROM pings")
        conn.execute("DELETE FROM participants")
        conn.execute("DELETE FROM places")
        conn.commit()

    # --- places (stand-in for OpenStreetMap data) --------------------------
    pois = json.loads((sample_dir / "pois.json").read_text())
    conn.executemany(
        "INSERT OR REPLACE INTO places (poi_id, name, kind, lat, lon) VALUES (?,?,?,?,?)",
        [(p["poi_id"], p["name"], p["kind"], p["lat"], p["lon"]) for p in pois])

    # --- observing infrastructure (cameras, readers, Wi-Fi, terminals) -----
    env_path = sample_dir / "environment.json"
    env_rows = []
    if env_path.exists():
        conn.execute("DELETE FROM environment_features")
        env_rows = [
            (f["feature_id"], f["kind"], f["lat"], f["lon"], f["name"], f["source"])
            for f in json.loads(env_path.read_text())
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO environment_features "
            "(feature_id, kind, lat, lon, name, source) VALUES (?,?,?,?,?,?)", env_rows)

    # --- participants ------------------------------------------------------
    people = json.loads((sample_dir / "participants.json").read_text())
    tokens: dict[str, str] = {}
    rows = []
    for i, p in enumerate(people, start=1):
        token, token_hash = auth.new_participant_token()
        tokens[p["participant_id"]] = token
        rows.append((
            p["participant_id"], f"Participant {i:02d}", p["device_model"],
            p["os_name"], p["os_version"], p["screen_w"], p["screen_h"],
            p["timezone"], p["language"], p["joined_at"],
            "sample-data-v1", p["joined_at"], token_hash,
        ))
    conn.executemany(
        "INSERT OR REPLACE INTO participants (participant_id, display_label, "
        "device_model, os_name, os_version, screen_w, screen_h, timezone, language, "
        "joined_at, consent_version, consented_at, token_hash) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    # --- location points ---------------------------------------------------
    # The day each point belongs to is worked out the same way as for a real
    # phone, rather than being taken from the first ten characters of the
    # timestamp. The sample file happens to carry local-offset timestamps, so
    # slicing them gives the right answer here and the wrong one for real
    # data — which is exactly how this bug survived so long.
    tz_name = course.get_location(conn)["timezone"]
    with (sample_dir / "pings.csv").open() as fh:
        ping_rows = [
            (r["participant_id"], r["session_id"], r["ts"], float(r["lat"]),
             float(r["lon"]), float(r["accuracy_m"]), int(r["battery_pct"]),
             r["connection"], r.get("collection_mode", "background"),
             db.local_day(r["ts"], tz_name),
             # received_at is set to when the point was taken, not to now.
             # Otherwise bulk-loading a week of history would look to the
             # monitoring panel like a sudden flood of live traffic.
             r["ts"])
            for r in csv.DictReader(fh)
        ]
    conn.executemany(
        "INSERT INTO pings (participant_id, session_id, ts, lat, lon, accuracy_m, "
        "battery_pct, connection, collection_mode, local_day, received_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", ping_rows)

    conn.execute(
        "UPDATE participants SET last_seen_at = "
        "(SELECT MAX(ts) FROM pings WHERE pings.participant_id = participants.participant_id)")

    created_password = make_demo_login(conn, demo_password) if with_demo_login else None
    conn.commit()
    db.audit(conn, "load_sample", "loaded_sample_data",
             f"{len(rows)} participants, {len(ping_rows)} points — all synthetic")
    conn.close()

    # Participant tokens are written next to the database so the mobile app and
    # the API examples can act as a real participant during development.
    token_file = Path(config.DB_PATH).parent / "sample_participant_tokens.json"
    token_file.write_text(json.dumps(tokens, indent=2) + "\n")

    summary = {
        "participants": len(rows),
        "pings": len(ping_rows),
        "places": len(pois),
        "environment": len(env_rows),
        "db": str(config.DB_PATH),
        "tokens": str(token_file),
    }
    if created_password:
        summary["demo_username"] = DEMO_USERNAME
        summary["demo_password"] = created_password
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load the synthetic practice data.")
    parser.add_argument(
        "--with-login", action="store_true",
        help="also create a practice sign-in with a generated password, "
             "printed once. Off by default: loading practice data should not "
             "silently put an account on a machine that might be public.")
    parser.add_argument(
        "--password-stdin", action="store_true",
        help="with --with-login, read the password from standard input instead "
             "of generating one. Used by the test harness, which needs to know "
             "it in advance. Not an argument, because arguments are visible to "
             "anybody who can run ps.")
    args = parser.parse_args(argv)

    password = None
    if args.password_stdin:
        if not args.with_login:
            parser.error("--password-stdin only makes sense with --with-login")
        password = sys.stdin.readline().rstrip("\n")

    result = load(with_demo_login=args.with_login, demo_password=password)
    print("Loaded synthetic sample data")
    for key, value in result.items():
        if key == "demo_password":
            continue
        print(f"  {key:14s}: {value}")

    if args.with_login and not args.password_stdin:
        print(f"\nPractice sign-in:  {result['demo_username']}  /  "
              f"{result['demo_password']}")
        print("Written down nowhere else — this is the only time it is shown.")
        print("Before hosting this anywhere, make your own:")
        print("  .venv/bin/python manage.py add-instructor <name>")
    elif not args.with_login:
        print("\nNo sign-in was created. To make one:")
        print("  .venv/bin/python manage.py add-instructor <name>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
