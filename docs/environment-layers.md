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
python3 tools/fetch_osm_environment.py --around 30.2672,-97.7431 --radius 5000
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

---

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
