/**
 * Settings, and withdrawal.
 *
 * Withdrawal is one tap plus one confirmation, and it is on this screen rather
 * than buried behind a support email. It stops collection, deletes everything
 * the server holds about this participant, and clears the phone — then reports
 * exactly how many location points were destroyed, because "your data has been
 * deleted" means more when it comes with a number.
 */

import React, { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import * as api from '../api';
import { colors, s } from '../theme';
import { getServerUrl, setServerUrl } from '../storage';
import { CONSENT_VERSION } from '../config';

type Props = {
  onBack: () => void;
  onWithdrawn: (deleted: number) => void;
  consentedAt: string | null;
  participantId: string | null;
};

export default function SettingsScreen({
  onBack,
  onWithdrawn,
  consentedAt,
  participantId,
}: Props) {
  const [server, setServer] = useState('');
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getServerUrl().then(setServer);
  }, []);

  async function saveServer() {
    await setServerUrl(server);
    setReachable(await api.ping());
  }

  function confirmWithdraw() {
    Alert.alert(
      'Withdraw and delete everything?',
      'Collection will stop immediately and every location point collected about you ' +
        'will be deleted from the server. This cannot be undone, and nobody will ask ' +
        'you why.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete my data',
          style: 'destructive',
          onPress: async () => {
            setBusy(true);
            try {
              const result = await api.withdraw();
              onWithdrawn(result.location_points_deleted);
            } catch (e: any) {
              Alert.alert(
                'Could not reach the server',
                'Your data was not deleted because the server could not be contacted. ' +
                  'Collection has not been stopped either — try again when you have a ' +
                  'connection, so that you get a confirmation rather than a guess.\n\n' +
                  (e.message || ''),
              );
            } finally {
              setBusy(false);
            }
          },
        },
      ],
    );
  }

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.h1}>Settings</Text>

        <Text style={s.h2}>Your participation</Text>
        <View style={s.card}>
          <Text style={s.small}>Participant number</Text>
          <Text style={[s.small, { color: colors.ink, marginBottom: 10 }]}>
            {participantId ?? '—'}
          </Text>
          <Text style={s.small}>You agreed on</Text>
          <Text style={[s.small, { color: colors.ink, marginBottom: 10 }]}>
            {consentedAt ? new Date(consentedAt).toLocaleString() : '—'}
          </Text>
          <Text style={s.small}>Version of the consent text you saw</Text>
          <Text style={[s.small, { color: colors.ink }]}>{CONSENT_VERSION}</Text>
        </View>

        <Text style={s.h2}>Course server</Text>
        <Text style={s.p}>
          Where your data is sent. Your instructors will give you this address.
        </Text>
        <TextInput
          value={server}
          onChangeText={setServer}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="https://…"
          placeholderTextColor={colors.inkDim}
          style={{
            backgroundColor: '#0d1218',
            borderColor: colors.line,
            borderWidth: 1,
            borderRadius: 8,
            color: colors.ink,
            padding: 12,
            fontSize: 15,
          }}
        />
        <Pressable style={s.buttonQuiet} onPress={saveServer}>
          <Text style={s.buttonQuietText}>Save and test</Text>
        </Pressable>
        {reachable !== null && (
          <Text style={[s.small, { color: reachable ? colors.good : colors.danger, marginTop: 8 }]}>
            {reachable ? 'Server reachable.' : 'Could not reach that address.'}
          </Text>
        )}

        <Text style={s.h2}>Withdraw</Text>
        <Text style={s.p}>
          Stops collection and deletes everything the server holds about you. Your place
          on the course is unaffected.
        </Text>
        <Pressable style={s.buttonDanger} onPress={confirmWithdraw} disabled={busy}>
          <Text style={s.buttonDangerText}>
            {busy ? 'Deleting…' : 'Withdraw and delete my data'}
          </Text>
        </Pressable>

        <Text style={s.h2}>Checking up on us</Text>
        <Text style={s.p}>
          This app is open source. Everything it collects is in one file called
          collection.ts, and everything it sends is in one file called api.ts. If what
          they do and what this screen says ever disagree, that is a bug worth reporting
          loudly.
        </Text>

        <Pressable style={s.buttonQuiet} onPress={onBack}>
          <Text style={s.buttonQuietText}>Back</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
