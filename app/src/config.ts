/**
 * Settings that decide how the app behaves.
 *
 * Kept in one small file on purpose. A participant who wants to check what this
 * app does should be able to read this, then `collection.ts`, and know.
 */

/**
 * Where location points are sent.
 *
 * Written into the build by `python3 dwell.py app`, which puts the course's
 * address in `app/.env`. Nothing in this file is edited by hand — that used to
 * be step one of distribution, and asking a non-technical person to edit
 * TypeScript before every build was the single most technical thing this
 * project required of anybody.
 *
 * Empty by default, deliberately. The old default was `http://localhost:5000`,
 * which on a phone means the phone itself: the app looked like it was working
 * and collected nothing. An empty address makes the app say plainly that it has
 * not been set up, which is the truth.
 *
 * Still overridable in the app's own Settings screen, for the rare case of
 * pointing one handset at a different server.
 */
export const DEFAULT_SERVER_URL =
  process.env.EXPO_PUBLIC_DWELL_SERVER ?? '';

/** Whether a build knows where to send anything at all. */
export const HAS_SERVER_CONFIGURED = DEFAULT_SERVER_URL.length > 0;

/** Bumped whenever the wording of the consent screen changes in a way that
 *  alters what somebody agreed to. Recorded alongside their agreement, so it is
 *  always possible to say which version a given participant accepted. */
export const CONSENT_VERSION = '2026-08-10.1';

/**
 * How often the app asks the phone for a location while running in the
 * background. Both platforms treat these as hints and will throttle harder to
 * protect the battery, especially when somebody is sitting still.
 */
export const LOCATION_INTERVAL_MS = 60_000;
export const LOCATION_DISTANCE_M = 25;

/** Points are batched and sent together rather than one request per fix. */
export const UPLOAD_BATCH_SIZE = 25;
export const MAX_QUEUE_LENGTH = 5_000;

/** The identifier the background task is registered under. */
export const LOCATION_TASK = 'dwell-background-location';

/**
 * When the evening reveal notification fires, in local time.
 *
 * The value lives in `reveal-schedule.ts` alongside the arithmetic that uses
 * it, so that module has no dependencies and can be tested on its own. It is
 * re-exported here because this is the file somebody reads to find out what the
 * app does, and a setting that is not in it may as well not be documented.
 */
export { REVEAL_HOUR, REVEAL_MINUTE } from './reveal-schedule';
