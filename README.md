# Dwell: Privacy Lab

**An open-source privacy-education tool for classroom use.**

This is a teaching instrument, not a product. It exists to make one lesson concrete:
ordinary phone apps, using ordinary permissions, can learn a surprising amount about
the person carrying the phone — and most people have never seen that demonstrated with
their *own* data.

Participants in a week-long course install this app on their own phones, give explicit
consent, and each evening receive a short summary of what the app was able to work out
about their day. Instructors use a separate dashboard to teach from the patterns.

> **Start here:** run `python3 setup.py`. It asks four questions and sets up
> everything else itself, including testing that it worked. No technical
> knowledge needed — see [Setting it up](#setting-it-up).

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
setup           Set up a course (setup.cmd on Windows). Seven stages.
dwell           Everything afterwards (dwell.cmd on Windows).
diagnose.py     Support report with nothing private in it.

start.py        The server itself (dwell.py start calls this).
verify.py       Every automated check (dwell.py check calls this).
manage.py       Advanced admin, for someone who wants the individual controls.

backend/        The server that receives pings and serves the dashboard.
dashboard/      The instructor dashboard.
app/            The mobile app (iOS + Android, one codebase).

tools/          Sample-data generator, the phone-API contract test, and
                optional fetchers for real local data.
data/sample/    Generated sample data (committed, safe, entirely invented).
docs/           Hosting, distribution, store disclosures, SDK research,
                facilitator's guide.
wsgi.py         Entry point for a real web host. See docs/hosting.md.
```

The two files to know are **`setup.py`** (once) and **`dwell.py`** (everything
after). The rest is either the thing being run or documentation about it.

---

## Project status

Everything is built. What matters more is which parts have actually been proved
to work, because that is not the same question.

### Checked automatically, every time you run `verify.py`

The server, the phone API, every instructor endpoint, the analysis, the privacy
rules, and every dashboard screen driven in a real browser. 55 checks. If any of
this breaks, that command says so.

### Built, and exercised by hand, but not covered by an automated check

- **The mobile app on real phones.** It builds and the API contract test proves
  the phone and server agree, but nothing here substitutes for installing it on
  an iPhone and an Android handset and living with it for two days. Do that
  before the course, not during it.
- **Hosting.** `docs/hosting.md` is a walkthrough; the server itself is proved
  by `verify.py`, and `manage.py check-production` covers the dangerous
  settings.

### Built, but never run against its real data source

These work on the sample data and on anything you curate by hand. Their
*fetchers* have never successfully talked to the live service, so treat a first
run as something to try a week early rather than the morning of:

- `tools/fetch_osm_environment.py` — real cameras and plate readers, via
  OpenStreetMap
- `tools/fetch_nearby_posts.py` — public geotagged photos
- `tools/fetch_area_context.py` — local news and events
- Geocoding a place name in **Data & teardown → Course location**. Entering
  coordinates directly always works and needs no network.

### Before a real course

1. `.venv/bin/python manage.py set-location "Your City, State" --timezone …`
2. `.venv/bin/python manage.py check-production` — it catches the demo login,
   which has a published password
3. `docs/distribution.md` for TestFlight and Play, allowing 2–7 days for review
4. Read `docs/facilitator-guide.md` properly. It is the actual teaching plan.

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

## Setting it up

**One command.**

```bash
./setup            # macOS and Linux
setup              # Windows
```

It works out which Python your computer has, checks everything it needs, asks a
few questions, and does the rest itself — including starting the server and
confirming it answers before claiming success.

It checks your computer, installs what it needs, asks what the course is
called, which city it is in, which timezone, and your name — then generates
your password, builds the course database, runs every automated test, and tells
you plainly whether it worked.

You are never asked for a password, a port, a file path, a secret or a
technical identifier. You never edit a file.

Afterwards there are three commands, and only three:

```bash
./dwell start       # run the course server
./dwell check       # confirm everything still works
./dwell deploy      # put it on the internet, for real phones
./dwell diagnose    # collect a support report if something is wrong
```

`./dwell` on its own lists them and tells you where you are. On Windows, drop
the `./`.

If setup fails it never shows a stack trace. It tells you what went wrong, why
it matters, what to do next, and where the detailed log is. `./dwell diagnose`
packages that log into a report with every password, key, token and coordinate
stripped out — checked automatically before it is written.

### Getting it onto real phones

Two things need accounts that only a human can create — a web host, and the
Apple/Google/Expo accounts for building an app. Everything either side of those
is automated:

```bash
./dwell deploy      # generates the complete upload, ready to go
./dwell app         # writes your server address into the app build
```

`deploy` produces a zip to upload, a start-up file with every value already
filled in, and a numbered list of what to click. `app` puts the server address
into the build so nobody edits code and no participant types a URL.

The unavoidable manual steps — creating accounts — are isolated in
`deploy/HOSTING_STEPS.txt` and `deploy/PHONE_APP_STEPS.txt`, generated with
your details already in them.

<details>
<summary>The individual pieces, if you would rather drive them yourself</summary>

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 tools/generate_sample_data.py --out data/sample
.venv/bin/python -m backend.load_sample
.venv/bin/python -m backend.app
```

`.venv/bin/python manage.py doctor` diagnoses a broken install.
`python3 verify.py --production` checks a live server is safe for real people.

</details>

### Teaching it somewhere other than Milwaukee

Milwaukee is the **default**, not a hard-coded assumption. Set the course
location once and the whole system follows it — where the dashboard opens, which
timezone times are read out in, where the sample generator invents a week, and
what area the fetch tools collect.

From the dashboard: **Data & teardown → Course location**. Type a city, pick from
the matches, done. Or from the command line:

```bash
.venv/bin/python manage.py where                       # where is it anchored now?
.venv/bin/python manage.py set-location "Cincinnati, Ohio" --timezone America/New_York
python3 tools/generate_sample_data.py --use-course-location --out data/sample
.venv/bin/python -m backend.load_sample
```

`--use-course-location` also works on `tools/fetch_osm_environment.py` and
`tools/fetch_nearby_posts.py`, so the surveillance infrastructure and the nearby
posts come from the right city too.

Two things worth knowing:

- **The timezone is asked for, not guessed.** Nothing in a geocoding response
  knows one, and guessing would show every time in the course an hour out for
  half the year. `EST` and similar fixed offsets are rejected for the same
  reason — use `America/New_York`.
- **Coordinates can be typed directly**, so this works with no internet at all.
  Looking up a place name is the only part that needs a connection, and it is
  an instructor action at setup time, never anything automatic during a course.

`.venv/bin/python manage.py check-production` warns if the location is still the default,
in case a course in Ohio is about to open on a map of Wisconsin.

### Two skins, switchable at any time

Top right of the dashboard: **Field** and **Console**.

Field reads like a consumer family-safety app — white, rounded, friendly. Console
reads like a surveillance monitoring station — dark, dense, monospaced. They show
identical data, and switching is instant even mid-playback.

Both ship because both teach. Console makes the room recognise the screen as what
it resembles. Field takes away the escape hatch: *"that's a spy tool, not the app
on my phone"* stops working when the same trails and the same social graph sit
behind an interface that looks like the one a parent installs to watch their
teenager. Flipping between them in front of a class, on the same participant, is
worth more than either alone.

### What you can show from the dashboard

- **Live map** — participants as dots on satellite imagery, with a clock you can
  play, pause and scrub through the whole course. The map **follows** them as
  they move, so nobody has to chase dots with a trackpad while teaching; it
  holds still while people stay put, and stands down the moment you pan or zoom
  it yourself.
- **Participant** — one person, one day: their movement, their stops sized by how
  long they were observed there, and what a marketing system would conclude about
  them, including where it is unsure. Switch the day selector to *Whole course*
  to see the places they keep returning to.
- **Whole course** — everybody at once as a grid of map cells, with the k-anonymity
  threshold on a slider. Dragging it to 1 in front of a class is the single most
  effective demonstration in the whole tool.
- **What else was watching** — for each day, the cameras, plate readers, mapped
  Wi-Fi and card terminals the route passed, and which stops several independent
  sources could confirm. A phone ping alone is deniable; four sources agreeing
  are not. Toggle each source on and off as a map overlay.
- **Pattern of life, signature, groups and anomaly** — the questions a security
  service asks rather than the ones an advertiser asks: how predictable somebody
  is, a description specific enough to pick them out of the room without knowing
  their name, which small groups reform day after day, and what today did that
  the baseline did not. Association and group analysis are instructor-only and
  never shown to participants — the contract test checks it.
- **Area context** — public news and event listings matched to stops by place and
  time, plus public photographs strangers posted within 120 metres and two hours
  of where somebody was standing. Offered as leads rather than findings.

  See [docs/environment-layers.md](docs/environment-layers.md). The default
  location is Milwaukee, Wisconsin.
- **Data & teardown** — what is stored, the audit log, and the wipe-everything
  control.

**Satellite and street maps are both built in**, in the layer switcher at the top
right of the map — one click between them, nothing to install. Both come from
Esri, which is free and needs no API key, no billing account and no per-view
charge; Google's tiles would require all three. Place-name labels ride over the
imagery and switch off automatically over the street map, which draws its own.

Satellite shows what a place looks like; the street map shows what it *is*. Being
able to flip mid-explanation is worth more than picking one.

Map tiles come from Esri, so a venue with no working connection will show a
blank map. Everything in the sidebar still works.

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
that a device token stops working the moment somebody withdraws, and that a
participant's own reveal never names another participant.

## Putting it online

Everything above runs on a laptop. To get it onto real phones, the server needs a
public address. **[docs/hosting.md](docs/hosting.md)** is a step-by-step
walkthrough written for somebody who has never hosted anything, using a free
service that needs no credit card. Allow about 45 minutes.

Before real participants use it, run:

```bash
.venv/bin/python manage.py check-production
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

## License

Apache License 2.0 — see [LICENSE](LICENSE). You may use, modify and redistribute this
freely, including commercially. Contributors grant patent rights along with copyright, and
modified files must be marked as changed.

If you use this to teach, we would genuinely like to hear how it went.
