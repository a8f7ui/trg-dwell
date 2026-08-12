/**
 * The evening notification lands on the right evening, saying the right thing.
 *
 *     node tools/reveal_schedule_test.mjs
 *
 * The fault being guarded against
 * -------------------------------
 * The app used to schedule one repeating daily notification, created with the
 * day-1 teaser. Every evening for the rest of the week it therefore said
 * "Day 1: I have started building a picture of you" — while the picture grew.
 * The one part of the course designed to make accumulation visible was the part
 * that concealed it.
 *
 * What is checked here is the arithmetic: which evenings are scheduled, in what
 * order, with which words, and what the clocks changing does to them. What is
 * not checked here is whether a real handset delivers them — no test on a
 * laptop can tell you that, and `docs/device-checklist.md` exists because of it.
 *
 * Runs under plain Node with no test framework, because adding one to a repo
 * whose audience cannot be assumed to have npm working is a poor trade.
 */

import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const APP = join(ROOT, 'app');

let failures = 0;

function check(name, got, expected) {
  const same = JSON.stringify(got) === JSON.stringify(expected);
  if (same) {
    console.log(`  PASS  ${name}`);
  } else {
    console.log(`  FAIL  ${name}`);
    console.log(`          expected ${JSON.stringify(expected)}`);
    console.log(`          got      ${JSON.stringify(got)}`);
    failures++;
  }
}

/** Compile the two files under test to plain JavaScript and import them. */
async function load() {
  const out = mkdtempSync(join(tmpdir(), 'dwell-reveal-'));
  const tsc = join(APP, 'node_modules', '.bin', 'tsc');
  try {
    // Run from the output directory, not from app/: naming files on the command
    // line while a tsconfig.json sits next to them is an error, and the point
    // here is to compile these two files alone.
    execFileSync(
      tsc,
      [
        join(APP, 'src', 'reveal-schedule.ts'),
        '--outDir', out,
        '--rootDir', join(APP, 'src'),
        '--module', 'es2022',
        '--target', 'es2022',
        '--moduleResolution', 'bundler',
        '--skipLibCheck',
      ],
      { cwd: out, stdio: 'pipe' },
    );
  } catch (err) {
    console.log('\n  Could not compile the schedule module:\n');
    console.log(String(err.stdout || err.message));
    process.exit(1);
  }
  const mod = await import(join(out, 'reveal-schedule.js'));
  return { mod, cleanup: () => rmSync(out, { recursive: true, force: true }) };
}

/** "2026-09-15 20:30" in whatever timezone this process is running in. */
function localMoment(y, m, d, hh = 0, mm = 0) {
  return new Date(y, m - 1, d, hh, mm, 0, 0);
}

function describe(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/**
 * The next day in the coming year on which this machine's clocks change, or
 * null if they do not. Found by walking days and watching the UTC offset.
 */
function nextClockChange() {
  const start = new Date();
  let previous = new Date(start.getFullYear(), start.getMonth(), start.getDate(), 12)
    .getTimezoneOffset();
  for (let n = 1; n <= 400; n++) {
    const day = new Date(start.getFullYear(), start.getMonth(),
                         start.getDate() + n, 12);
    const offset = day.getTimezoneOffset();
    if (offset !== previous) return day;
    previous = offset;
  }
  return null;
}

const { mod, cleanup } = await load();
const { remainingReveals, revealTime, teaserFor, COURSE_DAYS } = mod;

console.log('\n  The evening reveal lands on the right evening\n');

try {
  // --- a participant who joins on the morning of day 1 ----------------------
  const joined = localMoment(2026, 9, 14, 9, 15);
  let week = remainingReveals(joined, joined);

  check('a full course is five evenings', week.length, COURSE_DAYS);
  check(
    'one evening per day, all at 20:30 local',
    week.map((r) => describe(r.at)),
    ['2026-09-14 20:30', '2026-09-15 20:30', '2026-09-16 20:30',
     '2026-09-17 20:30', '2026-09-18 20:30'],
  );
  check('the day numbers run 1 to 5', week.map((r) => r.dayNumber), [1, 2, 3, 4, 5]);

  // The escalation is the whole point of the teasers, so check the ends of it
  // rather than trusting that an index worked.
  check('the first evening says day 1', teaserFor(week[0].dayNumber).slice(0, 6), 'Day 1:');
  check('the last evening says day 5', teaserFor(week[4].dayNumber).slice(0, 6), 'Day 5:');
  check(
    'the five evenings say five different things',
    new Set(week.map((r) => teaserFor(r.dayNumber))).size,
    5,
  );

  // --- somebody who installs it after that evening's reveal has passed ------
  const lateJoin = localMoment(2026, 9, 14, 21, 40);
  week = remainingReveals(lateJoin, lateJoin);
  check('installing after 20:30 skips that evening', week.length, COURSE_DAYS - 1);
  check('and starts at day 2', week[0].dayNumber, 2);
  check(
    'the skipped evening is not scheduled in the past',
    week.every((r) => r.at.getTime() > lateJoin.getTime()),
    true,
  );

  // --- the middle of the course --------------------------------------------
  const midweek = localMoment(2026, 9, 16, 14, 0);
  week = remainingReveals(joined, midweek);
  check('mid-course, only the evenings still ahead are scheduled',
        week.map((r) => r.dayNumber), [3, 4, 5]);

  // --- the end -------------------------------------------------------------
  const afterwards = localMoment(2026, 9, 19, 9, 0);
  check('once the course is over, nothing more is scheduled',
        remainingReveals(joined, afterwards).length, 0);
  const lastEvening = localMoment(2026, 9, 18, 21, 0);
  check('the app stops the evening the course ends, not weeks later',
        remainingReveals(joined, lastEvening).length, 0);

  // --- daylight saving ------------------------------------------------------
  // A course spanning the change. Adding 24 hours repeatedly would drag the
  // reveal to 19:30 or 21:30 — either side of the evening session — which is
  // the mistake this is here to catch.
  //
  // The window is found rather than hard-coded, because the clocks change on
  // different dates in different countries and a fixed date would quietly test
  // nothing on most machines. A check that skips itself by accident reads as a
  // clean run, which is worse than having no check at all.
  const change = nextClockChange();
  if (change) {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    // Start the course two days before the change, so it falls mid-week.
    const start = new Date(change.getFullYear(), change.getMonth(),
                           change.getDate() - 2, 9, 0);
    const across = remainingReveals(start, start);
    check(`every evening is 20:30 local across the ${zone} clock change ` +
          `(${describe(change).slice(0, 10)})`,
          across.map((r) => describe(r.at).slice(11)),
          ['20:30', '20:30', '20:30', '20:30', '20:30']);
    check('the days still run consecutively across it',
          across.map((r) => r.at.getDate()),
          [0, 1, 2, 3, 4].map((n) =>
            new Date(start.getFullYear(), start.getMonth(),
                     start.getDate() + n).getDate()));
    // The night itself is 23 or 25 hours long, never 24 — that difference is
    // exactly what naive millisecond arithmetic gets wrong.
    // across[2] is the transition day itself, so the interval from the evening
    // before it to that evening is the one containing the change.
    const gap = Math.round((across[2].at - across[1].at) / 3_600_000);
    check('the night the clocks change is not 24 hours long, and still lands at 20:30',
          gap !== 24 && (gap === 23 || gap === 25), true);
  } else {
    console.log('  ----  daylight saving: this machine\'s timezone ' +
                `(${Intl.DateTimeFormat().resolvedOptions().timeZone}) does not ` +
                'observe it, so there is nothing to check here. Re-run as ' +
                '`TZ=America/Chicago node tools/reveal_schedule_test.mjs` to ' +
                'check that path.');
  }

  // --- teaser bounds --------------------------------------------------------
  check('a day number below the range does not fall off the start',
        teaserFor(0).slice(0, 6), 'Day 1:');
  check('a day number past the end does not fall off the end',
        teaserFor(99).slice(0, 6), 'Day 5:');

  // --- day 1 is the participant's first day, not the course's ---------------
  const joinedWednesday = localMoment(2026, 9, 16, 8, 0);
  const theirs = remainingReveals(joinedWednesday, joinedWednesday);
  check('somebody who joins on Wednesday gets day 1 on Wednesday',
        describe(theirs[0].at), '2026-09-16 20:30');
  check('and their day 1 teaser is the day 1 teaser',
        teaserFor(theirs[0].dayNumber).slice(0, 6), 'Day 1:');

  check('revealTime and remainingReveals agree',
        describe(revealTime(joined, 3)), '2026-09-16 20:30');
} finally {
  cleanup();
}

console.log('');
if (failures) {
  console.log(`  ${failures} check(s) FAILED\n`);
  process.exit(1);
}
console.log('  All reveal-schedule checks passed.\n');
