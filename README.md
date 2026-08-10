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

### It really collects (only with consent, and only after you opt in)

| Data | Why it's here |
|---|---|
| A random participant ID generated on the device | So your data is yours, without using your name |
| Device model, OS version, screen size | The "device fingerprint" every analytics SDK reads |
| Timezone, language | Common profiling signals |
| Battery level, connection type | Genuinely collected by real SDKs; surprises most people |
| Location, with timestamps | The heart of the lesson |

### It illustrates but never collects

Real advertising and analytics SDKs reach for far more than the list above. This app
*shows you what that would look like* using clearly-labelled invented data. Your
contacts, photos, clipboard, microphone, installed apps and cross-app identifiers are
**never read and never transmitted**. The screens depicting them are demonstrations,
marked as such on screen.

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
- [ ] Stage 3 — Mobile app: consent flow, collection, daily reveal.
- [ ] Stage 4 — SDK research feeding the "illustrated" categories.
- [ ] Stage 5 — Backend hosting (guided walkthrough).
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
