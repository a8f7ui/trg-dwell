/**
 * Everything this app sends to, or asks of, the server.
 *
 * There are exactly four calls. If you are auditing this app, this file tells
 * you the complete set of things that ever leave the phone.
 *
 *   register()  — announces consent, receives an anonymous ID and a token
 *   upload()    — sends queued location points
 *   reveal()    — asks for this participant's own daily summary
 *   withdraw()  — asks the server to delete everything about this participant
 *
 * Nothing else is transmitted. There is no analytics SDK in this app, no crash
 * reporter, and no third-party network code — which would be an awkward thing
 * for a privacy-education tool to ship with.
 */

import { getServerUrl, getToken, QueuedPing } from './storage';

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function request(path: string, init?: RequestInit) {
  const base = await getServerUrl();
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { ...(await authHeaders()), ...(init?.headers || {}) },
  });
  const text = await res.text();
  let body: any = {};
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { raw: text };
  }
  if (!res.ok) {
    throw new Error(body?.error || `Server returned ${res.status}`);
  }
  return body;
}

export type DeviceFacts = {
  device_model: string | null;
  os_name: string | null;
  os_version: string | null;
  screen_w: number | null;
  screen_h: number | null;
  timezone: string | null;
  language: string | null;
};

export async function register(
  consentVersion: string,
  consentedAt: string,
  device: DeviceFacts,
): Promise<{ participant_id: string; token: string }> {
  return request('/api/v1/participants', {
    method: 'POST',
    body: JSON.stringify({
      consent_version: consentVersion,
      consented_at: consentedAt,
      ...device,
    }),
  });
}

export async function upload(pings: QueuedPing[]): Promise<{ accepted: number }> {
  return request('/api/v1/pings', {
    method: 'POST',
    body: JSON.stringify({ pings }),
  });
}

export async function reveal(day?: string): Promise<any> {
  return request(`/api/v1/me/reveal${day ? `?day=${encodeURIComponent(day)}` : ''}`);
}

export async function withdraw(): Promise<{
  location_points_deleted: number;
  message: string;
}> {
  return request('/api/v1/me/withdraw', { method: 'POST' });
}

/** Used by the settings screen so somebody can check the address they typed. */
export async function ping(): Promise<boolean> {
  try {
    const base = await getServerUrl();
    const res = await fetch(`${base}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
