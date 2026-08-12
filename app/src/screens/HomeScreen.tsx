/**
 * The main screen, and the permanent "collection is ON" indicator.
 *
 * The banner is not dismissible and is the first thing on the screen. Combined
 * with the notification Android requires and the indicator iOS shows, there is
 * no state in which this app is collecting without the participant being able
 * to see that it is.
 */

import React from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { colors, s } from '../theme';
import type { DeviceFacts } from '../api';
import { describeCollected } from '../device';

export type HomeStatus = {
  collecting: boolean;
  paused: boolean;
  queued: number;
  uploaded: number;
  participantId: string | null;
  permissionMessage: string;
  backgroundGranted: boolean;
};

type Props = {
  status: HomeStatus;
  facts: DeviceFacts;
  onOpenReveal: () => void;
  onOpenIllustrated: () => void;
  onOpenTeaching: () => void;
  onOpenSettings: () => void;
  onOpenStatus: () => void;
  onTogglePause: () => void;
  onRefresh: () => void;
};

export default function HomeScreen({
  status,
  facts,
  onOpenReveal,
  onOpenIllustrated,
  onOpenTeaching,
  onOpenSettings,
  onOpenStatus,
  onTogglePause,
  onRefresh,
}: Props) {
  const live = status.collecting && !status.paused;

  return (
    <View style={s.screen}>
      {/* The indicator. Always present, never dismissible. */}
      <View
        style={{
          backgroundColor: live ? '#1d3a26' : '#3a2a1a',
          borderBottomColor: live ? colors.good : colors.warn,
          borderBottomWidth: 2,
          paddingVertical: 12,
          paddingHorizontal: 18,
          flexDirection: 'row',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <View
          style={{
            width: 12,
            height: 12,
            borderRadius: 6,
            backgroundColor: live ? colors.good : colors.warn,
          }}
        />
        <Text style={{ color: live ? colors.good : colors.warn, fontWeight: '800', fontSize: 15 }}>
          {live ? 'Collection is ON' : status.paused ? 'Paused — nothing is being collected' : 'Not collecting'}
        </Text>
      </View>

      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.h1}>Dwell: Privacy Lab</Text>
        <Text style={s.p}>
          {live
            ? 'This app is recording your location right now, including when you are not looking at it.'
            : 'Collection is stopped. Nothing is being recorded.'}
        </Text>

        <View style={s.statRow}>
          <View style={s.stat}>
            <Text style={s.statN}>{status.uploaded}</Text>
            <Text style={s.statL}>POINTS SENT</Text>
          </View>
          <View style={s.stat}>
            <Text style={s.statN}>{status.queued}</Text>
            <Text style={s.statL}>WAITING TO SEND</Text>
          </View>
        </View>

        {!status.backgroundGranted && (
          <View style={[s.card, { borderColor: colors.warn }]}>
            <Text style={[s.h3, { color: colors.warn }]}>Heads up</Text>
            <Text style={[s.p, { marginBottom: 0 }]}>{status.permissionMessage}</Text>
          </View>
        )}

        <Pressable style={s.button} onPress={onOpenReveal}>
          <Text style={s.buttonText}>See what I know about you</Text>
        </Pressable>

        <Pressable style={s.buttonQuiet} onPress={onOpenIllustrated}>
          <Text style={s.buttonQuietText}>What a real ad SDK would also be taking</Text>
        </Pressable>

        <Pressable style={s.buttonQuiet} onPress={onOpenTeaching}>
          <Text style={s.buttonQuietText}>How those permission prompts actually work</Text>
        </Pressable>

        <Text style={s.h2}>What this app is really collecting</Text>
        <View style={s.card}>
          {describeCollected(facts).map((row) => (
            <View
              key={row.label}
              style={{
                flexDirection: 'row',
                justifyContent: 'space-between',
                paddingVertical: 7,
                borderBottomWidth: 1,
                borderBottomColor: colors.line,
              }}
            >
              <Text style={s.small}>{row.label}</Text>
              <Text style={[s.small, { color: colors.ink, flexShrink: 1, textAlign: 'right' }]}>
                {row.value}
              </Text>
            </View>
          ))}
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 7 }}>
            <Text style={s.small}>Your participant number</Text>
            <Text style={[s.small, { color: colors.ink }]}>{status.participantId ?? '—'}</Text>
          </View>
          <Text style={[s.small, { marginTop: 10 }]}>
            Plus your location with timestamps, your battery level, and your connection
            type. That is the complete list.
          </Text>
        </View>

        <Pressable style={s.buttonQuiet} onPress={onTogglePause}>
          <Text style={s.buttonQuietText}>
            {status.paused ? 'Resume collection' : 'Pause collection'}
          </Text>
        </Pressable>

        <Pressable style={s.buttonQuiet} onPress={onOpenStatus}>
          <Text style={s.buttonQuietText}>Is this working?</Text>
        </Pressable>

        <Pressable style={s.buttonQuiet} onPress={onOpenSettings}>
          <Text style={s.buttonQuietText}>Settings, and how to withdraw</Text>
        </Pressable>

        <Pressable onPress={onRefresh} style={{ paddingVertical: 16, alignItems: 'center' }}>
          <Text style={[s.small, { color: colors.accent }]}>Refresh</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
