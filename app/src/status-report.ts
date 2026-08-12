/**
 * The nine questions, turned into answers a person can read.
 *
 * An operator standing next to somebody whose phone is not working needs to
 * know which of nine things is wrong, and needs to know it without reading a
 * log. The nine are:
 *
 *   1. Is the phone connected?
 *   2. Does it have the correct server?
 *   3. Is location permission sufficient?
 *   4. Is background location enabled?
 *   5. Is tracking active?
 *   6. When was the last location collected?
 *   7. When was the last successful upload?
 *   8. How many locations are queued locally?
 *   9. When did the server last receive data from this device?
 *
 * The last one is the one that cannot be answered from the phone alone, and it
 * is the one that matters most: everything can look correct locally while
 * nothing is arriving.
 *
 * No coordinates appear anywhere in here. The point is to say how much and
 * when, never where — an operator helping somebody troubleshoot should not
 * thereby be shown their movements. That restraint is worth pointing at during
 * the course: it is a diagnostic screen that manages not to be surveillance.
 *
 * This file has no React and no Expo imports so the wording and the judgements
 * can be tested on a laptop; see `tools/status_report_test.mjs`.
 */

export type Severity = 'good' | 'attention' | 'problem' | 'unknown';

export type Answer = {
  question: string;
  answer: string;
  severity: Severity;
  /** What to do about it, when there is something a person can do. */
  fix?: string;
};

export type StatusInput = {
  online: boolean;
  serverUrl: string;
  /** What the build was told to use, for spotting a hand-edited override. */
  defaultServerUrl: string;
  foregroundPermission: boolean;
  backgroundPermission: boolean;
  collecting: boolean;
  paused: boolean;
  lastFixAt: string | null;
  lastUploadAt: string | null;
  lastUploadError: string | null;
  queued: number;
  /** Null when the server could not be reached, which is itself an answer. */
  serverLastReceivedAt: string | null;
  serverPointsReceived: number | null;
  serverReachable: boolean;
  now?: Date;
};

/** "4 minutes ago", "yesterday", "never". Deliberately vague at the top end. */
export function howLongAgo(when: string | null, now: Date = new Date()): string {
  if (!when) return 'never';
  const then = new Date(when);
  if (Number.isNaN(then.getTime())) return 'unknown';
  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  if (seconds < 0) return 'just now';
  if (seconds < 90) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return hours === 1 ? 'an hour ago' : `${hours} hours ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? 'yesterday' : `${days} days ago`;
}

function minutesSince(when: string | null, now: Date): number | null {
  if (!when) return null;
  const then = new Date(when);
  if (Number.isNaN(then.getTime())) return null;
  return (now.getTime() - then.getTime()) / 60000;
}

export function buildReport(input: StatusInput): Answer[] {
  const now = input.now ?? new Date();
  const out: Answer[] = [];

  // 1 -----------------------------------------------------------------------
  out.push(input.online
    ? { question: 'Is this phone connected?', answer: 'Yes.', severity: 'good' }
    : {
      question: 'Is this phone connected?',
      answer: 'No — there is no internet connection right now.',
      severity: 'attention',
      fix: 'Nothing is lost. Points are kept on the phone and sent when a '
        + 'connection comes back.',
    });

  // 2 -----------------------------------------------------------------------
  if (!input.serverUrl) {
    out.push({
      question: 'Does it know where to send the data?',
      answer: 'No. No course server address has been set, so nothing can be '
        + 'sent anywhere.',
      severity: 'problem',
      fix: 'This app was built without an address. Ask your instructor for the '
        + 'correct version.',
    });
  } else if (!input.serverUrl.startsWith('https://')) {
    out.push({
      question: 'Does it know where to send the data?',
      answer: `It is set to ${input.serverUrl}, which is not a secure address.`,
      severity: 'problem',
      fix: 'iPhones refuse to send anything to an address that is not https, '
        + 'and do it silently. Tell your instructor.',
    });
  } else {
    const overridden = Boolean(input.defaultServerUrl)
      && input.serverUrl !== input.defaultServerUrl;
    out.push({
      question: 'Does it know where to send the data?',
      answer: `Yes — ${input.serverUrl}`
        + (overridden ? ' (changed by hand from the one it was built with).' : ''),
      severity: overridden ? 'attention' : 'good',
      fix: overridden
        ? 'If you did not change this yourself, tell your instructor.'
        : undefined,
    });
  }

  // 3 -----------------------------------------------------------------------
  out.push(input.foregroundPermission
    ? {
      question: 'Has it been given permission to see your location?',
      answer: 'Yes.',
      severity: 'good',
    }
    : {
      question: 'Has it been given permission to see your location?',
      answer: 'No. Nothing is being collected at all.',
      severity: 'problem',
      fix: 'Open your phone\'s Settings, find this app, and allow location '
        + 'access.',
    });

  // 4 -----------------------------------------------------------------------
  if (!input.foregroundPermission) {
    out.push({
      question: 'Can it keep going when the app is closed?',
      answer: 'No — it has no location permission at all yet.',
      severity: 'problem',
      fix: 'Grant location access first.',
    });
  } else if (input.backgroundPermission) {
    out.push({
      question: 'Can it keep going when the app is closed?',
      answer: 'Yes. This is the part of the exercise that shows what an app '
        + 'learns while you are not looking at it.',
      severity: 'good',
    });
  } else {
    out.push({
      question: 'Can it keep going when the app is closed?',
      answer: 'No — only while this app is open on screen.',
      severity: 'attention',
      fix: 'That is a perfectly reasonable choice, and worth noticing that '
        + 'most apps never tell you it is available. To take part fully, set '
        + 'location to "Always" in your phone\'s settings for this app.',
    });
  }

  // 5 -----------------------------------------------------------------------
  if (input.paused) {
    out.push({
      question: 'Is it collecting now?',
      answer: 'No — you have paused it. Nothing is being recorded.',
      severity: 'attention',
      fix: 'Press Resume on the main screen when you want it to continue.',
    });
  } else if (input.collecting) {
    out.push({
      question: 'Is it collecting now?', answer: 'Yes.', severity: 'good',
    });
  } else {
    out.push({
      question: 'Is it collecting now?',
      answer: 'No. It is not running.',
      severity: 'problem',
      fix: 'Open the main screen and start collection.',
    });
  }

  // 6 -----------------------------------------------------------------------
  // Both platforms throttle hard when somebody is sitting still, so a gap of
  // half an hour is ordinary and must not be reported as a fault. Six hours
  // is not ordinary.
  const fixAge = minutesSince(input.lastFixAt, now);
  let fixSeverity: Severity = 'good';
  let fixFix: string | undefined;
  if (fixAge === null) {
    fixSeverity = input.collecting && !input.paused ? 'attention' : 'unknown';
    fixFix = 'If this stays empty for more than a few minutes while collection '
      + 'is on, tell your instructor.';
  } else if (fixAge > 360 && !input.paused) {
    fixSeverity = 'problem';
    fixFix = 'That is a long gap. Your phone may be stopping this app in the '
      + 'background to save battery. Tell your instructor.';
  } else if (fixAge > 90 && !input.paused) {
    fixSeverity = 'attention';
    fixFix = 'Gaps are normal when you are sitting still — both phone systems '
      + 'slow down to save battery.';
  }
  out.push({
    question: 'When did it last record a location?',
    answer: howLongAgo(input.lastFixAt, now),
    severity: fixSeverity,
    fix: fixFix,
  });

  // 7 -----------------------------------------------------------------------
  const uploadAge = minutesSince(input.lastUploadAt, now);
  let uploadSeverity: Severity = 'good';
  let uploadFix: string | undefined = undefined;
  if (input.lastUploadError) {
    uploadSeverity = input.online ? 'problem' : 'attention';
    uploadFix = input.online
      ? `The last attempt failed: ${input.lastUploadError}. Nothing is lost — `
        + 'the points are still on this phone. Tell your instructor.'
      : 'Expected while offline. It will retry.';
  } else if (uploadAge === null && input.queued > 0) {
    uploadSeverity = 'attention';
    uploadFix = 'Nothing has been sent yet.';
  } else if (uploadAge !== null && uploadAge > 360 && input.queued > 0) {
    uploadSeverity = 'problem';
    uploadFix = 'Points are piling up on the phone. Tell your instructor.';
  }
  out.push({
    question: 'When did it last send anything successfully?',
    answer: howLongAgo(input.lastUploadAt, now),
    severity: uploadSeverity,
    fix: uploadFix,
  });

  // 8 -----------------------------------------------------------------------
  out.push({
    question: 'How much is waiting to be sent?',
    answer: input.queued === 0
      ? 'Nothing — everything collected has been sent.'
      : `${input.queued} location${input.queued === 1 ? '' : 's'}.`,
    severity: input.queued > 500 ? 'problem'
      : input.queued > 50 ? 'attention' : 'good',
    fix: input.queued > 50
      ? 'This builds up while offline and clears itself when a connection '
        + 'returns. If it keeps growing with a connection, tell your instructor.'
      : undefined,
  });

  // 9 -----------------------------------------------------------------------
  // The one that cannot be faked from the phone's side, and the one that
  // catches an installation where everything local looks correct.
  if (!input.serverReachable) {
    out.push({
      question: 'When did the course server last hear from this phone?',
      answer: 'Could not ask — the server did not answer.',
      severity: input.online ? 'problem' : 'attention',
      fix: input.online
        ? 'The address may be wrong, or the server may be down. Tell your '
          + 'instructor.'
        : 'Expected while offline.',
    });
  } else {
    const serverAge = minutesSince(input.serverLastReceivedAt, now);
    const received = input.serverPointsReceived ?? 0;
    let severity: Severity = 'good';
    let fix: string | undefined;
    if (serverAge === null) {
      severity = 'problem';
      fix = 'The server has never received anything from this phone, even '
        + 'though it answered. Tell your instructor.';
    } else if (serverAge > 360) {
      severity = 'problem';
      fix = 'Nothing has arrived for hours. Tell your instructor.';
    } else if (serverAge > 120) {
      severity = 'attention';
    }
    out.push({
      question: 'When did the course server last hear from this phone?',
      answer: serverAge === null
        ? 'Never.'
        : `${howLongAgo(input.serverLastReceivedAt, now)} `
          + `(${received} location${received === 1 ? '' : 's'} in total).`,
      severity,
      fix,
    });
  }

  return out;
}

/** The single line to put at the top: the worst thing that is wrong. */
export function overallVerdict(answers: Answer[]): {
  severity: Severity; summary: string;
} {
  if (answers.some((a) => a.severity === 'problem')) {
    const first = answers.find((a) => a.severity === 'problem')!;
    return {
      severity: 'problem',
      summary: `Something is wrong: ${first.question.toLowerCase()
        .replace(/\?$/, '')} — ${first.answer}`,
    };
  }
  if (answers.some((a) => a.severity === 'attention')) {
    return {
      severity: 'attention',
      summary: 'Working, with something worth knowing about below.',
    };
  }
  if (answers.some((a) => a.severity === 'unknown')) {
    return { severity: 'unknown', summary: 'Starting up. Check again shortly.' };
  }
  return { severity: 'good', summary: 'Everything is working.' };
}
