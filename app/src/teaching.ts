/**
 * The narration shown alongside each real permission request.
 *
 * The contrast is the lesson. For every permission this app genuinely asks for,
 * a participant sees three things side by side:
 *
 *   1. what a normal app's dialog looks like at this moment
 *   2. the innocuous reason apps usually give
 *   3. what the permission actually enables
 *
 * This app asks honestly. Setting the honest version next to the usual version
 * is what makes the usual version visible — most people have never compared
 * them, because they have never seen an honest one.
 */

export type PermissionLesson = {
  id: string;
  permission: string;
  /** What a typical app's prompt says. */
  typicalDialog: string;
  /** The reason a typical app gives, in its own words. */
  typicalReason: string;
  /** What granting it actually allows. */
  reality: string;
  /** What this app says instead. */
  ourDialog: string;
  /** The thing worth pausing on. */
  punchline: string;
};

export const PERMISSION_LESSONS: PermissionLesson[] = [
  {
    id: 'location_foreground',
    permission: 'Location — while using the app',
    typicalDialog: '“Allow WeatherNow to use your location? Allow Once / While Using the App / Don’t Allow”',
    typicalReason: '“So we can show you the forecast where you are.”',
    reality:
      'A precise position, accurate to a few metres, every time the app is open. ' +
      'Not the city. The building. And every advertising or analytics SDK bundled ' +
      'inside that app inherits the same access, without a prompt of its own — you ' +
      'agreed with the weather app, not with them.',
    ourDialog:
      'This course app records where you go so it can show you, each evening, what ' +
      'an app can work out about you.',
    punchline:
      'The prompt names one app. The permission is granted to everything inside it.',
  },
  {
    id: 'location_background',
    permission: 'Location — always, including when closed',
    typicalDialog:
      '“WeatherNow has been using your location in the background. Keep Allowing? Change to Only While Using”',
    typicalReason: '“For weather alerts in your area.”',
    reality:
      'Continuous recording of everywhere you go, whether or not you ever open the ' +
      'app again. Over a week this produces where you sleep, where you work, who ' +
      'you spend evenings near, and any clinic, place of worship or meeting you ' +
      'attend. This is the permission the location-data industry is built on.',
    ourDialog:
      'This course app keeps recording your location even when it is closed. That is ' +
      'the point of the exercise. Your instructors can see this data, including your ' +
      'live position.',
    punchline:
      'Nobody has to collect a field marked “religion” or “health”. Where you go ' +
      'implies them, and implication is not what privacy law was written to cover.',
  },
  {
    id: 'notifications',
    permission: 'Notifications',
    typicalDialog: '“WeatherNow would like to send you notifications. Allow / Don’t Allow”',
    typicalReason: '“Important updates.”',
    reality:
      'A channel straight to your lock screen — and, for many apps, a way to tell ' +
      'when you are awake, when you look at your phone, and how reliably you respond. ' +
      'Notification content is also visible to anyone standing near you.',
    ourDialog:
      'We will send one notification each evening telling you your daily summary is ' +
      'ready. It will never contain any specifics — no place names, no map — because ' +
      'a lock screen is a public surface.',
    punchline:
      'Notice what our notification deliberately leaves out, and ask why other apps ' +
      'put your name, your address, or your bank balance on your lock screen.',
  },
];

/**
 * The "two layers at once" framing, shown once during the teaching flow.
 * The benign layer is real and watchable live; the invasive layer is illustrated.
 * Presenting them together is the honest version of the iceberg.
 */
export const TWO_LAYERS = {
  title: 'Two things are true at once',
  above:
    'Everything above the line is really happening on your phone right now. You can ' +
    'watch it accumulate, and you can check the code that does it.',
  below:
    'Everything below the line is what a commercial SDK would also be taking, using ' +
    'the very same permissions you just granted. This app does not take any of it. ' +
    'It shows you invented values so the category stops being abstract.',
  closing:
    'The dishonest version of this demonstration would fake the top half for effect. ' +
    'The dishonest version of a real app fakes the bottom half by never mentioning it.',
};
