/**
 * Settings that decide how the app behaves.
 *
 * Kept in one small file on purpose. A participant who wants to check what this
 * app does should be able to read this, then `collection.ts`, and know.
 */

/** Where location points are sent. Overridable in the app's own settings so a
 *  course can point at its own server without rebuilding the app. */
export const DEFAULT_SERVER_URL = 'http://localhost:5000';

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
export const LOCATION_TASK = 'wypk-background-location';

/** When the evening reveal notification fires, in local time. */
export const REVEAL_HOUR = 20;
export const REVEAL_MINUTE = 30;
