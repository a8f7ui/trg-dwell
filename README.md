# What Your Phone Knows

**An open-source privacy-education tool for classroom use.**

This is a teaching instrument, not a product. It exists to make one lesson concrete:
ordinary phone apps, using ordinary permissions, can learn a surprising amount about
the person carrying the phone — and most people have never seen that demonstrated with
their *own* data.

Participants in a week-long course install this app on their own phones, give explicit
consent, and each evening receive a short summary of what the app was able to work out
about their day. Instructors use a separate dashboard to teach from the patterns.

> **Status: in development.** This repository is being built in stages. See
> [Project status](#project-status) for what currently works.

---

## What this app does and does not do

Being trustworthy here is the entire point. If this tool were sneaky, it would be
teaching the opposite of its lesson. So:

### What it really collects — genuinely, and continuously

| Data | Why it's here |
|---|---|
| A random participant ID generated on the device | So your data is yours, without using your name |
| Device model, OS version, screen size | The "device fingerprint" every analytics SDK reads |
| Timezone, language | Common profiling signals |
| Battery level, connection type | Genuinely collected by real SDKs; surprises most people |
| **Location, with timestamps** | The heart of the lesson |

**This is real.** The app is not simulating collection, replaying a script, or showing
you a mock-up. It records your actual position, continuously, in the background, from
the moment you agree until the course ends or you stop it. The map you are shown each
evening is your own day.

That matters because a simulation would prove nothing. Everybody already accepts in
principle that phones can track people. What changes minds is seeing *your* Tuesday
drawn on a map, with the places you stopped named, by an app you agreed to install and
then forgot about. Faking that would be both dishonest and pointless.

You consent once, at the start. After that it simply runs. There is no repeated
prompting, no daily check-in — which is exactly how a commercial SDK behaves, and part
of what the week is meant to expose.

### The one exception: the invasive categories are invented

Real advertising and analytics SDKs reach much further than the list above — into
contacts, photos, the clipboard, the microphone, the list of installed apps, and
cross-app identifiers.

**Those, and only those, this app illustrates rather than takes.** It shows what such a
harvest would look like using clearly-labelled invented values. Nothing in those
categories is read from your phone or transmitted anywhere. There is no code in this
app that reads them, and the server has no field to store them in.

That line is drawn deliberately. Collecting real location from consenting adults who
were told plainly is a defensible teaching exercise. Hoovering up their contacts —
which would sweep in hundreds of people who never agreed to anything and are not on
the course — is not, and no amount of educational framing would make it so.

You do not have to take our word for any of this. That is why the code is public.

### Deliberate limits built into the design

- **This app collects in the background, and says so.** It keeps recording location
  when it is not open on screen. That is deliberate: an app that only collected while
  you were watching it could not demonstrate the thing this course is about, which is
  what happens when you are *not* watching. You are told this before you agree, not
  buried in a policy.
- **A visible indicator is shown the entire time collection is active.** On Android this
  is a permanent notification you cannot swipe away; on iOS the system shows its own
  location indicator and periodically reminds you the app has been collecting. These are
  enforced by the phone, not merely promised by us.
- **Pause it whenever you like** from inside the app, without withdrawing entirely.
- **One tap withdraws you.** Collection halts and your data is deleted from the server.
- **Data is retained for the course and then wiped.** Instructors have a "wipe everything"
  control for teardown.
- **The app characterises behaviour, not identity.** It will say "this looks like a
  visitor spending time in a commercial district". It will not look up your address, and
  it does not connect you to any outside record about you.
- **Instructors can see participant movement, including your live position.** This is
  disclosed on the consent screen before you agree, because a consent screen that hides
  something is a bad example to set in a privacy course.

---

## Who this is for

- **Course participants** — you install it, you consent, you see your own data and nobody
  else's.
- **Instructors** — you get a login-gated dashboard, a facilitator's guide, and a week-long
  teaching arc.
- **Reviewers and the merely suspicious** — the code is here. The claims above are meant to
  be checkable against it. If you find a place where the code and this README disagree,
  that's a bug and we want to hear about it.

---

## Repository layout

```
tools/          Sample-data generator — builds realistic synthetic participant
                data so the backend and dashboard can be built and demonstrated
                without any real phone or real person involved.
data/sample/    Generated sample data (committed, safe, entirely invented).
docs/           Facilitator's guide, store disclosures, hosting and demo guides.
backend/        The server that receives pings and serves the dashboard.  (later stage)
dashboard/      The instructor dashboard.                                  (later stage)
app/            The mobile app (iOS + Android, one codebase).              (later stage)
```

---

## Project status

Built in stages, each one runnable and demonstrable before the next begins.

- [x] **Stage 1 — Foundation.** Licence, README, sample-data generator.
- [x] **Stage 2 — Backend and instructor dashboard**, running locally on sample data.
- [x] **Stage 3 — Mobile app**: consent flow, collection, teaching flow, daily reveal.
- [x] **Stage 4 — SDK research** feeding the "illustrated" categories
      (`docs/sdk-research.md`).
- [x] **Stage 5 — Backend hosting** (guided walkthrough: `docs/hosting.md`).
- [ ] Stage 6 — Getting it onto attendee phones (guided walkthrough).
- [ ] Stage 7 — Store disclosures, facilitator's guide, demo guide.

---

## Sample data

Everything can be built and demonstrated before a single real phone is involved. The
generator in `tools/` invents participants, gives each a plausible daily routine, and
writes out the pings the app *would* have produced.

```bash
python3 tools/generate_sample_data.py --participants 12 --days 5 --out data/sample
```

No installation required — it uses only the Python standard library.

The generated data mimics how a phone really reports position: continuously in the
background, but throttled heavily when somebody is sitting still, with occasional holes
where the operating system suspended the app, and much denser bursts while the app is
actually open. Background fixes are given worse accuracy, because to save battery the
phone often serves a coarse position rather than waking the GPS chip.

Add `--mode foreground` to generate the far patchier data an app would produce if it only
collected while on screen. Running both and comparing them is a good teaching exercise:
it shows how much of the picture comes from the hours nobody was looking at their phone.

---

## Trying it on your own machine

Nothing here touches a real phone or a real server. Four commands:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 tools/generate_sample_data.py --out data/sample   # invent participants
.venv/bin/python -m backend.load_sample                   # load them locally
.venv/bin/python -m backend.app                           # start the server
```

Then open <http://localhost:5000> and log in as `instructor` / `demo-password`.

That demo password is fine on a laptop and unacceptable anywhere else. Before
hosting this, make a real account with `python manage.py add-instructor <name>`.

### What you can show from the dashboard

- **Live map** — participants as dots on satellite imagery, with a clock you can
  play, pause and scrub through the whole course.
- **Participant** — one person, one day: their movement, their stops sized by how
  long they were observed there, and what a marketing system would conclude about
  them, including where it is unsure. Switch the day selector to *Whole course*
  to see the places they keep returning to.
- **Whole course** — everybody at once as a hexagon grid, with the k-anonymity
  threshold on a slider. Dragging it to 1 in front of a class is the single most
  effective demonstration in the whole tool.
- **Data & teardown** — what is stored, the audit log, and the wipe-everything
  control.

The satellite imagery comes from Esri, which is free and needs no API key,
no billing account and no per-view charge. Google's tiles would require all
three.

## The app

One codebase for iPhone and Android, built with Expo. It lives in `app/`.

If you want to check what it does rather than take our word for it, two files
answer almost every question:

- **`app/src/collection.ts`** — every line of code that touches your location.
- **`app/src/api.ts`** — every request that ever leaves the phone. There are four.

There is no analytics package, no crash reporter and no advertising library
anywhere in the app, which would be an awkward thing for a privacy-education tool
to ship with.

### What the app does

- **A consent screen you cannot skip.** The agree button stays disabled until the
  text has actually been scrolled through, and the two uncomfortable facts —
  that collection continues when the app is closed, and that instructors can see
  a participant's live position — are at the top rather than buried.
- **Narrated permission requests.** Each system prompt is preceded by what a
  normal app would say at that exact moment, the reason it would give, and what
  saying yes actually allows. Declining is offered as a real option at every step.
- **A permanent "Collection is ON" indicator**, backed by the notification Android
  requires and the indicator iOS shows.
- **The illustrated categories** — contacts, photos, clipboard, installed apps,
  cross-app identifiers and the rest — shown with invented values, labelled as
  simulated on every card, each with the documented real-world case behind it.
- **The daily reveal**: the day's movement on a map, stops with dwell, the
  commercial segment a marketer would file the participant under, how that
  compares with earlier days, where the guess is shaky, and one concrete thing to
  do about it.
- **Withdrawal in two taps**, which deletes everything server-side and reports how
  many location points were destroyed.

### Checking the app still matches the backend

The app is TypeScript and the server is Python, so nothing checks them against
each other automatically. This does:

```bash
.venv/bin/python -m backend.app          # in one terminal
python3 tools/contract_test.py           # in another
```

It replays the exact requests the app makes and verifies the responses, including
that a device token stops working the moment somebody withdraws.

## Putting it online

Everything above runs on a laptop. To get it onto real phones, the server needs a
public address. **[docs/hosting.md](docs/hosting.md)** is a step-by-step
walkthrough written for somebody who has never hosted anything, using a free
service that needs no credit card. Allow about 45 minutes.

Before real participants use it, run:

```bash
python manage.py check-production
```

It checks the handful of things that are genuinely dangerous to get wrong — most
importantly that the demo login, whose password is published in this README, has
been removed — and tells you the exact command to fix each one.

## Running a course with this

Before using this with real participants, please read `docs/` (added in a later stage). In
short:

- Someone needs to be named as responsible for the data.
- Participants must be told what happens, before they consent, in language they understand.
- Location data about identifiable people is regulated in many places. In the United
  States, several state laws apply; elsewhere, GDPR and similar regimes do. This tool is
  designed to make compliance straightforward, but it cannot make it automatic.
- Delete the data at the end of the course. The tool has a control for this. Use it.

---

## Licence

Apache License 2.0 — see [LICENSE](LICENSE). You may use, modify and redistribute this
freely, including commercially. Contributors grant patent rights along with copyright, and
modified files must be marked as changed.

If you use this to teach, we would genuinely like to hear how it went.
