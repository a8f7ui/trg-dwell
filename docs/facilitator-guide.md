# Facilitator's guide

For whoever is standing at the front of the room. Assumes no technical
background. You do not need to understand how the app works to run the week
well — you need to know what to show, when, and what to say about it.

---

## The one idea the week is built on

Everything below serves a single argument, in three moves:

1. **Mechanism** — here is what your phone recorded.
2. **Pattern** — here is what that reveals once it accumulates.
3. **Consequence** — here is who buys this, and what they do with it.

Most privacy training stops at move one and produces a shrug. The week works
because participants see their *own* data, and because the picture visibly
tightens day after day in front of them.

---

## Before you start: five rules for the room

These matter more than any slide. You will be putting real people's movements on
a screen.

**1. Never single anybody out.** Always ask for a volunteer before showing an
individual's day. Never pick someone because their data looks interesting — that
is precisely the behaviour the course criticises.

**2. Never comment on where somebody went.** Not a joke, not an eyebrow. If a
volunteer's trail shows a pharmacy, a bar, or a two-hour stop at an address they
have not explained, say nothing about it and move on. Your job is to demonstrate
the mechanism, not the person.

**3. Give people an exit before every personal demo.** "I'm about to put one
person's day on screen — do I have a volunteer?" Nobody should ever be surprised
to see themselves.

**4. Expect somebody to be upset.** Some people find their own trail genuinely
distressing, especially if it reveals something they had not thought about. That
is a legitimate reaction to a real thing. Acknowledge it, do not minimise it, and
remind them withdrawal is two taps and takes effect immediately.

**5. If someone withdraws, say nothing.** No questions, no follow-up, no
mentioning it. Their participant count simply drops. Treating withdrawal as
unremarkable is what makes it a real option.

---

## Before day one

- [ ] **Course location set**, if you are not teaching in Milwaukee. Dashboard →
      *Data & teardown → Course location*, or
      `python manage.py set-location "Your City, State" --timezone America/...`.
      This decides where the map opens and which timezone every time on screen
      is shown in. Getting it wrong is not subtle but it is easy to miss:
      `python manage.py check-production` warns you.
- [ ] Server online and tested (`docs/hosting.md`).
- [ ] Install links sent at least a week ahead (`docs/distribution.md`).
- [ ] You have run the app on your own phone for **at least two days** — you
      cannot teach this from the dashboard alone.
- [ ] Dashboard logged in on the projector machine, with the demo participant
      view already open.
- [ ] Know how many participants installed. Chase the stragglers.
- [ ] If the venue's wifi is doubtful, install an *offline* copy of the street
      map (`docs/offline-maps.md`) and check it covers the venue and the hotels.
      Satellite and street basemaps are built in either way — this is only about
      surviving a bad connection.

**Have the sample data ready as a fallback.** If the server misbehaves, or too
few people installed, every teaching point below works against the synthetic
participants. Load it, and say plainly that you are showing example data. Never
pretend sample data is real.

---

## The two skins, and how to use them

Top right of the dashboard, always available:

| | Looks like | What it does in the room |
|---|---|---|
| **Field** | A consumer family-safety app — white, rounded, friendly, round colour avatars | Removes the escape hatch. This is the interface people already have on their phones and do not think of as surveillance. |
| **Console** | A surveillance monitoring station — dark, dense, monospaced, uppercase | Makes the room recognise the screen as what it resembles. |

**They show identical data.** Same trails, same corroboration, same social
graph, same everything. The only difference is the palette.

Switching is instant and does not interrupt anything — you can flip skins in
the middle of playback and the dots keep moving. Your choice is remembered on
that machine.

**The move worth rehearsing:** put a volunteer's week on the projector in
Console, let the room settle into *that's a spy tool*, then switch to Field
mid-sentence without changing anything else.

> Same data. Same person. Same week. Same conclusions.
>
> One of these two screens is what you picture when somebody says
> "surveillance". The other is what is actually on your phone.
>
> Nothing changed but the colours. Whatever you were feeling ten seconds ago
> was a reaction to the styling, not to what the system knows.

Use whichever suits the day otherwise. Field is easier to read from the back of
a lit room; Console suits Day 4, when the subject is who buys this.

### The two basemaps

Separately from the skins, the map itself switches between **Satellite** and
**Street map** in the panel at its top right, which is open by default. Both are
built in — nothing to install, and they work on a fresh clone.

Use both, and switch deliberately:

- **Satellite** for the first reveal. Rooftops and car parks make it feel like
  a photograph of a real afternoon, and people locate themselves faster on it.
- **Street map** the moment somebody asks *"where is that?"* Named roads and
  labelled buildings turn a dot into an address people recognise, and it is
  clearer on a projector in a lit room.

A useful move when a trail looks abstract: switch to streets, let somebody read
the road names aloud, then switch back. The dots did not change. What changed is
that the room can now say where they were.

---

## Day 1 — Consent, and the permission prompts

**Objective:** everyone installed and consenting, and the first lesson landed
before any data exists.

### Run the installation live (20 minutes)

Do this in the room, not by email. The installation *is* the lesson.

Ask everyone to open the app and **read the consent screen properly** — you will
be asking about it. Notice who scrolls and who tries to tap straight through.
They cannot: the button stays disabled until they reach the bottom.

**Talking point — the consent model:**

> Notice what just happened. You could not agree until you had scrolled to the
> end. Every app you have ever installed put the agree button where you could
> reach it in one tap.
>
> Notice also what is at the top of that screen rather than buried: that this
> keeps recording when the app is closed, and that I can see where you are.
> Those are the two most uncomfortable facts, and they are the first things you
> read.
>
> Hold that shape in your head. For the rest of the week, compare it against
> every consent screen you meet.

### Walk the permission prompts (15 minutes)

The app narrates each permission before requesting it. Let people read the
screens rather than reading them aloud.

**Talking point — permission inheritance.** This is the single most useful fact
in the course:

> When you tap Allow on a weather app's location request, you are not only
> agreeing with the weather app. Every advertising and analytics component
> bundled inside it inherits that same access, without a prompt of its own. You
> consented to the weather app. You have never heard of the companies actually
> receiving the data.
>
> That is not a loophole. That is the ordinary way the industry works.

### Set expectations (5 minutes)

> Leave it running. Do not think about it. That is the experiment — I want to
> know what an app learns about you while you are ignoring it.
>
> You will get one notification each evening. Open it when you get it.

**Do not show the dashboard today.** There is nothing in it, and the anticipation
does real work.

---

## Day 2 — Mechanism: "here is what it saw"

**Objective:** the abstract becomes concrete. Today is about accuracy, not
inference.

### Their own reveal first (10 minutes)

Everyone opens the app and reads their own day. Give them silence to do it.
This lands hardest privately, before any discussion.

### One volunteer on the projector (20 minutes)

Ask for a volunteer. Open **Participant → their day** on the dashboard.

Walk through: the trail, the stops sized by how long they were there, the times.

**Talking point — how little it took:**

> Look at the top of that panel. It says what proportion of these points were
> collected while the app was closed. That number is usually more than half.
>
> Most of what I know about your day, I learned while you were not looking at
> your phone. You did not decline to be observed. You simply were not present
> for it.

### Introduce the illustrated screens (15 minutes)

Have everyone open **"What a real ad SDK would also be taking"**.

**Talking point — the real-versus-illustrated distinction.** Be scrupulous here.
Your credibility for the rest of the week depends on it:

> Everything you have just seen on the map is real. That is your actual Tuesday.
>
> Everything on the screen you are looking at now is invented. Those are not your
> contacts. That is not your clipboard. Every card says SIMULATED.
>
> We could have taken them. The permissions you granted would have allowed some
> of it, and no permission at all is needed for the clipboard. We did not,
> because your contacts include hundreds of people who are not on this course and
> never agreed to anything.
>
> A commercial SDK would not have drawn that line, and would not have told you
> either way.

Then read out one documented case from `docs/sdk-research.md`. The Air Canada
session-replay case works well: an ordinary analytics integration transmitting
screen recordings containing passport and credit card numbers.

---

## Day 3 — Pattern: the profile tightens

**Objective:** show that the danger is not any single day. It is accumulation.

### The reveal compares itself to yesterday (10 minutes)

Each participant's reveal now contains a "compared with earlier days" section.

### Whole-week view for a volunteer (20 minutes)

**Participant → Day selector → Whole course.** Places they have returned to are
highlighted.

**Talking point:**

> One day is a list of dots. Three days is a routine.
>
> Nobody had to work out where you live or work. You simply went back, and the
> pattern did the rest. Repetition is what turns location data into a profile.

### The inference, and its confidence (15 minutes)

Show the segment: "business traveller", "commuting professional", with its
confidence percentage.

**Talking point — confidently wrong:**

> It has put you in a marketing category, with a confidence score, from movement
> alone.
>
> Now read the "where I might be wrong" section — it names a specific way this
> could be mistaken about you, and admits nothing in the data could tell the
> difference.
>
> A real system would show you none of that. It prints the verdict and acts on
> it. Advertisers buy it, insurers have wanted it, and it gets used whether or
> not it is right about you.

**If the app is wrong about a volunteer, that is a gift.** Spend time on it. A
confident, wrong, unchallengeable judgement is the whole risk in one example.

### The behavioural signature (10 minutes)

Still in the whole-course view, scroll to **Behavioural signature**. Read the
sentence out as written — when they start, when they stop, how tightly that
varies, how far they range.

Then stop, and put the question to the room rather than answering it:

> Nothing I just read is a name. It is not an address, an account, a phone
> number or an email. By most privacy policies, none of it is personal
> information.
>
> Hands up if you could tell me which of the twelve of you that describes.

Most rooms can. That is the point, and it is better made by them than by you.

**Talking point:**

> "We don't collect personally identifiable information" is not a promise that
> you cannot be identified. It is a promise about which *fields* are stored.
> Identification is a property of the whole picture, not of any one column in
> it — and this picture was built from coordinates and a clock.

---

## Day 4 — Consequence: the buyer's console

**Objective:** move from "this is about me" to "this is an industry".

### The live map (15 minutes)

Open **Live map**. Dots move.

The map follows them on its own — **Follow** is on by default, so as the group
moves across the city the view goes with them and you never have to chase the
dots with a trackpad while talking. It holds still while people stay put, so
nothing slides around under you mid-sentence.

Pan or zoom the map yourself and Follow switches off, because a map that argues
with your hand during a class is worse than one that never moved. **Fit** puts
you back on everybody and resumes following.

**Talking point:**

> Nobody in this room has the app open. You are all looking at me. And I can
> watch you move.
>
> This screen is not unusual. It is roughly what a location-data buyer's console
> looks like. The only differences are that you were told this exists, you agreed
> to it, and this map never leaves the room.

### What else was watching (15 minutes)

Open a volunteer's day and scroll to **What else was watching**.

**Talking point — corroboration:**

> Everything so far came from one source: your phone. One source can be argued
> with. "That's my phone, not me."
>
> At this stop, four sources agree — your phone, a camera on the corner, the
> shop's Wi-Fi, and a card terminal. Individually each is circumstantial.
> Together there is no version of events where you were not there.
>
> Nobody had to build that. It was assembled from things that already existed,
> owned by four organisations who have never spoken to each other.

Read the "what this does not prove" note aloud too. A camera near somebody is not
proof it filmed them, and the tool says so — which is exactly the hedging a
commercial system would omit. Full background in `docs/environment-layers.md`.

### Who you were with (10 minutes)

Scroll to **Recurring groups**. You will have moved people around in small groups
this week, so the groups it finds will be real ones the room recognises.

**Talking point:**

> Nobody handed over a contact list. Nobody's messages were read. No app asked
> who your friends are.
>
> Two sets of coordinates and two clocks. That is the entire input, and it
> reconstructed who you have been spending the week with.

Then the part that matters more than the finding:

> Notice what this does to consent. Every one of you agreed to this. But the
> moment two people's trails are compared, what comes out is a fact about a
> *relationship* — and a relationship cannot consent. It only takes one person
> in a pair carrying a tracked phone to expose both.

**Handle carefully.** Groups here are innocuous by design. In the real world the
same computation is what exposes a source meeting a journalist, or who somebody
is quietly seeing. Say that; do not act it out.

**Do not show this to participants on their own phones, and say so.** Association
and group analysis exist only on the instructor dashboard. Telling somebody "you
spent three hours near Participant 07" would disclose Participant 07's movements
to a person who was never given the right to see them — and the fact that we
could have shown it, and chose not to, is itself worth a minute of the room's
time.

### What was posted around you (10 minutes)

Scroll to **Area context**. Alongside the news items are public photographs
posted within 120 metres and two hours of where the volunteer was standing.

**Talking point:**

> None of these are about you. Nobody photographed you, nobody tagged you, and
> nobody knew you were there. They are strangers, posting in public, from where
> you happened to be standing.
>
> That is what makes it work. A determined observer does not need to follow you.
> They need only to read what everyone else is already publishing about the
> places you go.

Be straight about the source when asked, because somebody will ask about TikTok:
there is no lawful way to get geotagged TikTok posts, so this uses platforms that
publish coordinates openly. Which means what they are looking at is a *fraction*
of what actually exists — the real picture is denser, not thinner.

### The aggregate map and k-anonymity (25 minutes)

This is the best demonstration in the whole week. Do it live and slowly.

Open **Whole course**. The threshold starts at 5. A handful of hexagons show —
mostly the venue.

**Talking point — k-anonymity:**

> This is everybody's data at once. A hexagon only appears if at least five
> different people were recorded inside it. That rule is called k-anonymity, and
> five is the k.
>
> Now watch what happens when I lower it.

Drag the slider to 1. The map fills.

> At one, every hexagon appears — including places exactly one person went. That
> one over there is somebody's hotel. That one is somebody's street.
>
> This map is still "anonymous". Nobody's name is on it. But if only one person
> was ever in that hexagon at eight in the morning, and you know who was on this
> course, it is not anonymous at all.
>
> That is why the threshold exists. "Anonymised" is not a property of a dataset.
> It is a property of how many people are hiding in each bucket.

Drag it back up and watch the map empty. Land the trade-off:

> And notice the cost. At a high threshold this map is safe and nearly useless.
> Every organisation publishing "anonymised" data is somewhere on that slider,
> and most of them do not tell you where.

---

## Day 5 — Agency, and teardown

**Objective:** leave people with something to do, and prove the promise.

### The agency steps (15 minutes)

Each daily reveal has ended with one concrete action. Go round the room: what did
people actually change?

Then do the settings audit together, on real phones — location permissions, which
apps have "Always", precise location, resetting the advertising identifier.

**Talking point:**

> You will find apps in that list you had forgotten you installed. Every one of
> them could have produced the map you saw on Tuesday.

### Wipe the data, in front of them (10 minutes)

Do this live. Do not describe it — do it.

Open **Data & teardown**, type `DELETE ALL DATA`, confirm. Show the participant
count drop to zero. Show the audit log recording what was deleted and when.

**Talking point:**

> On Monday I told you this would be deleted at the end of the course. Here it
> is being deleted.
>
> You have no way to verify that from where you are sitting — you are trusting
> me. That is exactly the position you are in with every company holding your
> data, except that they do not do it in front of you, and there is usually no
> log.

Then tell them to delete the app.

### Close

> You cannot opt out of this industry by being careful. The settings help, and
> you should change them. But the useful thing you take away is not a checklist —
> it is that you now know what a week of your movements looks like from the
> outside, and you will not be able to un-know it.

---

## Questions you will be asked

**"Could you tell where I live?"**
Be precise and do not overclaim: *the app deliberately doesn't try to. It notes
where you start and end your day and calls it an anchor. It has no idea whose
address that is, and it never looks it up. A commercial system with a name
attached, or a data broker with other databases, would not have that
restriction.*

**"Is this legal?"**
*Collecting location about identifiable people is regulated. We have consent,
TRG is the responsible entity, there is a retention limit and a deletion route.
The uncomfortable part is that most of what the industry does is also legal —
which is rather the point.*

**"How accurate is it?"**
*Usually within ten to twenty metres outdoors, worse indoors and in the
background. Good enough to know which building, not always which floor.*

**"What if I just turn off location?"**
*Then this app learns nothing, and the reveal is a blank screen. That is a real
option and it works. Notice what else stops working, and decide whether the
trade is worth it — that is the actual decision, not a trick question.*

**"Are you selling this data?"**
*No. It never leaves TRG's server, and it is deleted at the end of the course.
You are right to ask, and you should ask it of every app that has this
permission.*

**"Can I see somebody else's data?"**
*No. The app only ever returns your own — that is enforced on the server, not
just hidden in the interface. I can see everyone's, and I told you that before
you agreed.*

**"You said it doesn't identify me, but that description was obviously me."**
*Both are true, and the gap between them is the lesson. It holds no name, no
address and no account, so by most privacy policies it holds nothing personal.
It still describes exactly one of you. Identification is a property of the whole
picture, not of any single field in it.*

**"Did you scrape TikTok for those posts?"**
*No, and we couldn't have lawfully — TikTok has no public way to search posts by
location, so the only route would be scraping, which breaks their terms. These
come from platforms that publish coordinates openly. Which means you are looking
at a fraction of what actually exists out there, not all of it.*

**"How did you know who I was with? I never told the app that."**
*You didn't, and it never asked. It compared your coordinates with everyone
else's, minute by minute. That is the whole method. Note that you consented and
so did they — but what came out is a fact about the pair of you, and a
relationship can't consent. One tracked phone exposes both people.*

---

## When things go wrong

**Nobody's data is arriving.** Check the server is up (`/health`). Then check
one participant's server address in Settings. If the server is down, switch to
sample data and carry on — say clearly that you have done so.

**One person has almost no data.** Usually background permission was declined,
or their phone is killing the app. Do not treat it as a failure — put their thin
reveal next to a full one. The comparison is a better lesson than either alone.

**A volunteer's trail shows something sensitive.** Close it immediately, without
comment, and move to another volunteer. Do not explain why.

**Somebody is angry about what the app knows.** They are not wrong to be. Do not
defend the app; agree with them, and point out that this one told them in
advance and deletes itself on Friday.

**Nothing works at all.** Run the whole week on sample data. Every teaching point
above survives except the personal reveals. Be honest about the substitution.
