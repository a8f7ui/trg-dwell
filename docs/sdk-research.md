# What real advertising and analytics SDKs actually collect

**Purpose of this document.** The app shows participants two things: a small
amount of data it genuinely collects, and a larger set of categories it only
*illustrates*. This document is the evidence base for the illustrated set. It
exists so that the simulated screens are accurate rather than alarmist, and so
that a facilitator challenged by a sceptical attendee — "come on, apps don't
really do that" — can answer with a specific case and a source.

Everything here is public, documented, and in most cases the subject of
regulatory action or mainstream reporting. Nothing in this document describes
behaviour of *this* app. See [What this app does instead](#what-this-app-does-instead).

Last reviewed: August 2026.

---

## The mechanism people find most surprising

Before the list of data categories, there is one structural fact that does more
teaching work than any individual example:

> **An SDK inherits the permissions of the app it lives inside.**

A third-party SDK bundled into a weather app does not show its own permission
prompt. When somebody taps "Allow" on the weather app's location request, every
SDK inside that app can generally use that grant. The user consented to the
weather app. They have usually never heard of the company actually receiving
the data.

This is why the industry concentrates on apps with a *plausible* reason to ask
for location — weather, navigation, local news, dating, fitness, prayer-time
apps. The permission looks reasonable in context, and the data flows onward to
parties the user never evaluated. Developers are paid to embed these SDKs,
often earning a small amount per user per month for adding a few lines of code.

Two corollaries worth stating in class:

1. **A privacy policy is not the same as a prompt.** Data sharing disclosed on
   page 14 of a policy is legally disclosed and practically invisible.
2. **"We don't sell your data" can be literally true** while the data is
   transferred under a different commercial label, or shared by an embedded
   partner rather than by the app publisher.

---

## The five families of SDK

Grouping them this way helps in teaching, because each family has a different
*stated* reason for existing, and each reaches beyond it.

### 1. Advertising and monetisation

*Examples: Google AdMob / Google Mobile Ads, Meta Audience Network, Unity Ads,
AppLovin, ironSource, Vungle.*

**Stated purpose:** show ads, pay the developer.

**Typically collects:** advertising identifier (IDFA on iOS, GAID on Android),
IP address, device model, OS version, screen dimensions, language, timezone,
coarse location, in-app interactions, and diagnostic data. Google's own
documentation for the Mobile Ads SDK states it collects IP addresses, user
interactions, diagnostic information and device/account identifiers, used for
advertising, analytics and fraud prevention.

### 2. Attribution and measurement

*Examples: AppsFlyer, Adjust, Branch, Kochava, Singular.*

**Stated purpose:** work out which advertisement caused an app install, so ad
spend can be measured.

**Typically collects:** install timestamps, device identifiers (IDFA, GAID,
IDFV), IP address, device model, OS version, language, and click metadata.

**The part worth teaching:** when a stable identifier is unavailable — for
instance after a user declines tracking on iOS — these systems fall back to
**probabilistic attribution**, better known as *device fingerprinting*. This
combines IP address, device model, OS version, screen size, language, timezone
and timing into a signature statistically likely to be unique, without using any
identifier the user can reset.

This is the single most useful thing to demonstrate, because it directly
undercuts the intuition that "I turned off tracking, so I'm fine." The
fingerprinting inputs are the same benign-looking fields this app really does
collect — which is exactly why we collect them.

### 3. Product analytics

*Examples: Firebase Analytics, Amplitude, Mixpanel, Segment.*

**Stated purpose:** understand how people use the app.

**Typically collects:** device model, OS version, screen resolution, IP address,
session duration, and detailed event streams. All of this is personal data under
GDPR's definition, and much of it under US state privacy laws too.

### 4. Session replay and behavioural recording

*Examples: Glassbox, FullStory, UXCam, Smartlook.*

**Stated purpose:** diagnose usability problems.

**What it can capture:** screen recordings and screenshots, taps, scrolls, and
in some cases keyboard entry.

**Documented incident (2019):** TechCrunch reported that a number of popular iOS
apps used session-replay technology to record user interactions without asking
permission. Customers included Abercrombie & Fitch, Hotels.com, Expedia, Air
Canada and Singapore Airlines. Air Canada's app was found to be transmitting
session-replay data containing **exposed passport and credit card numbers**.
None of the reviewed apps disclosed screen recording in their privacy policies,
and the SDK required no special permission from Apple or the user. Apple
subsequently told developers to disclose or remove the code.

This case is worth spending time on, because the failure was not exotic. It was
an ordinary analytics integration that captured more than anyone intended, at
companies with real compliance departments.

### 5. Location intelligence and data brokerage

*Examples: X-Mode Social / Outlogic, InMarket, Placer.ai, Foursquare, Gravy
Analytics / Venntel, SafeGraph.*

**Stated purpose:** "audience measurement", "foot traffic analytics".

**What it is:** the commercial resale of device location histories, matched
against points of interest to determine who visited where.

This is the family the instructor dashboard deliberately imitates, and the
regulatory record here is substantial:

- **X-Mode Social / Outlogic (FTC, January 2024).** The FTC issued its first
  ever order prohibiting the sale of sensitive location data. X-Mode was barred
  from sharing or selling location data revealing visits to sensitive places —
  medical facilities, religious organisations, and other locations supporting
  sensitive inferences. The FTC charged that the company failed to put
  reasonable safeguards on third-party use.
- **InMarket Media (FTC, January 2024).** The FTC alleged InMarket collected
  precise geolocation from **100 million unique devices per year** from 2016
  onward, cross-referencing location histories against points of interest to
  identify consumers who had visited particular places.
- **Kochava (FTC, ongoing).** The FTC is pursuing similar allegations; the
  district court denied Kochava's motion to dismiss.
- **Muslim prayer apps (2020).** Reporting by Motherboard/Vice found that
  location data from Muslim prayer apps with very large user bases reached US
  military contractors via X-Mode. Google later removed a related broker,
  Predicio, from its store. This is the clearest available illustration of why
  "just location data" is not a minor category: a movement trail can reveal
  religion, health, and political association without anyone ever collecting a
  field labelled "religion".

---

## The categories this app illustrates, and why each is credible

| Category | Why it is in the demonstration |
|---|---|
| **Contacts** | Requested by social and messaging SDKs far beyond what the feature needs; a contact list also exposes people who never installed anything. |
| **Photos and media** | Photo libraries carry embedded location and timestamps in EXIF metadata, so photo access can be location access by another route. |
| **Clipboard** | In 2020, researchers Tommy Mysk and Talal Haj Bakry identified roughly 50 apps reading the iOS clipboard on every open. iOS 14 added a visible banner, which exposed the scale of it — TikTok users saw near-constant notifications. Clipboards routinely hold passwords, addresses and one-time codes. |
| **Microphone and sensors** | Motion sensors are readable at high frequency and can support inferences about activity and, in research settings, more. |
| **Installed app list** | The set of apps on a device is a strong behavioural fingerprint, and can imply health status, sexuality, religion and politics. |
| **Cross-app identifiers** | IDFA/GAID are what let separate apps' observations be joined into one profile — the thread that makes everything else cumulative. |
| **Always-on background location** | The core of the data-broker industry, as the FTC actions above document. |
| **Wi-Fi and Bluetooth scanning** | Nearby network identifiers provide indoor positioning where GPS is weak, and are stable enough to act as location proxies. |

Research has also documented apps **circumventing** the Android permission
system through side and covert channels — obtaining data they were refused
(Reardon et al., *50 Ways to Leak Your Data*, USENIX Security 2019). Worth
mentioning as a caution against treating the permission screen as a complete
defence, though it should be presented as documented research rather than as
routine industry practice.

---

## What this app does instead

Stated plainly, because the credibility of the whole exercise depends on it:

- **Every category in the table above is simulated.** The app generates
  realistic-looking values, labels them as simulated on screen, and transmits
  none of them. The backend has nowhere to put them — there are no database
  columns for contacts, photos, clipboard contents, installed apps or audio.
- **What the app really collects** is the benign set: a randomly generated
  participant ID, device model, OS version, screen size, timezone, language,
  battery level, connection type, and timestamped location.
- **That benign set is not chosen arbitrarily.** It is very close to the input
  list for probabilistic attribution described above. The lesson is that the
  "harmless" fields *are* the fingerprint.
- **The app does not attempt identity resolution.** It characterises behaviour —
  visitor or local, the character of an area, the type of activity, the daily
  rhythm — in the manner of a location-intelligence product. It does not look up
  addresses, and does not connect anyone to any outside record.

---

## Teaching notes

Three framings that work better than a list of scary capabilities:

1. **"The permission you gave is not the permission that matters."** The
   inheritance mechanism explains why informed consent at the prompt is
   insufficient, without requiring anyone to believe in bad intent.
2. **"Nobody collected the sensitive fact. They derived it."** No prayer app
   collected a religion field. The FTC's sensitive-location theory exists
   precisely because inference from movement bypasses the categories privacy law
   traditionally protected.
3. **"Confidently wrong is a feature, not a bug."** Profiling systems commit to
   judgements on thin evidence and act on them anyway. The daily reveal in this
   app deliberately surfaces its own uncertainty, so participants can see both
   how much is knowable and how readily an automated system overstates it.

---

## Sources

- [FTC Order Prohibits Data Broker X-Mode Social and Outlogic from Selling Sensitive Location Data](https://www.ftc.gov/news-events/news/press-releases/2024/01/ftc-order-prohibits-data-broker-x-mode-social-outlogic-selling-sensitive-location-data) — Federal Trade Commission, January 2024
- [FTC Cracks Down on Mass Data Collectors: A Closer Look at Avast, X-Mode, and InMarket](https://www.ftc.gov/policy/advocacy-research/tech-at-ftc/2024/03/ftc-cracks-down-mass-data-collectors-closer-look-avast-x-mode-inmarket) — Federal Trade Commission, March 2024
- [Recent Enforcement Actions Signal FTC Focus on Protecting Location Data](https://www.wilmerhale.com/en/insights/blogs/wilmerhale-privacy-and-cybersecurity-law/20240209-recent-enforcement-actions-signal-ftc-focus-on-protecting-location-data) — WilmerHale
- [A view from DC: FTC v. Kochava — License to litigate](https://iapp.org/news/a/a-view-from-dc-ftc-v-kochava-license-to-litigate) — IAPP
- [Many popular iPhone apps secretly record your screen without asking](https://techcrunch.com/2019/02/06/iphone-session-replay-screenshots/) — TechCrunch, February 2019
- [Apple tells app developers to disclose or remove screen recording code](https://techcrunch.com/2019/02/07/apple-glassbox-apps/) — TechCrunch, February 2019
- [Mobile App Session Replay & Its Privacy Impact](https://www.nowsecure.com/blog/2019/02/18/mobile-app-session-replay-its-privacy-impact/) — NowSecure
- [Popular apps like TikTok are snooping on your iPhone clipboard](https://appleinsider.com/articles/20/03/13/popular-apps-like-tiktok-are-snooping-on-your-iphone-clipboard) — AppleInsider, March 2020
- [TikTok To Stop Clipboard Snooping After Apple Privacy Feature Exposes Behavior](https://threatpost.com/tiktok-to-stop-clipboard-snooping-after-apple-privacy-feature-exposes-behavior/156945/) — Threatpost, June 2020
- [US military buys location data from Muslim prayer app](https://9to5mac.com/2020/11/20/us-military-buys-location-data-from-muslim-prayer-app-and-more/) — 9to5Mac, November 2020
- [Google Kicks Location Data Broker That Sold Muslim Prayer App User Data](https://www.vice.com/en/article/google-predicio-ban-muslim-prayer-app/) — Vice
- [App Stores Have Kicked Out Some Location Data Brokers. Good, Now Kick Them All Out.](https://www.eff.org/deeplinks/2021/03/apple-and-google-kicked-two-location-data-brokers-out-their-app-stores-good-now) — Electronic Frontier Foundation
- [Google Play data disclosure — Google Mobile Ads SDK](https://developers.google.com/admob/android/privacy/play-data-disclosure) — Google for Developers
- [About device identifiers](https://support.appsflyer.com/hc/en-us/articles/4408847686161-About-device-identifiers) — AppsFlyer documentation
- [Differences Between Google's Data Safety and Apple's Nutrition Label](https://www.onetrust.com/blog/google-data-safety-vs-apple-nutrition-label/) — OneTrust
- Reardon et al., *50 Ways to Leak Your Data: An Exploration of Apps' Circumvention of the Android Permissions System*, USENIX Security 2019
