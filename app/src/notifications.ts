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
 *
 * One notification per course day, not one repeating one
 * -----------------------------------------------------
 * The teasers escalate: day 1 says a picture is being built, day 5 says there
 * is a week of movements. That escalation is the point of them — it is how the
 * app demonstrates accumulation to somebody only half paying attention.
 *
 * A single daily-repeating notification cannot escalate. It carries whichever
 * teaser it was created with, forever, so a participant who set the app up on
 * Monday was told "Day 1: I have started building a picture of you" every
 * evening for the rest of the week, while the app quietly knew far more each
 * night than the night before. The one part of the week designed to make
 * accumulation visible was the part that hid it.
 *
 * So each evening is scheduled separately, as its own dated notification. That
 * means the right teaser arrives on the right evening even if the participant
 * never opens the app again after the first day — which is exactly the
 * participant this is meant to reach — and the notifications stop when the
 * course does.
 *
 * The arithmetic lives in `reveal-schedule.ts` so it can be tested without a
 * phone. This file is only the part that talks to the operating system.
 */

import * as Notifications from 'expo-notifications';

import { remainingReveals, teaserFor } from './reveal-schedule';

export { COURSE_DAYS, remainingReveals, revealTime, teaserFor } from './reveal-schedule';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function requestPermission(): Promise<boolean> {
  const { status } = await Notifications.requestPermissionsAsync();
  return status === 'granted';
}

export async function hasPermission(): Promise<boolean> {
  const { status } = await Notifications.getPermissionsAsync();
  return status === 'granted';
}

/**
 * Schedule every remaining evening of the course.
 *
 * Safe to call more than once: it clears what was already scheduled first, so
 * re-running it on each app start leaves exactly one notification per evening
 * rather than a growing pile of duplicates.
 *
 * Returns how many were scheduled, so the status screen can show a number
 * rather than assert that notifications are working.
 */
export async function scheduleCourseReveals(
  startedAt: Date,
  now: Date = new Date(),
): Promise<number> {
  await Notifications.cancelAllScheduledNotificationsAsync();
  const upcoming = remainingReveals(startedAt, now);
  for (const { dayNumber, at } of upcoming) {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: 'Your daily summary is ready',
        body: teaserFor(dayNumber),
        // No place names, no coordinates, no inferences. On purpose.
        data: { screen: 'reveal', dayNumber },
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: at,
      },
    });
  }
  return upcoming.length;
}

/** How many evening notifications are currently waiting to fire. */
export async function scheduledCount(): Promise<number> {
  const pending = await Notifications.getAllScheduledNotificationsAsync();
  return pending.length;
}

export async function cancelAll(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
}

/** Used by the facilitator to demonstrate the notification without waiting. */
export async function sendPreviewNow(dayNumber: number): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: 'Your daily summary is ready',
      body: teaserFor(dayNumber),
      data: { screen: 'reveal', dayNumber },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: 3,
    },
  });
}
