/**
 * The consent screen.
 *
 * Two design decisions worth defending:
 *
 * 1. **You cannot agree until you have scrolled to the bottom.** The button is
 *    disabled until the text has actually been read past. This is the opposite
 *    of the industry norm, where the agree button is the first thing you can
 *    reach.
 *
 * 2. **The two most uncomfortable facts are at the top, not buried.** That
 *    collection continues when the app is closed, and that instructors can see
 *    a participant's live position. Anything else would make this screen a
 *    worked example of the problem it is meant to teach.
 */

import React, { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { colors, s } from '../theme';

type Props = {
  onAgree: () => void;
  onDecline: () => void;
  busy?: boolean;
  error?: string | null;
};

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', marginBottom: 10 }}>
      <Text style={{ color: colors.accent, marginRight: 8, fontSize: 15 }}>•</Text>
      <Text style={[s.p, { flex: 1, marginBottom: 0 }]}>{children}</Text>
    </View>
  );
}

export default function ConsentScreen({ onAgree, onDecline, busy, error }: Props) {
  const [readToEnd, setReadToEnd] = useState(false);

  return (
    <View style={s.screen}>
      <ScrollView
        contentContainerStyle={s.scroll}
        scrollEventThrottle={64}
        onScroll={(e) => {
          const { layoutMeasurement, contentOffset, contentSize } = e.nativeEvent;
          if (layoutMeasurement.height + contentOffset.y >= contentSize.height - 40) {
            setReadToEnd(true);
          }
        }}
      >
        <Text style={s.tag}>PLEASE READ THIS PROPERLY</Text>
        <Text style={s.h1}>This app will track you</Text>
        <Text style={s.pStrong}>
          That is what it is for. It is a teaching tool for this course, and it works by
          collecting real data about you and then showing you what can be worked out
          from it.
        </Text>

        <View style={[s.card, { borderColor: colors.warn }]}>
          <Text style={[s.h3, { color: colors.warn }]}>The two things people miss</Text>
          <Bullet>
            <Text style={{ color: colors.ink, fontWeight: '700' }}>
              It keeps recording when the app is closed.
            </Text>{' '}
            Not only while you are looking at it. That is deliberate — an app that only
            collected while you watched could not demonstrate what happens when you are
            not watching.
          </Bullet>
          <Bullet>
            <Text style={{ color: colors.ink, fontWeight: '700' }}>
              Your instructors can see where you are.
            </Text>{' '}
            Including your live position on a map, on a screen at the front of the room,
            labelled with your participant number.
          </Bullet>
        </View>

        <Text style={s.h2}>What is actually collected</Text>
        <Bullet>Where you are, with the time, continuously — including in the background.</Bullet>
        <Bullet>Your device model, operating system version and screen size.</Bullet>
        <Bullet>Your timezone and language.</Bullet>
        <Bullet>Your battery level and whether you are on Wi-Fi or mobile data.</Bullet>
        <Bullet>
          A random participant number generated on this phone. Not your name, not your
          email, not your phone number — the app never asks for them and the server has
          nowhere to put them.
        </Bullet>

        <Text style={s.h2}>What is NOT collected</Text>
        <Text style={s.p}>
          Later in the course this app will show you your contacts, your photos, your
          clipboard and other things a real advertising SDK would take. Those screens are
          a demonstration built from invented values. Nothing of the kind is read from
          your phone, and nothing of the kind is sent anywhere. The code that would do it
          does not exist in this app, and you are welcome to check — it is published in
          full.
        </Text>

        <Text style={s.h2}>Where it goes</Text>
        <Bullet>To a server run by the course organisers, and nowhere else.</Bullet>
        <Bullet>It is not sold, shared, or given to any third party. There are no advertising or analytics tools inside this app.</Bullet>
        <Bullet>You see your own data. Instructors see participant movement and combined patterns for teaching.</Bullet>

        <Text style={s.h2}>How long it is kept</Text>
        <Text style={s.p}>
          For the duration of the course, and then it is deleted. Instructors run a wipe
          at the end that removes everything for everybody.
        </Text>

        <Text style={s.h2}>How to stop</Text>
        <Bullet>
          <Text style={{ color: colors.ink, fontWeight: '700' }}>Pause</Text> at any time
          from the main screen. Collection halts immediately; your data so far is kept.
        </Bullet>
        <Bullet>
          <Text style={{ color: colors.ink, fontWeight: '700' }}>Withdraw</Text> at any
          time, also from the main screen. Collection stops and everything already
          collected about you is deleted from the server. The app will tell you exactly
          how many points were removed.
        </Bullet>
        <Bullet>
          You can also revoke location access in your phone’s own settings, or delete the
          app. Both stop collection immediately.
        </Bullet>
        <Bullet>
          Withdrawing has no effect on your participation in the course. Nobody will ask
          you why.
        </Bullet>

        <Text style={s.h2}>While it is running</Text>
        <Text style={s.p}>
          You will see a permanent “Collection is ON” notice for as long as it is
          collecting. On Android it is a notification you cannot swipe away. On iPhone the
          system shows its own location indicator and will periodically remind you this
          app has been recording. We do not control those reminders and would not turn
          them off if we could.
        </Text>

        <View style={[s.card, { borderColor: colors.line }]}>
          <Text style={s.small}>
            This is voluntary. If you would rather not take part, decline — you can still
            follow every part of the course using the shared example data, and no one will
            know which you chose.
          </Text>
        </View>

        {error ? (
          <Text style={[s.p, { color: colors.danger }]}>{error}</Text>
        ) : null}

        <Pressable
          onPress={onAgree}
          disabled={!readToEnd || busy}
          style={[
            s.button,
            (!readToEnd || busy) && { backgroundColor: colors.panel2 },
          ]}
        >
          <Text
            style={[
              s.buttonText,
              (!readToEnd || busy) && { color: colors.inkDim },
            ]}
          >
            {busy
              ? 'Setting up…'
              : readToEnd
                ? 'I understand — start collecting'
                : 'Scroll to the end to continue'}
          </Text>
        </Pressable>

        <Pressable onPress={onDecline} style={s.buttonQuiet} disabled={busy}>
          <Text style={s.buttonQuietText}>No thanks — I’ll watch instead</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
