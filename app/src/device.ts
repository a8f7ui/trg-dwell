/**
 * The benign facts this app really does collect.
 *
 * Read this list next to `docs/sdk-research.md`. These are close to the exact
 * inputs a real attribution SDK uses to build a device fingerprint when it has
 * no advertising identifier to work with: model, OS version, screen size,
 * language, timezone, and the IP address the server sees anyway.
 *
 * That is the point. The lesson is not "look at this scary data". It is that
 * this unremarkable list, the kind every app collects without anyone objecting,
 * is enough to pick one phone out of millions.
 */

import * as Battery from 'expo-battery';
import * as Device from 'expo-device';
import * as Localization from 'expo-localization';
import * as Network from 'expo-network';
import { Dimensions, Platform } from 'react-native';

import type { DeviceFacts } from './api';

export function getDeviceFacts(): DeviceFacts {
  const { width, height } = Dimensions.get('window');
  const calendars = Localization.getCalendars();
  const locales = Localization.getLocales();

  return {
    device_model: Device.modelName ?? null,
    os_name: Platform.OS === 'ios' ? 'iOS' : 'Android',
    os_version: Device.osVersion ?? String(Platform.Version),
    screen_w: Math.round(width),
    screen_h: Math.round(height),
    timezone: calendars[0]?.timeZone ?? null,
    language: locales[0]?.languageTag ?? null,
  };
}

/** Battery level as a whole percentage, or null if the phone will not say. */
export async function getBatteryPct(): Promise<number | null> {
  try {
    const level = await Battery.getBatteryLevelAsync();
    return level < 0 ? null : Math.round(level * 100);
  } catch {
    return null;
  }
}

/** "wifi", "cellular", "none" or "unknown". */
export async function getConnection(): Promise<string> {
  try {
    const state = await Network.getNetworkStateAsync();
    if (!state.isConnected) return 'none';
    switch (state.type) {
      case Network.NetworkStateType.WIFI:
        return 'wifi';
      case Network.NetworkStateType.CELLULAR:
        return 'cellular';
      case Network.NetworkStateType.ETHERNET:
        return 'ethernet';
      default:
        return 'unknown';
    }
  } catch {
    return 'unknown';
  }
}

/**
 * A human-readable list of what is genuinely collected, shown in the app so a
 * participant can compare it against what they are told.
 */
export function describeCollected(facts: DeviceFacts) {
  return [
    { label: 'Device model', value: facts.device_model ?? 'unknown' },
    { label: 'Operating system', value: `${facts.os_name ?? '?'} ${facts.os_version ?? ''}`.trim() },
    { label: 'Screen size', value: `${facts.screen_w} × ${facts.screen_h}` },
    { label: 'Timezone', value: facts.timezone ?? 'unknown' },
    { label: 'Language', value: facts.language ?? 'unknown' },
  ];
}
