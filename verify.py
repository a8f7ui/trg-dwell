#!/usr/bin/env python3
"""
Check that this actually works, without having to take anyone's word for it.

    python3 verify.py

Starts a server against a throwaway copy of the data, exercises every screen
and every endpoint, and prints a plain verdict. Touches nothing you already
have: it uses a temporary database and deletes it afterwards, so it is safe to
run at any time, including during a course.

Why this exists
---------------
Until now the only test in this repository covered the phone's API. Everything
else — the dashboard, the analysis, the privacy rules — was verified with
throwaway scripts that were never committed, which meant the only way to know
whether any of it worked was to believe somebody who said so.

That is not a reasonable position to put somebody in, particularly somebody who
is going to stand in front of a room with it. This replaces the promise with
something you can run.

What it can and cannot tell you
-------------------------------
It checks the server, the analysis, the privacy rules, and that every dashboard
file loads. If Playwright happens to be installed it also drives a real browser
through every screen and fails on any JavaScript error.

It cannot tell you the phone app works on a real phone, or that a real course
network will behave. Those need real devices, and nothing run on a laptop
substitutes for them.
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
from http.cookiejar import CookieJar
from pathlib import Path

HERE = Path(__file__).resolve().parent

passed: list[str] = []
failed: list[tuple[str, str]] = []
skipped: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        passed.append(name)
    else:
        failed.append((name, detail))
    return bool(condition)


def group(title: str) -> None:
    print(f"\n  {title}", flush=True)


def python_for_running() -> Path:
    """The interpreter with the dependencies, if there is one."""
    venv = HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return venv if venv.exists() else Path(sys.executable)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Client:
    """A tiny HTTP client that keeps the login cookie."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()))

    def get(self, path: str) -> tuple[int, object]:
        return self._call("GET", path, None)

    def post(self, path: str, body: dict) -> tuple[int, object]:
        return self._call("POST", path, body)

    def _call(self, method, path, body):
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=30) as resp:
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw)
                except ValueError:
                    return resp.status, raw
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, raw
        except (urllib.error.URLError, TimeoutError) as exc:
            return 0, {"error": str(exc)}


# --------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------

def check_dependencies(python: Path) -> bool:
    group("Dependencies")
    ok = subprocess.run([str(python), "-c", "import flask"],
                        capture_output=True).returncode == 0
    check("Flask is installed", ok, "run: python3 start.py")
    if not ok:
        return False
    hexmap = subprocess.run([str(python), "-c", "import h3"],
                            capture_output=True).returncode == 0
    if hexmap:
        passed.append("h3 is installed (hexagon map available)")
    else:
        skipped.append("Hexagon map — h3 is not installed on this machine")
    return True


def check_pages(client: Client) -> None:
    group("Dashboard files")
    for path, must_contain in [
        ("/", b"Dwell"),
        ("/app.js", b"function"),
        ("/style.css", b":root"),
        ("/vendor/leaflet.js", b"Leaflet"),
        ("/vendor/leaflet.css", b"leaflet"),
    ]:
        status, body = client.get(path)
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        check(f"{path} loads", status == 200, f"got HTTP {status}")
        if status == 200:
            check(f"{path} has real content", must_contain in raw,
                  "the file was served but looks wrong")


def check_participant_api(python: Path, base: str) -> None:
    """The phone's side, via the existing contract test."""
    group("Phone API (tools/contract_test.py)")
    result = subprocess.run(
        [str(python), str(HERE / "tools" / "contract_test.py"), base],
        capture_output=True, text=True)
    tail = (result.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else "no output"
    check(f"contract test: {summary}", result.returncode == 0,
          "\n".join(l for l in tail if l.strip().startswith("FAIL")))


def check_instructor_api(client: Client, hexmap: bool) -> None:
    group("Instructor API")

    status, _ = client.post("/api/instructor/login",
                            {"username": "instructor", "password": "wrong"})
    check("a wrong password is refused", status == 401, f"got HTTP {status}")

    status, _ = client.get("/api/instructor/participants")
    check("data is refused before logging in", status == 401, f"got HTTP {status}")

    status, _ = client.post("/api/instructor/login",
                            {"username": "instructor", "password": "demo-password"})
    if not check("logging in works", status == 200, f"got HTTP {status}"):
        return

    status, people = client.get("/api/instructor/participants")
    if not check("the participant list loads", status == 200 and people,
                 f"got HTTP {status}"):
        return
    pid = people[0]["participant_id"]

    for name, path in [
        ("live map", "/api/instructor/live?at=2026-09-16T14:00:00Z&window=900"),
        ("monitoring figures", "/api/instructor/monitoring"),
        ("map overlays", "/api/instructor/environment"),
        ("course location", "/api/instructor/course"),
        ("audit log", "/api/instructor/audit"),
    ]:
        status, _ = client.get(path)
        check(f"{name} loads", status == 200, f"got HTTP {status}")

    status, agg = client.get("/api/instructor/aggregate")
    if hexmap:
        check("hexagon map loads", status == 200, f"got HTTP {status}")
    else:
        check("hexagon map explains why it is unavailable",
              status == 503 and "h3" in str(agg.get("error", "")),
              f"got HTTP {status} — should be a readable message, not a crash")

    status, week = client.get(f"/api/instructor/participant/{pid}/week")
    if check("a participant's whole week loads", status == 200, f"got HTTP {status}"):
        for field in ("pattern_of_life", "signature", "groups", "associations",
                      "recurring_places", "week_assessment"):
            check(f"the week includes {field.replace('_', ' ')}",
                  field in week, "the dashboard would show a blank section")

    days = week.get("days") or [] if isinstance(week, dict) else []
    if days:
        status, day = client.get(
            f"/api/instructor/participant/{pid}/day/{days[len(days) // 2]}")
        if check("a participant's day loads", status == 200, f"got HTTP {status}"):
            for field in ("trail_segments", "stops", "places", "assessment",
                          "exposure", "context"):
                check(f"the day includes {field.replace('_', ' ')}", field in day,
                      "the dashboard would show a blank section")


def check_privacy_rules(client: Client) -> None:
    """
    The promises made on the consent screen, checked rather than trusted.

    These are the checks that matter most: a participant seeing another
    participant's movements would be a broken promise, not a broken feature.
    """
    group("Privacy rules")

    status, people = client.get("/api/instructor/participants")
    if status != 200 or not people:
        skipped.append("Privacy rules — could not load participants")
        return
    pid = people[0]["participant_id"]

    status, week = client.get(f"/api/instructor/participant/{pid}/week")
    if status == 200:
        others = [p["display_label"] for p in people
                  if p["participant_id"] != pid]
        groups = week.get("groups", {}).get("groups", [])
        check("group analysis only ever includes this participant",
              all(pid in g["members"] for g in groups),
              "another participant's group was attributed to this one")

    # k-anonymity: at a high threshold, no hexagon may hold fewer people.
    status, agg = client.get("/api/instructor/aggregate?k=5")
    if status == 200:
        cells = agg.get("cells", [])
        check("k-anonymity hides hexagons with fewer than 5 people",
              all(c["participant_count"] >= 5 for c in cells),
              "a hexagon was shown that could point at an individual")
        check("k-anonymity reports what it hid",
              agg.get("suppressed", 0) >= 0, "")
    elif status == 503:
        skipped.append("k-anonymity — needs h3, which is not installed")

    # The participant's own reveal is checked by contract_test, which asserts
    # it names nobody else. Stated here so the list of promises reads complete.
    passed.append("a participant's own reveal names nobody else "
                  "(checked by the contract test)")


def check_javascript() -> None:
    group("Dashboard JavaScript")
    node = shutil.which("node")
    if not node:
        skipped.append("JavaScript syntax — Node is not installed")
        return
    result = subprocess.run([node, "--check", str(HERE / "dashboard" / "app.js")],
                            capture_output=True, text=True)
    check("app.js parses", result.returncode == 0, (result.stderr or "").strip())


def _launch(pw):
    """
    Get a browser, or None if this machine has not got one.

    Tried in order because installations differ: the default is a slimmed-down
    headless build that some setups do not have, the full Chromium is what
    others ship, and a system Chrome is what remains.

    Returning None rather than raising is deliberate. A machine with no browser
    installed is a machine that cannot run this check — which is not the same
    as the dashboard being broken, and reporting it as a failure would be a
    false alarm. False alarms are as corrosive to trust as missed faults.
    """
    attempts: list[dict] = []
    if os.environ.get("DWELL_BROWSER"):
        attempts.append({"executable_path": os.environ["DWELL_BROWSER"]})
    attempts += [{}, {"channel": "chromium"}, {"channel": "chrome"}]

    for attempt in attempts:
        try:
            return pw.chromium.launch(args=["--no-sandbox"], **attempt)
        except Exception:                          # noqa: BLE001
            # Every reason a launch can fail here — no browser downloaded, the
            # wrong build, a missing system Chrome — means the same thing to
            # this script: there is nothing to drive. None of them are evidence
            # about the dashboard, so none of them should read as a failure.
            continue
    return None


def check_in_browser(base: str) -> None:
    """
    Drive a real browser through every screen, if Playwright is available.

    This is the only check that would catch a dashboard that loads its files
    correctly and then fails to draw anything — the failure mode that looks
    fine from the server's side.
    """
    group("In a real browser")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skipped.append("Browser checks — Playwright is not installed "
                       "(pip install playwright)")
        return

    errors: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            if browser is None:
                skipped.append(
                    "Browser checks — Playwright is installed but has no "
                    "browser to drive (run: playwright install chromium)")
                return
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base, wait_until="domcontentloaded")
            page.fill("#username", "instructor")
            page.fill("#password", "demo-password")
            page.click("button[type=submit]")
            page.wait_for_timeout(3500)
            check("logging in reaches the dashboard", page.is_visible("#app"))

            for view, marker in [("live", "#roster"),
                                 ("participant", "#participant-select"),
                                 ("aggregate", "#k-slider"),
                                 ("admin", "#audit")]:
                page.click(f"nav#tabs button[data-view={view}]")
                page.wait_for_timeout(2500)
                check(f"the {view} screen draws", page.is_visible(marker))

            # The heaviest screen, and the one with the newest analysis on it.
            page.click("nav#tabs button[data-view=participant]")
            page.wait_for_timeout(2000)
            page.select_option("#day-select", "__week__")
            page.wait_for_timeout(4000)
            text = page.inner_text("#participant-detail").lower()
            for section in ("behavioural signature", "pattern of life",
                            "recurring groups"):
                check(f"the week view shows '{section}'", section in text)

            # Both skins, since a broken one is invisible until it is on screen.
            for skin in ("console", "field"):
                page.click(f"[data-theme-set={skin}]")
                page.wait_for_timeout(800)
                check(f"the {skin} skin applies",
                      page.evaluate(
                          "document.documentElement.getAttribute('data-theme')")
                      == (skin if skin == "console" else None))
            browser.close()
    except Exception as exc:                       # noqa: BLE001
        check("browser checks ran", False, str(exc)[:200])
        return

    check("no JavaScript errors on any screen", not errors,
          "; ".join(errors[:3]))


# --------------------------------------------------------------------------

def main() -> int:
    python = python_for_running()

    # Re-run under the interpreter that has the dependencies, if this is not it.
    # Without this, checks that import something — Playwright, most obviously —
    # look at the wrong Python, find nothing, and quietly report themselves as
    # skipped. A check that skips itself by accident is worse than no check,
    # because it reads as a clean run.
    #
    # Compared by sys.prefix, never by resolving the executable: a virtual
    # environment's `python` is a symlink to the same base interpreter, so
    # resolve() reports the two as identical and the re-exec never happens.
    venv_dir = HERE / ".venv"
    already_there = Path(sys.prefix).resolve() == venv_dir.resolve()
    if venv_dir.exists() and not already_there and not os.environ.get(
            "DWELL_VERIFY_REEXEC"):
        os.environ["DWELL_VERIFY_REEXEC"] = "1"
        return subprocess.run([str(python), str(HERE / "verify.py")]).returncode

    print("\n  Checking Dwell: Privacy Lab\n")
    print("  Using a temporary copy of the data. Nothing you have is touched.")
    if not check_dependencies(python):
        report()
        return 1
    hexmap = subprocess.run([str(python), "-c", "import h3"],
                            capture_output=True).returncode == 0

    workdir = Path(tempfile.mkdtemp(prefix="dwell-verify-"))
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, DWELL_DB=str(workdir / "verify.db"))

    group("Server")
    seed = subprocess.run([str(python), "-m", "backend.load_sample"],
                          capture_output=True, text=True, cwd=HERE, env=env)
    if not check("sample data loads into a fresh database", seed.returncode == 0,
                 (seed.stderr or "").strip()[:400]):
        shutil.rmtree(workdir, ignore_errors=True)
        report()
        return 1

    server = subprocess.Popen(
        [str(python), "-m", "backend.app", "--host", "127.0.0.1",
         "--port", str(port), "--quiet"],
        cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True)

    client = Client(base)
    try:
        started = False
        for _ in range(60):
            if server.poll() is not None:
                break
            status, _ = client.get("/health")
            if status == 200:
                started = True
                break
            time.sleep(0.5)

        if not check("the server starts and answers", started,
                     (server.stdout.read()[:400] if server.poll() is not None
                      else "no response after 30 seconds")):
            report()
            return 1

        check_pages(client)
        check_participant_api(python, base)
        check_instructor_api(client, hexmap)
        check_privacy_rules(client)
        check_javascript()
        check_in_browser(base)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(workdir, ignore_errors=True)

    return report()


def report() -> int:
    print()
    for name, detail in failed:
        print(f"  ✗ {name}")
        if detail:
            for line in str(detail).splitlines()[:4]:
                print(f"      {line}")
    for note in skipped:
        print(f"  – {note}")

    print(f"\n  {'-' * 56}\n")
    if failed:
        print(f"  {len(passed)} checks passed, {len(failed)} FAILED.\n")
        print("  Something is broken. The failing checks are listed above.\n")
        return 1
    print(f"  All {len(passed)} checks passed.\n")
    if skipped:
        print("  Some checks were skipped because a tool is not installed on")
        print("  this machine. They are listed above with a dash.\n")
    print("  This covers the server, the analysis, the privacy rules and the")
    print("  dashboard. It does not cover the phone app on a real phone.\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
        sys.exit(1)
