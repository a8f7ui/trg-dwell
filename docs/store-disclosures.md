# Store privacy disclosures

Exact answers for Apple's **App Privacy** questionnaire and Google's **Data
safety** form. Both must be completed before you can distribute, including
through TestFlight and Play internal testing.

Fill these in from this document rather than from memory. A disclosure that
under-reports is a policy violation; one that over-reports frightens
participants for no reason. These answers are what the code actually does.

---

## The distinction that governs every answer

Dwell collects two very different things, and only one of them is real.

**Genuinely collected, transmitted, and stored on TRG's server:**

| Data | Detail |
|---|---|
| Precise location | With timestamps, continuously, including in the background |
| A participant ID | Random, generated on the device. Not a name, email or phone number |
| Device model, OS version, screen size | |
| Timezone, language | |
| Battery level, connection type | |

**Displayed but never collected:** contacts, photos, clipboard contents,
microphone, motion sensors, installed-app lists, cross-app advertising
identifiers, nearby Wi-Fi and Bluetooth, and screen recordings.

These appear on screens labelled **SIMULATED**, populated with invented values,
to illustrate what a commercial advertising SDK would take using the same
permissions. **The app does not request permission for any of them, contains no
code that reads them, and the server has no field to store them in.**

**Declare only the first list.** The second is a display feature, not
collection. If a reviewer queries the simulated screens, point them at
`app/src/illustrated.ts`, where every value is generated on the device.

---

## Apple — App Privacy ("nutrition label")

In App Store Connect: **App Privacy → Get Started**.

### Data types to declare

| Category | Type | Purpose | Linked to user? | Used for tracking? |
|---|---|---|---|---|
| Location | **Precise Location** | App Functionality | **Yes** | **No** |
| Identifiers | **User ID** | App Functionality | **Yes** | **No** |
| Diagnostics | **Other Diagnostic Data** | App Functionality | **Yes** | **No** |
| Other Data | **Other Data Types** | App Functionality | **Yes** | **No** |

- **Other Diagnostic Data** covers device model, OS version, screen size,
  battery level and connection type.
- **Other Data Types** covers timezone and language.

### Two answers people get wrong

**"Linked to the user" — answer Yes.** The participant ID is random and holds no
name, but it is persistent and instructors can view a named individual's
movement in the classroom. Treating that as unlinked would be a technicality
Apple would be right to reject, and would be dishonest in a privacy tool.

**"Used for tracking" — answer No.** Apple defines tracking as linking data with
third-party data for advertising, or sharing it with a data broker. Dwell does
neither. Nothing leaves TRG's server. **No App Tracking Transparency prompt is
required**, and adding one would misrepresent what the app does.

### Do NOT declare

Contacts, Photos, Audio, Browsing History, Search History, Advertising Data,
Device ID. None are collected. Declaring them because a screen depicts them
would be inaccurate.

---

## Google — Data safety

In Play Console: **Policy → App content → Data safety**.

### Overview answers

| Question | Answer |
|---|---|
| Does your app collect or share any of the required user data types? | **Yes** |
| Is all of the user data collected by your app encrypted in transit? | **Yes** (HTTPS enforced) |
| Do you provide a way for users to request that their data is deleted? | **Yes** (in-app, immediate) |

### Data types

**Location → Precise location**
- Collected: **Yes** · Shared: **No**
- Processed ephemerally: **No** (it is stored for the course, then deleted)
- Required: **No** — participants can decline and still use the app
- Purpose: **App functionality**

**Personal info → User IDs**
- Collected: **Yes** · Shared: **No**
- Required: **No** · Purpose: **App functionality**

**App info and performance → Other app performance data**
- Collected: **Yes** · Shared: **No**
- Required: **No** · Purpose: **App functionality**
- Covers device model, OS version, screen size, battery level, connection type.

### Answer "No" to everything else

Particularly Contacts, Photos and videos, Audio, Messages, Calendar, Files, and
**Device or other IDs**. That last one matters: Dwell does **not** collect the
Android advertising ID. It generates its own random participant ID, which is
declared above under User IDs.

### Deletion

Play asks for a deletion mechanism. Participants withdraw from inside the app —
Settings → Withdraw — which deletes their data immediately and reports how many
records were removed. Provide TRG's data-protection contact address as the
account-deletion URL.

---

## Store listing copy

Needed even for testing tracks.

**Name:** Dwell: Privacy Lab
**Subtitle (iOS, 30 chars):** See what your phone reveals

**Short description (Android, 80 chars):**
> A privacy course tool that shows you what an app can learn about you.

**Full description:**

> Dwell: Privacy Lab is a teaching tool for a classroom course on privacy and
> security. It is not a consumer app, and it is distributed only to enrolled
> participants.
>
> Most people accept in principle that phones can track them. Very few have seen
> it done with their own data. Dwell closes that gap.
>
> With your explicit consent, the app records your location for the duration of
> the course. Each evening it shows you your own day: where you went, where you
> stopped and for how long, and the conclusions a commercial location-analytics
> product would draw — whether you look like a visitor or a local, the character
> of the areas you spent time in, and the marketing segment you would be sorted
> into. It also tells you where those conclusions are shaky, and gives you one
> concrete thing you could change.
>
> WHAT IT COLLECTS
> Your location with timestamps, your device model and operating system version,
> screen size, timezone, language, battery level and connection type. A random
> participant number is generated on your phone. Your name, email address and
> phone number are never collected.
>
> WHAT IT DOES NOT COLLECT
> Some screens illustrate what a commercial advertising SDK would also take —
> contacts, photos, clipboard, installed apps, cross-app identifiers. Those
> screens are clearly labelled as simulated and use invented values. The app
> does not read any of that data and does not ask permission to.
>
> WHY IT RUNS IN THE BACKGROUND
> Because the lesson is about what happens when you are not watching. An app
> that only collected while you had it open could not demonstrate the thing this
> course exists to teach.
>
> YOUR CONTROL
> Consent is explicit and given before anything is collected. A visible
> indicator shows whenever collection is running. You can pause at any time, or
> withdraw — which stops collection and deletes everything about you from the
> server, telling you exactly how many records were removed. All data is deleted
> at the end of the course.
>
> Dwell is open source. Every claim above can be checked against the code:
> https://github.com/a8f7ui/trg-dwell

**Category:** Education
**Content rating:** Everyone / 4+
**Contains ads:** No · **In-app purchases:** No

---

## Privacy policy

Both stores require a public privacy-policy URL.

The in-app consent screen (`app/src/screens/ConsentScreen.tsx`) already contains
the substance in plain language. Publish that text at a stable TRG address and
add:

- TRG's legal entity name and postal address, as data controller.
- A contact address for privacy questions and data requests.
- The retention period: duration of the course, then deletion.
- The lawful basis: consent.
- The rights available to participants, and how to exercise them.

Have whoever gave institutional sign-off check this page before submission. It
is the one document here with legal weight.
