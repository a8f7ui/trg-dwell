# Getting Dwell onto attendee phones

A guided walkthrough. Assumes you have an Apple Developer account with TestFlight
already set up, and that the server from `docs/hosting.md` is online.

---

## What this step is, in plain language

The code in `app/` is not yet an app. It is instructions for building one. Two
real files have to be produced — one for iPhones, one for Android phones — and
then handed to people in a way their phones will accept.

You do **not** need a Mac. Expo runs a build service called **EAS** that compiles
both versions on their machines and gives you back finished files.

Phones refuse to install apps from arbitrary websites, so "handing it out" means
going through Apple's and Google's testing channels:

- **iPhone → TestFlight.** Apple's official channel for pre-release apps.
  Participants install TestFlight, tap your link, and get Dwell.
- **Android → Google Play internal testing.** Same idea. Participants tap a link
  and install from the Play Store as normal.

Both are designed for exactly this: a known group, not the general public.

**We are deliberately not doing a public App Store listing.** An app that only
makes sense to people on one course, and asks for always-on location, is a poor
fit for Apple's "useful to the general public" rules. It would invite the hardest
possible review for no benefit. Attendees do not care whether they install from a
public listing or a TestFlight link.

---

## Timeline, working back from mid-September

The one thing that can genuinely delay you is Apple's Beta App Review, which in
2026 is taking **two to seven days**, occasionally longer. Everything else you
control. This schedule leaves room for one rejection and resubmission.

| When | What |
|---|---|
| **Now** | Put the server online (`docs/hosting.md`). Point the app at it. First test build, installed on your own phone. |
| **~4 weeks out** | Team dry-run: three or four colleagues carry it for two full days. This is where real-world problems appear. |
| **~3 weeks out** | Submit for TestFlight external review. Set up Play internal testing. |
| **~2 weeks out** | Send install links to participants and ask them to install **before** they arrive. |
| **~1 week out** | Buffer. Chase anyone who has not installed. |
| **Course week** | Run it. |

**The two-day team dry-run is not optional.** Background location behaves
differently on real phones than anywhere else: battery optimisation, Do Not
Disturb, phones that aggressively kill background apps. You want to discover that
on a colleague's phone, not on thirty attendees' phones on day one.

---

## Step 1 — Point the app at your server

Before any build, tell the app where to send data. In `app/src/config.ts`:

```ts
export const DEFAULT_SERVER_URL = 'https://YOURNAME.pythonanywhere.com';
```

Get this right now. Participants can change it in Settings, but nobody wants to
talk thirty people through typing a URL.

---

## Step 2 — Set up EAS

On your own computer, in the `app` folder:

```bash
npm install --global eas-cli
eas login
eas init
```

`eas init` links this project to your Expo account and writes a project ID into
`app.json`. Commit that change.

---

## Step 3 — Confirm the app's permanent identity

In `app/app.json`, check:

```json
"bundleIdentifier": "org.trg.dwell",
"package": "org.trg.dwell"
```

**This cannot be changed after your first submission.** It should be a domain TRG
controls, reversed. If TRG's domain is `trg.com`, this should be `com.trg.dwell`.
Fix it now if it is wrong.

---

## Step 4 — Build a test version and try it yourself

```bash
eas build --profile preview --platform all
```

This takes 15–30 minutes on the free plan. You get two download links.

- **Android**: download the `.apk` straight onto a phone and open it. Android
  will warn about installing from an unknown source; allow it.
- **iPhone**: the preview build needs your device registered. Simpler to go
  straight to TestFlight (Step 5) for iOS.

Then walk the whole flow yourself: consent, the three permission prompts, leave
the phone alone for a few hours, and check the points arrive on the dashboard.

**What to check specifically:**

- The "Collection is ON" notice stays visible.
- Points keep arriving with the app fully closed. This is the whole premise —
  verify it rather than assuming.
- The evening notification arrives, and says nothing specific.
- Withdraw works, and tells you how many points it deleted.

---

## Step 5 — TestFlight (iPhone)

```bash
eas build --profile production --platform ios
eas submit --platform ios --latest
```

Then in **App Store Connect** → your app → **TestFlight**:

1. Add a **Test Information** section (Apple requires it before external testing).
2. Create an **External** testing group, e.g. "September course".
3. Enable the **public link**, and share that link with participants.
4. Submit for Beta App Review.

### What to write in the review notes

This matters more than anything else in this document. A reviewer seeing
always-on location on an unfamiliar app will reject it unless the reason is
immediately clear. Paste something like this:

> Dwell: Privacy Lab is a privacy-education tool used in a week-long classroom
> course run by TRG. It is not a consumer product and is distributed only to
> enrolled course participants.
>
> The app demonstrates to participants what an ordinary app can learn about them
> from their own phone. It records the participant's location and shows them,
> each evening, the inferences a commercial location-analytics product would
> draw from it — where they appear to have stayed, the character of the areas
> they visited, and the marketing segment they would be placed in.
>
> Background location is required because the entire educational point is to
> demonstrate what is collected when the user is *not* looking at the app.
> Foreground-only collection cannot demonstrate this.
>
> Participants give explicit written consent on an unmissable screen before any
> collection begins. The consent screen states plainly that collection continues
> when the app is closed, and that course instructors can see participant
> movement. The agree button is disabled until the participant has scrolled
> through the full text. Participants can pause at any time, or withdraw — which
> stops collection and deletes all their data from the server, reporting exactly
> how many records were removed.
>
> Data is retained only for the duration of the course and then deleted. No data
> is sold, shared, or transmitted to any third party. The app contains no
> advertising, analytics or crash-reporting SDKs of any kind.
>
> The complete source code is public at
> https://github.com/a8f7ui/trg-dwell so that every claim above can be verified.
>
> Note: several screens display contacts, photos, clipboard contents and similar
> data. These are clearly labelled SIMULATED and use invented values to
> illustrate what a commercial SDK would take. The app does not read any of these
> and requests no permission for them.
>
> To test: [demo server address], sign in is not required for participants.

Give the reviewer a working server address. If they cannot get past the first
screen, they will reject it.

---

## Step 6 — Google Play internal testing (Android)

```bash
eas build --profile production --platform android
eas submit --platform android --latest
```

In **Play Console** → **Testing → Internal testing**:

1. Create a tester list, paste in participants' Gmail addresses (up to 100).
2. Upload the build to the internal track.
3. Copy the opt-in link and share it.

Internal testing has no review wait — builds are usually available within
minutes. You will need to complete the **Data safety** form first; the exact
answers are in `docs/store-disclosures.md`.

**Simpler alternative:** skip Play entirely and send Android users the `.apk`
from Step 4. Free, instant, no Play account needed. The trade-off is that they
must allow installation from an unknown source, and updates are manual.

---

## Step 7 — What you send participants

Keep it short. Something like:

> Before the course, please install **Dwell: Privacy Lab** on your phone.
>
> **iPhone:** install TestFlight from the App Store, then open [link].
> **Android:** open [link] and install from the Play Store.
>
> When you first open it you will see a consent screen explaining exactly what
> the app collects. Please read it — it is part of the course. It will ask for
> location permission, including in the background. That is deliberate and we
> will explain why on day one.
>
> Taking part is voluntary. You can stop and delete your data at any time from
> inside the app, and you can follow the whole course without installing
> anything.
>
> Please install it **before** you arrive and leave it running.

Say "leave it running" explicitly. The reveals need a day or two of data before
they are interesting.

---

## Things that will actually go wrong

**"My data isn't showing up."** Almost always the server address. Settings →
Course server → Save and test.

**Android kills the app overnight.** Some manufacturers — Samsung, Xiaomi,
OnePlus especially — aggressively kill background apps. Affected participants
should exclude Dwell from battery optimisation (Settings → Apps → Dwell →
Battery → Unrestricted). Worth mentioning on day one; it is itself a teaching
point about how much the platform controls what apps can do.

**Someone declined background location.** They will get thin reveals. Not a
problem — it makes an excellent live comparison against someone who allowed it.

**Someone withdraws mid-course.** Expected and fine. Do not ask them why. The
dashboard participant count will drop by one.

**TestFlight builds expire after 90 days.** Irrelevant for a one-week course, but
worth knowing if you run the course again — you will need a fresh build.

---

## After the course

1. Wipe the data (dashboard → **Data & teardown**, then delete the database file
   as described in `docs/hosting.md`).
2. Expire the TestFlight build so nobody can install a version pointing at a
   server that no longer exists.
3. Remove the Play internal testing track.

Participants who keep the app will find it cannot reach the server. That is
harmless, but telling them to delete it at the end is tidier — and a reasonable
last teaching moment about what happens to apps you stop using.
