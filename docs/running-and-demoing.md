# How to run and demo Dwell

The single page to start from. Everything else is linked from here.

---

## What the pieces are

Three things, which talk to each other:

**The app** (`app/`) — installed on participants' phones. Collects location,
shows each person their own daily reveal. iPhone and Android from one codebase.

**The server** (`backend/`) — receives the location points, works out stops and
inferences, holds the database. One small program, one database file.

**The dashboard** (`dashboard/`) — where instructors teach from. Login-gated.
Served by the same server, so if the server is up, the dashboard is up.

---

## Demoing it in ten minutes, with no phones and no server

Useful for pitching the course, briefing colleagues, or getting institutional
sign-off. Runs entirely on synthetic data on one laptop.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 tools/generate_sample_data.py --out data/sample
.venv/bin/python -m backend.load_sample
.venv/bin/python -m backend.app
```

Open <http://localhost:5000>, log in as `instructor` / `demo-password`.

**The five-minute version:**

1. **Participant → pick anyone → any day.** One person's real-looking day: their
   trail, their stops sized by how long they were there, and the marketing
   segment a commercial system would assign them. Point at the line saying what
   proportion was collected while the app was closed.
2. **Day selector → Whole course.** The places they return to light up. *"One day
   is dots. Five days is a routine."* Keep scrolling: the **behavioural
   signature** describes this person in a sentence with no name in it, and
   **recurring groups** shows who they kept turning up beside — reconstructed
   from coordinates and clocks, with no contact list anywhere.
3. **Whole course tab.** Drag the k-anonymity slider from 5 down to 1. The map
   fills with hexagons that each contain one person. Drag it back. This is the
   best thirty seconds in the whole tool.
4. **Live map → press Play.** Dots move across the week, and the map follows
   them. Pan it yourself and following stands down; **Fit** resumes it.
5. **Data & teardown.** Show the audit log and the wipe control.

Say out loud that this is invented data. It is a demo of the tool, not of a
person.

---

## Running a real course

In order. Each links to a full walkthrough.

| # | Step | Time | Guide |
|---|---|---|---|
| 1 | Put the server online | ~45 min | [`hosting.md`](hosting.md) |
| 2 | Set the course location | 2 min | `python manage.py set-location "City, State" --timezone America/...` |
| 3 | Run the safety check | 5 min | `python manage.py check-production` |
| 4 | Build the app, point it at your server | ~1 hour | [`distribution.md`](distribution.md) |
| 5 | Team dry-run on real phones | 2 days | [`distribution.md`](distribution.md) |
| 6 | Submit to TestFlight / Play | 2–7 days waiting | [`distribution.md`](distribution.md) |
| 7 | Send install links | — | template in [`distribution.md`](distribution.md) |
| 8 | Run the week | 5 days | [`facilitator-guide.md`](facilitator-guide.md) |
| 9 | Wipe everything | 5 min | dashboard, then [`hosting.md`](hosting.md) |

**Step 3 is the one not to skip.** It catches the demo login — whose password is
published in this repository — still being active on a live server.

Satellite and street basemaps are both built in and switchable from the map's
layer panel — nothing to set up. Optional: if venue wifi is unreliable, add an
*offline* copy of the street map so the dashboard depends on nobody else's tile
servers — [`offline-maps.md`](offline-maps.md), about 15 minutes.

Store privacy forms are in [`store-disclosures.md`](store-disclosures.md), with
exact answers. The evidence base for the illustrated screens is in
[`sdk-research.md`](sdk-research.md); read it before you teach. The corroboration
lesson — how a phone trail becomes undeniable once other sources agree with it —
is in [`environment-layers.md`](environment-layers.md).

---

## The three talking points

Everything else is detail. These are the arguments the week exists to make.

### 1. The consent model

**What to show:** the consent screen on a real phone, day one.

**The point:** the agree button is disabled until the participant has scrolled to
the end, and the two most uncomfortable facts — that collection continues when
the app is closed, and that instructors can see their live position — are the
first things they read rather than the last.

**Say this:**

> Every app you have installed put the agree button where you could reach it in
> one tap. This one makes you scroll past the bad news to get to it. Compare the
> shape of this screen against every consent screen you meet this week.

**The sharpest version:** consent given once, at the start, and then collection
runs for a week without asking again. That is not a flaw in our design — it is
precisely how the apps already on their phone behave. The only difference is
that this one said so.

### 2. Real versus illustrated

**What to show:** their own reveal, then the illustrated screens, back to back.

**The point:** location is genuinely collected. Contacts, photos, clipboard,
installed apps and cross-app identifiers are invented and clearly labelled.

**Say this:**

> The map is your actual Tuesday. The contacts list is invented — every card says
> SIMULATED.
>
> We could have taken some of it. The clipboard needs no permission at all. We
> did not, because your contacts contain hundreds of people who are not on this
> course and never agreed to anything. A commercial SDK would not have drawn that
> line, and would not have mentioned it either way.

**Why this matters for you:** it is the credibility hinge of the whole week. If
participants suspect the location data is faked for effect, nothing else lands.
If they suspect their contacts were really taken, you have a serious problem.
Be exact, every time.

### 3. k-anonymity

**What to show:** the Whole course tab, sliding the threshold live.

**The point:** "anonymised" is not a property of a dataset. It is a property of
how many people are hiding in each bucket.

**Say this, while dragging to 1:**

> A hexagon only appears if at least five different people were recorded inside
> it. Watch what happens at one.
>
> Now every hexagon appears, including places exactly one person went. That is
> somebody's hotel. That is somebody's street. Nobody's name is on this map and
> it is not anonymous at all.

**Then the trade-off**, dragging back up:

> At a high threshold this map is safe and nearly useless. Every organisation
> publishing "anonymised" data is somewhere on that slider, and most never tell
> you where.

The threshold is `K_ANONYMITY_THRESHOLD` in `backend/config.py`, and the slider
changes it live without restarting anything.

---

## Everyday commands

Run from the project folder, with the virtual environment active.

```bash
python manage.py status              # what is stored right now
python manage.py where               # which city the course is anchored to
python manage.py check-production    # safety check before going live
python manage.py add-instructor NAME # create a teaching login
python manage.py audit               # log of deletions, wipes, logins
python manage.py wipe                # delete everything (asks for confirmation)
```

Checking the app and server still agree, after any change:

```bash
python3 tools/contract_test.py https://your-server-address
```

Thirty-four checks, including that a participant's token stops working the
moment they withdraw, and that their own reveal never names another participant. Safe against a live server — it creates a throwaway participant
and deletes it.

---

## If it breaks mid-course

**Server down.** Phones queue their points locally and retry, so an outage of an
hour or two loses nothing. Teach from sample data meanwhile and say so.

**One participant has no data.** Background permission declined, or their phone
is killing the app. Put their thin reveal next to a full one — the contrast
teaches better than either alone.

**Nothing works.** Run the whole week on synthetic data. Every teaching point
survives except the personal reveals. Say clearly that you have substituted it.

---

## Afterwards

1. **Dashboard → Data & teardown → Wipe everything.** Do this in front of the
   room on the last day.
2. **Delete the database file** on the server ([`hosting.md`](hosting.md)).
3. **Expire the TestFlight build** and remove the Play testing track.
4. **Tell participants to delete the app.**

Step 1 empties the tables. Step 2 removes the file that held them. Doing both is
the honest version of the promise made on the consent screen — and doing step 1
in front of the room is worth more than any assurance you could give in words.
