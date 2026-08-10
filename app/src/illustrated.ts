/**
 * The categories this app SHOWS but never TAKES.
 *
 * Every value produced here is invented on the phone, for display only. None of
 * it is read from the device and none of it is transmitted — there is no code
 * in this app that reads contacts, photos, the clipboard, the microphone, the
 * installed-app list or any cross-app identifier, and the server has no column
 * to store them in.
 *
 * The point of showing them is that a real advertising or analytics SDK would
 * reach for exactly these, using a permission the participant granted for some
 * entirely different reason. Each entry below is grounded in a documented case;
 * see `docs/sdk-research.md` for sources.
 */

export type IllustratedCategory = {
  id: string;
  title: string;
  /** The reassuring line an app typically gives when asking. */
  statedReason: string;
  /** What the permission actually makes possible. */
  actuallyEnables: string;
  /** A real, documented case. */
  realCase: string;
  /** Invented values, shown to make the abstract concrete. */
  sample: string[];
};

/** Small deterministic generator, so a participant sees stable values rather
 *  than a different fiction every time they open the screen. */
function seeded(seed: string) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FIRST = ['Priya', 'Daniel', 'Aisha', 'Marcus', 'Lena', 'Tomás', 'Grace',
  'Noor', 'Eli', 'Ruth', 'Sam', 'Ivan', 'Clara', 'Femi', 'Ana'];
const LAST = ['Whitlock', 'Osei', 'Barros', 'Nakamura', 'Halloran', 'Vance',
  'Petrov', 'Adeyemi', 'Lindqvist', 'Moreau', 'Bhatt', 'Okafor'];
const APPS = ['Banking (Halifax)', 'Grindr', 'Hinge', 'Calm', 'Strava',
  'Clue Period Tracker', 'AA Meeting Finder', 'Duolingo', 'Robinhood',
  'Signal', 'Headspace', 'MyFitnessPal', 'Bumble', 'Al-Quran', 'Wine-Searcher'];

export function buildIllustrated(seedKey: string): IllustratedCategory[] {
  const rnd = seeded(seedKey || 'demo');
  const pick = <T,>(arr: T[]) => arr[Math.floor(rnd() * arr.length)];
  const name = () => `${pick(FIRST)} ${pick(LAST)}`;
  const phone = () =>
    `+1 512 ${String(100 + Math.floor(rnd() * 899))} ${String(1000 + Math.floor(rnd() * 8999))}`;

  return [
    {
      id: 'contacts',
      title: 'Your contacts',
      statedReason: '“Find your friends who are already here!”',
      actuallyEnables:
        'A complete copy of every name, number and email in your phone — including ' +
        'people who never installed anything and never agreed to anything.',
      realCase:
        'Social and messaging SDKs routinely request contact access far beyond what ' +
        'the advertised feature needs. Your address book is also how a company builds ' +
        'a picture of people who are not its users at all.',
      sample: [
        `${name()} — ${phone()}`,
        `${name()} — ${phone()}`,
        `${name()} — ${phone()}`,
        `Dr ${name()} (Dentist) — ${phone()}`,
        `${name()} — work — ${phone()}`,
        `… and ${300 + Math.floor(rnd() * 500)} more`,
      ],
    },
    {
      id: 'photos',
      title: 'Your photo library',
      statedReason: '“Set a profile picture.”',
      actuallyEnables:
        'Access to every photo — and to the location and timestamp quietly embedded ' +
        'in each one. Photo access is location access by another route.',
      realCase:
        'Photos carry EXIF metadata including precise coordinates and the exact ' +
        'second they were taken. An app granted your library can reconstruct years ' +
        'of your movements without ever asking for location permission.',
      sample: [
        `IMG_${4000 + Math.floor(rnd() * 900)}.HEIC — 30.2691, −97.7402 — 14 Jun, 21:04`,
        `IMG_${4000 + Math.floor(rnd() * 900)}.HEIC — 30.2634, −97.7458 — 15 Jun, 08:47`,
        `IMG_${4000 + Math.floor(rnd() * 900)}.HEIC — 51.5074, −0.1278 — 2 Apr, 19:22`,
        `Screenshot — banking app — 11 May, 09:15`,
        `… ${2000 + Math.floor(rnd() * 6000)} photos, ${60 + Math.floor(rnd() * 35)}% with coordinates`,
      ],
    },
    {
      id: 'clipboard',
      title: 'Your clipboard',
      statedReason: 'Nothing. No permission is required, so you are never asked.',
      actuallyEnables:
        'Reading whatever you last copied. That is often a password, a bank ' +
        'account number, an address, or a two-factor code.',
      realCase:
        'In 2020 researchers found roughly 50 popular apps reading the iOS clipboard ' +
        'every time they opened. It only became visible when iOS 14 added a banner — ' +
        'users then saw a near-constant stream of notifications from apps like TikTok.',
      sample: [
        `"${['Tr0ub4dor&3', 'GB29 NWBK 6016 1331 9268 19', '847 392', '14 Blackthorn Rise'][Math.floor(rnd() * 4)]}"`,
        'Read 41 times today',
        'No permission prompt was ever shown',
      ],
    },
    {
      id: 'installed_apps',
      title: 'What else you have installed',
      statedReason: '“Improving your experience.”',
      actuallyEnables:
        'The full list of apps on your phone — one of the strongest behavioural ' +
        'fingerprints there is, and a direct route to inferences about health, ' +
        'sexuality, religion, finances and politics.',
      realCase:
        'Nobody has to collect a field marked "religion" or "health condition". The ' +
        'set of apps you have installed implies them, and implication is not covered ' +
        'by the categories privacy law traditionally protects.',
      sample: (() => {
        const chosen = new Set<string>();
        while (chosen.size < 6) chosen.add(pick(APPS));
        return [...chosen, `… and ${40 + Math.floor(rnd() * 80)} more`];
      })(),
    },
    {
      id: 'identifiers',
      title: 'Your cross-app identifier',
      statedReason: '“Personalised ads.”',
      actuallyEnables:
        'Joining what you do in this app to what you do in every other app that ' +
        'sees the same identifier. This is the thread that makes everything else ' +
        'cumulative rather than isolated.',
      realCase:
        'This identifier is why a profile builds over months. Resetting it — iOS: ' +
        'Settings → Privacy → Tracking; Android: Settings → Privacy → Ads — breaks ' +
        'the thread and splits your history into disconnected fragments.',
      sample: [
        `IDFA/GAID: ${[...Array(8)].map(() => Math.floor(rnd() * 16).toString(16)).join('')}-` +
          `${[...Array(4)].map(() => Math.floor(rnd() * 16).toString(16)).join('')}-` +
          `${[...Array(12)].map(() => Math.floor(rnd() * 16).toString(16)).join('')}`,
        `Seen by ${8 + Math.floor(rnd() * 20)} other apps on this device`,
        `Linked profile age: ${5 + Math.floor(rnd() * 30)} months`,
      ],
    },
    {
      id: 'microphone',
      title: 'Microphone and motion sensors',
      statedReason: '“Voice search.” / “Step counting.”',
      actuallyEnables:
        'The microphone needs a prompt. The motion sensors mostly do not, and they ' +
        'can be sampled continuously — enough to tell walking from driving from ' +
        'sitting, and to know when you picked your phone up.',
      realCase:
        'Sensor access is the quiet one. It rarely feels like a privacy decision ' +
        'when granted, and it is rarely presented as one.',
      sample: [
        'Motion: walking (6.2 km/h), 09:14–09:31',
        'Motion: vehicle (48 km/h), 17:42–18:05',
        'Device picked up 87 times today',
        'Microphone: not accessed (would require a prompt)',
      ],
    },
    {
      id: 'wifi',
      title: 'Nearby Wi-Fi and Bluetooth',
      statedReason: '“Better location accuracy.”',
      actuallyEnables:
        'A list of the networks and devices around you. Network identifiers are ' +
        'fixed to physical places, so they work as a location signal indoors where ' +
        'GPS fails — and they reveal who and what is near you.',
      realCase:
        'Nearby-network scanning positions you inside a specific building, and ' +
        'sometimes a specific floor, which satellite positioning cannot do.',
      sample: [
        'BT_Hotel_Guest — −52 dBm',
        'SKY9F2C1 — −71 dBm',
        `${pick(FIRST)}’s AirPods — −44 dBm`,
        'ConferenceCentre-AV — −38 dBm',
      ],
    },
    {
      id: 'session_replay',
      title: 'A recording of your screen',
      statedReason: '“Helping us improve the app.”',
      actuallyEnables:
        'Recording what appears on screen and what you tap, sometimes including ' +
        'what you type.',
      realCase:
        'In 2019 a number of major apps were found using session-replay technology ' +
        'without asking. Air Canada’s app was transmitting recordings containing ' +
        'exposed passport and credit card numbers. None of the apps disclosed it, ' +
        'and no permission was required. Apple then told developers to disclose it ' +
        'or remove it.',
      sample: [
        'Session 14:22:07 — 3 min 41 s recorded',
        'Fields captured: 12 (2 marked sensitive, 0 masked)',
        'Taps: 68 · Scrolls: 31 · Keyboard entries: 4',
      ],
    },
  ];
}
