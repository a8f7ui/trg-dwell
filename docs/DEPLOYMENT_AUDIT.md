# Deployment audit

**Date:** 11 August 2026
**Scope:** entire repository — backend, dashboard, mobile app, tooling, docs,
hosting and store configuration
**Method:** source inspection and execution. Every claim below was tested
against running code, not read from documentation. Where something could not be
tested here, that is stated rather than assumed.
**Target course:** Milwaukee, mid-to-late September 2026

---

## Executive summary

The software is in better shape than its deployment path. The server, the
analysis and the dashboard are genuinely solid and genuinely tested — 55
automated checks pass, the mobile app typechecks cleanly under `strict`, and
18 of 20 `expo-doctor` checks pass. A person can go from a fresh clone to a
working demo with one command in about ninety seconds.

**None of that is the problem.** The problem is the gap between *demo on a
laptop* and *course on real phones*, and there are four defects in that gap
that will each independently ruin the week.

Two of them are severe and neither is visible in any current test:

1. **`start.py` destroys real participant registrations.** Proven: three
   genuinely registered participants became zero, and the demo instructor
   account — whose password is published in this repository — was installed on
   the server. The trigger is a server where phones have registered but no
   location data has arrived yet, which is precisely the state of a course
   server between sending install links and the first upload.

2. **Days are bucketed by UTC date, not local date.** Proven: one Milwaukee
   day (08:00–22:00 local) became two server days, and the 20:30 evening
   reveal — the centrepiece of the entire course — showed **13 of 57 points**.
   This is invisible in testing because the sample-data generator writes
   timestamps with a local offset while real phones send UTC. Every one of the
   55 checks passes while this is broken.

Alongside those, the app cannot currently be built for distribution at all
(`eas init` has never been run, so there is no EAS project), and every build
requires hand-editing a TypeScript file to set the server address.

The honest summary: **the demo is ready; the deployment is not.** The work
needed is about three days, is well understood, and is listed in order below.

---

## Current architecture

```
  Participant phone                Server                    Instructor
  ─────────────────                ──────                    ──────────
  Expo / React Native      →   Flask + SQLite        →   Browser dashboard
  expo-location                 single file DB            Leaflet, plain JS
  background task               no DB server              login-gated
  queue + batch upload          gunicorn or PA WSGI
        │                             │                          │
        │  4 HTTPS calls, bearer token│                          │
        └─────────────────────────────┘                          │
                                      └──────── session cookie ──┘
```

**Server** — Flask 3.1.3, SQLite, two pure-Python dependencies. Participant
routes (`/api/v1/*`) authenticate by device token; instructor routes
(`/api/instructor/*`) by login session. Serves the dashboard as static files,
so if the server is up the dashboard is up.

**Phone** — Expo SDK 57 / React Native 0.86. A registered OS background task
delivers location fixes, which are queued in AsyncStorage and uploaded in
batches of 25. The device token lives in the platform keystore. Exactly four
network calls exist.

**Dashboard** — plain JavaScript, no build step, Leaflet vendored locally.
Two visual skins over identical data.

**Data** — one SQLite file. Schema created idempotently on every connection,
with an additive migration step for columns introduced later.

---

## Verified working components

Everything in this section was executed during the audit.

| Component | How it was verified | Result |
|---|---|---|
| One-command setup | Fresh clone, `python3 start.py` | Working server in ~90 s, 11 pure-Python packages |
| Server + all endpoints | `verify.py` | **55/55 pass** |
| Phone↔server API contract | `tools/contract_test.py` | **34/34 pass** |
| Mobile app types | `tsc --noEmit`, `strict: true` | **0 errors**; proven non-vacuous by injecting an error |
| Expo config | `expo config`, `expo-doctor` | Resolves; **18/20** checks pass (2 need network) |
| Production WSGI entry | `gunicorn wsgi:application` | Serves HTTP 200 |
| Privacy: k-anonymity | `verify.py`, threshold 5 and 1 | Suppression correct; k=1 exposes single-person cells |
| Privacy: no cross-participant leakage | `verify.py` + contract test | A reveal names no other participant |
| Token auth | contract test | Token stops working immediately on withdrawal |
| Login rate limiting | code + contract test | Per-username and per-IP lockout present |
| Password storage | `backend/auth.py` | scrypt, N=2^14, constant-time compare |
| Token storage | `backend/auth.py` | SHA-256 hashed at rest |
| Dashboard in a browser | Playwright, every screen, both skins | No JavaScript errors |
| Course location | API + UI test | Set, read back, reset; validation rejects swapped lat/lon and DST-less zones |

---

## Unverified components

Not broken — **unproven**. Each needs a real device or a real network.

| Component | Why it is unverified | Risk if wrong |
|---|---|---|
| Background location on iOS | No iPhone available | Course produces no data |
| Background location on Android | No Android device available | Course produces no data |
| Android foreground-service notification | Requires a device build | Play policy rejection |
| iOS "always" permission escalation | Requires a device | Participants stuck on "while using" |
| Evening notification delivery | Requires a device build; `expo-notifications` is limited in Expo Go | Reveal never announced |
| EAS build (iOS and Android) | No Expo account, and no EAS project exists | Cannot distribute at all |
| TestFlight / Play review | Requires Apple and Google accounts | 2–7 day delay, or rejection |
| `tools/fetch_osm_environment.py` | Overpass unreachable from this environment | No real camera data |
| `tools/fetch_nearby_posts.py` | Wikimedia/Flickr unreachable | No nearby-post layer |
| `tools/fetch_area_context.py` | RSS unreachable | No news matching |
| Place-name geocoding | Nominatim unreachable | Falls back to manual coordinates, which works |
| PythonAnywhere behaviour | No account | Hosting walkthrough unproven end to end |

---

## Critical blockers

*Will prevent the course from working. Fix before anything else.*

### C1 — `start.py` destroys real participant data

**Proven.** Registered three participants through the real API with no location
data yet, ran `start.py`, and got:

```
BEFORE: participants = 3 | pings = 0
AFTER : participants = 12 | genuinely-registered survivors = 0
        instructors now: ['instructor']      ← published demo password
```

`start.py`'s `ensure_loaded()` decides the database is empty by counting
**pings**, not participants. `backend/load_sample.load()` then runs with
`reset=True`, which executes `DELETE FROM participants`, and finishes by
creating the demo instructor account.

Two distinct harms: every participant's device token is invalidated (their app
silently stops working and they must re-consent), and an account whose password
is published on GitHub appears on the production server.

**Trigger window:** install links sent → first upload arrives. Hours to a day,
on exactly the morning an instructor is most likely to poke at the server.

**Fix:** `load_sample` must refuse to run against a database containing any
non-sample participant. `start.py` must never seed a server that has real
registrations. The demo instructor must never be created outside an explicit
demo mode.

---

### C2 — Days are bucketed in UTC, so the evening reveal is nearly empty

**Proven.** Uploaded one Milwaukee day, 08:00–22:00 local, as a real phone
sends it:

```
Uploaded 57 points covering ONE local day
  day shown      : 2026-09-15
  days available : ['2026-09-14', '2026-09-15']   ← one local day became two
  points in it   : 13 of 57
```

The database stores whatever timestamp arrives, and every day-grouping query
uses `substr(ts, 1, 10)` — the first ten characters. A phone sends
`2026-09-14T22:19:04.457Z`, so in Milwaukee (UTC−5) everything after **19:00
local** is filed under the following day.

Consequences: the 20:30 reveal shows about ninety minutes; the day selector
lists the wrong days; stop detection and pattern-of-life are computed over
split days; and "usually arrives at 09:16" is really 04:16 local.

**Why no test caught it:** the sample generator writes
`2026-09-14T00:00:00-05:00` — a local-offset timestamp, whose first ten
characters *are* the local date. Sample data is correct by accident. Real phone
data is not. The two formats diverge exactly where the tests cannot see.

**Fix:** convert to the course timezone before deriving a day, everywhere a day
is derived. The course timezone already exists as a stored setting. The
sample generator should also emit UTC, so tests exercise the real path.

---

### C3 — The app cannot be built for distribution

`app/app.json` contains no `projectId` and no `owner`, which means `eas init`
has never been run. Without an EAS project, no build can start on either
platform. `app/eas.json` also still contains the literal placeholder
`REPLACE_WITH_APP_STORE_CONNECT_APP_ID`.

**Fix:** run `eas init` against the TRG Expo account, commit the resulting
project ID, and replace the App Store Connect placeholder. Then produce one
build per platform and install it on a real device — which also closes most of
the "unverified" table above.

---

### C4 — Every phone points at `localhost` unless a source file is edited

`app/src/config.ts` ships `DEFAULT_SERVER_URL = 'http://localhost:5000'`. On a
phone, `localhost` is the phone. There is no build-time injection — no
`EXPO_PUBLIC_*` variable, no `process.env`, no deep link — so the only routes
to a working address are hand-editing a TypeScript file before the build
(`docs/distribution.md` step 1), or talking thirty people through typing a URL.

The default is also `http://`, and `app.json` declares no App Transport
Security exception, so **iOS will refuse the connection outright** to any
non-HTTPS server. The failure is silent from the participant's side.

**Fix:** read the server address from an EAS environment variable at build
time, default it to empty rather than `localhost`, and show a clear
"not configured" state instead of failing silently.

---

## High-risk issues

### H1 — Session secret differs per worker

**Proven.** Six processes started simultaneously against a fresh data
directory produced **four different secret keys**:

```
6 simultaneous workers produced 4 distinct secret key(s)
Consistent across workers: False
```

`config.get_secret_key()` checks whether a key file exists and writes one if
not — a read-then-write race with no atomicity. Under `gunicorn --workers N`,
instructors get logged out at random as requests land on workers with different
keys.

The recommended host (PythonAnywhere free) runs a single worker, which hides
this. Anyone using Render, Railway, a VPS or more than one worker hits it.

**Fix:** create the key file atomically (`O_CREAT | O_EXCL`), re-reading if the
create loses; or require `DWELL_SECRET_KEY` in production and have
`check-production` enforce it.

### H2 — Concurrent registration produces duplicate participant labels

**Proven.** Twenty simultaneous registrations produced
`Participant 09` four times, `Participant 05` three times, and so on. The label
comes from `SELECT COUNT(*)` followed by an insert, with no transaction.

This happens precisely when the facilitator's guide says to register everyone —
"run the installation live" — and the dashboard roster then shows several
people with the same name, defeating the colour-coded identification the course
depends on.

**Fix:** derive the label inside the insert, or from the row id.

### H3 — The demo instructor account reaches production

`backend/load_sample.py` unconditionally creates `instructor` /
`demo-password`, a credential published in this repository. `manage.py
check-production` does detect it and refuses to pass, which is good — but it is
a manual step a non-technical user may skip, and C1 can reinstall the account
after the check has been run.

### H4 — HTTPS-only cookies depend on a manually set variable

`SESSION_COOKIE_SECURE` is derived from `DWELL_PUBLIC_URL`. If that variable is
not set — a hand-edited line in a WSGI file per `docs/hosting.md` — login
cookies are not marked Secure on a live HTTPS server. Nothing fails visibly.

### H5 — The evening notification never advances past day 1

`App.tsx` calls `scheduleDailyReveal(1)` with a hard-coded day number, and the
teaser text is baked in when scheduled. A participant who does not open the app
receives "Day 1: I have started building a picture of you" every evening for
the whole week.

---

## Medium-risk issues

| # | Issue | Impact |
|---|---|---|
| M1 | `eas.json` declares `channel` for preview and production, but `expo-updates` is not installed | Build-time warning; over-the-air updates silently unavailable |
| M2 | SQLite under multiple gunicorn workers | "Database is locked" under simultaneous uploads; 20 concurrent registrations succeeded here on the threaded dev server, untested under real worker concurrency |
| M3 | PythonAnywhere free tier requires clicking a reactivation button every three months | Server silently stops between setup and course if set up early |
| M4 | PythonAnywhere free tier restricts outbound network to a whitelist | Place-name geocoding and all three fetchers will fail on the recommended host |
| M5 | Three fetchers never run against their live services | First real run may fail on the day it is needed |
| M6 | `app.json` version is `0.1.0` while `eas.json` sets `appVersionSource: remote` | Version confusion between local file and EAS-managed build numbers |
| M7 | No structured server logging or error reporting | A failure during the course is invisible until somebody notices missing data |
| M8 | Retention sweep (`manage.py sweep`) is manual | Data outlives its stated retention unless somebody remembers |

---

## Low-risk issues

| # | Issue |
|---|---|
| L1 | `H3_RESOLUTION` config name survives the removal of h3; it now selects a cell size on an 8/9/10 scale |
| L2 | No `LICENSE` header in individual source files (Apache-2.0 is at the repository root) |
| L3 | `docs/environment-layers.md` still shows `--flickr-key YOUR_KEY` without saying where to get one |
| L4 | Documentation totals ~2,600 lines across seven files, which is a lot for the intended reader |
| L5 | Sample participant tokens are written to `data/local/sample_participant_tokens.json` — correctly gitignored, but present on any server that ran the sample loader |

---

## Non-technical-user pain points

Ranked by how likely they are to stop somebody.

1. **Editing TypeScript to set the server address.** Opening `app/src/config.ts`
   and changing a quoted string is a code edit. It is step one of distribution
   and there is no alternative path.
2. **The Apple and Google account maze.** An Apple Developer account ($99/year),
   App Store Connect, a Google Play developer account ($25 one-off), and an
   Expo account — each with its own onboarding, and none of it explained by
   this repository beyond "assumes you have".
3. **Command-line-only instructor setup.** Creating a login, setting the course
   location and running the safety check are all terminal commands. There is no
   web-based first-run setup.
4. **Hand-editing a WSGI file on PythonAnywhere**, replacing `YOURNAME` in
   three places, with no validation that it was done correctly.
5. **Knowing which of eight commands to run.** `start.py`, `verify.py`, and ten
   `manage.py` subcommands, with no single "set up my course" flow.
6. **Silent failure modes.** Wrong server address, non-HTTPS server, denied
   background permission and battery optimisation all fail quietly on the
   phone. The participant sees an app that appears to work.
7. **No way to see whether it is working** without opening a terminal or the
   dashboard and interpreting it.

---

## Recommended deployment architecture

Unchanged in shape — the current design is right for this course. Small SQLite,
one server, no infrastructure. The changes are about making it reachable and
safe by default.

```
  Phones ──HTTPS──▶  One small server        ◀──HTTPS── Instructor browser
                     Flask + SQLite
                     single worker
                     DWELL_SECRET_KEY set explicitly
                     DWELL_PUBLIC_URL set explicitly
                     DB on a persistent path outside the code directory
```

**Host:** keep PythonAnywhere as the documented default — free, persistent
disk, no card, and single-worker by default which sidesteps H1. Note M3 and M4
prominently.

**Server address into the app:** an EAS build-time environment variable, set
once in `eas.json` or the EAS dashboard, so no source file is edited and no
participant types a URL.

**Setup:** a single `python3 setup.py` wizard replacing the current scatter of
commands — ask for course city, timezone, instructor username and password;
generate and persist the secret; write the environment file; remove the demo
account; print the address for the app build.

**What can become one command:**

| Today | Becomes |
|---|---|
| `start.py` + `manage.py add-instructor` + `set-location` + `check-production` | `python3 setup.py` (one wizard, once) |
| Editing `config.ts`, `eas init`, `eas build` ×2 | `npm run build:course` reading the address from EAS env |
| `verify.py` + `check-production` + `doctor` | `python3 verify.py --production` |

---

## Recommended order of implementation

Strictly ordered. Each step is safe to stop after.

**Phase 1 — Stop the bleeding (about half a day)**
1. C1: make `load_sample` refuse a database with real participants; remove
   demo-account creation from the non-demo path.
2. C2: derive days in the course timezone; make the sample generator emit UTC
   so tests exercise the real path.
3. Add a regression test for each, using real-phone-format timestamps.

**Phase 2 — Make it deployable (about one day)**
4. C4: server address from an EAS build-time variable; no `localhost` default;
   visible "not configured" state.
5. C3: `eas init`, commit the project ID, replace the App Store Connect
   placeholder.
6. H1: atomic secret-key creation, and require `DWELL_SECRET_KEY` in
   production.
7. H2: allocate participant labels atomically.

**Phase 3 — Prove it on real hardware (two days elapsed, mostly waiting)**
8. One EAS build per platform; install on a real iPhone and a real Android.
9. Carry both for 48 hours. Confirm background collection survives a reboot,
   an overnight, and battery optimisation.
10. Confirm the evening notification arrives, and fix H5.

**Phase 4 — Make it usable by the intended person (one day)**
11. `setup.py` wizard.
12. Fold `check-production` into `verify.py --production`.
13. Cut the documentation to a one-page quick start plus the facilitator's
    guide; move the rest to an appendix.

**Phase 5 — Before the course**
14. Full dress rehearsal on the real server with the real build, three phones,
    for two days.
15. TestFlight and Play submissions, allowing seven days.

---

## Exact definition of "done"

Done is **not** "the code works". It is all of the following, each demonstrable:

**Setup**
- [ ] A non-technical person, given only the repository URL, reaches a working
      hosted server without editing any source file.
- [ ] `python3 setup.py` is the only command needed, and it refuses to finish
      while the demo account exists or the secret key is unset.
- [ ] Setting the course city and timezone happens in that wizard.

**Distribution**
- [ ] `eas build` succeeds for both platforms with no manual file edits.
- [ ] The installed app reaches the production server with no participant
      typing an address.
- [ ] Both builds are live on TestFlight and Play internal testing, installed
      by at least three people who are not the developer.

**On real hardware**
- [ ] Background collection runs for 48 hours on a real iPhone across a
      reboot and an overnight.
- [ ] The same on a real Android, with battery optimisation left at its
      default.
- [ ] The permanent Android notification is present the whole time.
- [ ] The evening notification arrives at 20:30 local, with the correct day
      number, without the app being opened.
- [ ] A participant's reveal shows their **whole local day**, verified against
      what that person actually did.

**Safety**
- [ ] `verify.py --production` passes against the live server.
- [ ] No path exists by which any command destroys real participant data.
- [ ] Login cookies are Secure, verified in a browser against the live server.
- [ ] Withdrawal deletes server-side data and is verified by a second request.
- [ ] Teardown wipes everything, verified by inspection afterwards.

**Rehearsal**
- [ ] A two-day dress rehearsal with three real phones on the production
      server, followed by teaching one session from the dashboard using that
      data.

Until every box is ticked, the correct description is "working demo, untested
deployment" — which is exactly what it is today.
