/**
 * Location collection.
 *
 * If you are checking whether this app does what it claims, this is the file to
 * read. It contains every line of code that touches your location.
 *
 * What it does:
 *   - collects a location fix roughly once a minute while collection is on,
 *     including when the app is closed
 *   - queues those fixes on the phone and uploads them in batches
 *   - shows a permanent notification on Android for as long as it is running,
 *     which the operating system requires and which cannot be dismissed
 *
 * What it does not do:
 *   - it does not start until consent has been given and the participant has
 *     pressed the button
 *   - it does not read contacts, photos, the clipboard, the microphone, the
 *     list of installed apps, or any cross-app identifier. Those categories are
 *     *illustrated* elsewhere in this app using invented values, and the code
 *     for reading them does not exist here to be switched on.
 *   - it does not run at all while paused or after withdrawal
 */

import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';

import {
  LOCATION_DISTANCE_M,
  LOCATION_INTERVAL_MS,
  LOCATION_TASK,
  UPLOAD_BATCH_SIZE,
} from './config';
import { getBatteryPct, getConnection } from './device';
import * as api from './api';
import {
  dropFromQueue,
  enqueue,
  getQueue,
  getToken,
  isPaused,
  QueuedPing,
} from './storage';

// --------------------------------------------------------------------------
// The background task
// --------------------------------------------------------------------------

/**
 * Registered with the OS, and run by it — not by the app. This is what makes
 * collection continue after the app is closed, and it is exactly the mechanism
 * an ordinary app would use to do the same thing silently.
 */
TaskManager.defineTask(LOCATION_TASK, async ({ data, error }) => {
  if (error) {
    console.warn('[collection] background task error', error.message);
    return;
  }
  const locations = (data as { locations?: Location.LocationObject[] })?.locations;
  if (!locations?.length) return;

  // Two guards, both checked on every single delivery rather than assumed at
  // start-up: a participant who withdrew or paused while the app was closed
  // must not have another point recorded.
  if (!(await getToken())) return;
  if (await isPaused()) return;

  await recordFixes(locations, 'background');
  await flushQueue();
});

// --------------------------------------------------------------------------
// Recording and uploading
// --------------------------------------------------------------------------

export async function recordFixes(
  locations: Location.LocationObject[],
  mode: 'background' | 'foreground',
) {
  const battery = await getBatteryPct();
  const connection = await getConnection();

  const pings: QueuedPing[] = locations.map((l) => ({
    ts: new Date(l.timestamp).toISOString(),
    lat: l.coords.latitude,
    lon: l.coords.longitude,
    accuracy_m: l.coords.accuracy ?? 0,
    battery_pct: battery,
    connection,
    collection_mode: mode,
  }));

  await enqueue(pings);
}

/**
 * Send whatever is waiting. Points are only removed from the queue once the
 * server has confirmed it took them, so a failed upload means a retry rather
 * than a hole in somebody's day.
 */
export async function flushQueue(): Promise<number> {
  if (!(await getToken())) return 0;

  let sent = 0;
  // Bounded rather than `while (true)`: if the server is accepting but the
  // queue is enormous, we would rather return and try again than block.
  for (let round = 0; round < 20; round += 1) {
    const queue = await getQueue();
    if (!queue.length) break;

    const batch = queue.slice(0, UPLOAD_BATCH_SIZE);
    try {
      await api.upload(batch);
      await dropFromQueue(batch.length);
      sent += batch.length;
    } catch {
      // Offline, or the server is down. Keep the points and try later.
      break;
    }
  }
  return sent;
}

// --------------------------------------------------------------------------
// Starting and stopping
// --------------------------------------------------------------------------

export type PermissionOutcome = {
  foreground: boolean;
  background: boolean;
  message: string;
};

/**
 * Ask for location permission in the order the platforms require: "while using
 * the app" first, and only then the escalation to "always".
 *
 * The teaching screens narrate what is happening at each of these prompts, so
 * this deliberately does them one at a time rather than in a single burst.
 */
export async function requestForegroundPermission(): Promise<boolean> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  return status === 'granted';
}

export async function requestBackgroundPermission(): Promise<boolean> {
  const { status } = await Location.requestBackgroundPermissionsAsync();
  return status === 'granted';
}

export async function getPermissionState(): Promise<PermissionOutcome> {
  const fg = await Location.getForegroundPermissionsAsync();
  const bg = await Location.getBackgroundPermissionsAsync();
  const foreground = fg.status === 'granted';
  const background = bg.status === 'granted';

  let message: string;
  if (!foreground) {
    message = 'Location access has not been granted, so nothing is being collected.';
  } else if (!background) {
    message =
      'Location is only available while this app is open. Collection will stop ' +
      'when you switch away — which is a perfectly reasonable choice, and worth ' +
      'noticing that most apps never tell you it is available.';
  } else {
    message = 'Location is available even when this app is closed.';
  }
  return { foreground, background, message };
}

export async function isCollecting(): Promise<boolean> {
  try {
    return await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK);
  } catch {
    return false;
  }
}

export async function startCollection(): Promise<void> {
  if (await isCollecting()) return;

  await Location.startLocationUpdatesAsync(LOCATION_TASK, {
    accuracy: Location.Accuracy.Balanced,
    timeInterval: LOCATION_INTERVAL_MS,
    distanceInterval: LOCATION_DISTANCE_M,
    pausesUpdatesAutomatically: false,
    // Android requires a permanent notification for background location. It is
    // not dismissible, and that is a feature here rather than a nuisance: the
    // participant can see at a glance that collection is running.
    foregroundService: {
      notificationTitle: 'Collection is ON',
      notificationBody:
        'Dwell: Privacy Lab is recording your location for the course. Tap to stop.',
      notificationColor: '#4da3ff',
    },
    // iOS shows its own indicator; this adds the blue bar behaviour.
    showsBackgroundLocationIndicator: true,
    activityType: Location.ActivityType.Other,
  });
}

export async function stopCollection(): Promise<void> {
  if (await isCollecting()) {
    await Location.stopLocationUpdatesAsync(LOCATION_TASK);
  }
}

/** A single fix taken while the participant is looking at the app. */
export async function recordForegroundFix(): Promise<void> {
  if (await isPaused()) return;
  const location = await Location.getCurrentPositionAsync({
    accuracy: Location.Accuracy.Balanced,
  });
  await recordFixes([location], 'foreground');
  await flushQueue();
}
