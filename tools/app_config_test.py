#!/usr/bin/env python3
"""
Is the phone app configured to do what it claims?

    python3 tools/app_config_test.py

Background location is the whole exercise. If any one of a dozen small
configuration details is wrong, the app installs, opens, asks for permission,
looks completely normal — and then collects nothing once the screen goes off.
That failure is invisible until the evening, in front of a room, when the map
turns out to be empty.

None of this can be checked by running the app on a laptop, and all of it can
be checked by reading what the build will be told. So it is checked here.

What this cannot tell you is whether a real handset honours any of it. Both
platforms throttle, defer and kill background work in ways no configuration
file describes; `docs/device-checklist.md` is the part a person has to do.

Two things are reported as blocked rather than failed: the Expo project link
and the account that owns it. Both need somebody to sign in to an Expo account,
and neither can be invented here.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
APP = HERE / "app"

failures: list[str] = []
blocked: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))
        failures.append(name)
    return ok


def note_blocked(name: str, detail: str) -> None:
    print(f"  ----  {name}: {detail}")
    blocked.append(name)


def main() -> int:
    print("\n  The phone app's configuration\n")

    try:
        app_json = json.loads((APP / "app.json").read_text())
        eas_json = json.loads((APP / "eas.json").read_text())
    except (OSError, ValueError) as exc:
        check("app.json and eas.json are readable JSON", False, str(exc))
        return 1
    expo = app_json.get("expo", {})
    ios = expo.get("ios", {})
    android = expo.get("android", {})
    info = ios.get("infoPlist", {})
    plugins = expo.get("plugins", [])

    def plugin(name: str) -> dict | None:
        for entry in plugins:
            if entry == name:
                return {}
            if isinstance(entry, list) and entry and entry[0] == name:
                return entry[1] if len(entry) > 1 else {}
        return None

    # ---- identity -----------------------------------------------------------
    check("the app has a name and a slug",
          bool(expo.get("name")) and bool(expo.get("slug")))
    check("iOS and Android use the same identifier",
          bool(ios.get("bundleIdentifier"))
          and ios.get("bundleIdentifier") == android.get("package"),
          f"iOS {ios.get('bundleIdentifier')!r} vs Android "
          f"{android.get('package')!r}")
    check("the identifier is not an example one",
          not any(bad in str(ios.get("bundleIdentifier", "")).lower()
                  for bad in ("example", "yourcompany", "anonymous", "changeme")),
          f"it is {ios.get('bundleIdentifier')!r}")
    check("there is a version number", bool(expo.get("version")))

    # ---- build numbers ------------------------------------------------------
    # With remote version source, EAS keeps the build numbers and increments
    # them. Hard-coding them as well is how two builds end up with the same
    # number, which stores reject.
    remote = eas_json.get("cli", {}).get("appVersionSource") == "remote"
    check("build numbers are managed by the build service", remote,
          "set cli.appVersionSource to \"remote\" in eas.json")
    if remote:
        check("...and are therefore not also hard-coded here",
              "buildNumber" not in ios and "versionCode" not in android,
              "remove ios.buildNumber / android.versionCode from app.json")

    # ---- the link to an Expo account ----------------------------------------
    project_id = expo.get("extra", {}).get("eas", {}).get("projectId")
    if project_id:
        check("linked to an Expo project", True)
    else:
        note_blocked(
            "linked to an Expo project",
            "not linked yet. `eas build` will not start without this. Run "
            "`npx eas-cli@latest init` in the app folder while signed in — it "
            "is the one step that needs a person, and it cannot be invented "
            "here.")
    if expo.get("owner"):
        check("the owning Expo account is recorded", True)
    else:
        note_blocked(
            "the owning Expo account is recorded",
            "not set. Only needed when the Expo account is an organisation "
            "rather than a person; `eas init` sets it when it applies.")

    # ---- build profiles -------------------------------------------------------
    build = eas_json.get("build", {})
    for profile in ("development", "preview", "production"):
        check(f"there is a {profile} build profile", profile in build)
    preview = build.get("preview", {})
    check("the preview build produces an installable Android file",
          preview.get("android", {}).get("buildType") == "apk",
          "an app-bundle cannot be sideloaded, and sideloading is how "
          "participants get this without a Play account")
    check("the preview build is not an iOS simulator build",
          preview.get("ios", {}).get("simulator") is not True,
          "a simulator build will not install on a real iPhone")
    check("the production build produces a Play-uploadable file",
          build.get("production", {}).get("android", {}).get("buildType")
          == "app-bundle")

    # No invented account identifiers anywhere.
    submit = json.dumps(eas_json.get("submit", {}))
    check("no placeholder account identifiers are left in eas.json",
          "REPLACE_WITH" not in submit and "TODO" not in submit.upper(),
          "a placeholder here fails the submit step with a confusing error; "
          "leave the field out and be prompted for it instead")

    # ---- Android background location ------------------------------------------
    permissions = android.get("permissions", [])
    for needed, why in [
        ("ACCESS_FINE_LOCATION", "precise location"),
        ("ACCESS_COARSE_LOCATION", "location at all on some devices"),
        ("ACCESS_BACKGROUND_LOCATION", "collecting once the screen is off"),
        ("FOREGROUND_SERVICE", "the service that keeps collection alive"),
        ("FOREGROUND_SERVICE_LOCATION",
         "required since Android 14; without it the service is refused"),
        ("POST_NOTIFICATIONS",
         "required since Android 13 for the evening reveal to appear"),
    ]:
        check(f"Android asks for {needed}", needed in permissions,
              f"needed for {why}")

    location_plugin = plugin("expo-location")
    check("the location plugin is configured", location_plugin is not None)
    if location_plugin is not None:
        check("Android background location is switched on in the build",
              location_plugin.get("isAndroidBackgroundLocationEnabled") is True,
              "without this the manifest permission is not enough")
        check("the Android foreground service is switched on in the build",
              location_plugin.get("isAndroidForegroundServiceEnabled") is True,
              "without this, collection stops when the app is backgrounded")
        for key in ("locationWhenInUsePermission",
                    "locationAlwaysAndWhenInUsePermission"):
            text = location_plugin.get(key) or ""
            check(f"the {key} wording is present and specific",
                  len(text) > 60,
                  "stores reject vague permission text, and a participant "
                  "deserves to be told what they are agreeing to")

    # ---- iOS background location ------------------------------------------------
    modes = info.get("UIBackgroundModes", [])
    check("iOS declares the location background mode", "location" in modes,
          "without it iOS suspends the app and collection stops when the "
          "screen locks")
    check("iOS declares the fetch background mode", "fetch" in modes,
          "used by the task manager to deliver queued work")
    for key in ("NSLocationWhenInUseUsageDescription",
                "NSLocationAlwaysAndWhenInUseUsageDescription"):
        text = info.get(key) or ""
        check(f"iOS has a real {key}", len(text) > 60,
              "an app with a missing or vague one is rejected, and the text "
              "is what a participant reads at the prompt")

    always = info.get("NSLocationAlwaysAndWhenInUseUsageDescription", "")
    check("the iOS 'always' wording says instructors can see the data",
          "instructor" in always.lower(),
          "this is the sentence somebody reads before agreeing to be "
          "followed for a week; it must not be coy about who watches")
    check("the iOS 'always' wording says it can be stopped",
          "stop" in always.lower() or "delete" in always.lower())

    check("iOS declares its encryption status",
          info.get("ITSAppUsesNonExemptEncryption") is False,
          "without it every TestFlight upload stops and asks")

    # ---- notifications -----------------------------------------------------------
    notif = plugin("expo-notifications")
    check("the notifications plugin is configured", notif is not None)
    if notif is not None:
        icon = notif.get("icon")
        check("the Android notification has its own icon", bool(icon),
              "without one, Android draws a white or grey square")
        if icon:
            check("...and that icon file exists", (APP / icon).exists(),
                  f"{icon} is missing")

    # ---- the server address --------------------------------------------------------
    config_ts = (APP / "src" / "config.ts").read_text()
    # Comments removed first. This file explains at length why the old
    # localhost default was dangerous, and that explanation should not be the
    # thing that fails the check against it.
    code = re.sub(r"/\*.*?\*/", "", config_ts, flags=re.S)
    # Not preceded by a colon, or this strips the tail off every http:// URL in
    # the file — including the one it is looking for, which made this check
    # pass on exactly the code it exists to reject.
    code = re.sub(r"(?<!:)//.*", "", code)
    check("the app has no hard-coded server address",
          "localhost" not in code and "127.0.0.1" not in code,
          "a localhost default means the phone talks to itself: the app looks "
          "like it is working and collects nothing")
    check("the server address comes from the build environment",
          "EXPO_PUBLIC_DWELL_SERVER" in config_ts)
    check("an unconfigured build says so rather than guessing",
          "HAS_SERVER_CONFIGURED" in config_ts)

    # ---- nothing that watches the participant ---------------------------------------
    package = json.loads((APP / "package.json").read_text())
    deps = list(package.get("dependencies", {}))
    watchers = [d for d in deps if any(bad in d.lower() for bad in (
        "analytics", "sentry", "bugsnag", "firebase", "amplitude", "mixpanel",
        "segment", "facebook", "appsflyer", "adjust", "branch"))]
    check("the app depends on nothing that reports on its users", not watchers,
          f"found {watchers} — in a privacy-education tool")

    print()
    if blocked:
        print(f"  {len(blocked)} item(s) need an Expo account and are listed "
              f"above with a dash.")
    if failures:
        print(f"  {len(failures)} check(s) FAILED\n")
        return 1
    print("  All app-configuration checks passed.")
    print("  This says the build will be told the right things. It does not\n"
          "  say a real handset honours them — see docs/device-checklist.md.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
