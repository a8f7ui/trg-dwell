"""
Load the synthetic sample data into a local database, so the backend and
dashboard can be developed and demonstrated with nothing real involved.

    python -m backend.load_sample

Also creates a demo instructor login. That account uses a well-known password
and is fine for a laptop demo, but `manage.py add-instructor` should be used to
create a real one before this is ever hosted anywhere.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from . import auth, config, db

SAMPLE_DIR = config.BASE_DIR / "data" / "sample"

DEMO_INSTRUCTOR = ("instructor", "demo-password")


def load(sample_dir: Path = SAMPLE_DIR, reset: bool = True) -> dict:
    if not (sample_dir / "pings.csv").exists():
        raise SystemExit(
            f"No sample data found in {sample_dir}.\n"
            f"Generate it first:\n"
            f"  python3 tools/generate_sample_data.py --out data/sample")

    conn = db.connect()
    db.init_db(conn)

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
    with (sample_dir / "pings.csv").open() as fh:
        ping_rows = [
            (r["participant_id"], r["session_id"], r["ts"], float(r["lat"]),
             float(r["lon"]), float(r["accuracy_m"]), int(r["battery_pct"]),
             r["connection"], r.get("collection_mode", "background"),
             # received_at is set to when the point was taken, not to now.
             # Otherwise bulk-loading a week of history would look to the
             # monitoring panel like a sudden flood of live traffic.
             r["ts"])
            for r in csv.DictReader(fh)
        ]
    conn.executemany(
        "INSERT INTO pings (participant_id, session_id, ts, lat, lon, accuracy_m, "
        "battery_pct, connection, collection_mode, received_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", ping_rows)

    conn.execute(
        "UPDATE participants SET last_seen_at = "
        "(SELECT MAX(ts) FROM pings WHERE pings.participant_id = participants.participant_id)")

    auth.create_instructor(conn, *DEMO_INSTRUCTOR)
    conn.commit()
    db.audit(conn, "load_sample", "loaded_sample_data",
             f"{len(rows)} participants, {len(ping_rows)} points — all synthetic")
    conn.close()

    # Participant tokens are written next to the database so the mobile app and
    # the API examples can act as a real participant during development.
    token_file = Path(config.DB_PATH).parent / "sample_participant_tokens.json"
    token_file.write_text(json.dumps(tokens, indent=2) + "\n")

    return {
        "participants": len(rows),
        "pings": len(ping_rows),
        "places": len(pois),
        "environment": len(env_rows),
        "db": str(config.DB_PATH),
        "tokens": str(token_file),
    }


if __name__ == "__main__":
    result = load()
    print("Loaded synthetic sample data")
    for key, value in result.items():
        print(f"  {key:14s}: {value}")
    print(f"\nDemo instructor login: {DEMO_INSTRUCTOR[0]} / {DEMO_INSTRUCTOR[1]}")
    print("Change this before hosting anywhere: python manage.py add-instructor <name>")
