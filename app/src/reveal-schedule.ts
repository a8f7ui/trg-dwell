/**
 * When each evening reveal should fire, and what it should say.
 *
 * Separated from `notifications.ts` because that file talks to the operating
 * system the moment it is imported, and this arithmetic — which day is which,
 * what happens at the end of the course, what the clocks changing does — is
 * where the mistakes actually live. Keeping it here means it can be tested on
 * a laptop rather than only discovered on somebody's phone during a course.
 *
 * See `tools/reveal_schedule_test.mjs`.
 */

/**
 * When the evening reveal fires, in the participant's local time.
 *
 * Defined here rather than in `config.ts`, which re-exports it, so that this
 * module depends on nothing at all and can be compiled and run on its own.
 */
export const REVEAL_HOUR = 20;
export const REVEAL_MINUTE = 30;

/** Teasers, chosen by how far into the course we are. None names a place. */
export const TEASERS = [
  'Day 1: I have started building a picture of you. Tap to see what I have so far.',
  'Day 2: based on where you have been, I am starting to guess your routine. Tap to see.',
  'Day 3: based on where you have been today, I could infer where you have been ' +
    'staying, your daily routine, and what you seem to be doing. Tap to see what an ' +
    'app would know about you.',
  'Day 4: today mostly confirmed what I already suspected. Tap to see how confident ' +
    'I have become.',
  'Day 5: I have a week of your movements now. Tap to see the whole picture at once.',
];

/** How many evenings the course runs for. */
export const COURSE_DAYS = TEASERS.length;

export function teaserFor(dayNumber: number): string {
  return TEASERS[Math.min(Math.max(dayNumber - 1, 0), TEASERS.length - 1)];
}

/**
 * The moment day `dayNumber` of a course that began on `startedAt` should fire.
 *
 * Built from local calendar fields — year, month, date — rather than by adding
 * twenty-four hours repeatedly. The difference shows up when the clocks change
 * mid-course: adding milliseconds drags the reveal to 19:30 or 21:30, either
 * side of the evening session it is supposed to land in. Constructing a local
 * date asks the platform for "20:30 on that day", which is what was meant.
 *
 * Day 1 is the day the participant agreed to take part, not the day the course
 * opened — somebody who joins on Wednesday should get "Day 1" on Wednesday.
 */
export function revealTime(startedAt: Date, dayNumber: number): Date {
  return new Date(
    startedAt.getFullYear(),
    startedAt.getMonth(),
    startedAt.getDate() + (dayNumber - 1),
    REVEAL_HOUR,
    REVEAL_MINUTE,
    0,
    0,
  );
}

export type Reveal = { dayNumber: number; at: Date };

/**
 * Which evenings of the course are still ahead.
 *
 * Somebody who installs the app at 21:00 on the first day has already missed
 * that evening's reveal; scheduling it would either fire at once or be dropped,
 * and neither is the intended experience. They start at day 2.
 *
 * After the last day the list is empty, which is the intended end: the app
 * stops talking to somebody when the course they agreed to is over, rather than
 * following them home for weeks.
 */
export function remainingReveals(
  startedAt: Date,
  now: Date = new Date(),
  courseDays: number = COURSE_DAYS,
): Reveal[] {
  const out: Reveal[] = [];
  for (let day = 1; day <= courseDays; day++) {
    const at = revealTime(startedAt, day);
    if (at.getTime() > now.getTime()) out.push({ dayNumber: day, at });
  }
  return out;
}
