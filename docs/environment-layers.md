# Environmental enrichment: what else was watching

The strongest lesson in the whole course, and the one that needs the most care
in how it is presented.

---

## The idea

A phone trail on its own is **one source**, and one source is deniable. "That's
my phone, not me." "Location data is unreliable." "I lent it to someone."

What makes location data genuinely dangerous is **corroboration** — the moment
the phone ping lines up with a camera, a plate reader, a Wi-Fi association and a
card terminal, all at the same place and the same minute. Any one of those is
circumstantial. Together they are a record, and no amount of arguing dislodges
them.

That is precisely how a fragmented, cheaply-bought, nominally "anonymous"
location feed becomes something an intelligence service, a data broker or a
criminal buyer can act on. Dwell makes the mechanism visible.

---

## What it produces

For each participant-day, alongside the usual inferences:

- **What the route passed** — counts of cameras, plate readers, mapped Wi-Fi,
  card terminals and transit gates within range of their trail.
- **Which stops more than one source could confirm**, with a plain verdict:
  *phone only — deniable* through to *four or more kinds of source — not
  realistically deniable*.
- **A narrative** leading with the corroboration point rather than with a
  coverage percentage, because the percentage is the part most easily misread.
- **What it does not prove** — stated every time, unprompted.

---

## The line this does not cross

**Enrichment here describes the environment, never the person.**

It will say *"your route passed nine cameras, and four independent sources could
place you at that stop."* It will not look up who you are, pull records about
you, or match you against anything outside this system.

That distinction is the whole ethical basis of the exercise, and it is enforced
by simply never writing the code that would cross it. There is no identity
resolution in this repository, and adding some would change what this tool is.

---

## Being honest about what "in range" means

This is where a tool like this could very easily become the thing it criticises.

A camera near a point is **not** proof of anything. It may face the other way.
It may not be recording. It may overwrite in 48 hours. Its footage may be
entirely unavailable to anyone who wants it. Somebody sitting inside a building
for six hours generates hundreds of points "within range" of a camera bolted to
the outside wall that never once saw them.

So every figure here is **an upper bound on opportunity, not evidence of
observation**, and the wording says so on screen, every time. The coverage
percentage is deliberately reported *after* the corroboration point and
immediately qualified.

Getting this wrong would be the same failure the course exists to criticise:
confident, unhedged conclusions drawn from thin evidence. Do not let the number
run ahead of what it supports.

---

## Where the data comes from

### Included, and safe

**OpenStreetMap** — publicly mapped surveillance cameras, ALPR installations,
toll points and transit gates. Contributed by volunteers, describes street
furniture, needs no account:

```bash
python3 tools/fetch_osm_environment.py --around 43.0389,-87.9065 --radius 6000
python -m backend.load_sample
```

The sample dataset ships with **invented** infrastructure so the feature can be
demonstrated immediately, exactly as the places are invented.

### Deliberately excluded: WiGLE and similar

You asked about WiGLE. It is a genuinely rich dataset — crowdsourced Wi-Fi and
Bluetooth observations worldwide — and it is **deliberately not integrated**.

Querying it means sending the coordinates you are interested in to a third
party. Those coordinates are participants' locations. The consent screen tells
participants their data goes to the course server **and nowhere else**, and
quietly shipping their positions to an external service in order to build a
lesson about quietly shipping data would be indefensible.

If you want Wi-Fi in the picture, obtain a static extract for your area in
advance, convert it offline to the same JSON format, and load it. The data never
needs to move in the other direction.

This constraint is worth teaching in its own right: *we wanted this dataset, we
could have had it, and the promise we made to you cost us it.* Very few products
can say that.

### Nearby posts: what is actually obtainable

The moment worth engineering for is a participant realising that while they
stood on a particular corner, a stranger a hundred metres away posted a photo of
it publicly, and it is still there.

**TikTok cannot supply this, and it is worth saying why rather than quietly
substituting something else.** TikTok has no public API for searching posts by
location; its research API is grant-gated, does not expose geosearch, and its
terms forbid this use. The only route is scraping the web client, which breaks
TikTok's terms of service. A privacy course cannot run on data taken in breach
of somebody's terms — the contradiction would be the first thing a sharp
participant noticed, and they would be right.

Instagram and Facebook removed public location search in 2018, for exactly the
reason this exercise illustrates. X removed its free geo-search tier.

What remains are platforms that publish geotagged material openly and mean it:

| Source | Key needed | Genuinely geotagged | Dated |
|---|---|---|---|
| Wikimedia Commons | no | yes | not in geosearch results — pin with `--undated` |
| Flickr | free, one form | yes | yes, to the minute |

```bash
python3 tools/fetch_nearby_posts.py --around 43.0389,-87.9065 --radius 1500 \
    --days 2026-09-14:2026-09-18 --flickr-key YOUR_KEY \
    --out data/context/milwaukee-posts.json
python -m backend.load_sample
```

Flickr is the closest lawful equivalent to what TikTok would have given you:
real strangers, real coordinates, real timestamps. It is thinner than TikTok
would be, and the honest framing in the room is to say so —

> This is a fraction of what is actually out there. The platform with the most
> of it will not let us have it lawfully, so we did not take it. Assume the real
> picture is several times denser than what you are looking at.

— which lands harder than pretending the sample is complete.

The sample dataset ships with invented posts anchored to the sample locations, so
the feature demonstrates without any fetching at all.

---

## The assessment layer

Beyond corroboration, the analysis now asks the questions a security service
asks rather than the ones an advertiser asks. All of it from movement and public
information about places; none of it requiring anybody's name.

**Pattern of life** — which places recur, at what hour, and how tightly. A place
visited at 09:06 ± 6 minutes on five of six days is not a habit, it is a
schedule. The tool says so plainly: *somebody wanting to find this person would
not need to follow them; they would need only to be there and wait.*

**Behavioural signature** — the same person described rather than counted: when
they typically start and stop moving, how tightly that varies, how far from one
centre they range, how much ground they cover, and whether they explore or
return. It reads out as a sentence — *"an early start most days, stays within a
small central area, returns to the same handful of places"* — and then makes the
point the sentence exists for:

> That description fits one person in this room and not the other eleven. It was
> assembled from coordinates and a clock.

This is the sharpest illustration in the tool of why "we don't collect personal
information" is a hollow claim. Nothing here is a name, an address or an
account. It is still enough to pick somebody out of a group, which is what
identification actually means.

**Association** — who was repeatedly in the same place at the same minute.
Moments when four or more participants were together are discarded as crowd
rather than company, since everyone shares a venue; what remains is time spent
together away from the group. Nobody collected a contact list. The network falls
out of two sets of coordinates and two clocks.

**Recurring groups** — the same question asked of the cohort rather than of one
person: which *sets* of people reformed, day after day, away from the whole-group
moments. Participants on this course move in small groups by design, so this is
not a hypothetical — a third party watching for a week would notice exactly this,
and the dashboard shows them noticing it.

Pairs and threes are reported; anything from four people up is treated as the
class being the class. A group that reforms on five separate days is the finding.
Two people who queued together once is not.

**Anomaly** — what today did that the baseline did not. Monitoring systems are
not interested in the routine; they are interested in the day it breaks.

**Area context** — public, dated, located items such as local news and event
listings, matched to stops by place and time. This is the step where a trail
stops being coordinates and becomes an account of somebody's day.

**Nearby public posts** — the same idea at much closer range: photographs
strangers posted publicly, within **120 metres and two hours** of where a
participant was actually standing. The wider 400-metre radius used for news is
deliberately not used here, because at 400 metres this only means "somebody in
the same neighbourhood", and the feeling the moment depends on is *right where I
was*.

Nothing about this is person-targeted. It does not search for posts by or about
a participant, and author names are discarded on the way in — the item format
has no field to put them in. It searches a **place**, and the place happens to be
where somebody stood.

Two constraints, both load-bearing:

- **Association and group analysis are instructor-only.** Neither is ever
  returned to a participant's own reveal, because telling somebody "you spent
  three hours near Participant 07" discloses another participant's movements to
  them. Instructors were disclosed as able to see everyone. Participants were
  not. `tools/contract_test.py` asserts this on every run rather than trusting
  the code to stay that way.
- **Context is about places and events, never people.** Nothing searches for
  posts by or about a participant, and nothing matches anybody to a social media
  account. Person-targeted collection is precisely what a real service adds
  next, and the honest way to teach that is to describe the step and decline to
  take it.

## Teaching it

Run it on day four, after participants already understand the trail. The arc is:

1. **Day 2:** here is what your phone recorded.
2. **Day 3:** here is the routine that emerges when days stack up.
3. **Day 4:** and here is everything *else* that could confirm it.

**The line that lands:**

> Everything you have seen so far came from one source — your phone. One source
> can be argued with.
>
> At this stop, four sources agree. Your phone, a camera on the corner, the
> shop's Wi-Fi, and a card terminal. Individually, each is circumstantial.
> Together, there is no version of events where you were not there.
>
> Nobody had to build that. It was assembled from things that already existed,
> owned by four organisations who have never spoken to each other.

Then who would want it. The tool lists four buyers — a data broker, an
advertiser or insurer, a state security service, a criminal or stalker — with
what each actually needs from the picture, and what access each would require.
The broker needs nothing you did not already give away. The intelligence service
needs the corroboration. The stalker needs only the routine.

**Handle with the same care as the personal reveals.** Ask for a volunteer. Do
not comment on where they went. This section makes the exposure feel much more
concrete than the trail alone, and some people find it genuinely unsettling —
which is a reasonable response to a real thing, not something to talk them out
of.
