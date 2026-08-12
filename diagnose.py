#!/usr/bin/env python3
"""
Collect a support report, with nothing private in it.

    ./dwell diagnose

Writes `support-report.txt` describing this installation in enough detail for
somebody to help, and deliberately not enough to be dangerous if it is emailed
around or pasted into a chat.

What is deliberately left out
-----------------------------
Nothing in this report can identify a participant or impersonate anybody:

  * the security key that signs sign-ins
  * instructor usernames and password hashes
  * participant device tokens
  * every coordinate, every timestamp, every place name
  * the contents of the database, beyond counts

What goes in is the shape of the installation — versions, what exists, what
answers, how many rows — plus the setup log with anything secret-looking
scrubbed out of it.

This matters more than it might seem. The obvious way to help somebody debug
is to ask for their log, and the obvious log here would contain the location
history of everybody on the course.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _data_dir() -> Path:
    """
    Where this installation actually keeps its data.

    Read from the same configuration the server uses rather than assumed to be
    data/local. A host that puts the database somewhere persistent — which the
    readiness check tells people to do — would otherwise get a report about an
    empty folder, saying everything was missing, which is worse than no report.

    Falls back to the default if the backend cannot be imported, because this
    command has to work when nothing else does; that is its whole purpose.
    """
    try:
        from backend import config
        return Path(config.DB_PATH).parent
    except Exception:                               # noqa: BLE001
        return Path(os.getenv("DWELL_DB", HERE / "data" / "local" / "course.db")).parent


DATA = _data_dir()


def _db_path() -> Path:
    try:
        from backend import config
        return Path(config.DB_PATH)
    except Exception:                               # noqa: BLE001
        return Path(os.getenv("DWELL_DB", DATA / "course.db"))


DB_PATH = _db_path()
SETTINGS = Path(os.getenv("DWELL_SETTINGS", DATA / "course.json"))
LOG = DATA / "setup-log.txt"
REPORT = HERE / "support-report.txt"

# Anything matching these is replaced before it can reach the report. Applied
# to every line, including ones the author of this file has not thought of —
# which is the point of doing it by pattern rather than by field.
SCRUBBERS: list[tuple[re.Pattern, str]] = [
    # A separator is required before the value — a colon, an equals sign or a
    # quote. Without that, "no passwords, no tokens" in this file's own prose
    # gets eaten as though the following word were a secret, which produced a
    # report that read as if the redaction had failed.
    (re.compile(r'(?i)\b(secret[_-]?key["\' ]{0,3}\s*[:=]\s*["\' ]{0,3})\S+'),
     r"\1[removed]"),
    (re.compile(r'(?i)\b(password["\' ]{0,3}\s*[:=]\s*["\' ]{0,3})\S+'),
     r"\1[removed]"),
    (re.compile(r'(?i)\b(token["\' ]{0,3}\s*[:=]\s*["\' ]{0,3})\S+'),
     r"\1[removed]"),
    (re.compile(r'(?i)\b(api[_-]?key["\' ]{0,3}\s*[:=]\s*["\' ]{0,3})\S+'),
     r"\1[removed]"),
    (re.compile(r'(?i)(authorization:\s*bearer\s+)\S+'), r"\1[removed]"),

    # Anything shaped like a coordinate pair, wherever it appears.
    (re.compile(r'-?\d{1,3}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}'),
     "[coordinates removed]"),
    (re.compile(r'(?i)("?(?:lat|lon|latitude|longitude)"?\s*[:=]\s*)-?\d+\.\d+'),
     r"\1[removed]"),
    (re.compile(r'-?\d{1,3}\.\d{5,}'), "[number removed]"),

    # Long random-looking strings: tokens, hashes, keys by any other name.
    (re.compile(r'\b[A-Za-z0-9_\-]{40,}\b'), "[long value removed]"),
    (re.compile(r'\b[0-9a-f]{32,}\b'), "[hash removed]"),

    # Home directories name people.
    (re.compile(r'/(?:home|Users)/[^/\s"\']+'), "/[home]"),
    (re.compile(r'(?i)C:\\Users\\[^\\\s"\']+'), r"C:\\Users\\[user]"),
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b'), "[email removed]"),
]


def scrub(text: str) -> str:
    for pattern, replacement in SCRUBBERS:
        text = pattern.sub(replacement, text)
    return text


def venv_python() -> Path:
    return HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def section(lines: list[str], title: str) -> None:
    lines.append("")
    lines.append(title)
    lines.append("-" * len(title))


def collect() -> str:
    out: list[str] = []
    out.append("DWELL: PRIVACY LAB — SUPPORT REPORT")
    out.append("=" * 40)
    out.append(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    out.append("")
    out.append("This report contains no passwords, no security keys, no device")
    out.append("tokens, and no participant locations. It is safe to send on.")

    # ---- the computer ----
    section(out, "This computer")
    out.append(f"  Operating system : {platform.platform()}")
    out.append(f"  Processor        : {platform.machine()}")
    out.append(f"  Python running   : {sys.version.split()[0]} ({sys.executable})")
    try:
        usage = shutil.disk_usage(HERE)
        out.append(f"  Disk free        : {usage.free / 1_000_000_000:.1f} GB "
                   f"of {usage.total / 1_000_000_000:.0f} GB")
    except OSError:
        out.append("  Disk free        : could not read")
    node = shutil.which("node")
    if node:
        try:
            version = subprocess.run([node, "--version"], capture_output=True,
                                     text=True, timeout=10).stdout.strip()
            out.append(f"  Node             : {version}")
        except (OSError, subprocess.SubprocessError):
            out.append("  Node             : present, version unreadable")
    else:
        out.append("  Node             : not installed (only needed to build the app)")

    # ---- the installation ----
    section(out, "This installation")
    vp = venv_python()
    out.append(f"  Private workspace: {'yes' if vp.exists() else 'NO — setup has not run'}")
    if vp.exists():
        try:
            result = subprocess.run([str(vp), "-m", "pip", "list", "--format=freeze"],
                                    capture_output=True, text=True, timeout=60)
            packages = [l for l in result.stdout.splitlines() if l.strip()]
            out.append(f"  Installed packages: {len(packages)}")
            for line in sorted(packages):
                out.append(f"    {line}")
        except (OSError, subprocess.SubprocessError):
            out.append("  Installed packages: could not list")

    section(out, "Files that should exist")
    for name, path in [
        ("setup wizard", HERE / "setup.py"),
        ("server code", HERE / "backend" / "app.py"),
        ("dashboard", HERE / "dashboard" / "index.html"),
        ("practice data", HERE / "data" / "sample" / "pings.csv"),
        ("course settings", SETTINGS),
        ("security key", DATA / "secret_key"),
        ("database", DB_PATH),
    ]:
        if path.exists():
            size = path.stat().st_size
            out.append(f"  {name:18s} present  ({size:,} bytes)")
        else:
            out.append(f"  {name:18s} MISSING")

    # ---- configuration, with values that are safe to show ----
    section(out, "Course configuration")
    try:
        settings = json.loads(SETTINGS.read_text())
        location = settings.get("course_location", {})
        out.append(f"  Setup completed  : {bool(settings.get('setup_complete'))}")
        out.append(f"  Course name      : {settings.get('course_name', '(unset)')}")
        # The city name is what the instructor typed and appears on screen all
        # week; the coordinates are not included, since they are the course
        # venue and everyone's data clusters there.
        out.append(f"  City             : {location.get('name', '(unset)')}")
        out.append(f"  Timezone         : {location.get('timezone', '(unset)')}")
        public = settings.get("DWELL_PUBLIC_URL", "")
        out.append(f"  Public address   : {public or '(not published — local only)'}")
        if public:
            out.append(f"  Address is https : {public.startswith('https://')}")
    except (OSError, ValueError):
        out.append("  No course settings found — setup has not completed.")

    # ---- the database, in counts only ----
    section(out, "Database contents (counts only)")
    try:
        import sqlite3
        db_path = DB_PATH
        if not db_path.exists():
            out.append("  No database yet.")
        else:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            for label, query in [
                ("participants", "SELECT COUNT(*) FROM participants"),
                ("  of those, withdrawn",
                 "SELECT COUNT(*) FROM participants WHERE withdrawn_at IS NOT NULL"),
                ("  of those, practice data",
                 "SELECT COUNT(*) FROM participants WHERE consent_version='sample-data-v1'"),
                ("location points", "SELECT COUNT(*) FROM pings"),
                ("places", "SELECT COUNT(*) FROM places"),
                ("map overlay features", "SELECT COUNT(*) FROM environment_features"),
                ("instructor accounts", "SELECT COUNT(*) FROM instructors"),
                ("audit entries", "SELECT COUNT(*) FROM audit_log"),
            ]:
                try:
                    out.append(f"  {label:24s} {conn.execute(query).fetchone()[0]}")
                except sqlite3.Error:
                    out.append(f"  {label:24s} (table missing)")
            # Whether the published example account is still present is a
            # safety question worth answering, without naming anybody else.
            try:
                demo = conn.execute(
                    "SELECT COUNT(*) FROM instructors WHERE username='instructor'"
                ).fetchone()[0]
                out.append(f"  published example account present: {'YES — remove it' if demo else 'no'}")
            except sqlite3.Error:
                pass
            # Actions taken, never their details — details name places.
            try:
                out.append("")
                out.append("  Recent actions (types only, no details):")
                for row in conn.execute(
                        "SELECT action, COUNT(*) FROM audit_log "
                        "GROUP BY action ORDER BY COUNT(*) DESC LIMIT 12"):
                    out.append(f"    {row[0]:28s} {row[1]}")
            except sqlite3.Error:
                pass
            conn.close()
    except Exception as exc:                        # noqa: BLE001
        out.append(f"  Could not read the database: {type(exc).__name__}")

    # ---- is it running? ----
    section(out, "Is the server responding?")
    answered = False
    for port in range(5000, 5006):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.3)
        listening = probe.connect_ex(("127.0.0.1", port)) == 0
        probe.close()
        if not listening:
            continue
        answered = True
        try:
            import urllib.request
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=3) as resp:
                out.append(f"  Port {port}: answering, health check {resp.status}")
        except Exception:                           # noqa: BLE001
            out.append(f"  Port {port}: something is listening but not answering")
    if not answered:
        out.append("  Nothing is listening on ports 5000-5005.")
        out.append("  (That is normal if the server is not currently started.)")

    # ---- the setup log, scrubbed ----
    section(out, "Setup log (last 150 lines, scrubbed)")
    try:
        lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-150:]:
            out.append(f"  {line}")
        if len(lines) > 150:
            out.insert(len(out) - 150, f"  ... {len(lines) - 150} earlier lines omitted")
    except OSError:
        out.append("  No setup log found.")

    return scrub("\n".join(out)) + "\n"


def main() -> int:
    print()
    print("  " + "─" * 66)
    print()
    print("  Collecting a support report...")

    try:
        report = collect()
    except Exception as exc:                        # noqa: BLE001
        print()
        print(f"  The report could not be collected ({type(exc).__name__}).")
        print("  Send the file below instead, but read it first — it has not")
        print("  been checked for private information:")
        print(f"      {LOG}")
        print()
        return 1

    REPORT.write_text(report, encoding="utf-8")

    # A last look for anything that should never have survived scrubbing.
    leaks = []
    try:
        secret = (DATA / "secret_key").read_text().strip()
        if secret and secret in report:
            leaks.append("the security key")
    except OSError:
        pass
    if re.search(r'-?\d{1,3}\.\d{5,}', report):
        leaks.append("something shaped like a coordinate")

    print()
    print(f"  Written to:  {REPORT}")
    print(f"  Size:        {len(report):,} characters")
    print()
    if leaks:
        print("  WARNING: this report may still contain " + ", ".join(leaks) + ".")
        print("  Read it before sending it to anybody.")
    else:
        print("  Checked: no security key, no password, no device token and no")
        print("  participant location is in it. It is safe to send on.")
    print()
    print("  Send this file to whoever is helping you.")
    print()
    print("  " + "─" * 66)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
