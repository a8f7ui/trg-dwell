/**
 * The nine questions give the right answers.
 *
 *     node tools/status_report_test.mjs
 *
 * The status screen exists so that an instructor standing next to somebody at a
 * break can find out, in under a minute, which of nine things is wrong. Its
 * value is entirely in whether it says the right thing — a screen that reports
 * "everything is working" while nothing has been uploaded since Tuesday is
 * worse than no screen, because it stops the question being asked again.
 *
 * So this drives the judgements directly: a healthy phone, a phone with no
 * permission, a phone collecting but not uploading, a phone whose uploads work
 * but whose data is not arriving, an offline phone, a paused phone.
 *
 * It also checks the thing that is easy to lose sight of: no coordinate ever
 * appears in any answer.
 */

import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const APP = join(ROOT, 'app');

let failures = 0;

function check(name, got, expected) {
  if (JSON.stringify(got) === JSON.stringify(expected)) {
    console.log(`  PASS  ${name}`);
  } else {
    console.log(`  FAIL  ${name}`);
    console.log(`          expected ${JSON.stringify(expected)}`);
    console.log(`          got      ${JSON.stringify(got)}`);
    failures++;
  }
}

async function load() {
  const out = mkdtempSync(join(tmpdir(), 'dwell-status-'));
  try {
    execFileSync(
      join(APP, 'node_modules', '.bin', 'tsc'),
      [join(APP, 'src', 'status-report.ts'),
       '--outDir', out, '--rootDir', join(APP, 'src'),
       '--module', 'es2022', '--target', 'es2022',
       '--moduleResolution', 'bundler', '--skipLibCheck'],
      { cwd: out, stdio: 'pipe' },
    );
  } catch (err) {
    console.log('\n  Could not compile the status module:\n');
    console.log(String(err.stdout || err.message));
    process.exit(1);
  }
  const mod = await import(join(out, 'status-report.js'));
  return { mod, cleanup: () => rmSync(out, { recursive: true, force: true }) };
}

const NOW = new Date('2026-09-16T15:00:00Z');
const minutesAgo = (n) => new Date(NOW.getTime() - n * 60000).toISOString();

/** A phone where everything is fine. Each case below breaks one thing. */
const HEALTHY = {
  online: true,
  serverUrl: 'https://course.example.org',
  defaultServerUrl: 'https://course.example.org',
  foregroundPermission: true,
  backgroundPermission: true,
  collecting: true,
  paused: false,
  lastFixAt: minutesAgo(3),
  lastUploadAt: minutesAgo(2),
  lastUploadError: null,
  queued: 0,
  serverLastReceivedAt: minutesAgo(2),
  serverPointsReceived: 412,
  serverReachable: true,
  now: NOW,
};

const { mod, cleanup } = await load();
const { buildReport, overallVerdict, howLongAgo } = mod;

const severities = (input) => buildReport(input).map((a) => a.severity);
const verdict = (input) => overallVerdict(buildReport(input)).severity;

console.log('\n  The nine questions\n');

try {
  // --- shape ----------------------------------------------------------------
  const healthy = buildReport(HEALTHY);
  check('there are nine questions', healthy.length, 9);
  check('every question is distinct',
        new Set(healthy.map((a) => a.question)).size, 9);
  check('every question is a question',
        healthy.every((a) => a.question.endsWith('?')), true);
  check('every one has an answer',
        healthy.every((a) => a.answer && a.answer.length > 0), true);

  // --- a phone that is working ----------------------------------------------
  check('a healthy phone reports no problems',
        severities(HEALTHY).every((v) => v === 'good'), true);
  check('...and says so at the top', verdict(HEALTHY), 'good');
  check('...in one sentence a person can read',
        overallVerdict(healthy).summary, 'Everything is working.');

  // --- no permission ---------------------------------------------------------
  const noPermission = { ...HEALTHY, foregroundPermission: false,
                         backgroundPermission: false };
  check('no location permission is a problem', verdict(noPermission), 'problem');
  check('...and names the permission question first',
        overallVerdict(buildReport(noPermission)).summary
          .includes('permission to see your location'), true);

  // --- "while using the app" only --------------------------------------------
  const foregroundOnly = { ...HEALTHY, backgroundPermission: false };
  check('foreground-only permission is worth flagging, not a fault',
        verdict(foregroundOnly), 'attention');
  check('...and the wording does not scold the participant for it',
        buildReport(foregroundOnly)
          .find((a) => a.question.startsWith('Can it keep going'))
          .fix.includes('perfectly reasonable choice'), true);

  // --- paused -----------------------------------------------------------------
  const paused = { ...HEALTHY, paused: true, collecting: false,
                   lastFixAt: minutesAgo(400) };
  const pausedReport = buildReport(paused);
  check('pausing is not reported as a fault', verdict(paused), 'attention');
  check('...and an old last-fix while paused is not a fault either',
        pausedReport.find((a) => a.question.startsWith('When did it last record'))
          .severity, 'good');

  // --- offline -----------------------------------------------------------------
  const offline = { ...HEALTHY, online: false, serverReachable: false,
                    queued: 40, lastUploadAt: minutesAgo(50) };
  check('being offline is not reported as a fault', verdict(offline), 'attention');
  check('...and the server question says it could not ask',
        buildReport(offline)
          .find((a) => a.question.startsWith('When did the course server'))
          .answer.includes('Could not ask'), true);
  check('...and reassures that nothing is lost',
        buildReport(offline)[0].fix.includes('Nothing is lost'), true);

  // --- collecting, but nothing arriving ----------------------------------------
  // The failure this screen exists for. Everything local looks right.
  const notArriving = {
    ...HEALTHY,
    lastUploadAt: minutesAgo(400),
    queued: 600,
    serverLastReceivedAt: minutesAgo(400),
    serverPointsReceived: 12,
  };
  check('collecting but not arriving is a problem', verdict(notArriving), 'problem');
  const stale = buildReport(notArriving);
  check('...the queue is flagged',
        stale.find((a) => a.question.startsWith('How much is waiting')).severity,
        'problem');
  check('...the upload is flagged',
        stale.find((a) => a.question.startsWith('When did it last send')).severity,
        'problem');
  check('...and so is the server',
        stale.find((a) => a.question.startsWith('When did the course server')).severity,
        'problem');

  // --- the server answers but has never heard from this phone -------------------
  const neverArrived = { ...HEALTHY, serverLastReceivedAt: null,
                         serverPointsReceived: 0 };
  const never = buildReport(neverArrived)
    .find((a) => a.question.startsWith('When did the course server'));
  check('a server that has never heard from this phone is a problem',
        never.severity, 'problem');
  check('...and says so plainly', never.answer, 'Never.');

  // --- a bad server address -------------------------------------------------------
  check('no server address at all is a problem',
        verdict({ ...HEALTHY, serverUrl: '' }), 'problem');
  check('a plain-http address is a problem',
        verdict({ ...HEALTHY, serverUrl: 'http://course.example.org' }), 'problem');
  const overridden = { ...HEALTHY, serverUrl: 'https://elsewhere.example.org' };
  check('an address changed by hand is flagged but not a fault',
        buildReport(overridden)
          .find((a) => a.question.startsWith('Does it know where')).severity,
        'attention');

  // --- an upload error -------------------------------------------------------------
  const failing = { ...HEALTHY, lastUploadError: 'Server returned 502' };
  check('a failed upload while online is a problem', verdict(failing), 'problem');
  check('...and the reason is shown',
        buildReport(failing)
          .find((a) => a.question.startsWith('When did it last send'))
          .fix.includes('502'), true);
  check('the same error while offline is only worth knowing',
        buildReport({ ...failing, online: false, serverReachable: false })
          .find((a) => a.question.startsWith('When did it last send')).severity,
        'attention');

  // --- no coordinates, anywhere -------------------------------------------------
  // The screen is shown to an instructor, in a room, over somebody's shoulder.
  const everyCase = [HEALTHY, noPermission, foregroundOnly, paused, offline,
                     notArriving, neverArrived, failing, overridden,
                     { ...HEALTHY, serverUrl: '' }];
  const allText = everyCase
    .flatMap((c) => buildReport(c))
    .flatMap((a) => [a.question, a.answer, a.fix || ''])
    .join(' ');
  check('no answer contains anything shaped like a coordinate',
        /-?\d{1,3}\.\d{4,}/.test(allText), false);
  check('no answer contains the words latitude or longitude',
        /latitude|longitude/i.test(allText), false);

  // --- the wording of times ---------------------------------------------------
  check('never is "never"', howLongAgo(null, NOW), 'never');
  check('a moment ago is "just now"', howLongAgo(minutesAgo(0.5), NOW), 'just now');
  check('minutes read as minutes', howLongAgo(minutesAgo(12), NOW), '12 minutes ago');
  check('one hour reads as "an hour ago"', howLongAgo(minutesAgo(60), NOW),
        'an hour ago');
  check('hours read as hours', howLongAgo(minutesAgo(300), NOW), '5 hours ago');
  check('a day reads as "yesterday"', howLongAgo(minutesAgo(1440), NOW),
        'yesterday');
  check('more reads as days', howLongAgo(minutesAgo(4320), NOW), '3 days ago');
  check('a nonsense timestamp does not crash', howLongAgo('not-a-time', NOW),
        'unknown');
  check('a clock skewed into the future does not read as negative',
        howLongAgo(new Date(NOW.getTime() + 60000).toISOString(), NOW), 'just now');
} finally {
  cleanup();
}

console.log('');
if (failures) {
  console.log(`  ${failures} check(s) FAILED\n`);
  process.exit(1);
}
console.log('  All status-screen checks passed.\n');
