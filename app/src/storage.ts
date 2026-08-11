/**
 * Everything this app keeps on the phone.
 *
 * There are only four things:
 *   - the device token issued by the server at registration
 *   - a record of the consent that was given, and when
 *   - a queue of location points waiting to be uploaded
 *   - the server address
 *
 * The token lives in the platform keystore (Keychain on iOS, EncryptedSharedPreferences
 * on Android) rather than in ordinary storage, because anybody holding it could
 * read that participant's data.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

import { DEFAULT_SERVER_URL, MAX_QUEUE_LENGTH } from './config';

const TOKEN_KEY = 'dwell_token';
const PARTICIPANT_KEY = 'dwell_participant_id';
const CONSENT_KEY = 'dwell_consent';
const QUEUE_KEY = 'dwell_queue';
const SERVER_KEY = 'dwell_server';
const PAUSED_KEY = 'dwell_paused';

export type ConsentRecord = {
  version: string;
  agreedAt: string;
};

export type QueuedPing = {
  ts: string;
  lat: number;
  lon: number;
  accuracy_m: number;
  battery_pct: number | null;
  connection: string;
  collection_mode: 'background' | 'foreground';
  session_id?: string;
};

// ---------------------------------------------------------------- credentials

export async function saveCredentials(participantId: string, token: string) {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
  await AsyncStorage.setItem(PARTICIPANT_KEY, participantId);
}

export async function getToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function getParticipantId(): Promise<string | null> {
  return AsyncStorage.getItem(PARTICIPANT_KEY);
}

// ---------------------------------------------------------------- consent

export async function saveConsent(record: ConsentRecord) {
  await AsyncStorage.setItem(CONSENT_KEY, JSON.stringify(record));
}

export async function getConsent(): Promise<ConsentRecord | null> {
  const raw = await AsyncStorage.getItem(CONSENT_KEY);
  return raw ? (JSON.parse(raw) as ConsentRecord) : null;
}

// ---------------------------------------------------------------- pause

export async function setPaused(paused: boolean) {
  await AsyncStorage.setItem(PAUSED_KEY, paused ? '1' : '0');
}

export async function isPaused(): Promise<boolean> {
  return (await AsyncStorage.getItem(PAUSED_KEY)) === '1';
}

// ---------------------------------------------------------------- server

export async function getServerUrl(): Promise<string> {
  return (await AsyncStorage.getItem(SERVER_KEY)) || DEFAULT_SERVER_URL;
}

export async function setServerUrl(url: string) {
  await AsyncStorage.setItem(SERVER_KEY, url.replace(/\/+$/, ''));
}

// ---------------------------------------------------------------- ping queue

/**
 * Points are queued locally first and uploaded in batches. This means a
 * participant walking around with no signal does not silently lose their day —
 * and it means the app is not making a network request every minute.
 */
export async function enqueue(pings: QueuedPing[]) {
  const queue = await getQueue();
  const merged = queue.concat(pings);
  // Never let the queue grow without limit. If somebody is offline for days,
  // drop the oldest rather than filling their phone.
  const trimmed = merged.slice(-MAX_QUEUE_LENGTH);
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(trimmed));
}

export async function getQueue(): Promise<QueuedPing[]> {
  const raw = await AsyncStorage.getItem(QUEUE_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as QueuedPing[];
  } catch {
    return [];
  }
}

export async function dropFromQueue(count: number) {
  const queue = await getQueue();
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue.slice(count)));
}

// ---------------------------------------------------------------- teardown

/**
 * Remove every trace of this participant from the phone.
 *
 * Called when somebody withdraws. The server delete happens separately; this is
 * the local half, and it must leave nothing behind that could restart
 * collection or re-identify the device.
 */
export async function wipeLocal() {
  await SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => {});
  await AsyncStorage.removeMany([
    PARTICIPANT_KEY,
    CONSENT_KEY,
    QUEUE_KEY,
    PAUSED_KEY,
  ]);
}
