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
python3 start.py
```

That is the whole thing. It sets up whatever is missing, skips whatever is
already done, and prints one address to open. Log in as `instructor` /
`demo-password`. Ctrl-C stops it.

Run it again whenever you like — it checks each step rather than repeating it,
so the second run is instant. It also picks a different port if 5000 is busy,
and if a dependency will not install on your machine it says so in a sentence
and carries on without that one feature.

<details>
<summary>The same thing by hand</summary>

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python3 tools/generate_sample_data.py --out data/sample
.venv/bin/python -m backend.load_sample
.venv/bin/python -m backend.app
```

</details>

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

## Demoing from a tablet, or anything else underpowered

The dashboard is a map with twelve moving things on it, backed by a Python
server doing real analysis over tens of thousands of points. That is fine on a
laptop and can be a struggle on a tablet, especially one running the server and
the browser at the same time.

### The arrangement that works

**Run the server on a laptop; look at the dashboard on the tablet.** The tablet
then only has to draw a web page, which is what it is good at.

```bash
.venv/bin/python -m backend.app --host 0.0.0.0          # on the laptop
```

It prints the address to open on the tablet — the laptop's own IP, port 5000,
both on the same wifi. The server binds to localhost unless you ask for this,
deliberately: anyone who can reach it gets the login page, so do not leave the
demo password in place on a conference network.

`DWELL_BIND` and `DWELL_PORT` do the same thing if environment variables suit
you better.

---

## Running it in Docker

The one thing to know: **inside a container, `127.0.0.1` means the container's
own loopback**, which nothing outside can reach — not even with
`-p 5000:5000`, because the published port forwards to the container's external
interface and a localhost-bound server is not listening there.

The symptom is nasty because it looks like nothing is wrong: the server says it
is running, the port mapping is present in `docker ps`, and the browser gets an
empty response.

**The server now detects containers and listens on `0.0.0.0` automatically**, so
this should not bite. It says so on startup. Publish the port when you start the
container and open it on the host:

```bash
docker run --rm -it -p 5000:5000 ubuntu:24.04 bash
# inside:
apt-get update && apt-get install -y git python3 python3-venv
git clone https://github.com/a8f7ui/trg-dwell.git && cd trg-dwell
python3 start.py
```

Then <http://127.0.0.1:5000> on the host.

Two traps this repository used to set, both now fixed but worth knowing:

- **`python` often does not exist** on a minimal Ubuntu image — only `python3`.
  And even where it does, it is not the virtual environment, so the
  dependencies are invisible to it. Always use `.venv/bin/python`, which every
  command in these docs now does.
- **The server used to ignore `--host`**, so `--host 0.0.0.0` bound to
  localhost anyway while printing an address that looked like agreement. It
  accepts the flag now.

If something still will not start, `.venv/bin/python manage.py doctor` checks
the interpreter, the dependencies, the port, the database and the bind address,
and names the command that fixes whatever it finds.

### If the tablet has to do both

It can, with three things known in advance.

**`python3 start.py` handles this too** — if the hexagon library will not
install, it says so in one line and carries on without it. The rest of this
section is only worth reading if you want to know why, or want that feature
back.

Everything here is pure Python except `h3`, the hexagon library, which contains
compiled C. On Termux there is no prebuilt wheel for it.

Left alone, pip responds to that by building h3 from source; h3's build wants
CMake; there is no CMake wheel either; so pip downloads the CMake *source* and
starts compiling a C++ build system, file by file, on a tablet. That is hours of
work for a hexagon library, and it commonly fails or runs out of memory at the
end anyway. If you see page after page of `g++ ... -c ... cmake-4.4.2/Source/...`
scrolling past, that is what is happening — stop it.

`requirements.txt` now pins h3 to prebuilt wheels only, so instead of that,
pip fails in seconds with "no matching distribution". Then:

```bash
pip install -r requirements-core.txt     # everything except the hexagon map
```

You lose the **Whole course** aggregate view and the k-anonymity slider with it,
which is a real loss — it is the best thirty seconds in the tool. Everything
else works normally, and that screen explains itself rather than failing blankly.

If you want the hexagon map on the tablet badly enough, install Termux's own
CMake first so pip does not try to build one:

```bash
pkg install clang cmake ninja
pip install scikit-build-core
pip install h3 --no-build-isolation      # still several minutes, but minutes
```

`--no-build-isolation` is the part that matters: without it pip builds in a
fresh environment and fetches CMake from PyPI again, ignoring the one you just
installed.

`gunicorn` is only needed for hosting and can be skipped entirely for a demo.

**Generate less data.** The defaults invent about 38,000 location points across
twelve people. Six people over three days is roughly 13,000, teaches every
lesson in the week just as well, and roughly halves the work on the heaviest
screen:

```bash
python3 tools/generate_sample_data.py --participants 6 --days 3 --out data/sample
.venv/bin/python -m backend.load_sample
```

**Give playback a bigger step.** Set the speed selector to *30 min / tick*, so
each redraw covers more ground and there are fewer of them. Playback waits for
each tick to finish before starting the next, so a slow device plays back more
slowly rather than falling behind and locking up.

### If it still crawls

In rough order of how much they cost you:

| Symptom | Try |
|---|---|
| Whole dashboard sluggish | Fewer participants and days, as above |
| Playback stutters | 30 min / tick; switch the basemap to **Street map**, which is lighter than satellite imagery |
| The map is blank | Venue wifi cannot reach Esri — install an [offline map](offline-maps.md) |
| Participant *Whole course* view is slow | Expected: it is the heaviest screen in the tool. Open it once and leave it open rather than switching participants repeatedly |
| Android kills the server when you switch apps | `termux-wake-lock` before starting it |
| Anything at all refuses to start | `.venv/bin/python manage.py doctor` |

---

## Running a real course

In order. Each links to a full walkthrough.

| # | Step | Time | Guide |
|---|---|---|---|
| 1 | Put the server online | ~45 min | [`hosting.md`](hosting.md) |
| 2 | Set the course location | 2 min | `.venv/bin/python manage.py set-location "City, State" --timezone America/...` |
| 3 | Run the safety check | 5 min | `.venv/bin/python manage.py check-production` |
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
.venv/bin/python manage.py status              # what is stored right now
.venv/bin/python manage.py where               # which city the course is anchored to
.venv/bin/python manage.py check-production    # safety check before going live
.venv/bin/python manage.py add-instructor NAME # create a teaching login
.venv/bin/python manage.py audit               # log of deletions, wipes, logins
.venv/bin/python manage.py wipe                # delete everything (asks for confirmation)
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
