/**
 * The narrated permission walkthrough (the classroom teaching flow).
 *
 * For each permission this app genuinely asks for, the participant sees the
 * usual dialog, the usual stated reason, and what the permission actually
 * enables — with our own honest wording underneath for comparison.
 */

import React from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { colors, s } from '../theme';
import { PERMISSION_LESSONS, TWO_LAYERS } from '../teaching';

export default function TeachingScreen({ onBack }: { onBack: () => void }) {
  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.tag}>THE LESSON</Text>
        <Text style={s.h1}>What you actually agreed to</Text>
        <Text style={s.p}>
          Every permission below is one this app really asked you for. For each one,
          here is what a normal app’s prompt says, why it says it, and what it means.
        </Text>

        {PERMISSION_LESSONS.map((lesson) => (
          <View key={lesson.id} style={s.card}>
            <Text style={s.h3}>{lesson.permission}</Text>

            <Text style={[s.small, { color: colors.inkDim, marginTop: 10, marginBottom: 4 }]}>
              WHAT A NORMAL APP SHOWS YOU
            </Text>
            <View
              style={{
                backgroundColor: '#0d1218',
                borderRadius: 8,
                padding: 12,
                borderLeftWidth: 3,
                borderLeftColor: colors.line,
              }}
            >
              <Text style={[s.small, { color: colors.ink, fontStyle: 'italic' }]}>
                {lesson.typicalDialog}
              </Text>
            </View>

            <Text style={[s.small, { color: colors.inkDim, marginTop: 14, marginBottom: 4 }]}>
              THE REASON THEY GIVE
            </Text>
            <Text style={[s.small, { color: colors.ink }]}>{lesson.typicalReason}</Text>

            <Text style={[s.small, { color: colors.warn, marginTop: 14, marginBottom: 4 }]}>
              WHAT IT ACTUALLY ENABLES
            </Text>
            <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>
              {lesson.reality}
            </Text>

            <Text style={[s.small, { color: colors.good, marginTop: 14, marginBottom: 4 }]}>
              WHAT THIS APP SAID INSTEAD
            </Text>
            <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>
              {lesson.ourDialog}
            </Text>

            <View
              style={{
                marginTop: 14,
                backgroundColor: '#16283a',
                borderLeftWidth: 3,
                borderLeftColor: colors.accent,
                borderRadius: 6,
                padding: 11,
              }}
            >
              <Text style={[s.small, { color: '#cfe4ff', lineHeight: 20 }]}>
                {lesson.punchline}
              </Text>
            </View>
          </View>
        ))}

        <Text style={s.h2}>{TWO_LAYERS.title}</Text>
        <View style={[s.card, { borderColor: colors.good }]}>
          <Text style={[s.small, { color: colors.good, fontWeight: '700', marginBottom: 6 }]}>
            ABOVE THE LINE — REAL
          </Text>
          <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>{TWO_LAYERS.above}</Text>
        </View>
        <View style={[s.card, { borderColor: colors.simulated }]}>
          <Text style={[s.small, { color: colors.simulated, fontWeight: '700', marginBottom: 6 }]}>
            BELOW THE LINE — ILLUSTRATED, NOT TAKEN
          </Text>
          <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>{TWO_LAYERS.below}</Text>
        </View>
        <Text style={[s.p, { fontStyle: 'italic' }]}>{TWO_LAYERS.closing}</Text>

        <Pressable style={s.buttonQuiet} onPress={onBack}>
          <Text style={s.buttonQuietText}>Back</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
