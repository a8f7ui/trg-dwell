/**
 * Dwell: Privacy Lab — a privacy-education app for classroom use.
 *
 * The whole app is here and in `src/`. There is no analytics package, no crash
 * reporter and no advertising library anywhere in it, which would be an
 * embarrassing thing for a tool like this to ship with.
 *
 * Flow:
 *   first run  → consent screen → permission walkthrough → collecting
 *   after that → home, with the reveal, the illustrated categories and settings
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Alert, StatusBar, Text, View } from 'react-native';

import * as api from './src/api';
import * as collection from './src/collection';
import * as notifications from './src/notifications';
import { CONSENT_VERSION } from './src/config';
import { getDeviceFacts } from './src/device';
import {
  ConsentRecord,
  getConsent,
  getParticipantId,
  getQueue,
  isPaused,
  saveConsent,
  saveCredentials,
  setPaused,
  wipeLocal,
} from './src/storage';
import { colors, s } from './src/theme';

import ConsentScreen from './src/screens/ConsentScreen';
import HomeScreen, { HomeStatus } from './src/screens/HomeScreen';
import IllustratedScreen from './src/screens/IllustratedScreen';
import PermissionWalkthrough from './src/screens/PermissionWalkthrough';
import RevealScreen from './src/screens/RevealScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import TeachingScreen from './src/screens/TeachingScreen';

type Screen =
  | 'loading'
  | 'consent'
  | 'declined'
  | 'walkthrough'
  | 'home'
  | 'reveal'
  | 'illustrated'
  | 'teaching'
  | 'settings';

const facts = getDeviceFacts();

export default function App() {
  const [screen, setScreen] = useState<Screen>('loading');
  const [consent, setConsent] = useState<ConsentRecord | null>(null);
  const [participantId, setParticipantId] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState(0);

  const [status, setStatus] = useState<HomeStatus>({
    collecting: false,
    paused: false,
    queued: 0,
    uploaded: 0,
    participantId: null,
    permissionMessage: '',
    backgroundGranted: false,
  });

  const refreshStatus = useCallback(async () => {
    const [collecting, paused, queue, perms, pid] = await Promise.all([
      collection.isCollecting(),
      isPaused(),
      getQueue(),
      collection.getPermissionState(),
      getParticipantId(),
    ]);
    setStatus({
      collecting,
      paused,
      queued: queue.length,
      uploaded,
      participantId: pid,
      permissionMessage: perms.message,
      backgroundGranted: perms.background,
    });
  }, [uploaded]);

  // Decide where to start.
  useEffect(() => {
    (async () => {
      const existing = await getConsent();
      const pid = await getParticipantId();
      setConsent(existing);
      setParticipantId(pid);
      // Re-schedule the remaining evenings on every start. Scheduled
      // notifications do not survive a reinstall, a restore to a new handset,
      // or some manufacturers' battery settings, and a participant who lost
      // them would simply never hear from the app again — silently, which is
      // the worst way for the centrepiece of the week to fail.
      if (existing && pid && (await notifications.hasPermission())) {
        await notifications
          .scheduleCourseReveals(new Date(existing.agreedAt))
          .catch(() => {});
      }
      await refreshStatus();
      setScreen(existing && pid ? 'home' : 'consent');
    })();
    // refreshStatus is intentionally not a dependency here: this should run once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Send anything queued whenever the app is in use.
  useEffect(() => {
    if (screen === 'loading' || screen === 'consent') return;
    let cancelled = false;
    const tick = async () => {
      const sent = await collection.flushQueue();
      if (!cancelled && sent) setUploaded((n) => n + sent);
      if (!cancelled) await refreshStatus();
    };
    tick();
    const timer = setInterval(tick, 20_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [screen, refreshStatus]);

  // ------------------------------------------------------------------ consent

  async function handleAgree() {
    setRegistering(true);
    setRegisterError(null);
    try {
      const agreedAt = new Date().toISOString();
      const result = await api.register(CONSENT_VERSION, agreedAt, facts);
      await saveCredentials(result.participant_id, result.token);
      const record = { version: CONSENT_VERSION, agreedAt };
      await saveConsent(record);
      setConsent(record);
      setParticipantId(result.participant_id);
      setScreen('walkthrough');
    } catch (e: any) {
      setRegisterError(
        `Could not reach the course server. ${e.message || ''}\n\n` +
          'Nothing has been collected. Check the address with your instructor — you ' +
          'can set it on the settings screen once you are signed up.',
      );
    } finally {
      setRegistering(false);
    }
  }

  // ------------------------------------------------------------- walkthrough

  async function handleWalkthroughDone() {
    await collection.startCollection();
    await collection.recordForegroundFix().catch(() => {});
    if (await notifications.hasPermission()) {
      // The whole course, one notification per evening, counted from the day
      // this participant agreed. Not a single repeating one: that would tell
      // them "Day 1: I have started building a picture of you" every night of
      // the week, while the picture quietly grew.
      const startedAt = consent ? new Date(consent.agreedAt) : new Date();
      await notifications.scheduleCourseReveals(startedAt).catch(() => {});
    }
    await refreshStatus();
    setScreen('home');
  }

  // ------------------------------------------------------------------- home

  async function handleTogglePause() {
    const paused = await isPaused();
    await setPaused(!paused);
    if (!paused) {
      await collection.stopCollection();
    } else {
      await collection.startCollection();
    }
    await refreshStatus();
  }

  async function handleWithdrawn(deleted: number) {
    await collection.stopCollection();
    await notifications.cancelAll();
    await wipeLocal();
    setConsent(null);
    setParticipantId(null);
    Alert.alert(
      'Your data has been deleted',
      `${deleted} location points were removed from the server, along with your ` +
        'participant record. Collection has stopped and nothing about you remains.',
    );
    setScreen('declined');
  }

  // ------------------------------------------------------------------ render

  if (screen === 'loading') {
    return (
      <View style={[s.screen, { justifyContent: 'center', alignItems: 'center' }]}>
        <StatusBar barStyle="light-content" />
        <Text style={s.p}>Starting…</Text>
      </View>
    );
  }

  if (screen === 'consent') {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <ConsentScreen
          onAgree={handleAgree}
          onDecline={() => setScreen('declined')}
          busy={registering}
          error={registerError}
        />
      </>
    );
  }

  if (screen === 'declined') {
    return (
      <View style={[s.screen, { justifyContent: 'center', padding: 28 }]}>
        <StatusBar barStyle="light-content" />
        <Text style={s.h1}>Nothing is being collected</Text>
        <Text style={s.p}>
          This app is not recording anything about you. You can follow every part of the
          course using the shared example data — you will not miss a thing.
        </Text>
        <Text style={s.p}>
          If you change your mind, close and reopen the app.
        </Text>
      </View>
    );
  }

  if (screen === 'walkthrough') {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <PermissionWalkthrough onDone={handleWalkthroughDone} />
      </>
    );
  }

  if (screen === 'reveal') {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <RevealScreen onBack={() => setScreen('home')} />
      </>
    );
  }

  if (screen === 'illustrated') {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <IllustratedScreen
          seedKey={participantId ?? 'demo'}
          onBack={() => setScreen('home')}
        />
      </>
    );
  }

  if (screen === 'teaching') {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <TeachingScreen onBack={() => setScreen('home')} />
      </>
    );
  }

  if (screen === 'settings') {
    return (
      <>
        <StatusBar barStyle="light-content" />
        <SettingsScreen
          onBack={() => setScreen('home')}
          onWithdrawn={handleWithdrawn}
          consentedAt={consent?.agreedAt ?? null}
          participantId={participantId}
        />
      </>
    );
  }

  return (
    <>
      <StatusBar barStyle="light-content" />
      <HomeScreen
        status={status}
        facts={facts}
        onOpenReveal={() => setScreen('reveal')}
        onOpenIllustrated={() => setScreen('illustrated')}
        onOpenTeaching={() => setScreen('teaching')}
        onOpenSettings={() => setScreen('settings')}
        onTogglePause={handleTogglePause}
        onRefresh={refreshStatus}
      />
    </>
  );
}
