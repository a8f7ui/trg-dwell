/**
 * The daily reveal.
 *
 * This is the payoff of the whole exercise: the participant's own day, drawn on
 * a map, with the inferences a commercial system would draw from it, how those
 * inferences are tightening as the week goes on, where they are shaky, and one
 * concrete thing to do about it.
 *
 * A participant only ever sees their own data. The server takes the identity
 * from the device token, so there is no way to ask this screen for anybody else.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { WebView } from 'react-native-webview';

import * as api from '../api';
import { buildRevealMapHtml } from '../revealMap';
import { colors, s } from '../theme';

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export default function RevealScreen({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<any>(null);
  const [day, setDay] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (which?: string) => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.reveal(which));
    } catch (e: any) {
      setError(e.message || 'Could not load your summary.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(day);
  }, [day, load]);

  if (loading) {
    return (
      <View style={[s.screen, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator color={colors.accent} size="large" />
        <Text style={[s.p, { marginTop: 16 }]}>Working out what I know about you…</Text>
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={s.screen}>
        <ScrollView contentContainerStyle={s.scroll}>
          <Text style={s.h1}>Nothing to show yet</Text>
          <Text style={s.p}>{error}</Text>
          <Text style={s.p}>
            If collection only just started, come back this evening — there needs to be
            a few hours of movement before there is anything worth showing.
          </Text>
          <Pressable style={s.button} onPress={() => load(day)}>
            <Text style={s.buttonText}>Try again</Text>
          </Pressable>
          <Pressable style={s.buttonQuiet} onPress={onBack}>
            <Text style={s.buttonQuietText}>Back</Text>
          </Pressable>
        </ScrollView>
      </View>
    );
  }

  const f = data.assessment?.findings || {};
  const cov = data.assessment?.coverage || {};
  const caveats: string[] = data.assessment?.caveats || [];
  const cmp = data.comparison || {};
  const agency = data.agency_step || {};
  const seg = f.segment || {};
  const rhythm = f.rhythm || {};

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.tag}>DAY {data.day_number} OF THE COURSE</Text>
        <Text style={s.h1}>Here is your day</Text>

        <View style={{ height: 300, borderRadius: 12, overflow: 'hidden', marginBottom: 16 }}>
          <WebView
            originWhitelist={['*']}
            source={{ html: buildRevealMapHtml(data.trail_segments || [], data.stops || []) }}
            style={{ backgroundColor: colors.bg }}
            scrollEnabled={false}
          />
        </View>

        {/* The number that lands hardest. */}
        {cov.background_pct != null && (
          <View style={[s.card, { borderColor: colors.warn }]}>
            <Text style={[s.h3, { color: colors.warn }]}>
              {cov.background_pct}% of this was collected while the app was closed
            </Text>
            <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>
              You opened this app {cov.session_count ?? 0} time(s) today. Everything on
              this screen was worked out from {cov.point_count ?? 0} location points, and
              most of them were recorded while you were not looking at your phone.
            </Text>
          </View>
        )}

        <Text style={s.h2}>What I would sell you as</Text>
        <View style={s.card}>
          <Text style={{ color: colors.accent, fontSize: 22, fontWeight: '800' }}>
            {seg.value ?? 'unknown'}
          </Text>
          <Text style={[s.small, { color: colors.inkDim, marginTop: 4 }]}>
            {seg.confidence_word} · {Math.round((seg.confidence ?? 0) * 100)}% confident
          </Text>
          <Text style={[s.small, { color: colors.ink, marginTop: 10, lineHeight: 20 }]}>
            {seg.basis}
          </Text>
        </View>

        {f.visitor_or_local && (
          <View style={s.card}>
            <Text style={s.h3}>Visitor or local</Text>
            <Text style={{ color: colors.accent, fontSize: 17, fontWeight: '700' }}>
              {f.visitor_or_local.value}
            </Text>
            <Text style={[s.small, { color: colors.ink, marginTop: 8, lineHeight: 20 }]}>
              {f.visitor_or_local.basis}
            </Text>
          </View>
        )}

        {f.area_character && (
          <View style={s.card}>
            <Text style={s.h3}>The kind of area you spent time in</Text>
            <Text style={{ color: colors.accent, fontSize: 17, fontWeight: '700' }}>
              {f.area_character.value}
            </Text>
            <Text style={[s.small, { color: colors.ink, marginTop: 8, lineHeight: 20 }]}>
              {f.area_character.basis}
            </Text>
          </View>
        )}

        {rhythm.left_anchor_local && (
          <View style={s.card}>
            <Text style={s.h3}>Your rhythm today</Text>
            <Text style={[s.small, { color: colors.ink, lineHeight: 20 }]}>
              Out at {rhythm.left_anchor_local}, back by {rhythm.returned_local} —{' '}
              {rhythm.hours_out} hours, across {rhythm.distinct_places} places.
            </Text>
          </View>
        )}

        <Text style={s.h2}>Where you stopped</Text>
        {(data.places || []).length === 0 ? (
          <Text style={s.p}>No stops long enough to detect today.</Text>
        ) : (
          <View style={s.card}>
            {data.places.map((p: any, i: number) => (
              <View
                key={i}
                style={{
                  paddingVertical: 9,
                  borderBottomWidth: i === data.places.length - 1 ? 0 : 1,
                  borderBottomColor: colors.line,
                }}
              >
                <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                  <Text style={{ color: colors.ink, fontSize: 15, flex: 1 }}>{p.name}</Text>
                  <Text style={{ color: colors.accent, fontSize: 14 }}>
                    {p.observed_minutes} min
                  </Text>
                </View>
                <Text style={[s.small, { marginTop: 2 }]}>
                  {p.kind_label} · {p.activity_guess} · from {fmtTime(p.first_seen)}
                </Text>
              </View>
            ))}
          </View>
        )}

        {cmp.narrative ? (
          <>
            <Text style={s.h2}>Compared with earlier days</Text>
            <View style={[s.card, { borderColor: colors.accent }]}>
              <Text style={[s.small, { color: colors.ink, lineHeight: 21 }]}>
                {cmp.narrative}
              </Text>
            </View>
          </>
        ) : null}

        {caveats.length > 0 && (
          <>
            <Text style={s.h2}>Where I might be wrong</Text>
            <View
              style={{
                backgroundColor: '#2b2418',
                borderLeftWidth: 3,
                borderLeftColor: colors.warn,
                borderRadius: 8,
                padding: 14,
                marginBottom: 14,
              }}
            >
              {caveats.map((c, i) => (
                <Text
                  key={i}
                  style={{ color: '#e6d8c2', fontSize: 13.5, lineHeight: 20, marginBottom: 10 }}
                >
                  • {c}
                </Text>
              ))}
              <Text style={{ color: colors.warn, fontSize: 13, fontStyle: 'italic' }}>
                A real system would show you none of this. It would print the verdict and
                act on it.
              </Text>
            </View>
          </>
        )}

        {agency.title && (
          <>
            <Text style={s.h2}>One thing to do about it</Text>
            <View style={[s.card, { borderColor: colors.good }]}>
              <Text style={[s.h3, { color: colors.good }]}>{agency.title}</Text>
              <Text style={[s.small, { color: colors.ink, lineHeight: 20, marginTop: 6 }]}>
                {agency.detail}
              </Text>
              <Text style={[s.small, { color: colors.inkDim, marginTop: 10, lineHeight: 20 }]}>
                <Text style={{ fontWeight: '700', color: colors.ink }}>
                  Had you already done this:{' '}
                </Text>
                {agency.what_would_have_changed}
              </Text>
            </View>
          </>
        )}

        {(data.days_available || []).length > 1 && (
          <>
            <Text style={s.h2}>Other days</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {data.days_available.map((d: string) => (
                <Pressable
                  key={d}
                  onPress={() => setDay(d)}
                  style={{
                    paddingVertical: 9,
                    paddingHorizontal: 14,
                    borderRadius: 8,
                    borderWidth: 1,
                    borderColor: d === data.day ? colors.accent : colors.line,
                    backgroundColor: d === data.day ? '#16283a' : colors.panel2,
                  }}
                >
                  <Text style={{ color: d === data.day ? colors.accent : colors.inkDim, fontSize: 13 }}>
                    {new Date(d).toLocaleDateString([], { weekday: 'short', day: 'numeric' })}
                  </Text>
                </Pressable>
              ))}
            </View>
          </>
        )}

        <Pressable style={s.buttonQuiet} onPress={onBack}>
          <Text style={s.buttonQuietText}>Back</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
