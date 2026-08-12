# Real deployment status

What is actually proven about this software, and what is not.

The distinction this document exists to keep is between *the code looks ready*
and *a real instructor can run a course with it*. Those are different claims and
only one of them can be established from a laptop.

**The phrase "production ready" does not appear as a verdict anywhere below**,
because the evidence does not support it. Nothing here has been run on a real
web host, a real iPhone or a real Android handset. What has been established is
narrower and worth stating precisely.

Last updated: the commit that added this file. Re-run `python3 verify.py` to
confirm the automatic section still holds.

---

## 1. The blockers from the deployment audit

Every row was checked by looking at the current code, not by assuming an
earlier phase fixed it.

| Issue | Code changed? | Regression test? | Actually verified? | Remaining work |
| --- | --- | --- | --- | --- |
| **C1** Data destruction — setup wiping a live course | Yes. `load_sample.load()` refuses when any participant registered from a real phone, counting participants rather than points | Yes — `tools/data_safety_test.py` | **Yes.** Three registered participants and nine points; two attempts to load practice data; both refused; all three and all nine survive | None |
| **C2** UTC vs local dates | Yes. `pings.local_day`, filled on arrival from the course timezone; the four query sites share one `DAY_EXPR` | Yes — `tools/day_boundary_test.py` and a section of `verify.py` | **Yes.** 13 points spanning one Milwaukee day but two UTC dates upload and come back as one day with all 13. Reverting `DAY_EXPR` to the old slice reproduces the original symptom exactly: two days, opening on the wrong one, 3 of 13 points | None |
| **C3** EAS configuration | Partly. Profiles, identifiers, permissions, background modes and version handling all audited and corrected | Yes — `tools/app_config_test.py` (38 checks) | **Configuration yes, build no.** The project is not linked to an Expo account, and `eas build` will not start without that link | `npx eas-cli@latest init` while signed in. Cannot be done here and is not invented |
| **C4** localhost / server URL | Yes. `.easignore` at the top of the project, so `app/.env` reaches the build while staying out of the repository | Yes — `tools/build_upload_test.py` | **Yes, up to the build service.** Confirmed twice: the value is traced into the compiled Hermes bundle by `expo export`, and eas-cli's own `Ignore` class, asked about this repository, agrees on all twenty paths | An actual EAS build would settle the last step |
| **H1** Secret key race | Yes. `O_CREAT｜O_EXCL`, so exactly one process can win | Yes — `tools/concurrency_test.py` | **Yes.** Eight worker processes starting together produce one key, and it is the one on disk. Before the fix, six produced four | None |
| **H2** Duplicate participant labels | Yes. Allocated inside one `BEGIN IMMEDIATE` transaction | Yes — `tools/concurrency_test.py` | **Yes.** Sixty simultaneous registrations, sixty distinct ids, tokens and on-screen numbers, running consecutively from one | None |
| **H3** Demo account with a published password | Yes. `load()` creates no sign-in unless asked; when asked the password is generated and shown once | Yes — `tools/data_safety_test.py` and `backend/readiness.py` | **Yes.** A plain load creates no account and the published password does not authenticate. Two runs give two different passwords | None. The published pair stays in the source only so `check-production` can recognise a database made by an older version |
| **H4** Secure cookies | Already correct; now proven | Yes — `tools/https_test.py` | **Yes, over real TLS.** The `Set-Cookie` header carries Secure, HttpOnly and SameSite. Pointing the server at a non-HTTPS address makes that check fail | None |
| **H5** Notification hard-coded to Day 1 | Yes. One dated notification per evening, counted from the day that participant consented | Yes — `tools/reveal_schedule_test.mjs` | **Logic yes, delivery no.** First day, middle, final day, late install, end of course and daylight saving all pass. Making `teaserFor` always return the first teaser fails three checks; naive millisecond arithmetic fails the DST pair | Whether a handset delivers them. Checklist item 9 |

Two faults were found *while* writing those regression tests, and both were
introduced or exposed by this phase's own work:

- Every request re-ran the schema migration, so the new `local_day` column
  raced: two requests both ran `ALTER TABLE`, and the loser answered 500. Ten of
  thirty simultaneous registrations failed.
- Underneath it, `init_db` ran the whole schema script — including
  `PRAGMA journal_mode = WAL`, which needs an exclusive lock — on every request.
  Thirty connections fought over it and some got "database is locked". This one
  was intermittent, which is worse, because it reads as a flaky test rather than
  a broken server.

Both are fixed, and the test that found them runs in `verify.py`.

---

## VERIFIED AUTOMATICALLY

Proven by tests that anybody can run with `python3 verify.py`. 247 checks, all
passing, on a throwaway database that is deleted afterwards.

**The server and the analysis**
- Every dashboard file loads and has real content in it
- The phone's whole API, via `tools/contract_test.py`
- The instructor API: sign-in, refusal of a wrong password, refusal of data
  before signing in, the live map, monitoring, overlays, location, audit,
  aggregate, a participant's day and a participant's week
- Group analysis never attributes another participant's group to this one
- k-anonymity hides cells below the threshold, draws at the default, and
  exposes single-person cells when the threshold is dropped to one — the last
  of these being how we know the first two are not vacuous

**Days**
- A day means the course's day, in the course's timezone, at every point where
  anything is grouped by day
- An older database is migrated and its existing points re-filed
- Moving a course to another timezone re-files them again; resetting puts them
  back
- Daylight saving handled by zoneinfo, checked against the running machine's
  own clock change rather than a hard-coded date

**Over real TLS** (a certificate generated for the run)
- The dashboard loads, sign-in works, a wrong password is still refused
- The sign-in cookie carries Secure, HttpOnly and SameSite — read from the
  header the browser was sent, not from configuration
- A phone can register, upload and be refused with a bad token
- Plain HTTP does not work against the TLS port

**A whole room at once**
- Eight workers starting together agree on one signing key
- Sixty simultaneous registrations, all distinct, none failed

**Safe for a course already running**
- Loading practice data refuses on a real course, twice over, and every
  participant and point survives
- No instructor account appears behind the operator's back
- The one-command demo starter creates nothing on a real course
- Generating practice data writes nothing to the course database
- Withdrawal deletes the person and their points and leaves an audit entry with
  no coordinates in it
- The support report contains no coordinate, no signing key, no password hash
  and no device token — and describes the configured database, so those four
  checks are not passing by describing an empty one

**The phone app, as far as a laptop can tell**
- The TypeScript is consistent
- The evening reveal is scheduled for the right evening with the right words
- The nine status questions give the right answers in ten situations, and no
  answer in any of them contains a coordinate
- The build will be told the right permissions, background modes, foreground
  service and notification settings
- `app/.env` reaches the build; the course database, signing key, device tokens
  and deploy bundle do not

**In a real browser** (Playwright)
- Every dashboard screen draws, both skins apply, and no screen produces a
  JavaScript error

---

## VERIFIED ON A REAL SERVER

**Nothing.**

No part of this has been run on external hosting. `dwell deploy` generates the
upload bundle and the WSGI file, and `backend/readiness.py` checks nine
conditions including whether the health endpoint and dashboard actually answer —
but the address it has been pointed at so far has always been a local one.

What that leaves unproven: whether PythonAnywhere (or any host) serves this
correctly, whether the database survives the host's restarts in practice,
whether a real certificate is trusted by a real phone, and whether the free tier
is fast enough for a room uploading together.

To move something into this section, deploy and then run:

```
python3 dwell.py ready
```

against the public address, and record what it said.

---

## VERIFIED ON REAL IPHONE

**Nothing.**

No iOS build has been produced, because that needs an Expo account and an Apple
Developer account, and neither exists here. Nothing in this repository has run
on an iPhone.

Specifically unproven: whether background location continues with the screen
locked, whether it survives the app being swiped away, whether it resumes after
a reboot (it is *expected not to* until the app is opened once), whether the
evening notification is delivered, and whether iOS ever offers the "Always"
permission escalation for this app.

`docs/device-checklist.md` is the procedure. Fill in its results table and copy
the outcome here — from that table and nothing else.

---

## VERIFIED ON REAL ANDROID

**Nothing.**

No Android build has been produced. Nothing has run on a handset.

Specifically unproven: whether the foreground-service notification appears and
stays, whether collection survives the app being closed, whether it resumes
after a reboot, and — the most likely thing to go wrong — whether any given
manufacturer's battery optimiser kills it overnight. The checklist lists the
settings for Samsung, Xiaomi, Huawei, OnePlus and Oppo because that is where
this usually fails.

---

## BLOCKED BY EXTERNAL ACCOUNTS

These cannot be done from this repository. Each needs a person to sign in,
accept terms, or pay.

| What | Why it is blocked | Cost | What unblocks it |
| --- | --- | --- | --- |
| Linking to an Expo project | `eas build` will not start without a project id, and `eas init` requires being signed in | Free | `cd app && npx eas-cli@latest login && npx eas-cli@latest init` |
| Any mobile build at all | Follows from the above | Free tier available | The same |
| Installing on an iPhone | Apple requires TestFlight, which requires the Developer Program, which verifies identity | $99/year, and enrolling as an organisation needs a D-U-N-S number — start early | Enrolment, then `eas build --platform ios --profile preview` |
| Publishing on Google Play | Play Console account | $25 once | Not required — see below |
| Hosting the server | Any host needs an account | Free tier available | `python3 dwell.py deploy` writes the steps |

**Android does not need any paid account.** The preview profile produces an
`.apk`, which participants can install from a link. If the course can be run on
Android handsets only, everything above except the Expo login and the hosting
account is avoidable.

No Apple, Google or Expo identifier has been invented anywhere in this
repository. `eas.json` previously carried a placeholder App Store Connect id;
it has been removed, because a placeholder fails the submit step with a
confusing error and being prompted is better.

---

## STILL UNPROVEN

Things that are neither verified nor blocked — they simply have not been
established, and it would be wrong to imply otherwise.

**The chain, end to end.** Every link has been exercised. The chain has not.
Nobody has gone fresh machine → setup → hosted server → HTTPS → build → phone →
pocket → overnight → dashboard → evening reveal in one pass. Until somebody
does, this is a set of parts that each work.

**Battery cost over a week.** Collection at a one-minute interval for five days
has not been measured on any handset. If it turns out to cost a fifth of a
battery a day, that changes what participants must be told at consent.

**A room's worth of load.** Sixty registrations in one instant is proven against
Flask's development server on a laptop. A shared host's free tier is a different
machine with different limits, and the interesting number — thirty phones
uploading every few minutes for five days — has not been measured anywhere.

**The reveal on a real day of real movement.** Every analysis check runs on
generated data, which is well-behaved in ways real GPS is not: no urban canyon
scatter, no cold-start fixes half a mile away, no tunnels. Whether the stop
detection produces a day a participant recognises is exactly the thing the
course depends on, and synthetic data cannot answer it.

**Recovery from a mid-course failure.** What happens if the host restarts on
Wednesday evening has not been tested. The readiness check now refuses a
database on temporary storage, which is the failure that would lose the week,
but restarting a live course has not been rehearsed.

**Whether a non-technical operator can actually do this.** The setup path was
rebuilt for that person and has been run repeatedly here — by someone who wrote
it. That is not evidence. One person who has not seen it before, working from
the README alone, would tell you more than any test in this repository.

---

## What to run, and when

| When | Command | Answers |
| --- | --- | --- |
| Any time | `python3 dwell.py check` | Does the software still work? (247 checks) |
| Before install links go out | `python3 dwell.py ready` | Is *this installation* safe for real people? |
| When something is wrong | `python3 dwell.py diagnose` | A support report with nothing private in it |
| Before the course, on a phone | `docs/device-checklist.md` | The eleven things no machine can check |

`check` and `ready` ask different questions, and a machine can pass one while
failing the other. `ready` refuses to say yes while a single blocking condition
stands, however many other things are fine.
