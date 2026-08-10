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

const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const fmtDate = (iso) => new Date(iso).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
const fmtDateTime = (d) => d.toLocaleString([], {
  weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
});

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------------------------------------------------------------- map setup

let map, baseSatellite, baseStreet, labelLayer;
const layers = {};      // one layer group per view

function initMap() {
  map = L.map('map', { zoomControl: true, preferCanvas: true })
         .setView([30.2672, -97.7431], 14);

  // Esri World Imagery: free to use with attribution, and — unlike Google's
  // tiles — needs no API key, no billing account and no per-load charge.
  baseSatellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' });

  // Place and road names, drawn over the imagery so the map stays readable.
  labelLayer = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, opacity: 0.9 });

  baseStreet = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' });

  baseSatellite.addTo(map);
  labelLayer.addTo(map);

  L.control.layers(
    { 'Satellite': baseSatellite, 'Street map': baseStreet },
    { 'Place names': labelLayer },
    { position: 'topright' }
  ).addTo(map);

  ['live', 'participant', 'aggregate'].forEach((v) => {
    layers[v] = L.layerGroup().addTo(map);
  });
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

async function showView(name) {
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.view === name));
  $$('[data-panel]').forEach((p) => { p.hidden = p.dataset.panel !== name; });
  Object.keys(layers).forEach(clearLayer);
  $('#map-legend').hidden = true;
  stopPlayback();

  if (name === 'live') await renderLive();
  if (name === 'participant') await renderParticipant();
  if (name === 'aggregate') await renderAggregate();
  if (name === 'admin') await renderAdmin();
}

$$('#tabs button').forEach((b) =>
  b.addEventListener('click', () => showView(b.dataset.view)));

// ---------------------------------------------------------------- live view

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

$('#clock').addEventListener('input', () => { updateClockReadout(); renderLive(); });
$('#live-window').addEventListener('change', renderLive);

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

  clearLayer('live');
  live.visible.forEach((p) => {
    // Fade the dot as the reading gets older, so "last seen 12 minutes ago"
    // is visible at a glance rather than hidden in a popup.
    const age = p.age_seconds / Number(windowS);
    L.circleMarker([p.lat, p.lon], {
      radius: 9,
      color: '#ffffff', weight: 2,
      fillColor: '#4da3ff',
      fillOpacity: Math.max(0.25, 1 - age),
    }).bindPopup(
      `<b>${escapeHtml(p.label)}</b><br>Last seen ${fmtTime(p.ts)}` +
      ` (${Math.round(p.age_seconds / 60)} min ago)<br>` +
      `Battery ${p.battery_pct}% · ${escapeHtml(p.connection || 'unknown')}<br>` +
      `Accuracy ±${Math.round(p.accuracy_m)} m`
    ).addTo(layers.live);

    L.marker([p.lat, p.lon], {
      icon: L.divIcon({
        className: '', html: `<div style="color:#fff;font:600 11px system-ui;
          text-shadow:0 1px 3px #000;white-space:nowrap;transform:translate(12px,-8px)">
          ${escapeHtml(p.label)}</div>`,
      }),
    }).addTo(layers.live);
  });

  if (live.visible.length && !map._userMoved) {
    map.fitBounds(L.latLngBounds(live.visible.map((p) => [p.lat, p.lon])).pad(0.4),
      { maxZoom: 16 });
  }

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
      `<b>${escapeHtml(p.name)}</b><br>${escapeHtml(p.kind || 'unmatched')}<br>` +
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
              <div class="kind">${escapeHtml(p.kind || 'unmatched')} · ${p.day_count} days</div></div>
            <div class="dwell">${p.observed_minutes} min</div>
          </div>`).join('')
        : '<p class="empty">No place was seen on more than one day.</p>'
    }</div>
    ${renderCaveats(a.caveats)}`;
}

function drawTrail(segments, stops) {
  const pts = [];

  // Each segment is a separate window when the app was open. They are drawn
  // as separate lines, never joined, because joining them would invent a route
  // across a gap nobody observed.
  segments.forEach((seg) => {
    const line = seg.map((p) => [p.lat, p.lon]);
    if (line.length > 1) {
      L.polyline(line, { color: '#4da3ff', weight: 3, opacity: 0.75 })
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
      `${escapeHtml(s.poi_kind || 'no nearby place found')}<br>` +
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
    ['#4da3ff', 'Movement'],
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
      <p class="basis">Active from ${escapeHtml(rhythm.first_seen_local)} to
        ${escapeHtml(rhythm.last_seen_local)} — a span of
        ${rhythm.active_span_hours} hours, across ${rhythm.distinct_places}
        distinct place(s) and ${rhythm.stop_count} stop(s).</p>
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
              <div class="kind">${escapeHtml(p.kind || 'unmatched')} · ${escapeHtml(p.activity_guess)}</div></div>
            <div class="dwell">${p.observed_minutes} min</div>
          </div>`).join('')
        : '<p class="empty">No stops detected on this day.</p>'
    }</div>

    ${cmp.narrative ? `<div class="card">
      <h4>Compared with earlier days</h4>
      <p class="basis">${escapeHtml(cmp.narrative)}</p>
    </div>` : ''}

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
}

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
    (note ? `<div style="margin-top:7px;color:#9fb0c2">${escapeHtml(note)}</div>` : '');
  el.hidden = false;
}

// ---------------------------------------------------------------- go

checkSession().catch(() => showLogin());
