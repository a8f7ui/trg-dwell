/**
 * Connection and tracking status.
 *
 * Nine questions with plain answers, for two audiences at once: a participant
 * who wants to know whether the thing on their phone is doing anything, and an
 * instructor standing next to them at a break trying to work out why one
 * person's map is empty.
 *
 * There are no coordinates on this screen, and that is deliberate. Everything
 * here is how much and when, never where. A diagnostic screen that showed the
 * participant's position would be a small piece of surveillance built into a
 * tool for teaching people to notice surveillance — and it would be read over
 * their shoulder in a room full of people.
 *
 * The wording and the judgements live in `../status-report`, which imports
 * nothing, so they can be tested without a phone.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';

import * as api from '../api';
import * as collection from '../collection';
import { DEFAULT_SERVER_URL } from '../config';
import { getConnection } from '../device';
import { getActivity, getQueue, getServerUrl, isPaused } from '../storage';
import {
  Answer,
  buildReport,
  overallVerdict,
  Severity,
} from '../status-report';
import { colors, s } from '../theme';

const DOT: Record<Severity, string> = {
  good: colors.good,
  attention: colors.warn,
  problem: colors.danger,
  unknown: colors.inkDim,
};

const HEADLINE: Record<Severity, string> = {
  good: colors.good,
  attention: colors.warn,
  problem: colors.danger,
  unknown: colors.inkDim,
};

type Props = { onBack: () => void };

export default function StatusScreen({ onBack }: Props) {
  const [answers, setAnswers] = useState<Answer[] | null>(null);
  const [checking, setChecking] = useState(false);

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      const [connectionKind, serverUrl, permissions, collecting, paused,
             activity, queue] = await Promise.all([
        getConnection(),
        getServerUrl(),
        collection.getPermissionState(),
        collection.isCollecting(),
        isPaused(),
        getActivity(),
        getQueue(),
      ]);

      // Asked last, and allowed to fail: the server not answering is one of
      // the nine answers rather than an error that empties the screen.
      let serverReachable = false;
      let serverLastReceivedAt: string | null = null;
      let serverPointsReceived: number | null = null;
      try {
        const remote = await api.status();
        serverReachable = true;
        serverLastReceivedAt = remote.last_received_at;
        serverPointsReceived = remote.points_received;
      } catch {
        serverReachable = false;
      }

      setAnswers(buildReport({
        online: connectionKind !== 'none' && connectionKind !== 'unknown',
        serverUrl,
        defaultServerUrl: DEFAULT_SERVER_URL,
        foregroundPermission: permissions.foreground,
        backgroundPermission: permissions.background,
        collecting,
        paused,
        lastFixAt: activity.lastFixAt,
        lastUploadAt: activity.lastUploadAt,
        lastUploadError: activity.lastUploadError,
        queued: queue.length,
        serverLastReceivedAt,
        serverPointsReceived,
        serverReachable,
      }));
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const verdict = answers ? overallVerdict(answers) : null;

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.h1}>Is this working?</Text>
        <Text style={s.p}>
          Nine questions about what this app is doing right now. Show this
          screen to an instructor if something looks wrong — there is nothing on
          it that says where you have been.
        </Text>

        {verdict && (
          <View style={[s.card, { borderColor: HEADLINE[verdict.severity] }]}>
            <Text style={{
              color: HEADLINE[verdict.severity],
              fontSize: 17,
              fontWeight: '800',
              lineHeight: 24,
            }}>
              {verdict.summary}
            </Text>
          </View>
        )}

        {!answers && (
          <View style={[s.card, { alignItems: 'center' }]}>
            <ActivityIndicator color={colors.accent} />
            <Text style={[s.small, { marginTop: 10 }]}>Checking…</Text>
          </View>
        )}

        {answers?.map((a) => (
          <View key={a.question} style={s.card}>
            <View style={[s.row, { alignItems: 'flex-start' }]}>
              <View style={{
                width: 10,
                height: 10,
                borderRadius: 5,
                marginTop: 6,
                backgroundColor: DOT[a.severity],
              }} />
              <View style={{ flex: 1 }}>
                <Text style={s.h3}>{a.question}</Text>
                <Text style={[s.pStrong, { marginBottom: a.fix ? 8 : 0 }]}>
                  {a.answer}
                </Text>
                {a.fix ? <Text style={[s.small, { marginBottom: 0 }]}>{a.fix}</Text> : null}
              </View>
            </View>
          </View>
        ))}

        <Pressable style={s.buttonQuiet} onPress={refresh} disabled={checking}>
          <Text style={s.buttonQuietText}>
            {checking ? 'Checking…' : 'Check again'}
          </Text>
        </Pressable>

        <Pressable style={s.buttonQuiet} onPress={onBack}>
          <Text style={s.buttonQuietText}>Back</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
