#!/usr/bin/env python3
"""
Things that must never happen to a course that is already under way.

    python3 tools/data_safety_test.py

Every check here corresponds to a way this software could betray the people
using it: by deleting what they contributed, by putting a known password on
their server, by leaking where they have been into a file meant to be safe to
send to a stranger. Several of them are regression tests for faults that were
actually present.

Runs on throwaway databases in a temporary folder. Nothing real is touched.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

PYTHON = HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))
        failures.append(name)
    return ok


def register_real_participants(conn, n: int = 3) -> list[str]:
    """Participants indistinguishable from ones that registered from a phone."""
    from backend import auth, db

    ids = []
    for i in range(1, n + 1):
        pid = f"p_{i:03d}_real"
        _, token_hash = auth.new_participant_token()
        conn.execute(
            "INSERT INTO participants (participant_id, display_label, joined_at, "
            "consent_version, consented_at, token_hash) VALUES (?,?,?,?,?,?)",
            (pid, f"Participant {i:02d}", db.now_iso(), "2026-08-10.1",
             db.now_iso(), token_hash))
        for hour in (14, 18, 22):
            ts = f"2026-09-15T{hour:02d}:00:00+00:00"
            conn.execute(
                "INSERT INTO pings (participant_id, ts, lat, lon, accuracy_m, "
                "local_day, received_at) VALUES (?,?,?,?,?,?,?)",
                (pid, ts, 43.0389 + i * 0.001, -87.9065, 10.0, "2026-09-15", ts))
        ids.append(pid)
    conn.commit()
    return ids


def run(args: list[str], env: dict, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run([str(PYTHON)] + args, capture_output=True, text=True,
                          cwd=HERE, env=env, input=stdin or None)


def main() -> int:
    print("\n  Things that must never happen to a running course\n")

    work = Path(tempfile.mkdtemp(prefix="dwell-safety-"))
    db_path = work / "course.db"
    env = dict(os.environ, DWELL_DB=str(db_path),
               DWELL_SETTINGS=str(work / "absent.json"))
    os.environ["DWELL_DB"] = str(db_path)
    os.environ["DWELL_SETTINGS"] = str(work / "absent.json")

    try:
        from backend import auth, config, db, load_sample

        conn = db.connect(db_path)
        db.init_db(conn)
        real_ids = register_real_participants(conn)
        before = conn.execute("SELECT COUNT(*) AS n FROM pings").fetchone()["n"]
        conn.close()

        # --- restarting must not destroy anybody ------------------------------
        # This one happened. Somebody ran the setup command on a live server
        # between the install links going out and the first upload arriving;
        # three registered participants became zero.
        for attempt in range(2):
            result = run(["-m", "backend.load_sample"], env)
            check(f"loading practice data refuses on a real course (attempt "
                  f"{attempt + 1})",
                  result.returncode != 0 and "RealDataPresent" in
                  (result.stderr or ""),
                  f"exit {result.returncode}; stderr: "
                  f"{(result.stderr or '')[:200]}")

        conn = db.connect(db_path)
        db.init_db(conn)
        survivors = conn.execute(
            "SELECT COUNT(*) AS n FROM participants").fetchone()["n"]
        points = conn.execute("SELECT COUNT(*) AS n FROM pings").fetchone()["n"]
        check("every registered participant survived",
              survivors == len(real_ids),
              f"{survivors} of {len(real_ids)} left")
        check("every location point survived", points == before,
              f"{points} of {before} left")

        # --- restarting must not install a known password ---------------------
        names = [r["username"] for r in conn.execute(
            "SELECT username FROM instructors")]
        check("no instructor account was created behind the operator's back",
              names == [], f"found {names}")
        check("the published demo password does not work",
              not auth.check_instructor(conn, *load_sample.PUBLISHED_DEMO_LOGIN))
        conn.close()

        # --- and neither may the one-command demo starter ---------------------
        import start
        password = start.ensure_login(PYTHON)
        check("the demo starter creates no sign-in on a real course",
              password is None, f"it produced a password: {bool(password)}")
        conn = db.connect(db_path)
        db.init_db(conn)
        check("...and left the instructor table empty",
              [r["username"] for r in conn.execute(
                  "SELECT username FROM instructors")] == [])

        # --- generating sample data must not touch the course -----------------
        elsewhere = work / "generated"
        result = run(["tools/generate_sample_data.py", "--out", str(elsewhere),
                      "--days", "1", "--participants", "2"], env)
        after = conn.execute("SELECT COUNT(*) AS n FROM pings").fetchone()["n"]
        check("generating practice data writes nothing to the course database",
              after == before, f"{before} points became {after}")
        check("...and it did write its files somewhere else",
              result.returncode == 0 and (elsewhere / "pings.csv").exists(),
              (result.stderr or "")[:200])

        # --- withdrawal is irreversible ---------------------------------------
        victim = real_ids[0]
        deleted = db.delete_participant(conn, victim, actor="safety-test")
        left = conn.execute(
            "SELECT COUNT(*) AS n FROM pings WHERE participant_id = ?",
            (victim,)).fetchone()["n"]
        person = conn.execute(
            "SELECT COUNT(*) AS n FROM participants WHERE participant_id = ?",
            (victim,)).fetchone()["n"]
        check("withdrawal deletes the person's location points", left == 0,
              f"{left} points remain")
        check("withdrawal deletes the person", person == 0)
        check("withdrawal reports what it removed", deleted == 3,
              f"reported {deleted}")
        check("withdrawal is recorded in the audit log",
              conn.execute(
                  "SELECT COUNT(*) AS n FROM audit_log WHERE action = "
                  "'delete_participant'").fetchone()["n"] == 1)
        # A withdrawal that could be undone would not be a withdrawal. The
        # audit entry must describe the act without preserving the data.
        entry = conn.execute(
            "SELECT detail FROM audit_log WHERE action = 'delete_participant'"
        ).fetchone()["detail"]
        check("the audit entry keeps no coordinates",
              not re.search(r"-?\d{1,3}\.\d{4,}", entry or ""),
              f"audit detail was: {entry}")
        conn.close()

        # --- the support report ------------------------------------------------
        report = run(["diagnose.py"], env)
        report_path = HERE / "support-report.txt"
        if check("a support report can be collected",
                 report.returncode == 0 and report_path.exists(),
                 (report.stderr or "")[:300]):
            text = report_path.read_text()
            # Without this, every leak check below could pass by describing a
            # different, empty database — which is exactly what happened before
            # diagnose.py was taught to read the configured location.
            expected = len(real_ids) - 1        # one was withdrawn above
            check("the support report describes the configured database, not "
                  "a default one",
                  f"participants             {expected}" in text,
                  f"expected to see {expected} participants in the report")
            check("the support report contains no coordinates",
                  not re.search(r"-?\d{1,3}\.\d{5,}", text),
                  "something shaped like a coordinate is in it")
            check("the support report contains no signing key",
                  not _leaks_secret(text, db_path),
                  "the signing key is in it")
            check("the support report contains no password hash",
                  "scrypt" not in text.lower() and
                  not re.search(r"\b[0-9a-f]{64}\b", text),
                  "something shaped like a hash is in it")
            check("the support report contains no device token",
                  not _leaks_tokens(text, db_path))
            report_path.unlink(missing_ok=True)

        # --- the setup log ------------------------------------------------------
        log = Path(config.BASE_DIR) / "data" / "local" / "setup-log.txt"
        if log.exists():
            text = log.read_text(errors="replace")
            check("the setup log holds no coordinates",
                  not re.search(r"-?\d{1,3}\.\d{5,}", text))
        else:
            print("  ----  no setup log on this machine to check")

    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if failures:
        print(f"  {len(failures)} check(s) FAILED\n")
        return 1
    print("  All data-safety checks passed.\n")
    return 0


def _leaks_secret(text: str, db_path: Path) -> bool:
    key_file = db_path.parent / "secret_key"
    try:
        secret = key_file.read_text().strip()
    except OSError:
        return False
    return bool(secret) and secret in text


def _leaks_tokens(text: str, db_path: Path) -> bool:
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        hashes = [r[0] for r in conn.execute(
            "SELECT token_hash FROM participants WHERE token_hash IS NOT NULL")]
        conn.close()
    except sqlite3.Error:
        return False
    return any(h and h in text for h in hashes)


if __name__ == "__main__":
    raise SystemExit(main())
