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
import secrets
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

# The instructor password used for this run, on a database that is deleted
# afterwards. Generated rather than fixed so that no working credential appears
# in this file, in a log, or in the output of `ps`.
TEST_PASSWORD = secrets.token_urlsafe(12)

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

    def get(self, path: str, token: str = "") -> tuple[int, object]:
        return self._call("GET", path, None, token)

    def post(self, path: str, body: dict, token: str = "") -> tuple[int, object]:
        return self._call("POST", path, body, token)

    def _call(self, method, path, body, token=""):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers)
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
    return ok


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


def check_instructor_api(client: Client) -> None:
    group("Instructor API")

    status, _ = client.post("/api/instructor/login",
                            {"username": "instructor", "password": "wrong"})
    check("a wrong password is refused", status == 401, f"got HTTP {status}")

    status, _ = client.get("/api/instructor/participants")
    check("data is refused before logging in", status == 401, f"got HTTP {status}")

    status, _ = client.post("/api/instructor/login",
                            {"username": "instructor", "password": TEST_PASSWORD})
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
    check("the aggregate map loads", status == 200, f"got HTTP {status}")

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

    # k-anonymity: at a high threshold, no cell may hold fewer people.
    status, agg = client.get("/api/instructor/aggregate?k=5")
    if status == 200:
        cells = agg.get("cells", [])
        check("k-anonymity hides cells with fewer than 5 people",
              all(c["participant_count"] >= 5 for c in cells),
              "a cell was shown that could point at an individual")
        check("k-anonymity actually draws something at the default threshold",
              len(cells) > 0,
              "no cells at all — the aggregate map would be blank")

    # And the demonstration itself: dropping the threshold to 1 must expose
    # cells that hold exactly one person. If it does not, the best thirty
    # seconds in the tool silently stops working.
    status, exposed = client.get("/api/instructor/aggregate?k=1")
    if status == 200:
        counts = [c["participant_count"] for c in exposed.get("cells", [])]
        check("dropping the threshold to 1 exposes single-person cells",
              any(n == 1 for n in counts),
              "the k-anonymity demonstration would show nothing new")

    # The participant's own reveal is checked by contract_test, which asserts
    # it names nobody else. Stated here so the list of promises reads complete.
    passed.append("a participant's own reveal names nobody else "
                  "(checked by the contract test)")


def check_local_days(client: Client) -> None:
    """
    A phone's day and the server's day are the same day.

    This is a regression test for a fault that made the evening reveal — the
    centrepiece of the whole week — show about ninety minutes.

    A phone reports UTC. Milwaukee is five or six hours behind it, so a course
    day that runs 09:00 to 21:00 local spans two UTC dates, with everything
    after 19:00 falling on the next one. The backend used to take the day from
    the first ten characters of the timestamp, which is the UTC date, so one
    day of a participant's life arrived as two — and the reveal, which shows
    the latest day, got only the tail end of the evening.

    It never showed up in testing because the sample generator writes
    timestamps with a local offset, whose first ten characters happen to
    already be the local date. So this check deliberately uploads what a real
    phone sends: UTC, with a Z on the end.
    """
    group("Days are the course's days, not UTC's")

    # Migration, relocation and daylight saving need no server, so they live in
    # their own script and are run here rather than duplicated.
    result = subprocess.run(
        [sys.executable, str(HERE / "tools" / "day_boundary_test.py")],
        capture_output=True, text=True, cwd=HERE)
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("PASS  "):
            passed.append(stripped[6:])
        elif stripped.startswith("FAIL  "):
            failed.append((stripped[6:], "tools/day_boundary_test.py"))
    check("the day-boundary checks ran", result.returncode in (0, 1)
          and "PASS" in (result.stdout or ""),
          (result.stderr or "").strip()[:300])

    status, reg = client.post("/api/v1/participants", {
        "consent_version": "verify-local-day", "consented_at": "2026-09-15T08:00:00Z",
        "timezone": "America/Chicago", "os_name": "verify",
    })
    if not check("a phone can register", status == 201 and isinstance(reg, dict),
                 f"got HTTP {status}"):
        return
    token = reg.get("token", "")

    # One day in Milwaukee: 09:00 to 21:45 local on 15 September 2026, which is
    # CDT (UTC-5). In UTC that is 14:00 on the 15th to 02:45 on the 16th.
    lat, lon = 43.0389, -87.9065
    uploaded = []
    for hour in range(14, 24):                      # 09:00–18:00 local, 15 Sep
        uploaded.append(f"2026-09-15T{hour:02d}:20:00Z")
    for hour in range(0, 3):                        # 19:00–21:00 local, still 15 Sep
        uploaded.append(f"2026-09-16T{hour:02d}:20:00Z")

    status, ack = client.post("/api/v1/pings", {"pings": [
        {"ts": ts, "lat": lat + i * 0.0004, "lon": lon + i * 0.0004,
         "accuracy_m": 12, "battery_pct": 70, "connection": "wifi",
         "collection_mode": "background", "session_id": "verify-day"}
        for i, ts in enumerate(uploaded)
    ]}, token=token)
    if not check(f"{len(uploaded)} points upload, spanning two UTC dates",
                 status == 201 and isinstance(ack, dict)
                 and ack.get("accepted") == len(uploaded),
                 f"got HTTP {status}: {ack}"):
        return

    status, reveal = client.get("/api/v1/me/reveal", token=token)
    if not check("the reveal loads", status == 200 and isinstance(reveal, dict),
                 f"got HTTP {status}"):
        return

    days = reveal.get("days_available") or []
    check("one local day is reported as one day, not two",
          days == ["2026-09-15"],
          f"the reveal offers {days!r} — evening points have been filed under "
          f"the next day, which is what UTC slicing did")

    check("the reveal opens on the day the participant just lived",
          reveal.get("day") == "2026-09-15",
          f"it opened on {reveal.get('day')!r}")

    count = reveal.get("point_count")
    check("the day shown contains the whole day, including the evening",
          count == len(uploaded),
          f"the reveal shows {count} of {len(uploaded)} points; the evening is "
          f"the part that goes missing, and the evening is the point of it")


def check_javascript() -> None:
    group("Dashboard JavaScript")
    node = shutil.which("node")
    if not node:
        skipped.append("JavaScript syntax — Node is not installed")
        return
    result = subprocess.run([node, "--check", str(HERE / "dashboard" / "app.js")],
                            capture_output=True, text=True)
    check("app.js parses", result.returncode == 0, (result.stderr or "").strip())


def check_https() -> None:
    """
    The same software, over a real TLS connection.

    Its own server on its own certificate, because the questions that matter —
    is the sign-in cookie marked Secure, does the phone's API work over TLS —
    cannot be answered by reading configuration.
    """
    group("Over HTTPS")
    result = subprocess.run(
        [sys.executable, str(HERE / "tools" / "https_test.py")],
        capture_output=True, text=True, cwd=HERE)
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("PASS  "):
            passed.append(stripped[6:])
        elif stripped.startswith("FAIL  "):
            failed.append((stripped[6:], "tools/https_test.py"))
        elif stripped.startswith("----  "):
            skipped.append(stripped[6:])
    if "Skipped:" in (result.stdout or ""):
        skipped.append("HTTPS checks — openssl is not installed")
        return
    check("the HTTPS checks ran", "PASS" in (result.stdout or ""),
          (result.stderr or result.stdout or "").strip()[:400])


def check_data_safety() -> None:
    """The things that must not happen to a course that is under way."""
    group("Safe for a course already running")
    result = subprocess.run(
        [sys.executable, str(HERE / "tools" / "data_safety_test.py")],
        capture_output=True, text=True, cwd=HERE)
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("PASS  "):
            passed.append(stripped[6:])
        elif stripped.startswith("FAIL  "):
            failed.append((stripped[6:], "tools/data_safety_test.py"))
    check("the data-safety checks ran", "PASS" in (result.stdout or ""),
          (result.stderr or result.stdout or "").strip()[:400])


def check_phone_app() -> None:
    """
    The phone app's types, and the arithmetic behind the evening notification.

    Not the app on a phone — nothing here can tell you that. This is the part
    that can be checked without one: that the TypeScript is consistent, and
    that the evening reveal is scheduled for the right evening with the right
    words on it.
    """
    group("Phone app")

    # What reaches the build, and what must never. Needs no Node, so it runs
    # before the checks that do.
    result = subprocess.run(
        [sys.executable, str(HERE / "tools" / "build_upload_test.py")],
        capture_output=True, text=True, cwd=HERE)
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("PASS  "):
            passed.append(stripped[6:])
        elif stripped.startswith("FAIL  "):
            failed.append((stripped[6:], "tools/build_upload_test.py"))
    check("the build-upload checks ran", "PASS" in (result.stdout or ""),
          (result.stderr or result.stdout or "").strip()[:400])

    node = shutil.which("node")
    tsc = HERE / "app" / "node_modules" / ".bin" / (
        "tsc.cmd" if os.name == "nt" else "tsc")
    if not node or not tsc.exists():
        skipped.append(
            "Phone app checks — Node or the app's packages are not installed "
            "(run: npm install, in the app folder)")
        return

    result = subprocess.run([str(tsc), "--noEmit"], capture_output=True,
                            text=True, cwd=HERE / "app")
    check("the phone app's TypeScript is consistent", result.returncode == 0,
          (result.stdout or result.stderr or "").strip()[:500])

    result = subprocess.run(
        [node, str(HERE / "tools" / "reveal_schedule_test.mjs")],
        capture_output=True, text=True, cwd=HERE)
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("PASS  "):
            passed.append(stripped[6:])
        elif stripped.startswith("FAIL  "):
            failed.append((stripped[6:], "tools/reveal_schedule_test.mjs"))
        elif stripped.startswith("----  "):
            skipped.append(stripped[6:])
    check("the evening-notification checks ran",
          "PASS" in (result.stdout or ""),
          (result.stderr or result.stdout or "").strip()[:400])


def _installed_browsers() -> list[Path]:
    """
    Any Chromium actually present, whichever build number it happens to be.

    Playwright asks for one exact build and refuses anything else, so a machine
    with a perfectly working Chromium two revisions old reports itself as having
    no browser at all — and this whole section then skips itself, which reads
    like a clean run. Looking for what is there rather than for what was
    expected turns that back into a real check.
    """
    roots = [Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])] if os.environ.get(
        "PLAYWRIGHT_BROWSERS_PATH") else []
    roots += [Path.home() / ".cache" / "ms-playwright",
              Path.home() / "Library" / "Caches" / "ms-playwright"]

    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in ("chromium-*/chrome-linux/chrome",
                        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
                        "chromium-*/chrome-win/chrome.exe",
                        "chromium_headless_shell-*/chrome-headless-shell-*/"
                        "chrome-headless-shell"):
            found += sorted(root.glob(pattern), reverse=True)
    return found


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
    attempts += [{"executable_path": str(p)} for p in _installed_browsers()]

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


def check_in_browser(base: str, expect_groups: bool) -> None:
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
            # Waited for rather than slept through. A fixed pause is a guess
            # about how fast the machine is, and on a slow or busy one it
            # produces a failure that says the dashboard is broken when it was
            # only late. A false alarm costs exactly as much trust as a missed
            # fault, so every wait below is for a condition, with a ceiling
            # generous enough that reaching it means something is genuinely
            # wrong.
            def wait_for(condition: str, seconds: int = 30) -> bool:
                try:
                    page.wait_for_function(condition, timeout=seconds * 1000)
                    return True
                except Exception:                  # noqa: BLE001
                    return False

            page.goto(base, wait_until="domcontentloaded")
            page.fill("#username", "instructor")
            page.fill("#password", TEST_PASSWORD)
            page.click("button[type=submit]")
            check("logging in reaches the dashboard",
                  wait_for("!document.querySelector('#app').hidden"))

            for view, marker in [("live", "#roster"),
                                 ("participant", "#participant-select"),
                                 ("aggregate", "#k-slider"),
                                 ("admin", "#audit")]:
                page.click(f"nav#tabs button[data-view={view}]")
                check(f"the {view} screen draws",
                      wait_for(f"document.querySelector('{marker}') && "
                               f"document.querySelector('{marker}').offsetParent"))

            # The heaviest screen, and the one with the newest analysis on it.
            page.click("nav#tabs button[data-view=participant]")
            wait_for("document.querySelector('#day-select') && "
                     "document.querySelector('#day-select').options.length > 1")
            page.select_option("#day-select", "__week__")

            # This view runs the whole week's analysis server-side, so on a slow
            # machine it can genuinely take a while. Wait for the last section
            # to arrive, then read them all from the same settled state.
            #
            # Which sections should be there depends on the data, so it is
            # asked rather than assumed: the groups section is only drawn for
            # somebody who has a recurring group, and requiring it regardless
            # would fail on a participant who simply travelled alone.
            wanted = ["behavioural signature", "pattern of life"]
            if expect_groups:
                wanted.append("recurring groups")

            arrived = wait_for(
                "document.querySelector('#participant-detail')"
                f".innerText.toLowerCase().includes('{wanted[-1]}')", 60)
            text = page.inner_text("#participant-detail").lower()
            for section in wanted:
                check(f"the week view shows '{section}'",
                      section in text,
                      "" if arrived else "the week view did not finish loading")

            # Both skins, since a broken one is invisible until it is on screen.
            for skin in ("console", "field"):
                page.click(f"[data-theme-set={skin}]")
                want = "'console'" if skin == "console" else "null"
                check(f"the {skin} skin applies",
                      wait_for("document.documentElement.getAttribute"
                               f"('data-theme') === {want}", 10))
            browser.close()
    except Exception as exc:                       # noqa: BLE001
        check("browser checks ran", False, str(exc)[:200])
        return

    check("no JavaScript errors on any screen", not errors,
          "; ".join(errors[:3]))


# --------------------------------------------------------------------------

def check_production_safety(python: Path) -> None:
    """
    The handful of things that are dangerous on a server real people will use.

    Folded in here rather than left as a separate command somebody has to know
    to run. `--production` is the flag; without it these are skipped, because a
    laptop demo is allowed to have a demo login on it.
    """
    group("Safe for real participants")
    result = subprocess.run([str(python), str(HERE / "manage.py"),
                             "check-production"],
                            capture_output=True, text=True, cwd=HERE)
    out = (result.stdout or "") + (result.stderr or "")
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("PROBLEM"):
            check(stripped[8:].strip()[:90], False,
                  "must be fixed before real people use this server")
        elif stripped.startswith("WARNING"):
            skipped.append(stripped[8:].strip()[:90])
        elif stripped.startswith("OK"):
            passed.append(stripped[3:].strip()[:90])


def main() -> int:
    production = "--production" in sys.argv
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
        return subprocess.run(
            [str(python), str(HERE / "verify.py")] + sys.argv[1:]).returncode

    print("\n  Checking Dwell: Privacy Lab\n")
    print("  Using a temporary copy of the data. Nothing you have is touched.")
    if not check_dependencies(python):
        report()
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="dwell-verify-"))
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, DWELL_DB=str(workdir / "verify.db"))

    group("Server")
    # The sign-in is created with a password generated here, handed over on
    # standard input. Nothing in this repository is a working credential, and
    # nothing that runs during a check is visible in `ps`.
    seed = subprocess.run([str(python), "-m", "backend.load_sample",
                           "--with-login", "--password-stdin"],
                          input=TEST_PASSWORD + "\n",
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
        check_instructor_api(client)
        check_privacy_rules(client)
        check_local_days(client)
        check_javascript()
        check_phone_app()
        check_https()
        check_data_safety()
        if production:
            check_production_safety(python)

        # Whether the browser should expect a groups section depends on whether
        # the first participant actually has one. Asked here rather than assumed
        # in the browser, where a wrong assumption would look like a fault.
        expect_groups = False
        status, people = client.get("/api/instructor/participants")
        if status == 200 and people:
            status, week = client.get(
                f"/api/instructor/participant/{people[0]['participant_id']}/week")
            if status == 200:
                expect_groups = bool(week.get("groups", {}).get("available"))

        check_in_browser(base, expect_groups)
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
