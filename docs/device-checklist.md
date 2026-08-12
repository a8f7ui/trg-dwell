# Testing on a real phone

Everything in this project that can be checked by a machine is checked by
`verify.py`. This page is the part that cannot be.

Background location is the whole exercise, and no test on a laptop can tell you
whether a particular handset honours it. Both platforms defer, throttle and kill
background work according to rules that are undocumented, vary by manufacturer,
and change between versions. The configuration can be perfect and a Samsung
running a battery optimiser will still stop the app overnight.

So: **carry the phone for two days before anybody else does.** There is no
substitute, and the cost of skipping it is a room full of people whose maps are
empty on the evening it matters.

Two handsets is the minimum — one iPhone, one Android. If only one is possible,
make it Android, because that is where the manufacturer-specific battery killing
lives.

---

## Before you start

| | |
| --- | --- |
| Server | Reachable at its https:// address from mobile data, not just Wi-Fi |
| Build | Installed from the build service, not run through Expo Go — Expo Go cannot do background location |
| Readiness | `python3 dwell.py check` reports no problems |
| Timing | Start in the morning. Several of these need a whole day to answer |

Expo Go is worth stating twice: a phone running the app through Expo Go will
appear to work and will not collect in the background. Every test below must be
done on a build produced by `eas build`.

---

## The tests

Each row is: what to do, what should happen, and what it means if it does not.
Record the result. "Seemed fine" is not a result.

### 1. Permission, in the order the platforms require

| Step | Expected |
| --- | --- |
| Install and open. Agree on the consent screen. | The walkthrough appears |
| Grant "While using the app" | Accepted, walkthrough continues |
| Grant the escalation to "Always" | Accepted. On iOS this may arrive as a *separate prompt a few minutes later* rather than immediately |
| Open **Is this working?** | All nine answers green |

If iOS never offers the "Always" prompt, that is iOS deciding, not a fault. It
often appears after the app has been used in the background once. Check again
after an hour.

### 2. It keeps going with the screen off

| Step | Expected |
| --- | --- |
| Lock the phone. Put it in a pocket. Walk for 15 minutes. | — |
| Open **Is this working?** | "When did it last record a location?" is minutes ago, not the time you locked it |
| Android: look at the notification shade while walking | "Collection is ON" is present the whole time and cannot be swiped away |
| iOS: look at the status bar | The blue location indicator appears while moving |

**If the last fix is the moment you locked the phone**, background location is
not working. On Android this is almost always battery optimisation — see
section 8. On iOS check that "Always" was granted, not "While using".

### 3. It survives the app being closed

| Step | Expected |
| --- | --- |
| Swipe the app away from the recent-apps list | Android: the "Collection is ON" notice stays. iOS: no visible change |
| Wait 20 minutes, moving around | — |
| Reopen the app, open **Is this working?** | New locations recorded during the 20 minutes |

On iOS, swiping an app away from the app switcher is a stronger signal than most
people realise: it tells iOS the user does not want it running. Location updates
usually resume on significant movement, but not always immediately. Test it
rather than assuming either way.

### 4. It survives a reboot

| Step | Expected |
| --- | --- |
| Restart the phone. Do **not** open the app. | — |
| Wait 30 minutes, moving around | — |
| Open the app and check | Either new points during that window, or none |

**This one is expected to fail on iOS**, and the checklist says so rather than
pretending. iOS does not restart a background location task after a reboot until
the app is opened once. Android usually does.

The practical consequence is a line in the facilitator's script: *"if your phone
restarts, open the app once."* Test it so you know whether you need to say it.

### 5. Offline, and coming back

| Step | Expected |
| --- | --- |
| Turn on aeroplane mode. Walk for 10 minutes. | — |
| Open **Is this working?** | "Is this phone connected?" says no; "How much is waiting?" is a growing number; nothing is described as broken |
| Turn aeroplane mode off. Wait two minutes with the app open. | The waiting count drops to nothing |
| Check the instructor dashboard | The offline stretch appears in the trail, with the right times |

The times matter more than the count. A queued point keeps the time it was
*collected*, not the time it was sent; if the trail shows ten minutes of
movement compressed into the moment the connection returned, that is a fault.

### 6. Nothing is uploaded twice

| Step | Expected |
| --- | --- |
| After the offline test, look at the dashboard trail | No stack of points at the same place and time |
| Open the participant's day. Compare the point count with the phone's total. | Roughly equal — not double |

### 7. Low battery

| Step | Expected |
| --- | --- |
| Run the phone down below 20% and let power-saving switch on | — |
| Carry it for an hour | — |
| Check the gaps | Larger gaps are normal and fine. A complete stop is not |

Record what actually happened. "Points every 15 minutes instead of every minute"
is a usable answer for the facilitator's script. "Nothing after 6pm" is a
problem to solve before the course.

### 8. Android battery optimisation

This is the single most common cause of a phone that collects nothing overnight,
and it is different on every manufacturer.

| Step | Expected |
| --- | --- |
| Settings → Apps → Dwell → Battery | Set to **Unrestricted** |
| Samsung: Settings → Battery → Background usage limits | Dwell is not in "Sleeping apps" or "Deep sleeping apps" |
| Xiaomi / Redmi: Settings → Apps → Dwell → Battery saver | Set to **No restrictions**, and enable **Autostart** |
| Huawei: Settings → Battery → App launch | Dwell set to **Manage manually**, all three switches on |
| OnePlus / Oppo: Settings → Battery → Battery optimisation | Dwell set to **Don't optimise** |
| Then leave the phone overnight | Morning check shows points through the night |

Whichever of these applies to the handsets in the room belongs in the setup
instructions participants are given. Find out which ones apply by testing.

### 9. The evening notification

| Step | Expected |
| --- | --- |
| Leave the phone until 20:30 local | The notification arrives |
| Read it on the lock screen | It says a summary is ready and **names no place** |
| Tap it | The app opens on the reveal |
| Check again the following evening | The wording has moved on to Day 2 |

That last row is the one worth being careful about: an earlier version repeated
the Day 1 wording every night for a week. Two consecutive evenings is the only
way to see it.

### 10. The day boundary

The most important test in this list, and the easiest to skip.

| Step | Expected |
| --- | --- |
| Carry the phone from morning until after 20:00 local | — |
| Open the reveal that evening | It covers **the whole day**, not just the evening |
| On the dashboard, open that participant's week | One day, not two |

A course in Milwaukee runs five or six hours behind UTC, so everything after
19:00 falls on the next UTC date. If the reveal shows only the last ninety
minutes of the day, the course timezone is wrong — check
`python3 dwell.py check`.

### 11. Withdrawal

| Step | Expected |
| --- | --- |
| Settings → withdraw, and confirm | It reports how many points were deleted |
| Check the dashboard | The participant is gone entirely, not greyed out |
| Reopen the app | It behaves as a fresh install; collection has stopped |
| Android | The "Collection is ON" notice is gone |

Do this on a test phone, and do it before the course. A participant who
withdraws in front of the room and sees it half-work has been failed in the most
visible way possible.

---

## Recording the results

Copy this and fill it in. It is the evidence for the "verified on real hardware"
section of `docs/REAL_DEPLOYMENT_STATUS.md`, which should not be filled in from
anything else.

```
Handset:            (make, model, OS version)
Build:              (eas build id, or the date)
Tested by:          (name)                     Dates:

 1. Permission granted in both stages         PASS / FAIL / not tested   notes:
 2. Collects with the screen off              PASS / FAIL / not tested   notes:
 3. Survives the app being closed             PASS / FAIL / not tested   notes:
 4. Survives a reboot                         PASS / FAIL / not tested   notes:
 5. Offline queue drains, times correct       PASS / FAIL / not tested   notes:
 6. No duplicate uploads                      PASS / FAIL / not tested   notes:
 7. Low battery behaviour                     PASS / FAIL / not tested   notes:
 8. Battery optimisation settings needed      PASS / FAIL / not tested   notes:
 9. Evening notification, two nights running  PASS / FAIL / not tested   notes:
10. The day boundary                          PASS / FAIL / not tested   notes:
11. Withdrawal                                PASS / FAIL / not tested   notes:
```

An honest "not tested" is worth more than an optimistic "PASS". The point of
this page is to know which of these you have actually seen work.
