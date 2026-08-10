/**
 * The narrated permission requests.
 *
 * Permissions are asked for one at a time, and each system prompt is preceded by
 * a plain-language aside explaining what a normal app would say at this exact
 * moment, and what saying yes actually allows.
 *
 * The order is dictated by the platforms: "while using the app" must be granted
 * before "always" can even be requested. That sequencing is itself worth
 * pointing at — it is why apps ask for the modest version first and escalate
 * later, once you are already using them.
 */

import React, { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import * as collection from '../collection';
import * as notifications from '../notifications';
import { PERMISSION_LESSONS } from '../teaching';
import { colors, s } from '../theme';

type StepId = 'location_foreground' | 'location_background' | 'notifications';

const ORDER: StepId[] = ['location_foreground', 'location_background', 'notifications'];

export default function PermissionWalkthrough({ onDone }: { onDone: () => void }) {
  const [index, setIndex] = useState(0);
  const [outcome, setOutcome] = useState<Record<string, boolean>>({});
  const [asking, setAsking] = useState(false);

  const stepId = ORDER[index];
  const lesson = PERMISSION_LESSONS.find((l) => l.id === stepId)!;
  const answered = stepId in outcome;

  async function ask() {
    setAsking(true);
    let granted = false;
    try {
      if (stepId === 'location_foreground') {
        granted = await collection.requestForegroundPermission();
      } else if (stepId === 'location_background') {
        granted = await collection.requestBackgroundPermission();
      } else {
        granted = await notifications.requestPermission();
      }
    } catch {
      granted = false;
    }
    setOutcome((o) => ({ ...o, [stepId]: granted }));
    setAsking(false);
  }

  function next() {
    if (index + 1 < ORDER.length) {
      setIndex(index + 1);
    } else {
      onDone();
    }
  }

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.tag}>
          PERMISSION {index + 1} OF {ORDER.length}
        </Text>
        <Text style={s.h1}>{lesson.permission}</Text>
        <Text style={s.p}>
          In a moment your phone will ask you this. Before it does, here is what is
          really going on.
        </Text>

        <View style={s.card}>
          <Text style={[s.small, { color: colors.inkDim, marginBottom: 5 }]}>
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
          <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>{lesson.reality}</Text>
        </View>

        <View style={[s.card, { borderColor: colors.good }]}>
          <Text style={[s.small, { color: colors.good, marginBottom: 5 }]}>
            WHAT WE ARE ABOUT TO ASK
          </Text>
          <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>{lesson.ourDialog}</Text>
        </View>

        {!answered ? (
          <Pressable style={s.button} onPress={ask} disabled={asking}>
            <Text style={s.buttonText}>
              {asking ? 'Waiting for your answer…' : 'Show me the real prompt'}
            </Text>
          </Pressable>
        ) : (
          <>
            <View
              style={{
                backgroundColor: outcome[stepId] ? '#1d3a26' : '#3a2a1a',
                borderLeftWidth: 3,
                borderLeftColor: outcome[stepId] ? colors.good : colors.warn,
                borderRadius: 8,
                padding: 13,
                marginTop: 10,
              }}
            >
              <Text
                style={{
                  color: outcome[stepId] ? colors.good : colors.warn,
                  fontWeight: '700',
                  marginBottom: 5,
                }}
              >
                {outcome[stepId] ? 'You allowed it' : 'You declined'}
              </Text>
              <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>
                {outcome[stepId]
                  ? stepId === 'location_background'
                    ? 'This app can now record your location when it is closed. Your phone ' +
                      'will keep reminding you about this — let it.'
                    : stepId === 'location_foreground'
                      ? 'This app can now see where you are while you have it open.'
                      : 'You will get one notification each evening. It will never contain ' +
                        'any specifics.'
                  : 'That is a completely reasonable answer, and the course works either ' +
                    'way. Declining here is the same choice you could make with any app — ' +
                    'notice how rarely you are given a reason to.'}
              </Text>
            </View>

            <View
              style={{
                marginTop: 14,
                backgroundColor: '#16283a',
                borderLeftWidth: 3,
                borderLeftColor: colors.accent,
                borderRadius: 6,
                padding: 12,
              }}
            >
              <Text style={[s.small, { color: '#cfe4ff', lineHeight: 20 }]}>
                {lesson.punchline}
              </Text>
            </View>

            <Pressable style={s.button} onPress={next}>
              <Text style={s.buttonText}>
                {index + 1 < ORDER.length ? 'Next permission' : 'Start the week'}
              </Text>
            </Pressable>
          </>
        )}

        {!answered && (
          <Pressable style={s.buttonQuiet} onPress={next}>
            <Text style={s.buttonQuietText}>Skip this one</Text>
          </Pressable>
        )}
      </ScrollView>
    </View>
  );
}
