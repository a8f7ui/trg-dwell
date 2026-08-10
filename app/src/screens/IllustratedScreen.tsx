/**
 * The illustrated categories — what a real SDK would also be taking.
 *
 * Every value on this screen is invented. The labelling is deliberately heavy
 * and repeated per card rather than stated once at the top, because a
 * screenshot of a single card will circulate without the header, and it must
 * still be obvious that the data is not real.
 */

import React from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { colors, s } from '../theme';
import { buildIllustrated } from '../illustrated';

export default function IllustratedScreen({
  seedKey,
  onBack,
}: {
  seedKey: string;
  onBack: () => void;
}) {
  const categories = buildIllustrated(seedKey);

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.simulatedTag}>NONE OF THIS WAS TAKEN FROM YOUR PHONE</Text>
        <Text style={s.h1}>What a real SDK would also have</Text>
        <Text style={s.p}>
          Using the permissions you have already granted, a commercial advertising or
          analytics SDK could reach all of the following. This app takes none of it.
          Every value below is invented, to make the category concrete rather than
          abstract.
        </Text>
        <View style={[s.card, { borderColor: colors.simulated }]}>
          <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>
            You do not have to take our word for this. The app is open source, and there
            is no code in it that reads contacts, photos, the clipboard, the microphone
            or your installed apps. The server has no field to store them in.
          </Text>
        </View>

        {categories.map((c) => (
          <View key={c.id} style={[s.card, { borderColor: colors.simulated }]}>
            <Text style={s.simulatedTag}>SIMULATED</Text>
            <Text style={s.h3}>{c.title}</Text>

            <Text style={[s.small, { color: colors.inkDim, marginTop: 10 }]}>
              WHAT AN APP WOULD SAY
            </Text>
            <Text style={[s.small, { color: colors.ink, marginTop: 3 }]}>{c.statedReason}</Text>

            <Text style={[s.small, { color: colors.warn, marginTop: 12 }]}>
              WHAT IT ACTUALLY ENABLES
            </Text>
            <Text style={[s.small, { color: colors.ink, marginTop: 3, lineHeight: 20 }]}>
              {c.actuallyEnables}
            </Text>

            <Text style={[s.small, { color: colors.simulated, marginTop: 14 }]}>
              INVENTED EXAMPLE OF WHAT WOULD BE SENT
            </Text>
            <View
              style={{
                backgroundColor: '#0d1218',
                borderRadius: 8,
                padding: 12,
                marginTop: 6,
                borderLeftWidth: 3,
                borderLeftColor: colors.simulated,
              }}
            >
              {c.sample.map((line, i) => (
                <Text
                  key={i}
                  style={{
                    color: colors.inkDim,
                    fontSize: 12.5,
                    fontFamily: 'monospace',
                    lineHeight: 19,
                  }}
                >
                  {line}
                </Text>
              ))}
            </View>

            <Text style={[s.small, { color: colors.inkDim, marginTop: 14 }]}>
              THIS HAS ACTUALLY HAPPENED
            </Text>
            <Text style={[s.small, { color: colors.ink, marginTop: 3, lineHeight: 20 }]}>
              {c.realCase}
            </Text>
          </View>
        ))}

        <Pressable style={s.buttonQuiet} onPress={onBack}>
          <Text style={s.buttonQuietText}>Back</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
