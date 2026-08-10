import { StyleSheet } from 'react-native';

export const colors = {
  bg: '#10151c',
  panel: '#182029',
  panel2: '#1f2935',
  ink: '#e8eef5',
  inkDim: '#9fb0c2',
  line: '#2c3a49',
  accent: '#4da3ff',
  warn: '#ffb454',
  danger: '#ff6b6b',
  good: '#4ade80',
  simulated: '#c084fc',
};

export const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  scroll: { padding: 20, paddingBottom: 48 },

  h1: { color: colors.ink, fontSize: 26, fontWeight: '800', marginBottom: 6 },
  h2: { color: colors.ink, fontSize: 20, fontWeight: '700', marginTop: 22, marginBottom: 8 },
  h3: { color: colors.ink, fontSize: 16, fontWeight: '700', marginBottom: 6 },
  p: { color: colors.inkDim, fontSize: 15, lineHeight: 22, marginBottom: 12 },
  pStrong: { color: colors.ink, fontSize: 16, lineHeight: 24, marginBottom: 12 },
  small: { color: colors.inkDim, fontSize: 13, lineHeight: 19 },

  card: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginBottom: 14,
  },

  button: {
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 15,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonText: { color: '#04121f', fontSize: 16, fontWeight: '800' },

  buttonQuiet: {
    backgroundColor: colors.panel2,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonQuietText: { color: colors.ink, fontSize: 15, fontWeight: '600' },

  buttonDanger: {
    backgroundColor: '#3a1a1e',
    borderColor: '#5c2b30',
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonDangerText: { color: colors.danger, fontSize: 15, fontWeight: '700' },

  tag: {
    alignSelf: 'flex-start',
    backgroundColor: '#24425f',
    color: '#9fd0ff',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.6,
    paddingHorizontal: 9,
    paddingVertical: 3,
    borderRadius: 999,
    overflow: 'hidden',
    marginBottom: 10,
  },

  simulatedTag: {
    alignSelf: 'flex-start',
    backgroundColor: '#3b2a52',
    color: colors.simulated,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.6,
    paddingHorizontal: 9,
    paddingVertical: 3,
    borderRadius: 999,
    overflow: 'hidden',
    marginBottom: 8,
  },

  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  statRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginVertical: 10 },
  stat: {
    backgroundColor: colors.panel2,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    minWidth: 96,
    flexGrow: 1,
  },
  statN: { color: colors.ink, fontSize: 22, fontWeight: '800' },
  statL: { color: colors.inkDim, fontSize: 11, letterSpacing: 0.5, marginTop: 2 },
});
