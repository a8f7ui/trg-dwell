/* Instructor dashboard.
 *
 * Plain JavaScript on purpose. This project asks people to trust that it does
 * what it says, so the dashboard is written to be readable by somebody who is
 * checking rather than somebody who is extending it. No build step, no
 * framework, no bundle to un-minify.
 */

'use strict';

// ---------------------------------------------------------------- utilities

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

async function api(path, options) {
  const res = await fetch(path, Object.assign({
    headers: { 'Content-Type': 'application/json' },
  }, options || {}));
  if (res.status === 401) { showLogin(); throw new Error('Login required'); }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}

/**
 * Every time on this dashboard is shown in the timezone the course is running
 * in, not the one this computer is set to.
 *
 * Without this, an instructor whose laptop is on UTC — or who has flown in from
 * elsewhere — would see every time shifted by hours and tell the room somebody
 * went for dinner at one in the morning. Set from the server; falls back to the
 * local zone if it has not loaded yet.
 */
let courseTz = null;

const tzOpts = (extra) => Object.assign(
  courseTz ? { timeZone: courseTz } : {}, extra);

const fmtTime = (iso) => new Date(iso)
  .toLocaleTimeString([], tzOpts({ hour: '2-digit', minute: '2-digit' }));
const fmtDate = (iso) => new Date(iso)
  .toLocaleDateString([], tzOpts({ weekday: 'short', month: 'short', day: 'numeric' }));
const fmtDateTime = (d) => d.toLocaleString([], tzOpts({
  weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
}));

/**
 * A stable colour per participant.
 *
 * Assigned by position in the roster rather than by hashing the ID, because
 * even spacing round the colour wheel is what makes twelve tracks tellable
 * apart at a glance. Hashing gives you two near-identical blues sooner or
 * later, and on a projector that is the difference between a legible map and a
 * useless one.
 */
const participantColors = {};

function assignColors(people) {
  const n = Math.max(1, people.length);
  people.forEach((p, i) => {
    const hue = Math.round((i * 360) / n);
    // Alternate lightness so neighbouring hues separate further.
    const light = i % 2 ? 68 : 56;
    participantColors[p.participant_id] = `hsl(${hue} 80% ${light}%)`;
  });
}

const colorFor = (id) => participantColors[id] || '#4da3ff';

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------------------------------------------------------------- map setup

let map, baseSatellite, baseStreet, labelLayer, layerControl;
const layers = {};      // one layer group per view

function initMap() {
  // Milwaukee only as the opening frame before the server answers; startApp
  // moves the map to the configured course location a moment later.
  map = L.map('map', { zoomControl: true, preferCanvas: true })
         .setView([43.0389, -87.9065], 14);

  // Two basemaps, both built in and both always available. Neither is an
  // optional extra: satellite shows what a place looks like, streets show what
  // it *is*, and different teaching moments want different ones. Somebody's
  // evening reads very differently over a photograph of rooftops than it does
  // over named roads and labelled buildings.
  //
  // Both come from Esri, which serves them free with attribution and — unlike
  // Google's tiles — needs no API key, no billing account and no per-load
  // charge. Using one provider for both also means the street map does not
  // lean on OpenStreetMap's donated tile servers, whose usage policy asks
  // applications not to.
  baseSatellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' });

  // Place and road names, drawn over the imagery so the map stays readable.
  // Redundant over the street map, which draws its own — see the handler below.
  labelLayer = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, opacity: 0.9 });

  baseStreet = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19,
      attribution: 'Esri, HERE, Garmin, &copy; OpenStreetMap contributors' });

  baseSatellite.addTo(map);
  labelLayer.addTo(map);

  // Left open rather than hidden behind a hover icon. An instructor should be
  // able to switch basemaps in front of a class without hunting for a control,
  // and the room should see that it was one click.
  layerControl = L.control.layers(
    { 'Satellite': baseSatellite, 'Street map': baseStreet },
    { 'Place names': labelLayer },
    { position: 'topright', collapsed: false }
  ).addTo(map);

  // The street map draws its own labels, so the overlay would double every name
  // on screen. Follow the basemap rather than making somebody notice.
  //
  // Deferred by a tick on purpose: this event fires from inside the layer
  // control's own click handler, which afterwards re-applies every overlay
  // whose box is still ticked. Removing the layer synchronously would be undone
  // a moment later, silently.
  map.on('baselayerchange', (e) => {
    const wantLabels = e.layer === baseSatellite;
    setTimeout(() => {
      if (wantLabels) map.addLayer(labelLayer);
      else map.removeLayer(labelLayer);
    }, 0);
  });

  addOfflineBasemaps();
  addEnvironmentOverlays();

  ['live', 'participant', 'aggregate'].forEach((v) => {
    layers[v] = L.layerGroup().addTo(map);
  });

  // Whether two dots overlap depends on the zoom level, so the live view has to
  // be regrouped whenever the map moves. Redraw from data already held rather
  // than refetching.
  map.on('zoomend', () => {
    if (currentView === 'live') drawLive();
  });

  // Follow mode yields the moment a person touches the map. Dragging is always
  // the user, so it needs no guard; zooming also happens under our own control,
  // so that one is only counted when we are not the ones doing it.
  map.on('dragstart', () => { if (followLive) setFollow(false); });
  map.on('zoomstart', () => {
    if (followLive && !programmaticMove) setFollow(false);
  });
  map.on('moveend', () => { programmaticMove = false; });
}

/**
 * Offer any offline map the server has, as a further basemap choice.
 *
 * This is not how you get streets — the street map above is built in and always
 * there. This is about *independence from the internet*. Both Esri basemaps are
 * fetched from Esri's servers, so on a bad venue connection the map is simply
 * blank, which is awkward when the map is the lesson. A PMTiles archive is one
 * file holding an entire city's streets, served from the same machine as
 * everything else, so it keeps drawing with no connection at all.
 *
 * If no archive is installed the option does not appear and nothing else
 * changes, because nothing else depends on it.
 */
const offlineBasemaps = [];

async function addOfflineBasemaps() {
  try {
    const { basemaps } = await api('/api/basemaps');
    if (!basemaps || !basemaps.length) return;
    if (typeof protomapsL === 'undefined') return;

    basemaps.forEach((b) => {
      const layer = protomapsL.leafletLayer({
        url: b.url,
        theme: mapTheme(),
        maxDataZoom: 15,
      });
      const label = basemaps.length === 1
        ? `Street map, offline (${b.size_mb} MB)`
        : `Offline: ${b.name.replace(/\.pmtiles$/, '')}`;
      offlineBasemaps.push({ layer, label, url: b.url });
      layerControl.addBaseLayer(layer, label);
    });
  } catch {
    // No offline map available, or the server did not answer. The built-in
    // basemaps still work; this is an addition, never a dependency.
  }
}

/** Which protomaps theme suits the current skin. */
function mapTheme() {
  return document.documentElement.getAttribute('data-theme') === 'console'
    ? 'black' : 'light';
}

/**
 * Redraw the offline basemap in the other skin's colours.
 *
 * The online tiles are photographs and pre-rendered images, so they look the
 * same either way. The offline map is drawn in the browser from vector data,
 * which means it can and should follow the skin — a white street map under the
 * console skin would be the one thing on screen that did not.
 */
function restyleOfflineBasemaps() {
  if (!offlineBasemaps.length || typeof protomapsL === 'undefined') return;
  offlineBasemaps.forEach((entry) => {
    const wasVisible = map.hasLayer(entry.layer);
    layerControl.removeLayer(entry.layer);
    if (wasVisible) map.removeLayer(entry.layer);
    entry.layer = protomapsL.leafletLayer({
      url: entry.url, theme: mapTheme(), maxDataZoom: 15,
    });
    layerControl.addBaseLayer(entry.layer, entry.label);
    if (wasVisible) map.addLayer(entry.layer);
  });
}

const ENV_STYLE = {
  camera:  { color: '#ff5f56', label: 'CCTV cameras' },
  alpr:    { color: '#ffb454', label: 'Plate readers' },
  wifi:    { color: '#3ddc84', label: 'Wi-Fi / wardrive' },
  payment: { color: '#c084fc', label: 'Card terminals' },
  transit: { color: '#4da3ff', label: 'Transit readers' },
};

/**
 * Observing infrastructure, as overlays that can be switched on and off.
 *
 * Kept out of the way deliberately: all off by default, so the map stays about
 * the participant until an instructor chooses to show what else was there. The
 * moment to turn these on is day four, not day one.
 */
async function addEnvironmentOverlays() {
  try {
    const data = await api('/api/instructor/environment');
    if (!data.features || !data.features.length) return;

    const byKind = {};
    data.features.forEach((f) => {
      (byKind[f.kind] = byKind[f.kind] || []).push(f);
    });

    Object.entries(byKind).forEach(([kind, features]) => {
      const style = ENV_STYLE[kind] || { color: '#8fa6bd', label: kind };
      const group = L.layerGroup();
      features.forEach((f) => {
        L.circleMarker([f.lat, f.lon], {
          radius: 3.5,
          color: style.color,
          weight: 1,
          fillColor: style.color,
          fillOpacity: 0.75,
        }).bindPopup(
          `<b>${escapeHtml(f.label)}</b><br>` +
          (f.name ? `${escapeHtml(f.name)}<br>` : '') +
          `Range assumed ~${f.range_m} m<br>` +
          `<i>source: ${escapeHtml(f.source || 'unknown')}</i>`
        ).addTo(group);
      });
      layerControl.addOverlay(group, `${style.label} (${features.length})`);
    });
  } catch {
    // Not logged in yet, or no infrastructure loaded. Nothing to add.
  }
}

function clearLayer(name) { layers[name].clearLayers(); }

// ---------------------------------------------------------------- login

function showLogin() {
  $('#login-screen').hidden = false;
  $('#app').hidden = true;
}

async function checkSession() {
  const s = await api('/api/instructor/session');
  if (s.logged_in) { await startApp(s.username); } else { showLogin(); }
}

$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const err = $('#login-error');
  err.hidden = true;
  try {
    const r = await api('/api/instructor/login', {
      method: 'POST',
      body: JSON.stringify({ username: $('#username').value, password: $('#password').value }),
    });
    await startApp(r.username);
  } catch (ex) {
    err.textContent = ex.message;
    err.hidden = false;
  }
});

$('#logout').addEventListener('click', async () => {
  await api('/api/instructor/logout', { method: 'POST' });
  location.reload();
});

// ---------------------------------------------------------------- app start

let courseStart = null, courseEnd = null, participants = [], allDays = [];

// Where the course is being taught. Milwaukee unless an instructor has set
// otherwise; the server is the authority and this is only the local copy.
let courseLocation = null;

async function startApp(username) {
  $('#login-screen').hidden = true;
  $('#app').hidden = false;
  $('#who').textContent = username;

  if (!map) initMap();

  const [mon, people] = await Promise.all([
    api('/api/instructor/monitoring'),
    api('/api/instructor/participants'),
  ]);
  participants = people;
  assignColors(people);
  courseTz = mon.course_timezone || null;

  // Open on wherever the course is being taught, before any data exists to
  // frame the map for us. Views with data refit to it; this is what stops a
  // freshly set-up dashboard opening on the wrong city.
  courseLocation = mon.course_location || courseLocation;
  if (courseLocation && !map._dwellFramed) {
    map.setView([courseLocation.lat, courseLocation.lon], courseLocation.zoom);
    map._dwellFramed = true;
  }

  if (mon.first_ping && mon.last_ping) {
    courseStart = new Date(mon.first_ping);
    courseEnd = new Date(mon.last_ping);
  }

  // Days present in the data, taken from the participant list.
  const days = new Set();
  people.forEach((p) => {
    if (p.first_ping) {
      const a = new Date(p.first_ping), b = new Date(p.last_ping);
      for (let d = new Date(a.toDateString()); d <= b; d.setDate(d.getDate() + 1)) {
        days.add(d.toISOString().slice(0, 10));
      }
    }
  });
  allDays = Array.from(days).sort();

  // Populate selectors.
  $('#participant-select').innerHTML = people.map((p) =>
    `<option value="${escapeHtml(p.participant_id)}">${escapeHtml(p.display_label)} — ${p.ping_count} points</option>`
  ).join('');
  $('#agg-day').innerHTML = '<option value="">Whole course</option>' +
    allDays.map((d) => `<option value="${d}">${fmtDate(d)}</option>`).join('');

  setupClock();
  await showView('live');
}

// ---------------------------------------------------------------- views

let currentView = 'live';

async function showView(name) {
  currentView = name;
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.view === name));
  $$('[data-panel]').forEach((p) => { p.hidden = p.dataset.panel !== name; });
  Object.keys(layers).forEach(clearLayer);
  $('#map-legend').hidden = true;
  stopPlayback();
  // Re-frame the map when arriving at the live view, but not on every tick
  // afterwards, or playback would keep yanking it back.
  if (name === 'live') liveFitted = false;

  if (name === 'live') await renderLive();
  if (name === 'participant') await renderParticipant();
  if (name === 'aggregate') await renderAggregate();
  if (name === 'admin') await renderAdmin();
}

$$('#tabs button').forEach((b) =>
  b.addEventListener('click', () => showView(b.dataset.view)));

// ---------------------------------------------------------------- appearance

/**
 * Two skins over identical data: 'field' reads like a consumer family-safety
 * app, 'console' like a surveillance monitoring station. See the note at the
 * top of style.css for why both ship.
 *
 * Every visual difference lives in CSS custom properties, including the map
 * pins, so switching is a single attribute on <html>. Nothing is re-fetched
 * and nothing is redrawn — which means an instructor can flip skins in the
 * middle of playback without the dots stopping, and that is the version of
 * this demonstration worth having.
 */
function applyTheme(name) {
  if (name === 'console') document.documentElement.setAttribute('data-theme', 'console');
  else document.documentElement.removeAttribute('data-theme');
  try { localStorage.setItem('dwell-theme', name); } catch (e) { /* private mode */ }
  $$('[data-theme-set]').forEach((b) =>
    b.setAttribute('aria-pressed', String(b.dataset.themeSet === name)));
  // The one thing on the map that is drawn rather than fetched.
  if (map) restyleOfflineBasemaps();
}

$$('[data-theme-set]').forEach((b) =>
  b.addEventListener('click', () => applyTheme(b.dataset.themeSet)));

applyTheme(
  (() => {
    try { return localStorage.getItem('dwell-theme') === 'console' ? 'console' : 'field'; }
    catch (e) { return 'field'; }
  })()
);

// ---------------------------------------------------------------- live view

let lastLive = null;        // kept so the map can redraw on zoom without refetching
let liveFitted = false;     // has this view been framed at all yet

// ------------------------------------------------------------ follow mode

/**
 * Keep the map on whoever is currently visible.
 *
 * The obvious implementation — refit on every tick — is unwatchable. Twelve
 * people drifting a few metres would slide the map continuously, and nobody
 * could point at anything on a projector. So the map only moves when it
 * genuinely needs to: when somebody has left a margin inside the view, or when
 * the group has clustered so tightly that the current zoom is well past useful.
 * In between it holds still, which is what makes it possible to talk over.
 *
 * And it always yields to a person. Pan or zoom the map yourself and follow
 * switches off, because a map that argues with the hand on the trackpad during
 * a class is worse than one that never moved.
 */
let followLive = true;
let programmaticMove = false;   // true while the code, not the user, is moving

function setFollow(on) {
  followLive = on;
  const btn = $('#follow');
  btn.setAttribute('aria-pressed', String(on));
  btn.classList.toggle('active', on);
  btn.textContent = on ? '◎ Following' : '◎ Follow';
}

/** Whether the visible people have drifted far enough to justify moving. */
function needsReframe(bounds) {
  // A 15% margin inside the view: somebody reaching the edge of the screen is
  // about to leave it, and waiting until they have is too late to look smooth.
  if (!map.getBounds().pad(-0.15).contains(bounds)) return true;
  // Everyone has bunched into a corner — the view is now far wider than the
  // thing it is showing. Two zoom levels of slack keeps this from oscillating.
  const target = Math.min(16, map.getBoundsZoom(bounds.pad(0.4)));
  return Math.abs(target - map.getZoom()) >= 2;
}

function frameLive(points, force = false) {
  if (!points.length) return;
  const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lon]));
  if (!force && !needsReframe(bounds)) return;
  programmaticMove = true;
  // Belt and braces: if the flight ends up being a no-op the map may never fire
  // moveend, and a stuck flag would stop follow ever releasing to the user.
  clearTimeout(frameLive._release);
  frameLive._release = setTimeout(() => { programmaticMove = false; }, 1500);
  // Flown rather than jumped: a cut leaves the room wondering whether the map
  // moved or the people did. Watching it travel answers that.
  map.flyToBounds(bounds.pad(0.4), { maxZoom: 16, duration: 0.6 });
}


let playTimer = null;

function setupClock() {
  if (!courseStart) return;
  const slider = $('#clock');
  slider.min = 0;
  slider.max = 1000;
  slider.value = 0;
  updateClockReadout();
}

function clockTime() {
  if (!courseStart) return new Date();
  const frac = Number($('#clock').value) / 1000;
  return new Date(courseStart.getTime() + frac * (courseEnd - courseStart));
}

function updateClockReadout() {
  $('#clock-readout').textContent = courseStart ? fmtDateTime(clockTime()) : '—';
}

$('#clock').addEventListener('input', () => {
  liveFitted = false;
  updateClockReadout();
  renderLive();
});
$('#live-window').addEventListener('change', () => { liveFitted = false; renderLive(); });

// Fit is the "put it back" button, so it also resumes following. Somebody who
// panned away and now wants the map recentred is asking for it to stay there.
$('#recentre').addEventListener('click', () => {
  setFollow(true);
  if (lastLive && lastLive.live.visible.length) frameLive(lastLive.live.visible, true);
  else { liveFitted = false; renderLive(); }
});

$('#follow').addEventListener('click', () => {
  setFollow(!followLive);
  if (followLive && lastLive && lastLive.live.visible.length) {
    frameLive(lastLive.live.visible, true);
  }
});

setFollow(true);   // on by default; the button has to say so from the start

$('#play').addEventListener('click', () => {
  if (playTimer) { stopPlayback(); } else { startPlayback(); }
});

function startPlayback() {
  if (!courseStart) return;
  $('#play').textContent = '⏸ Pause';
  const stepSeconds = Number($('#speed').value);
  const totalSeconds = (courseEnd - courseStart) / 1000;
  playTimer = setInterval(() => {
    const slider = $('#clock');
    const next = Number(slider.value) + (stepSeconds / totalSeconds) * 1000;
    if (next >= 1000) { slider.value = 1000; stopPlayback(); }
    else { slider.value = next; }
    updateClockReadout();
    renderLive();
  }, 900);
}

function stopPlayback() {
  if (playTimer) { clearInterval(playTimer); playTimer = null; }
  $('#play').textContent = '▶ Play';
}

async function renderLive() {
  if (!courseStart) {
    $('#monitoring').innerHTML = '<p class="empty">No data loaded yet.</p>';
    return;
  }
  const at = clockTime().toISOString();
  const windowS = $('#live-window').value;

  const [live, mon] = await Promise.all([
    api(`/api/instructor/live?at=${encodeURIComponent(at)}&window=${windowS}`),
    api(`/api/instructor/monitoring?at=${encodeURIComponent(at)}&window=${windowS}`),
  ]);

  lastLive = { live, windowS: Number(windowS) };
  drawLive();

  if (live.visible.length) {
    // The first frame of a view is unconditional — there is nothing sensible to
    // hold still for yet. After that, only when following and only when needed.
    if (!liveFitted) {
      frameLive(live.visible, true);
      liveFitted = true;
    } else if (followLive) {
      frameLive(live.visible);
    }
  }

  const seen = new Set(live.visible.map((p) => p.participant_id));
  $('#roster').innerHTML = participants.map((p) => {
    const on = seen.has(p.participant_id);
    return `<div class="roster-row ${on ? 'on' : 'off'}">
      <span class="swatch" style="background:${colorFor(p.participant_id)}"></span>
      <span class="who">${escapeHtml(p.display_label)}</span>
      <span class="state">${on ? 'tracking' : 'no signal'}</span>
    </div>`;
  }).join('');

  $('#monitoring').innerHTML = `
    <div class="stat"><div class="n">${live.visible_count}</div>
      <div class="l">visible now</div></div>
    <div class="stat"><div class="n">${mon.participants_registered}</div>
      <div class="l">enrolled</div></div>
    <div class="stat"><div class="n">${mon.total_pings.toLocaleString()}</div>
      <div class="l">points stored</div></div>
    <div class="stat"><div class="n">${mon.pings_per_second}</div>
      <div class="l">points / second</div></div>`;
}

/**
 * Draw the dots.
 *
 * Participants standing in the same place — which, during a course session, is
 * most of them — land on exactly the same pixel. Drawn naively, eight people at
 * the venue look like one, and the map contradicts the "12 visible" counter
 * beside it. So anyone within a few pixels of each other is drawn as a single
 * marker carrying the count, and the individual names move into its popup.
 */
function drawLive() {
  if (!lastLive) return;
  const { live, windowS } = lastLive;
  clearLayer('live');

  const clusters = [];
  live.visible.forEach((p) => {
    const pt = map.latLngToContainerPoint([p.lat, p.lon]);
    const near = clusters.find((c) => pt.distanceTo(c.pt) < 26);
    if (near) {
      near.members.push(p);
    } else {
      clusters.push({ pt, lat: p.lat, lon: p.lon, members: [p] });
    }
  });

  clusters.forEach((c) => {
    const n = c.members.length;
    // Fade with the age of the freshest reading, so "seen 12 minutes ago" is
    // visible at a glance rather than hidden in a popup.
    const freshest = Math.min(...c.members.map((m) => m.age_seconds));
    const opacity = Math.max(0.3, 1 - freshest / windowS);

    L.circleMarker([c.lat, c.lon], {
      radius: n > 1 ? Math.min(22, 11 + n * 1.6) : 9,
      color: '#ffffff',
      weight: n > 1 ? 2 : 2.5,
      // A single track keeps its own colour; a pile of people cannot, so it
      // goes neutral and carries the count instead.
      fillColor: n > 1 ? '#8fa6bd' : colorFor(c.members[0].participant_id),
      fillOpacity: opacity,
    }).bindPopup(
      n === 1
        ? `<b>${escapeHtml(c.members[0].label)}</b><br>` +
          `Last seen ${fmtTime(c.members[0].ts)} ` +
          `(${Math.round(c.members[0].age_seconds / 60)} min ago)<br>` +
          `Battery ${c.members[0].battery_pct}% · ` +
          `${escapeHtml(c.members[0].connection || 'unknown')}<br>` +
          `Accuracy ±${Math.round(c.members[0].accuracy_m)} m`
        : `<b>${n} participants here</b><br>` +
          c.members
            .map((m) => `<span style="color:${colorFor(m.participant_id)}">` +
                        `&#9679;</span> ${escapeHtml(m.label)} — ${fmtTime(m.ts)}`)
            .join('<br>')
    ).addTo(layers.live);

    // A soft white pill in the field skin, stencilled text in the person's own
    // colour in the console skin. Both live in style.css; the only thing passed
    // in here is whose colour it is.
    L.marker([c.lat, c.lon], {
      icon: L.divIcon({
        className: '',
        html: n > 1
          ? `<div class="pin-cluster" style="width:${
              Math.min(44, 22 + n * 3.2)}px">${n}</div>`
          : `<div class="pin-label" style="--own:${
              colorFor(c.members[0].participant_id)}">${
              escapeHtml(c.members[0].label)}</div>`,
      }),
    }).addTo(layers.live);
  });
}

// ---------------------------------------------------------------- participant

$('#participant-select').addEventListener('change', renderParticipant);
$('#day-select').addEventListener('change', () => renderParticipantDay());

async function renderParticipant() {
  const pid = $('#participant-select').value;
  if (!pid) return;
  const person = participants.find((p) => p.participant_id === pid);
  const days = [];
  if (person && person.first_ping) {
    const a = new Date(person.first_ping), b = new Date(person.last_ping);
    for (let d = new Date(a.toDateString()); d <= b; d.setDate(d.getDate() + 1)) {
      days.push(d.toISOString().slice(0, 10));
    }
  }
  $('#day-select').innerHTML =
    days.map((d) => `<option value="${d}">${fmtDate(d)}</option>`).join('') +
    '<option value="__week__">— Whole course —</option>';
  await renderParticipantDay();
}

async function renderParticipantDay() {
  const pid = $('#participant-select').value;
  const day = $('#day-select').value;
  if (!pid || !day) return;
  if (day === '__week__') return renderParticipantWeek(pid);

  const d = await api(`/api/instructor/participant/${pid}/day/${day}`);
  clearLayer('participant');
  drawTrail(d.trail_segments, d.stops);
  $('#participant-detail').innerHTML = renderAssessment(d);
}

async function renderParticipantWeek(pid) {
  const w = await api(`/api/instructor/participant/${pid}/week`);
  clearLayer('participant');

  const pts = [];
  w.week_places.forEach((p) => {
    const minutes = p.observed_minutes;
    const recurring = p.day_count >= 2;
    L.circleMarker([p.lat, p.lon], {
      radius: Math.min(34, 7 + Math.sqrt(minutes) * 1.5),
      color: recurring ? '#ffb454' : '#4da3ff',
      weight: recurring ? 3 : 2,
      fillColor: recurring ? '#ffb454' : '#4da3ff',
      fillOpacity: 0.35,
    }).bindPopup(
      `<b>${escapeHtml(p.name)}</b><br>${escapeHtml(p.kind_label || 'unmatched')}<br>` +
      `Seen on ${p.day_count} day(s), ${p.visit_count} visit(s)<br>` +
      `${p.observed_minutes} minutes observed`
    ).addTo(layers.participant);
    pts.push([p.lat, p.lon]);
  });
  if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.25));

  showLegend('Whole course, one participant', [
    ['#ffb454', 'Returned to on 2+ days'],
    ['#4da3ff', 'Visited once'],
  ], 'Circle size shows how long the app observed them there.');

  const a = w.week_assessment;
  $('#participant-detail').innerHTML = `
    <div class="card">
      <h4>Across the whole course</h4>
      <p class="basis">${escapeHtml(w.summary)}</p>
    </div>
    ${renderVerdictCard(a)}
    <h3>Places returned to</h3>
    <div class="place-list">${
      w.recurring_places.length
        ? w.recurring_places.map((p) => `
          <div class="place">
            <div><div>${escapeHtml(p.name)}</div>
              <div class="kind">${escapeHtml(p.kind_label || 'unmatched')} · ${p.day_count} days</div></div>
            <div class="dwell">${p.observed_minutes} min</div>
          </div>`).join('')
        : '<p class="empty">No place was seen on more than one day.</p>'
    }</div>
    ${renderCaveats(a.caveats)}
    ${renderSignature(w.signature)}
    ${renderPatternOfLife(w.pattern_of_life)}
    ${renderGroups(w.groups)}
    ${renderAssociations(w.associations)}`;
}

/**
 * The behavioural signature: a description specific enough to pick one person
 * out of the room, built without ever learning who they are. That gap — highly
 * identifying, entirely nameless — is the point of the card.
 */
function renderSignature(sig) {
  if (!sig || !sig.available) return '';
  const facts = [
    sig.typical_start ? ['Typical first move', sig.typical_start] : null,
    sig.typical_end ? ['Typical last move', sig.typical_end] : null,
    sig.start_spread_hours !== null && sig.start_spread_hours !== undefined
      ? ['Start varies by', `±${sig.start_spread_hours} h`] : null,
    ['Range from centre', `${sig.max_radius_km} km`],
    ['Distance covered', `${sig.distance_travelled_km} km`],
    ['New places per day', sig.new_places_per_day],
  ].filter(Boolean);
  return `
    <h3>Behavioural signature</h3>
    <div class="card">
      <p class="basis">${escapeHtml(sig.narrative)}</p>
      <div class="place-list">${facts.map(([k, v]) => `
        <div class="place">
          <div><div>${escapeHtml(k)}</div></div>
          <div class="dwell">${escapeHtml(String(v))}</div>
        </div>`).join('')}</div>
    </div>`;
}

/**
 * Recurring small groups. Instructor-only, for the same reason association is:
 * it describes other participants' movements, and only instructors were
 * disclosed as able to see those.
 */
function renderGroups(groups) {
  if (!groups || !groups.available) return '';
  return `
    <h3>Recurring groups</h3>
    <div class="card">
      ${groups.groups.map((g) => `
        <div class="place">
          <div><div>${g.members.map((m, i) => `<span class="swatch"
            style="display:inline-block;width:9px;height:9px;border-radius:50%;
            margin-right:4px;background:${colorFor(m)}"></span>${
            escapeHtml(g.labels[i] || m)}`).join(' ')}</div>
            <div class="kind">${g.size} people · ${g.days_together} days</div></div>
          <div class="dwell">${g.minutes_together} min</div>
        </div>`).join('')}
      <p class="basis">${escapeHtml(groups.narrative)}</p>
    </div>
    <div class="caveats">
      <h4>Why this is not proof</h4>
      <ul><li>${escapeHtml(groups.caveat)}</li></ul>
    </div>`;
}

/**
 * The questions an intelligence or security service asks, as opposed to the
 * ones an advertiser asks. None of this requires knowing who somebody is —
 * which is exactly what makes it worth showing.
 */
function renderPatternOfLife(pol) {
  if (!pol || !pol.available) return '';
  return `
    <h3>Pattern of life</h3>
    <div class="card">
      <h4>Predictability</h4>
      <div class="verdict">${escapeHtml(pol.predictability_word)}
        <span class="confidence">${Math.round(pol.predictability * 100)}%</span></div>
      <p class="basis">${escapeHtml(pol.narrative)}</p>
    </div>
    ${pol.anchors && pol.anchors.length ? `
      <div class="card">
        <h4>Recurring places</h4>
        ${pol.anchors.map((a) => `
          <div class="place">
            <div><div>${escapeHtml(a.place)}</div>
              <div class="kind">${a.days_seen} of ${pol.days_observed} days${
                a.overnight_anchor ? ' · overnight anchor'
                : a.typical_time ? ' · usually ' + escapeHtml(a.typical_time) : ''}${
                a.predictable ? ' · predictable' : ''}</div></div>
            <div class="dwell">${a.predictable ? '\u25cf' : ''}</div>
          </div>`).join('')}
      </div>` : ''}`;
}

function renderAssociations(assoc) {
  if (!assoc || !assoc.available) return '';
  const rows = assoc.notable && assoc.notable.length ? assoc.notable : assoc.associations;
  if (!rows || !rows.length) {
    return `<h3>Association</h3>
      <div class="card"><p class="basis">${escapeHtml(assoc.narrative)}</p></div>`;
  }
  return `
    <h3>Association</h3>
    <div class="card">
      ${rows.map((r) => `
        <div class="place">
          <div><div><span class="swatch" style="display:inline-block;width:9px;
            height:9px;border-radius:50%;margin-right:6px;
            background:${colorFor(r.participant_id)}"></span>${escapeHtml(r.label)}</div>
            <div class="kind">${escapeHtml(r.strength)} · ${r.days_together} days</div></div>
          <div class="dwell">${r.shared_minutes} min</div>
        </div>`).join('')}
      <p class="basis">${escapeHtml(assoc.narrative)}</p>
    </div>
    <div class="caveats">
      <h4>Why this is not proof</h4>
      <ul><li>${escapeHtml(assoc.caveat)}</li></ul>
    </div>`;
}

function drawTrail(segments, stops) {
  const pts = [];
  const trailColor = colorFor($('#participant-select').value);

  // Each segment is a separate window when the app was open. They are drawn
  // as separate lines, never joined, because joining them would invent a route
  // across a gap nobody observed.
  segments.forEach((seg) => {
    const line = seg.map((p) => [p.lat, p.lon]);
    if (line.length > 1) {
      L.polyline(line, { color: trailColor, weight: 3, opacity: 0.8 })
        .addTo(layers.participant);
    }
    line.forEach((p) => pts.push(p));
  });

  stops.forEach((s) => {
    L.circleMarker([s.lat, s.lon], {
      radius: Math.min(30, 8 + Math.sqrt(s.observed_minutes) * 2.2),
      color: '#ffb454', weight: 3,
      fillColor: '#ffb454', fillOpacity: 0.3,
    }).bindPopup(
      `<b>${escapeHtml(s.poi_name || 'Unmatched stop')}</b><br>` +
      `${escapeHtml(s.poi_kind_label || 'no nearby place found')}<br>` +
      `${fmtTime(s.start)} – ${fmtTime(s.end)}<br>` +
      `<b>${s.observed_minutes} min observed</b><br>` +
      `Likely activity: ${escapeHtml(s.activity_guess)}` +
      (s.poi_alternatives && s.poi_alternatives.length
        ? `<br><i>Could also be: ${s.poi_alternatives.map((a) =>
            escapeHtml(a.name)).join(', ')}</i>` : '')
    ).addTo(layers.participant);
    pts.push([s.lat, s.lon]);
  });

  if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.2));

  showLegend('One participant, one day', [
    [trailColor, 'Movement'],
    ['#ffb454', 'Stop (circle size = observed dwell)'],
  ], 'Breaks in the line are gaps the phone did not report — usually the OS ' +
     'suspending the app or throttling while somebody sat still.');
}

function renderVerdictCard(a) {
  const f = a.findings || {};
  const seg = f.segment || {};
  const vl = f.visitor_or_local || {};
  const area = f.area_character || {};
  const rhythm = f.rhythm || {};
  return `
    <div class="card">
      <h4>What a marketing system would conclude</h4>
      <div class="verdict">${escapeHtml(seg.value || 'unknown')}
        <span class="confidence">${escapeHtml(seg.confidence_word || '')}
          ${seg.confidence != null ? Math.round(seg.confidence * 100) + '%' : ''}</span></div>
      <p class="basis">${escapeHtml(seg.basis || '')}</p>
    </div>
    <div class="card">
      <h4>Visitor or local</h4>
      <div class="verdict">${escapeHtml(vl.value || 'unknown')}
        <span class="confidence">${vl.confidence != null ? Math.round(vl.confidence * 100) + '%' : ''}</span></div>
      <p class="basis">${escapeHtml(vl.basis || '')}</p>
    </div>
    ${area.value ? `<div class="card">
      <h4>Character of the area</h4>
      <div class="verdict">${escapeHtml(area.value)}</div>
      <p class="basis">${escapeHtml(area.basis || '')}</p>
    </div>` : ''}
    ${rhythm.first_seen_local ? `<div class="card">
      <h4>Daily rhythm</h4>
      <p class="basis">${
        rhythm.left_anchor_local
          ? `Left at ${escapeHtml(rhythm.left_anchor_local)}, back by
             ${escapeHtml(rhythm.returned_local)} — ${rhythm.hours_out} hours out,
             across ${rhythm.distinct_places} distinct places and
             ${rhythm.stop_count} stops.`
          : `Recorded across ${rhythm.distinct_places} distinct places and
             ${rhythm.stop_count} stops.`
      }</p>
    </div>` : ''}`;
}

/**
 * What else could have seen them.
 *
 * The point of this block is corroboration, not surveillance-spotting: a phone
 * ping alone places a device and can be argued with, whereas a ping that agrees
 * with a camera and a card terminal cannot. That is how a location feed becomes
 * something an agency or a broker can act on.
 */
function renderExposure(ex) {
  if (!ex || !ex.available) return '';

  const kinds = Object.entries(ex.passed || {});
  const corroborated = (ex.stops || []).filter((s) => s.source_kinds.length >= 2);

  return `
    <h3>What else was watching</h3>
    <div class="card">
      <h4>Sources the route passed</h4>
      ${kinds.map(([k, v]) => `
        <div class="place">
          <div><div>${escapeHtml(v.label)}</div>
            <div class="kind">${escapeHtml(v.observes)}</div></div>
          <div class="dwell">${v.count}</div>
        </div>`).join('')}
      <p class="basis">${escapeHtml(ex.narrative)}</p>
    </div>

    ${corroborated.length ? `
      <div class="card">
        <h4>Stops more than one source could confirm</h4>
        ${corroborated.slice(0, 4).map((s) => `
          <div class="place">
            <div><div>${escapeHtml(s.poi_name || 'Unidentified stop')}</div>
              <div class="kind">${escapeHtml(s.verdict)}</div></div>
            <div class="dwell">${s.source_count}&times;</div>
          </div>`).join('')}
        <p class="basis">A phone ping places a device, not a person, and can be
          argued with. Several independent sources agreeing at the same place and
          minute cannot.</p>
      </div>` : ''}

    ${(ex.caveats || []).length ? `<div class="caveats">
      <h4>What this does not prove</h4>
      <ul>${ex.caveats.map((c) => `<li>${escapeHtml(c)}</li>`).join('')}</ul>
    </div>` : ''}`;
}

/**
 * What was happening nearby, from public reporting.
 *
 * Presented as possible explanations, never as findings. Being two hundred
 * metres from a protest is not attending it, and the difference between an
 * analyst and a careless one is entirely in that distinction.
 */
function renderContext(ctx) {
  if (!ctx || !ctx.available) return '';
  const rows = ctx.matches || [];
  const wide = ctx.city_wide || [];
  if (!rows.length && !wide.length) return '';
  return `
    <h3>What was happening nearby</h3>
    <div class="card">
      ${rows.map((m) => `
        <div class="place">
          <div><div>${escapeHtml(m.title)}</div>
            <div class="kind">${escapeHtml(m.kind)} · ${m.distance_m} m from
              ${escapeHtml(m.stop_place || 'a stop')}${
              m.source ? ' · ' + escapeHtml(m.source) : ''}</div></div>
        </div>`).join('')}
      ${wide.map((m) => `
        <div class="place">
          <div><div>${escapeHtml(m.title)}</div>
            <div class="kind">${escapeHtml(m.kind)} · city-wide</div></div>
        </div>`).join('')}
      <p class="basis">${escapeHtml(ctx.narrative)}</p>
    </div>
    ${ctx.caveat ? `<div class="caveats">
      <h4>Leads, not findings</h4>
      <ul><li>${escapeHtml(ctx.caveat)}</li></ul>
    </div>` : ''}`;
}

function renderCaveats(caveats) {
  if (!caveats || !caveats.length) return '';
  return `<div class="caveats">
    <h4>Where this is shaky</h4>
    <ul>${caveats.map((c) => `<li>${escapeHtml(c)}</li>`).join('')}</ul>
  </div>`;
}

function renderAssessment(d) {
  const a = d.assessment;
  const cov = a.coverage || {};
  const cmp = d.comparison || {};
  const agency = d.agency_step || {};

  return `
    <div class="stats">
      <div class="stat"><div class="n">${d.point_count}</div><div class="l">points</div></div>
      <div class="stat"><div class="n">${d.stops.length}</div><div class="l">stops</div></div>
      <div class="stat"><div class="n">${cov.observed_minutes || 0}</div><div class="l">minutes seen</div></div>
      <div class="stat"><div class="n">${cov.coverage_pct || 0}%</div><div class="l">of the day</div></div>
    </div>

    <div class="card">
      <h4>How much came from the background</h4>
      <p class="basis">${
        cov.background_pct != null
          ? `<strong>${cov.background_pct}% of these ${cov.point_count} location
             points were collected while the app was not open.</strong> The
             participant opened it ${cov.session_count || 0} time(s) that day.
             Everything below was worked out from that — and most of it was
             gathered while nobody was looking at the screen.`
          : `The app recorded ${cov.point_count || 0} location points across a
             ${cov.span_hours || 0}-hour span.`
      }</p>
    </div>

    ${renderVerdictCard(a)}

    <h3>Stops</h3>
    <div class="place-list">${
      d.places.length
        ? d.places.map((p) => `
          <div class="place">
            <div><div>${escapeHtml(p.name)}</div>
              <div class="kind">${escapeHtml(p.kind_label || 'unmatched')} · ${escapeHtml(p.activity_guess)}</div></div>
            <div class="dwell">${p.observed_minutes} min</div>
          </div>`).join('')
        : '<p class="empty">No stops detected on this day.</p>'
    }</div>

    ${cmp.narrative ? `<div class="card">
      <h4>Compared with earlier days</h4>
      <p class="basis">${escapeHtml(cmp.narrative)}</p>
    </div>` : ''}

    ${renderExposure(d.exposure)}
    ${renderContext(d.context)}

    ${renderCaveats(a.caveats)}

    ${agency.title ? `<div class="agency">
      <h4>${escapeHtml(agency.title)}</h4>
      <p>${escapeHtml(agency.detail)}</p>
      <p><strong>Had you done this already:</strong>
        ${escapeHtml(agency.what_would_have_changed)}</p>
    </div>` : ''}`;
}

// ---------------------------------------------------------------- aggregate

$('#k-slider').addEventListener('input', () => {
  $('#k-out').textContent = $('#k-slider').value;
  renderAggregate();
});
$('#resolution').addEventListener('change', renderAggregate);
$('#agg-day').addEventListener('change', renderAggregate);

async function renderAggregate() {
  const k = $('#k-slider').value;
  const res = $('#resolution').value;
  const day = $('#agg-day').value;

  const d = await api(`/api/instructor/aggregate?k=${k}&resolution=${res}` +
                      (day ? `&day=${day}` : ''));
  clearLayer('aggregate');

  const max = d.cells.reduce((m, c) => Math.max(m, c.participant_count), 1);
  const pts = [];
  d.cells.forEach((c) => {
    const t = c.participant_count / max;
    L.polygon(c.boundary.map((p) => [p[1], p[0]]), {
      color: '#4da3ff',
      weight: 1,
      fillColor: t > 0.66 ? '#ff6b6b' : t > 0.33 ? '#ffb454' : '#4da3ff',
      fillOpacity: 0.25 + 0.45 * t,
    }).bindPopup(
      `<b>${c.participant_count} participants</b><br>${c.ping_count} location points`
    ).addTo(layers.aggregate);
    c.boundary.forEach((p) => pts.push([p[1], p[0]]));
  });
  if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.15));

  showLegend('Whole course, everybody', [
    ['#ff6b6b', 'Busiest hexagons'],
    ['#ffb454', 'Moderate'],
    ['#4da3ff', 'Quieter'],
  ], `${d.cells_suppressed} hexagon(s) hidden by the k-anonymity threshold.`);

  $('#aggregate-detail').innerHTML = `
    <div class="stats">
      <div class="stat"><div class="n">${d.cells_shown}</div><div class="l">hexagons shown</div></div>
      <div class="stat"><div class="n">${d.cells_suppressed}</div><div class="l">hidden</div></div>
      <div class="stat"><div class="n">${d.total_participants}</div><div class="l">participants</div></div>
      <div class="stat"><div class="n">${(d.total_pings || 0).toLocaleString()}</div><div class="l">points</div></div>
    </div>
    <div class="card">
      <h4>What the threshold is doing</h4>
      <p class="basis">${escapeHtml(d.explanation)}</p>
    </div>`;
}

// ---------------------------------------------------------------- admin

async function renderAdmin() {
  const [mon, log] = await Promise.all([
    api('/api/instructor/monitoring'),
    api('/api/instructor/audit'),
  ]);
  $('#admin-stats').innerHTML = `
    <div class="stat"><div class="n">${mon.participants_registered}</div><div class="l">participants</div></div>
    <div class="stat"><div class="n">${mon.total_pings.toLocaleString()}</div><div class="l">location points</div></div>
    <div class="stat"><div class="n">${mon.days_of_data}</div><div class="l">days of data</div></div>
    <div class="stat"><div class="n">${mon.retention_days}</div><div class="l">day retention</div></div>`;
  $('#audit').innerHTML = log.map((r) =>
    `<div>${escapeHtml(r.ts.slice(0, 19).replace('T', ' '))} · ${escapeHtml(r.actor)} · ` +
    `${escapeHtml(r.action)}${r.detail ? ' · ' + escapeHtml(r.detail) : ''}</div>`).join('')
    || '<p class="empty">Nothing recorded yet.</p>';
  await renderCourseLocation();
}

// ------------------------------------------------------- course location

/**
 * Where the course is being taught.
 *
 * Everything downstream reads this: where the map opens, and which timezone
 * times are read out in before any participant phone has reported one. Getting
 * it wrong is not subtle — the dashboard opens on the wrong city — but it is
 * only obvious to somebody who knows what they are looking at, so the current
 * value is shown plainly rather than hidden behind a settings screen.
 */
async function renderCourseLocation() {
  const { location, timezones } = await api('/api/instructor/course');
  courseLocation = location;

  $('#course-current').innerHTML =
    `<b>${escapeHtml(location.name)}</b>` +
    `<div class="basis">${location.lat}, ${location.lon} · ` +
    `${escapeHtml(location.timezone)}${
      location.is_default ? ' · still the built-in default' : ''}</div>`;

  const tzSelect = $('#course-tz');
  const options = timezones.includes(location.timezone)
    ? timezones : [location.timezone, ...timezones];
  tzSelect.innerHTML = options.map((t) =>
    `<option value="${escapeHtml(t)}"${
      t === location.timezone ? ' selected' : ''}>${escapeHtml(t)}</option>`).join('');
}

function courseMessage(text, ok = true) {
  const out = $('#course-result');
  out.textContent = text;
  out.style.color = ok ? 'var(--good)' : 'var(--danger)';
  out.hidden = false;
}

/** Move the map to the newly set location, so the change is visibly real. */
async function afterLocationSaved(location) {
  courseLocation = location;
  map.setView([location.lat, location.lon], location.zoom);
  $('#course-results').innerHTML = '';
  $('#course-search').value = '';
  await renderCourseLocation();
  courseMessage(`Course location set to ${location.name}. The map has moved ` +
                `there, and times are now shown in ${location.timezone}.`);
}

$('#course-lookup').addEventListener('click', async () => {
  const q = $('#course-search').value.trim();
  if (!q) return courseMessage('Type a town or city to look up.', false);
  $('#course-results').innerHTML = '<p class="empty">Looking up…</p>';
  try {
    const { results, error } = await api(
      `/api/instructor/course/geocode?q=${encodeURIComponent(q)}`);
    if (error || !results.length) {
      $('#course-results').innerHTML = '';
      // The manual entry path always works, so point at it rather than
      // leaving somebody stuck behind a network they cannot fix.
      $('#course-manual').open = true;
      return courseMessage(error || `Nothing found for '${q}'.`, false);
    }
    $('#course-result').hidden = true;
    $('#course-results').innerHTML = results.map((r, i) =>
      `<button class="pick" data-pick="${i}">${escapeHtml(r.short_name)}
        <div class="where">${escapeHtml(r.name)}</div></button>`).join('');
    $$('#course-results [data-pick]').forEach((b) =>
      b.addEventListener('click', async () => {
        const r = results[Number(b.dataset.pick)];
        // The lookup gives coordinates, not a timezone — nothing in the
        // response knows one. Whatever is selected below is used, which is why
        // the current zone stays selected by default rather than resetting.
        try {
          const { location } = await api('/api/instructor/course', {
            method: 'POST',
            body: JSON.stringify({
              name: r.short_name, lat: r.lat, lon: r.lon,
              timezone: $('#course-tz').value, zoom: 14,
            }),
          });
          await afterLocationSaved(location);
        } catch (ex) { courseMessage(ex.message, false); }
      }));
  } catch (ex) {
    $('#course-results').innerHTML = '';
    courseMessage(ex.message, false);
  }
});

$('#course-save').addEventListener('click', async () => {
  const raw = $('#course-latlon').value.trim();
  const [latText, lonText] = raw.split(/[,\s]+/);
  if (!latText || !lonText) {
    return courseMessage('Enter latitude and longitude, as in 39.1031, -84.5120.',
                         false);
  }
  try {
    const { location } = await api('/api/instructor/course', {
      method: 'POST',
      body: JSON.stringify({
        name: $('#course-name').value.trim() || raw,
        lat: Number(latText), lon: Number(lonText),
        timezone: $('#course-tz').value, zoom: 14,
      }),
    });
    await afterLocationSaved(location);
  } catch (ex) { courseMessage(ex.message, false); }
});

$('#course-reset').addEventListener('click', async () => {
  try {
    const { location } = await api('/api/instructor/course', {
      method: 'POST', body: JSON.stringify({ reset: true }),
    });
    await afterLocationSaved(location);
  } catch (ex) { courseMessage(ex.message, false); }
});

/**
 * Import wardrive or infrastructure data.
 *
 * The file is read in the browser and posted to our own server. It is never
 * sent to WiGLE or anywhere else — the whole reason this is an upload rather
 * than a lookup is that querying an outside service would mean sending
 * participants' locations to it, which the consent screen rules out.
 */
$('#import-btn').addEventListener('click', async () => {
  const out = $('#import-result');
  const input = $('#import-file');
  const file = input.files && input.files[0];
  if (!file) {
    out.textContent = 'Choose a file first.';
    out.hidden = false;
    return;
  }
  out.textContent = `Reading ${file.name}…`;
  out.hidden = false;
  try {
    const content = await file.text();
    const label = ($('#import-label').value || file.name.replace(/\.[^.]+$/, ''))
      .trim().slice(0, 40);
    const r = await api('/api/instructor/environment/import', {
      method: 'POST',
      body: JSON.stringify({ content, source: label }),
    });
    const kinds = Object.entries(r.kinds || {})
      .map(([k, n]) => `${n} ${k}`).join(', ');
    out.textContent = `Imported ${r.imported} features (${kinds}). ` +
                      `Reload to see the new layer.`;
    input.value = '';
  } catch (ex) {
    out.textContent = ex.message;
  }
});

$('#wipe-btn').addEventListener('click', async () => {
  const confirmText = $('#wipe-confirm').value;
  const out = $('#wipe-result');
  try {
    const r = await api('/api/instructor/wipe', {
      method: 'POST', body: JSON.stringify({ confirm: confirmText }),
    });
    out.textContent = `Deleted ${r.participants_deleted} participants and ` +
                      `${r.pings_deleted} location points.`;
    out.hidden = false;
    $('#wipe-confirm').value = '';
    await renderAdmin();
  } catch (ex) {
    out.textContent = ex.message;
    out.hidden = false;
  }
});

// ---------------------------------------------------------------- legend

function showLegend(title, entries, note) {
  const el = $('#map-legend');
  el.innerHTML = `<h4>${escapeHtml(title)}</h4>` +
    entries.map(([c, label]) =>
      `<div><span class="swatch" style="background:${c}"></span>${escapeHtml(label)}</div>`).join('') +
    (note ? `<div style="margin-top:7px;color:var(--ink-dim)">${escapeHtml(note)}</div>` : '');
  el.hidden = false;
}

// ---------------------------------------------------------------- go

checkSession().catch(() => showLogin());
