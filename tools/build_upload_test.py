#!/usr/bin/env python3
"""
What reaches the phone app's build, and what must never.

    python3 tools/build_upload_test.py

`eas build` sends a copy of this repository to Expo's build servers. Two
opposite mistakes are possible, and this checks for both:

  * the course server's address does NOT reach the build, so the app that comes
    back has nowhere to send anything and tells participants it has not been
    set up. That was the state of things before `.easignore` existed;

  * participant data DOES reach the build. `.easignore` replaces every
    `.gitignore` in the project when it exists, so the protections that keep
    the course database out of the repository do not apply to the upload. A
    line missing here would post everybody's location history to a build
    server.

How it checks
-------------
Rather than reimplementing the ignore rules — the mistake would be in the
reimplementation — it builds a scratch repository, drops `.easignore` in as its
`.gitignore`, creates the paths in question, and asks git. Git's matching is
what the ignore library used by EAS is emulating, so this is the closest
answerable version of the question without an Expo account.

What it cannot tell you: that Expo's servers behave as documented. That needs a
real build, and `docs/REAL_DEPLOYMENT_STATUS.md` says so plainly.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# (path, must_be_uploaded, why)
CASES: list[tuple[str, bool, str]] = [
    # The reason this file exists.
    ("app/.env", True,
     "the course server's address; without it the built app collects nothing"),
    ("app/app.json", True, "the app's own configuration"),
    ("app/eas.json", True, "the build profiles"),
    ("app/App.tsx", True, "the app"),
    ("app/src/config.ts", True, "the app's settings"),
    ("app/package.json", True, "the app's dependencies"),
    ("app/assets/icon.png", True, "the app's icon"),

    # The things that would be a disclosure.
    ("data/local/course.db", False, "every participant's location history"),
    ("data/local/secret_key", False, "the key that signs instructor sign-ins"),
    ("data/local/sample_participant_tokens.json", False, "device tokens"),
    ("data/local/setup-log.txt", False, "the setup log for this installation"),
    ("data/local/course.json", False, "this installation's settings"),
    ("deploy/UPLOAD_THIS.zip", False, "a server bundle holding the secret key"),
    ("deploy/wsgi_for_host.py", False, "generated, and holds the secret key"),
    ("support-report.txt", False, "a support report about this machine"),
    ("course.db", False, "a database, wherever it was put"),
    ("backend/anything.sqlite3", False, "a database, wherever it was put"),

    # Bulk that has no business in an upload.
    (".venv/bin/python", False, "the Python workspace"),
    ("node_modules/react/index.js", False, "installed packages"),
    ("app/node_modules/expo/package.json", False, "installed packages"),
]

# app/.env must be kept OUT of the repository at the same time as it is kept IN
# the upload. Those two rules live in different files and it is easy to fix one
# by breaking the other, so both are checked here, together.
MUST_NOT_BE_COMMITTED = ["app/.env", "data/local/course.db",
                         "data/local/secret_key", "support-report.txt"]

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))
        failures.append(name)


def ignored_by(rules: Path, paths: list[str]) -> set[str]:
    """
    Which of `paths` a git-style ignore file excludes.

    Asked in a scratch repository so that the real one is untouched and so the
    answer does not depend on which files happen to exist here.
    """
    work = Path(tempfile.mkdtemp(prefix="dwell-upload-"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=work, check=True,
                       capture_output=True)
        shutil.copyfile(rules, work / ".gitignore")
        for p in paths:
            target = work / p
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x")
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-z", "--stdin"],
            cwd=work, input="\0".join(paths), capture_output=True, text=True)
        return {p for p in result.stdout.split("\0") if p}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    print("\n  What reaches the phone app's build\n")

    easignore = HERE / ".easignore"
    if not easignore.exists():
        check(".easignore exists at the top of the project", False,
              "Without it, EAS follows .gitignore, which excludes app/.env — "
              "so the built app would not know where the course server is.")
        print()
        return 1
    check(".easignore exists at the top of the project", True)

    paths = [c[0] for c in CASES]
    excluded = ignored_by(easignore, paths)

    for path, should_upload, why in CASES:
        uploaded = path not in excluded
        if should_upload:
            check(f"reaches the build: {path}", uploaded,
                  f"It is excluded, and it is needed — {why}.")
        else:
            check(f"stays out of the build: {path}", not uploaded,
                  f"It would be uploaded to Expo's build servers, and it is "
                  f"{why}.")

    # The other half: the address must still be kept out of the repository.
    gitignored = ignored_by(HERE / ".gitignore", MUST_NOT_BE_COMMITTED)
    for path in MUST_NOT_BE_COMMITTED:
        check(f"stays out of the repository: {path}", path in gitignored,
              "It is not excluded by .gitignore, so it could be committed.")

    print()
    if failures:
        print(f"  {len(failures)} check(s) FAILED\n")
        return 1
    print("  All build-upload checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
