"""
Pattern-of-life assessment: what an analyst would derive, and why it matters.

What this is for
----------------
A commercial system asks "what can I sell this person?" An intelligence or
security service asks a different set of questions, and they are the ones worth
teaching:

  * How regular is this person? Could I predict where they will be tomorrow?
  * Which places anchor their week, and which were one-offs?
  * When are they most predictable, and therefore most findable?
  * Who else moves with them?
  * What changed today against their own baseline?

None of that requires knowing who somebody is. That is the uncomfortable part,
and the reason this module exists: the assessment below is built entirely from
movement and public information about places, and it is still enough to say when
and where a person can be found.

The line, again
---------------
No identity resolution. Nothing here looks a person up, matches them to an
outside record, or tries to attach a name. It characterises a pattern.

Association analysis is **instructor-only** and is never returned to a
participant's own reveal. Telling somebody "you spent three hours near
Participant 07" would disclose another participant's movements to them, which
nobody consented to. Instructors were disclosed as able to see all participants;
participants were not.

Honesty
-------
Every judgement carries a confidence and a stated basis, and a thin week
produces thin conclusions rather than confident ones. An assessment that cannot
be wrong is not an assessment, it is a horoscope.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from .analysis import Point, Stop, haversine_m

# Two participants within this distance at the same time are treated as
# co-located. Generous enough to survive GPS error, tight enough that it means
# "in the same room or the same queue" rather than "in the same postcode".
COLOCATION_RADIUS_M = 60.0
COLOCATION_WINDOW_S = 300

# If this many participants are in the same place at the same moment, it is a
# crowd rather than a relationship. Everybody on this course shares a venue for
# most of the day, so without this the analysis simply reports that all twelve
# know each other, which is true, useless, and hides the real signal: who spends
# time together *away* from the crowd.
CROWD_THRESHOLD = 4


# --------------------------------------------------------------------------
# Regularity and predictability
# --------------------------------------------------------------------------

def assess_pattern_of_life(per_day: list[dict]) -> dict:
    """
    How much of a routine is visible across the days observed.

    `per_day` is a list of {day, places: [...]} as the week endpoint already
    builds. Places recur by name, which is how a routine reveals itself.
    """
    days_seen = [d for d in per_day if d.get("places")]
    if len(days_seen) < 2:
        return {
            "available": False,
            "reason": "Fewer than two days with data — no routine can be seen yet.",
        }

    # Which places appear on which days, and at what hour they were first seen.
    place_days: dict[str, set[str]] = defaultdict(set)
    place_hours: dict[str, list[float]] = defaultdict(list)
    for day in days_seen:
        for place in day["places"]:
            place_days[place["name"]].add(day["day"])
            try:
                first = datetime.fromisoformat(place["first_seen"])
                place_hours[place["name"]].append(first.hour + first.minute / 60)
            except (KeyError, ValueError):
                pass

    n_days = len(days_seen)
    recurring = {name: days for name, days in place_days.items() if len(days) >= 2}

    # A place visited at nearly the same time every day is far more useful to
    # somebody trying to find you than one visited at random hours.
    anchors = []
    for name, days in sorted(recurring.items(), key=lambda kv: -len(kv[1])):
        hours = place_hours.get(name, [])
        spread = statistics.pstdev(hours) if len(hours) >= 2 else None
        mean_hour = statistics.mean(hours) if hours else None
        # A place first seen just after midnight is where somebody slept, not
        # somewhere they arrived at 00:00. Saying "predictably at their hotel at
        # midnight" is both useless and slightly absurd, so overnight anchors are
        # labelled as such and kept out of the arrival-time reasoning.
        overnight = mean_hour is not None and mean_hour < 5.0
        anchors.append({
            "place": name,
            "days_seen": len(days),
            "day_fraction": round(len(days) / n_days, 2),
            "typical_hour": (round(mean_hour, 2) if mean_hour is not None else None),
            "typical_time": (_fmt_hour(mean_hour) if mean_hour is not None else None),
            "timing_spread_hours": (round(spread, 2) if spread is not None else None),
            "overnight_anchor": overnight,
            "predictable": bool(
                not overnight and spread is not None
                and spread < 1.0 and len(days) >= 3),
        })

    predictable = [a for a in anchors if a["predictable"]]

    # Predictability: how much of the week is accounted for by places that recur
    # at a consistent hour.
    if anchors:
        score = min(1.0, sum(a["day_fraction"] for a in predictable) / max(1, n_days) * 2)
    else:
        score = 0.0

    return {
        "available": True,
        "days_observed": n_days,
        "distinct_places": len(place_days),
        "recurring_places": len(recurring),
        "anchors": anchors[:8],
        "predictable_anchors": predictable[:5],
        "predictability": round(score, 2),
        "predictability_word": _predictability_word(score),
        "narrative": _pattern_narrative(n_days, anchors, predictable),
    }


def _fmt_hour(h: float) -> str:
    hour = int(h) % 24
    minute = int(round((h - int(h)) * 60)) % 60
    return f"{hour:02d}:{minute:02d}"


def _predictability_word(score: float) -> str:
    if score >= 0.7:
        return "highly predictable"
    if score >= 0.4:
        return "broadly predictable"
    if score >= 0.2:
        return "loosely patterned"
    return "little visible routine"


def _pattern_narrative(n_days: int, anchors: list[dict],
                       predictable: list[dict]) -> str:
    if not anchors:
        return (f"Across {n_days} days, no place was visited more than once. On this "
                f"evidence there is no routine to exploit — though a longer "
                f"observation window would very likely find one.")

    bits = [f"Across {n_days} days, {len(anchors)} places recur."]

    overnight = [a for a in anchors if a.get("overnight_anchor")]
    if overnight:
        bits.append(
            f"{overnight[0]['place']} appears on {overnight[0]['days_seen']} of "
            f"{n_days} nights — the place this person sleeps.")

    if predictable:
        top = predictable[0]
        bits.append(
            f"The most predictable daytime arrival is {top['place']}: seen on "
            f"{top['days_seen']} of {n_days} days, typically around "
            f"{top['typical_time']}, varying by under an hour.")
        bits.append(
            "Somebody wanting to find this person on a given morning would not "
            "need to follow them. They would need only to be there and wait.")
    else:
        bits.append(
            "The timing varies enough that arrival could not be predicted to "
            "within an hour — which is, in this narrow sense, protective.")
    return " ".join(bits)


# --------------------------------------------------------------------------
# Individual signature: what makes this person's pattern theirs
# --------------------------------------------------------------------------

def assess_signature(points: list[Point], per_day: list[dict]) -> dict:
    """
    The traits that distinguish one anonymous participant from another.

    This is the part of the lesson people find hardest to shrug off. Without a
    name, an address or an account, a week of movement still produces a
    description specific enough that a participant recognises themselves in it
    immediately — and specific enough to tell them apart from eleven others.

    Everything here is derived from their own coordinates and clock. Nothing is
    looked up.
    """
    if len(points) < 20:
        return {"available": False}

    pts = sorted(points, key=lambda p: p.ts)

    # Chronotype: when the day starts and ends, averaged over days observed.
    starts: list[float] = []
    ends: list[float] = []
    by_day: dict[str, list[Point]] = defaultdict(list)
    for p in pts:
        by_day[p.ts.date().isoformat()].append(p)

    for day_pts in by_day.values():
        # Ignore the overnight tail: the first real movement of the day is what
        # says whether somebody is an early riser, not the phone on the bedside
        # table at 3am.
        moving = _first_movement(day_pts)
        if moving:
            starts.append(moving.ts.hour + moving.ts.minute / 60)
        last = _last_movement(day_pts)
        if last:
            ends.append(last.ts.hour + last.ts.minute / 60)

    # Mobility: how far from their anchor they range, and how much ground covered.
    lats = [p.lat for p in pts]
    lons = [p.lon for p in pts]
    centre = (statistics.median(lats), statistics.median(lons))
    radii = [haversine_m(centre[0], centre[1], p.lat, p.lon) for p in pts]
    radius_km = round(max(radii) / 1000, 1) if radii else 0

    distance_km = 0.0
    for a, b in zip(pts, pts[1:]):
        gap = (b.ts - a.ts).total_seconds()
        if gap <= 1800:
            distance_km += haversine_m(a.lat, a.lon, b.lat, b.lon) / 1000

    # Exploration: how much of the week was spent somewhere new.
    seen: set[str] = set()
    new_by_day = []
    for day in per_day:
        names = {pl["name"] for pl in day.get("places", [])}
        new_by_day.append(len(names - seen))
        seen |= names
    exploration = (round(sum(new_by_day[1:]) / max(1, len(new_by_day) - 1), 1)
                   if len(new_by_day) > 1 else 0)

    traits = []
    if starts:
        mean_start = statistics.mean(starts)
        traits.append(_chronotype(mean_start))
    if ends:
        mean_end = statistics.mean(ends)
        if mean_end >= 22:
            traits.append("out late most evenings")
        elif mean_end <= 19:
            traits.append("home early most evenings")
    if radius_km >= 8:
        traits.append("ranges well beyond the city centre")
    elif radius_km <= 2:
        traits.append("stays within a small central area")
    if exploration >= 2:
        traits.append("visits somewhere new most days")
    elif exploration <= 0.5:
        traits.append("returns to the same handful of places")

    return {
        "available": True,
        "typical_start": _fmt_hour(statistics.mean(starts)) if starts else None,
        "typical_end": _fmt_hour(statistics.mean(ends)) if ends else None,
        "start_spread_hours": (round(statistics.pstdev(starts), 2)
                               if len(starts) >= 2 else None),
        "max_radius_km": radius_km,
        "distance_travelled_km": round(distance_km, 1),
        "new_places_per_day": exploration,
        "traits": traits,
        "narrative": _signature_narrative(traits, starts, ends, radius_km, distance_km),
    }


def _first_movement(day_pts: list[Point], threshold_m: float = 120) -> Point | None:
    """The first point meaningfully away from where the day started."""
    if not day_pts:
        return None
    ordered = sorted(day_pts, key=lambda p: p.ts)
    origin = ordered[0]
    for p in ordered:
        if haversine_m(origin.lat, origin.lon, p.lat, p.lon) > threshold_m:
            return p
    return None


def _last_movement(day_pts: list[Point], threshold_m: float = 120) -> Point | None:
    if not day_pts:
        return None
    ordered = sorted(day_pts, key=lambda p: p.ts)
    end = ordered[-1]
    for p in reversed(ordered):
        if haversine_m(end.lat, end.lon, p.lat, p.lon) > threshold_m:
            return p
    return None


def _chronotype(mean_start: float) -> str:
    if mean_start < 7:
        return "up and out before seven"
    if mean_start < 8.5:
        return "an early start most days"
    if mean_start < 10:
        return "a conventional morning"
    return "a late start most days"


def _signature_narrative(traits, starts, ends, radius_km, distance_km) -> str:
    if not traits:
        return "Not enough movement to describe a personal pattern yet."
    bits = ["Without a name, an address, or an account, this week describes "
            "somebody who is " + ", ".join(traits) + "."]
    if starts and ends:
        bits.append(
            f"Typically moving by {_fmt_hour(statistics.mean(starts))} and "
            f"settled by {_fmt_hour(statistics.mean(ends))}, covering roughly "
            f"{round(distance_km)} km across the week within about "
            f"{radius_km} km of one centre.")
    bits.append(
        "That description fits one person in this room and not the other eleven. "
        "It was assembled from coordinates and a clock.")
    return " ".join(bits)


# --------------------------------------------------------------------------
# Association: who moves with whom
# --------------------------------------------------------------------------

def assess_associations(subject_id: str,
                        subject_points: list[Point],
                        others: dict[str, list[Point]],
                        labels: dict[str, str] | None = None) -> dict:
    """
    Which other participants were repeatedly in the same place at the same time.

    INSTRUCTOR-ONLY. This is other people's location data by implication, and
    must never be returned to a participant's own reveal.

    The teaching point is that association falls out of the data without anybody
    collecting a contact list: a network is visible purely from who keeps
    turning up in the same place at the same minute.
    """
    labels = labels or {}
    if not subject_points:
        return {"available": False}

    # Index everybody by time bucket, so each moment can be judged for how
    # crowded it was before it is credited as an association.
    buckets: dict[int, list[tuple[str, Point]]] = defaultdict(list)
    for pid, pts in others.items():
        if pid == subject_id:
            continue
        for q in pts:
            buckets[int(q.ts.timestamp() // COLOCATION_WINDOW_S)].append((pid, q))

    together: dict[str, dict] = defaultdict(
        lambda: {"windows": set(), "days": set(), "closest": None})
    crowd_windows = 0

    for p in subject_points:
        bucket = int(p.ts.timestamp() // COLOCATION_WINDOW_S)
        nearby: dict[str, float] = {}
        for delta in (-1, 0, 1):
            for pid, q in buckets.get(bucket + delta, ()):
                if abs((p.ts - q.ts).total_seconds()) > COLOCATION_WINDOW_S:
                    continue
                d = haversine_m(p.lat, p.lon, q.lat, q.lon)
                if d <= COLOCATION_RADIUS_M:
                    if pid not in nearby or d < nearby[pid]:
                        nearby[pid] = d

        # A room with most of the course in it says nothing about anybody.
        if len(nearby) >= CROWD_THRESHOLD:
            crowd_windows += 1
            continue

        day = p.ts.date().isoformat()
        for pid, d in nearby.items():
            rec = together[pid]
            rec["windows"].add(bucket)
            rec["days"].add(day)
            if rec["closest"] is None or d < rec["closest"]:
                rec["closest"] = d

    results = []
    for pid, rec in together.items():
        minutes = len(rec["windows"]) * COLOCATION_WINDOW_S / 60
        results.append({
            "participant_id": pid,
            "label": labels.get(pid, pid),
            "shared_minutes": round(minutes),
            "days_together": len(rec["days"]),
            "days": sorted(rec["days"]),
            "closest_m": round(rec["closest"]) if rec["closest"] is not None else None,
            "strength": _association_strength(minutes, len(rec["days"])),
        })

    results.sort(key=lambda r: (r["days_together"], r["shared_minutes"]), reverse=True)

    # Almost everyone shares the venue during sessions, which is not a
    # relationship. What matters is time together *away* from the crowd, so the
    # narrative leans on days rather than raw minutes.
    notable = [r for r in results if r["days_together"] >= 2]

    return {
        "available": True,
        "associations": results[:10],
        "notable": notable[:5],
        "crowd_windows_ignored": crowd_windows,
        "narrative": _association_narrative(notable, len(results), crowd_windows),
        "caveat": (
            "Moments when four or more participants were in the same place have "
            "been discarded as crowd rather than company — otherwise this would "
            "simply report that everyone on the course knows everyone. What "
            "remains is time spent together away from the group, and even that is "
            "not proof: two people in the same cafe are not necessarily "
            "together."),
    }


def detect_groups(all_points: dict[str, list[Point]],
                  labels: dict[str, str] | None = None,
                  min_days: int = 2) -> dict:
    """
    Recurring small groups, rather than pairs one at a time.

    Participants on this course move about in small groups by design, and that
    is precisely what a third party watching over a week would pick out: not
    "these two were once in the same bar", but "these four are together most
    evenings". Groups are far more revealing than pairs, because a group that
    keeps reforming is a relationship rather than a coincidence.

    Moments with the whole cohort present are still excluded — a lecture theatre
    is not a friendship — so what surfaces is the sub-group that keeps meeting
    away from the room.
    """
    labels = labels or {}
    buckets: dict[int, list[tuple[str, Point]]] = defaultdict(list)
    for pid, pts in all_points.items():
        for p in pts:
            buckets[int(p.ts.timestamp() // COLOCATION_WINDOW_S)].append((pid, p))

    # For each moment, which small sets of people were together.
    seen_groups: dict[frozenset, dict] = defaultdict(
        lambda: {"windows": set(), "days": set()})

    for bucket, members in buckets.items():
        if len(members) < 2:
            continue
        # Cluster the people present at this moment by proximity.
        remaining = list(members)
        while remaining:
            pid, anchor = remaining.pop()
            cluster = {pid}
            still = []
            for other_pid, q in remaining:
                if haversine_m(anchor.lat, anchor.lon, q.lat, q.lon) <= COLOCATION_RADIUS_M:
                    cluster.add(other_pid)
                else:
                    still.append((other_pid, q))
            remaining = still
            # Two is a pair, and the whole room is a lecture. The interesting
            # band is in between.
            if 2 <= len(cluster) < CROWD_THRESHOLD:
                rec = seen_groups[frozenset(cluster)]
                rec["windows"].add(bucket)
                rec["days"].add(anchor.ts.date().isoformat())

    groups = []
    for members, rec in seen_groups.items():
        if len(rec["days"]) < min_days:
            continue
        groups.append({
            "members": sorted(members),
            "labels": [labels.get(m, m) for m in sorted(members)],
            "size": len(members),
            "days_together": len(rec["days"]),
            "days": sorted(rec["days"]),
            "minutes_together": round(len(rec["windows"]) * COLOCATION_WINDOW_S / 60),
        })

    groups.sort(key=lambda g: (g["days_together"], g["minutes_together"]), reverse=True)
    return {
        "available": bool(groups),
        "groups": groups[:12],
        "narrative": _group_narrative(groups),
        "caveat": (
            "Groups are inferred from being in the same place at the same minute, "
            "repeatedly. That is strong evidence of association and weak evidence "
            "of anything else — people share a lift, a queue and a bus stop "
            "without knowing each other."),
    }


def _group_narrative(groups: list[dict]) -> str:
    if not groups:
        return ("No small group reformed on more than one day, once moments with "
                "the whole cohort present are excluded.")
    top = groups[0]
    names = ", ".join(top["labels"])
    return (
        f"{len(groups)} recurring group(s) were detected. The strongest is "
        f"{names} — together on {top['days_together']} days for around "
        f"{top['minutes_together']} minutes, away from the whole-cohort moments. "
        f"Nobody collected a contact list, and no message was read. This social "
        f"graph fell out of coordinates and timestamps alone.")


def _association_strength(minutes: float, days: int) -> str:
    if days >= 4 and minutes > 240:
        return "consistent companion"
    if days >= 3:
        return "repeated co-location"
    if days >= 2:
        return "co-located on multiple days"
    return "incidental"


def _association_narrative(notable: list[dict], total: int,
                           crowd_windows: int = 0) -> str:
    if not notable:
        return ("No other participant was repeatedly in the same place at the same "
                "time, once moments with the whole group present are discounted.")
    top = notable[0]
    bits = [
        f"Discounting {crowd_windows} moments when the group was together, "
        f"{len(notable)} other participant(s) were repeatedly in the same place at "
        f"the same time on more than one day."]
    bits.append(
        f"The strongest is {top['label']}: {top['shared_minutes']} minutes across "
        f"{top['days_together']} days.")
    bits.append(
        "Nobody collected a contact list. This network fell out of two sets of "
        "coordinates and two clocks.")
    return " ".join(bits)


# --------------------------------------------------------------------------
# Anomaly: what changed against their own baseline
# --------------------------------------------------------------------------

def assess_anomaly(today: dict, prior: list[dict]) -> dict:
    """
    What today did that the earlier days did not.

    Deviation is what draws attention in a monitoring system: not the routine
    itself, but the day the routine breaks.
    """
    if not prior:
        return {"available": False}

    prior_places = set()
    prior_last_hours = []
    for day in prior:
        for place in day.get("places", []):
            prior_places.add(place["name"])
        rhythm = day.get("assessment", {}).get("findings", {}).get("rhythm", {})
        if rhythm.get("returned_local"):
            try:
                hh, mm = rhythm["returned_local"].split(":")
                prior_last_hours.append(int(hh) + int(mm) / 60)
            except ValueError:
                pass

    today_places = [p["name"] for p in today.get("places", [])]
    new_places = [n for n in today_places if n not in prior_places]

    flags = []
    if new_places:
        flags.append(f"{len(new_places)} place(s) not seen on any earlier day: "
                     f"{', '.join(new_places[:3])}.")

    rhythm = today.get("assessment", {}).get("findings", {}).get("rhythm", {})
    if prior_last_hours and rhythm.get("returned_local"):
        try:
            hh, mm = rhythm["returned_local"].split(":")
            today_last = int(hh) + int(mm) / 60
            baseline = statistics.mean(prior_last_hours)
            if abs(today_last - baseline) >= 1.5:
                direction = "later" if today_last > baseline else "earlier"
                flags.append(
                    f"Returned {abs(today_last - baseline):.1f} hours {direction} "
                    f"than the usual {_fmt_hour(baseline)}.")
        except ValueError:
            pass

    return {
        "available": True,
        "flags": flags,
        "new_places": new_places,
        "narrative": (
            "Nothing today departed from the established pattern."
            if not flags else
            "A monitoring system would flag today for review: " + " ".join(flags)),
    }
