#!/usr/bin/env python3
"""
What happens when a whole room does the same thing at once.

    python3 tools/concurrency_test.py

Two faults live here, and both were real. Both are invisible with one phone and
one worker, which is how they survived: everything works while you are testing
it alone, and breaks in the first ten minutes of the first course.

  * Several web-server workers starting together each found no signing key and
    each wrote a different one. Measured before the fix: six workers, four keys.
    The symptom is instructors being signed out at random as their requests land
    on different workers.

  * Twenty phones registering in the same moment were handed the same
    participant number, because the count-then-insert was not one operation.
    The facilitator's guide tells a room to install the app together, so this is
    the normal case rather than an edge one. Instructors then cannot tell two
    people apart, and the colour coding the live map depends on is ambiguous.

Both are checked by doing the thing at once, in real processes and real
threads, rather than by reading the code that is supposed to prevent it.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

WORKERS = 8
REGISTRATIONS = 60

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))
        failures.append(name)
    return ok


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main() -> int:
    print("\n  When a whole room does the same thing at once\n")

    python = HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt"
                               else "bin/python")
    if not python.exists():
        python = Path(sys.executable)

    work = Path(tempfile.mkdtemp(prefix="dwell-concurrent-"))
    env = dict(os.environ, DWELL_DB=str(work / "course.db"),
               DWELL_SETTINGS=str(work / "absent.json"))
    env.pop("DWELL_SECRET_KEY", None)

    server = None
    try:
        # ---- H1: several workers starting together --------------------------
        # Each subprocess is a separate interpreter with no shared memory, which
        # is what a real multi-worker web server looks like, and is the only way
        # the race can appear at all.
        (work).mkdir(parents=True, exist_ok=True)
        starter = ("import backend.config as c; print(c.get_secret_key())")
        procs = [subprocess.Popen([str(python), "-c", starter], cwd=HERE,
                                  env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
                 for _ in range(WORKERS)]
        keys = set()
        for p in procs:
            out, _ = p.communicate(timeout=60)
            if out.strip():
                keys.add(out.strip())

        check(f"{WORKERS} workers starting together agree on one signing key",
              len(keys) == 1,
              f"they produced {len(keys)} different keys; every instructor "
              f"would be signed out whenever a request landed on the wrong one")
        stored = (work / "secret_key").read_text().strip()
        check("...and it is the one written to disk", keys == {stored} if keys
              else False)
        mode = (work / "secret_key").stat().st_mode & 0o777
        check("...stored so that only this account can read it",
              os.name == "nt" or not (mode & 0o077), f"permissions are {mode:o}")

        # ---- H2: a room registering together --------------------------------
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [str(python), "-m", "backend.app", "--host", "127.0.0.1",
             "--port", str(port), "--quiet"],
            cwd=HERE, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)

        started = False
        for _ in range(60):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=2) as r:
                    if r.status == 200:
                        started = True
                        break
            except Exception:                       # noqa: BLE001
                time.sleep(0.5)
        if not check("the server starts", started,
                     (server.stdout.read()[:400] if server.poll() is not None
                      else "no answer")):
            return 1

        def register(_n: int):
            body = json.dumps({
                "consent_version": "concurrency-check",
                "consented_at": "2026-09-15T08:00:00Z",
            }).encode()
            req = urllib.request.Request(
                f"{base}/api/v1/participants", data=body, method="POST",
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                return {"error": str(exc)}

        with ThreadPoolExecutor(max_workers=REGISTRATIONS) as pool:
            results = list(pool.map(register, range(REGISTRATIONS)))

        ok = [r for r in results if r.get("participant_id")]
        if not check(f"all {REGISTRATIONS} simultaneous registrations succeed",
                     len(ok) == REGISTRATIONS,
                     f"{len(ok)} succeeded; errors: "
                     f"{[r.get('error') for r in results if not r.get('participant_id')][:3]}"):
            # The reason lives in the server's own output, and guessing at it
            # from a 500 is how a real fault gets mistaken for flakiness.
            server.terminate()
            try:
                log = server.stdout.read() or ""
            except Exception:                       # noqa: BLE001
                log = ""
            interesting = [l for l in log.splitlines()
                           if "Error" in l or "error" in l]
            print("          server said: "
                  + " | ".join(sorted(set(interesting))[:4]))

        ids = [r["participant_id"] for r in ok]
        check("every participant gets a distinct id", len(set(ids)) == len(ids),
              f"{len(ids) - len(set(ids))} were duplicated")

        tokens = [r["token"] for r in ok]
        check("every participant gets a distinct token",
              len(set(tokens)) == len(tokens),
              "two phones sharing a token could read each other's data")

        # The label is what an instructor reads off the screen. Two people
        # called "Participant 09" is the failure that was actually measured.
        import sqlite3
        conn = sqlite3.connect(f"file:{work / 'course.db'}?mode=ro", uri=True)
        labels = [r[0] for r in conn.execute(
            "SELECT display_label FROM participants")]
        conn.close()
        check("every participant gets a distinct number on screen",
              len(set(labels)) == len(labels),
              f"{len(labels) - len(set(labels))} duplicate labels: "
              f"{sorted(l for l in set(labels) if labels.count(l) > 1)[:5]}")
        check("...and they run consecutively from one",
              sorted(labels) == sorted(f"Participant {i:02d}"
                                       for i in range(1, len(labels) + 1)),
              f"got {sorted(labels)[:5]}...")

    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        shutil.rmtree(work, ignore_errors=True)

    print()
    if failures:
        print(f"  {len(failures)} check(s) FAILED\n")
        return 1
    print("  All concurrency checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
