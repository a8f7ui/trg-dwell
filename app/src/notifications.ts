/**
 * The evening notification.
 *
 * Deliberately vague. A lock screen is a public surface — anybody standing near
 * the phone can read it — so the notification says only that a summary exists.
 * Every specific (place names, the map, the inferences) waits until the app is
 * opened.
 *
 * This restraint is itself part of the teaching. The teaching flow points at it
 * and asks why other apps are happy to put your name, your address or your
 * account balance on your lock screen.
 */

import * as Notifications from 'expo-notifications';

import { REVEAL_HOUR, REVEAL_MINUTE } from './config';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

/** Teasers, chosen by how far into the course we are. None names a place. */
const TEASERS = [
  'Day 1: I have started building a picture of you. Tap to see what I have so far.',
  'Day 2: based on where you have been, I am starting to guess your routine. Tap to see.',
  'Day 3: based on where you have been today, I could infer where you have been ' +
    'staying, your daily routine, and what you seem to be doing. Tap to see what an ' +
    'app would know about you.',
  'Day 4: today mostly confirmed what I already suspected. Tap to see how confident ' +
    'I have become.',
  'Day 5: I have a week of your movements now. Tap to see the whole picture at once.',
];

export async function requestPermission(): Promise<boolean> {
  const { status } = await Notifications.requestPermissionsAsync();
  return status === 'granted';
}

export async function hasPermission(): Promise<boolean> {
  const { status } = await Notifications.getPermissionsAsync();
  return status === 'granted';
}

/**
 * Schedule the evening reveal. Repeats daily, so it survives the app being
 * closed for the rest of the course.
 */
export async function scheduleDailyReveal(dayNumber: number): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
  await Notifications.scheduleNotificationAsync({
    content: {
      title: 'Your daily summary is ready',
      body: TEASERS[Math.min(Math.max(dayNumber - 1, 0), TEASERS.length - 1)],
      // No place names, no coordinates, no inferences. On purpose.
      data: { screen: 'reveal' },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DAILY,
      hour: REVEAL_HOUR,
      minute: REVEAL_MINUTE,
    },
  });
}

export async function cancelAll(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
}

/** Used by the facilitator to demonstrate the notification without waiting. */
export async function sendPreviewNow(dayNumber: number): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: 'Your daily summary is ready',
      body: TEASERS[Math.min(Math.max(dayNumber - 1, 0), TEASERS.length - 1)],
      data: { screen: 'reveal' },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: 3,
    },
  });
}
