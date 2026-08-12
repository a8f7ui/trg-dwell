#!/usr/bin/env python3
"""
Dwell: Privacy Lab.

    python3 dwell.py            what can I do?
    python3 dwell.py start      start the course server
    python3 dwell.py check      is everything still working?
    python3 dwell.py deploy     put it on the internet for real phones
    python3 dwell.py app        prepare the phone app for your course

One command with a handful of words after it, rather than a dozen scripts. If
you have not run `python3 setup.py` yet, every one of these will say so.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "local"
SETTINGS = DATA / "course.json"
DEPLOY = HERE / "deploy"

W = 68


def rule() -> None:
    print("  " + "─" * W)


def say(text: str = "") -> None:
    print(f"  {text}" if text else "")


def title(text: str) -> None:
    print(f"\n  {text}\n")


def venv_python() -> Path:
    return HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        return {}


def require_setup() -> dict:
    s = settings()
    if not s.get("setup_complete") or not venv_python().exists():
        print()
        rule()
        title("This has not been set up yet")
        say("Run this first — it takes a couple of minutes and asks four")
        say("questions:")
        say()
        say("      python3 setup.py")
        rule()
        print()
        sys.exit(1)
    return s


# --------------------------------------------------------------------------

def cmd_start(_args: list[str]) -> int:
    require_setup()
    return subprocess.run([sys.executable, str(HERE / "start.py")]).returncode


def cmd_check(args: list[str]) -> int:
    require_setup()
    return subprocess.run(
        [str(venv_python()), str(HERE / "verify.py")] + args).returncode


def cmd_app(_args: list[str]) -> int:
    """Write the server address into the phone app's build settings."""
    s = require_setup()
    address = s.get("DWELL_PUBLIC_URL", "")

    print()
    rule()
    title("Preparing the phone app")

    if not address:
        say("The app needs to know the web address of your course server, and")
        say("this computer does not have one yet — the server is only running")
        say("locally.")
        say()
        say("Run this first, which sets one up:")
        say()
        say("      python3 dwell.py deploy")
        rule()
        print()
        return 1

    if not address.startswith("https://"):
        say(f"The address saved for your server is:  {address}")
        say()
        say("iPhones refuse to send anything to an address that is not https,")
        say("and they do it silently — the app would look fine and collect")
        say("nothing. So this will not continue with that address.")
        say()
        say("Run `python3 dwell.py deploy` again and use the https address")
        say("your host gave you.")
        rule()
        print()
        return 1

    env_path = HERE / "app" / ".env"
    env_path.write_text(
        "# Written by `python3 dwell.py app`. Do not edit by hand.\n"
        "# This is how the phone app knows where your course server is.\n"
        f"EXPO_PUBLIC_DWELL_SERVER={address}\n")

    say(f"The app will send its data to:  {address}")
    say()
    say("Saved. Nothing in the app's code needs changing.")
    say()

    # The address is written into the app when it is built, not when it runs,
    # so it has to survive the trip to the build service. It does that because
    # of `.easignore`; without it the address is treated as a private file and
    # left behind, and the app comes back saying it has not been set up.
    if not (HERE / ".easignore").exists():
        say("WARNING: the file `.easignore` is missing from this folder. Without")
        say("it, the address above will not reach the build service, and the")
        say("app that comes back will not know where to send anything.")
        say()

    project_id = expo_project_id()
    if project_id:
        say(f"This project is already linked to Expo (id ending {project_id[-6:]}).")
    else:
        say("This project is not linked to an Expo account yet. That link is the")
        say("one step that needs a person — it means signing in — and it is the")
        say("first of the commands in the file below.")
    say()
    rule()
    title("What only a person can do")
    say("Building an app that installs on real phones needs accounts that")
    say("Apple, Google and Expo will only give to a human being.")
    say()
    say("Written for you:  deploy/PHONE_APP_STEPS.txt")
    say()
    say("It lists exactly what to sign up for, what it costs, and the two")
    say("commands to run afterwards. There are no decisions left in it.")
    rule()
    print()
    write_phone_steps(address)
    return 0


# --------------------------------------------------------------------------

def cmd_deploy(_args: list[str]) -> int:
    """Generate everything a web host needs, and isolate what a person must do."""
    s = require_setup()
    DEPLOY.mkdir(exist_ok=True)

    print()
    rule()
    title("Putting your course server on the internet")
    say("Your server currently runs only on this computer, which is fine for")
    say("teaching from a laptop but cannot be reached by phones.")
    say()
    say("Putting it online needs an account somewhere. Creating an account is")
    say("the one thing no software can do for you — it needs a person to")
    say("accept terms and confirm an email address.")
    say()
    say("Everything after that account exists is done for you here.")
    rule()

    say()
    username = input("  Your PythonAnywhere username (or press Enter to decide later)\n  > ").strip()
    if not username:
        write_host_steps(None, s)
        say()
        say("No problem. Written for you:  deploy/HOSTING_STEPS.txt")
        say("It walks through creating the free account. Run this again after.")
        print()
        return 0

    address = f"https://{username}.pythonanywhere.com"
    secret = read_secret()

    # The file the host runs. Complete, with real values, nothing to edit.
    (DEPLOY / "wsgi_for_host.py").write_text(f'''"""
Generated by `python3 dwell.py deploy`. Do not edit.

This is the file your web host runs to start the course server. Every value in
it is already filled in for your course.
"""

import os
import sys

PROJECT = "/home/{username}/trg-dwell"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# Where the course data lives — deliberately outside the code folder, so that
# updating the code can never touch participant data.
os.environ["DWELL_DB"] = "/home/{username}/dwell-data/course.db"
os.environ["DWELL_SETTINGS"] = "/home/{username}/dwell-data/course.json"

# The public address, which is what makes sign-in cookies https-only.
os.environ["DWELL_PUBLIC_URL"] = "{address}"

# The key that signs instructor sign-ins. Generated for your course.
os.environ["DWELL_SECRET_KEY"] = "{secret}"

from wsgi import application  # noqa: E402,F401
''')

    # The settings file that travels with it.
    hosted = dict(s, DWELL_PUBLIC_URL=address)
    (DEPLOY / "course.json").write_text(json.dumps(hosted, indent=2) + "\n")

    # Remember the address so `dwell.py app` can use it.
    SETTINGS.write_text(json.dumps(hosted, indent=2) + "\n")

    bundle = make_bundle()
    write_host_steps(username, hosted)

    say()
    rule()
    title("Ready to upload")
    say(f"Your course will live at:  {address}")
    say()
    say("Three files have been prepared in the “deploy” folder:")
    say()
    say(f"    UPLOAD_THIS.zip      the whole course server ({bundle // 1024} KB)")
    say("    wsgi_for_host.py     the start-up file, already filled in")
    say("    HOSTING_STEPS.txt    what to click, in order")
    say()
    say("Open HOSTING_STEPS.txt and follow it. It is six steps, all clicking,")
    say("no typing except your password.")
    rule()
    print()
    return 0


def read_secret() -> str:
    path = DATA / "secret_key"
    try:
        return path.read_text().strip()
    except OSError:
        import secrets
        return secrets.token_urlsafe(48)


def make_bundle() -> int:
    """Zip exactly what the host needs and nothing else."""
    import zipfile

    include_dirs = ["backend", "dashboard", "tools", "data/sample"]
    include_files = ["wsgi.py", "manage.py", "requirements.txt", "verify.py",
                     "start.py", "LICENSE"]
    target = DEPLOY / "UPLOAD_THIS.zip"

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for d in include_dirs:
            root = HERE / d
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    z.write(path, f"trg-dwell/{path.relative_to(HERE)}")
        for f in include_files:
            if (HERE / f).exists():
                z.write(HERE / f, f"trg-dwell/{f}")
    return target.stat().st_size


def write_host_steps(username: str | None, s: dict) -> None:
    name = username or "YOURNAME"
    address = s.get("DWELL_PUBLIC_URL") or f"https://{name}.pythonanywhere.com"
    (DEPLOY / "HOSTING_STEPS.txt").write_text(f"""
PUTTING YOUR COURSE SERVER ON THE INTERNET
==========================================

Only the numbered steps need a person. Everything else is already done.

Time: about twenty minutes. Cost: nothing.


WHY THIS STEP EXISTS
--------------------
Phones cannot reach a server running on your laptop. They need an address on
the internet. Getting one means having an account somewhere, and creating an
account needs a human to accept terms and confirm an email address. That is the
only part of this that software cannot do for you.


{"" if username else '''
STEP 0 — CREATE THE FREE ACCOUNT
--------------------------------
  a. Go to  https://www.pythonanywhere.com
  b. Click "Pricing & signup", then "Create a Beginner account" (the free one).
  c. It does NOT ask for a card.
  d. Confirm the email it sends you.
  e. Come back here and run:   python3 dwell.py deploy
     — this time enter the username you just chose.

Stop here until you have done that.
'''}

STEP 1 — SIGN IN
----------------
  Go to  https://www.pythonanywhere.com  and sign in as: {name}


STEP 2 — UPLOAD THE COURSE SERVER
---------------------------------
  a. Click the "Files" tab at the top.
  b. Click "Upload a file".
  c. Choose:  deploy/UPLOAD_THIS.zip   (from this computer)
  d. Wait for it to finish.


STEP 3 — UNPACK IT
------------------
  a. Click the "Consoles" tab, then "Bash".
  b. Copy this line, paste it in, and press Enter:

       unzip -o UPLOAD_THIS.zip && mkdir -p ~/dwell-data && cd trg-dwell && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && echo DONE

  c. Wait for it to say DONE. It takes two or three minutes.


STEP 4 — CREATE THE WEB APP
---------------------------
  a. Click the "Web" tab, then "Add a new web app".
  b. Click "Next" at the domain step (the free plan gives you {name}.pythonanywhere.com).
  c. Choose "Manual configuration".
  d. Choose the newest Python version offered.
  e. Click "Next".


STEP 5 — POINT IT AT THE COURSE SERVER
--------------------------------------
  Still on the "Web" tab:

  a. Find "Virtualenv". Click it and enter exactly:

       /home/{name}/trg-dwell/.venv

  b. Look for a link labelled "WSGI configuration file" — that is just the
     name of this host's start-up file. Click it to edit.
  c. Select everything in that file and delete it.
  d. Open  deploy/wsgi_for_host.py  on this computer, copy ALL of it,
     and paste it in.
  e. Click "Save".

  (That file already contains every setting for your course. Nothing in it
   needs changing.)


STEP 6 — START IT
-----------------
  a. Scroll to the top of the "Web" tab.
  b. Click the big green "Reload" button.
  c. Wait about ten seconds.
  d. Open:  {address}

  You should see the sign-in page. Use the name and password setup gave you.


IF SOMETHING IS WRONG
---------------------
  On the "Web" tab there is an "Error log" link. Open it and read the last few
  lines. Send those lines to whoever set this up for you.


AFTERWARDS
----------
  Come back to this computer and run:

       python3 dwell.py check --production

  It confirms the live server is set up safely before real people use it.


ONE THING TO DIARISE
--------------------
  A free PythonAnywhere account switches itself off after three months unless
  you click a button. If you are setting this up well before the course, put a
  reminder in your calendar to sign in and click "Run until 3 months from
  today" on the "Web" tab.
""".strip() + "\n")


def expo_project_id() -> str:
    """
    The Expo project this is linked to, or "" if it has not been linked yet.

    `eas build` refuses to start without one, and the link is created by
    `eas init`, which needs somebody to be signed in to an Expo account. That
    cannot be done here or invented, so the honest thing is to detect it and
    say which state you are in.
    """
    try:
        config = json.loads((HERE / "app" / "app.json").read_text())
    except (OSError, ValueError):
        return ""
    extra = config.get("expo", {}).get("extra", {})
    return str(extra.get("eas", {}).get("projectId") or "")


def write_phone_steps(address: str) -> None:
    (DEPLOY / "PHONE_APP_STEPS.txt").write_text(f"""
PUTTING THE APP ON PARTICIPANTS' PHONES
=======================================

Your server address is already written into the app. Nothing in the app's code
needs editing.

What remains needs accounts that Apple, Google and Expo will only give to a
human being, because they verify identity and take payment. That is why these
steps are here rather than automated.

Server the app will use:  {address}


WHAT YOU MUST SIGN UP FOR
-------------------------

  1. Expo account                                          FREE
     https://expo.dev/signup
     This is the service that builds the app for you, so you do not need a Mac.

  2. Apple Developer Program                               $99 / year
     https://developer.apple.com/programs/enroll
     Required for iPhones. Enrolment as an organisation needs a D-U-N-S number
     and can take a few days, so start this early.

  3. Google Play Developer account                         $25 once
     https://play.google.com/console/signup
     Required for Android.

  Android only? You can skip 2 and 3 entirely — see "The shortcut" below.


THEN RUN TWO COMMANDS
---------------------

  In this folder, run:

      cd app
      npx eas-cli@latest login          (sign in with the Expo account)
      npx eas-cli@latest init           (links this to your Expo account)
      npx eas-cli@latest build --platform all --profile preview

  The build happens on Expo's computers and takes 15–30 minutes. You get two
  download links at the end.


THE SHORTCUT, IF YOU ONLY NEED ANDROID
--------------------------------------
  The Android build from the command above is an .apk file. You can send that
  link straight to participants — no Google account, no review, no waiting.
  They tap it, allow "install from this source", and it installs.

  iPhones cannot do this. Apple requires TestFlight, which requires the $99
  account and a review that takes 1–3 days.


BEFORE YOU SEND IT TO ANYONE
----------------------------
  Install it on your own phone first and carry it for two days. Check that:

    - the map fills in overnight, not just while you are using the phone
    - the "Collection is ON" notice stays visible on Android
    - the evening summary arrives
    - your day looks like the day you actually had

  Nothing else substitutes for this. A server test cannot tell you whether a
  phone kept collecting while it was in your pocket.
""".strip() + "\n")


# --------------------------------------------------------------------------

def cmd_diagnose(_args: list[str]) -> int:
    """A support report with nothing private in it. Works even if setup failed."""
    return subprocess.run([sys.executable, str(HERE / "diagnose.py")]).returncode


def cmd_help(_args: list[str]) -> int:
    s = settings()
    ready = s.get("setup_complete")
    print()
    rule()
    title(f"Dwell: Privacy Lab{' — ' + s['course_name'] if s.get('course_name') else ''}")
    if not ready:
        say("Not set up yet. Start here:")
        say()
        say("      python3 setup.py")
        say()
        say("It asks four questions and does everything else itself.")
        rule()
        print()
        return 0

    say("  python3 dwell.py start      start the course server")
    say("  python3 dwell.py check      confirm everything still works")
    say("  python3 dwell.py deploy     put it on the internet for real phones")
    say("  python3 dwell.py app        prepare the app for participants' phones")
    say("  python3 dwell.py diagnose   collect a support report if something is wrong")
    say()
    if s.get("DWELL_PUBLIC_URL"):
        say(f"Your course server:  {s['DWELL_PUBLIC_URL']}")
    else:
        say("Your course runs on this computer only. `deploy` changes that.")
    rule()
    print()
    return 0


COMMANDS = {
    "start": cmd_start,
    "check": cmd_check,
    "deploy": cmd_deploy,
    "app": cmd_app,
    "diagnose": cmd_diagnose,
    "help": cmd_help,
}


def main() -> int:
    if len(sys.argv) < 2:
        return cmd_help([])
    name = sys.argv[1].lstrip("-")
    if name not in COMMANDS:
        print(f"\n  There is no command called “{sys.argv[1]}”.\n")
        return cmd_help([])
    return COMMANDS[name](sys.argv[2:])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
        sys.exit(1)
