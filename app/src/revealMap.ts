/**
 * Builds the HTML for the little map inside the daily reveal.
 *
 * This is a WebView running Leaflet rather than a native map component, for one
 * practical reason: the native map library needs a Google Maps API key and a
 * billing account on Android. Leaflet with Esri's imagery needs neither, on
 * either platform, which matters when the people running a course should not
 * have to set up cloud billing to show a map.
 *
 * If the phone is offline the map will not draw, but every other part of the
 * reveal — the stops, the times, the inferences — still works, because it comes
 * from data already fetched.
 */

type Segment = { lat: number; lon: number; ts: string }[];
type Stop = {
  lat: number;
  lon: number;
  poi_name: string;
  poi_kind_label: string;
  observed_minutes: number;
  start: string;
  end: string;
};

export function buildRevealMapHtml(segments: Segment[], stops: Stop[]): string {
  const data = JSON.stringify({ segments, stops }).replace(/</g, '\\u003c');

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  html, body, #map { margin:0; padding:0; height:100%; background:#10151c; }
  .leaflet-popup-content-wrapper, .leaflet-popup-tip { background:#1f2935; color:#e8eef5; }
  .leaflet-popup-content { font: 13px system-ui; }
  .leaflet-popup-content b { color:#4da3ff; }
  #offline { color:#9fb0c2; font:14px system-ui; padding:24px; text-align:center; }
</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function () {
  var D = ${data};

  if (typeof L === 'undefined') {
    document.getElementById('map').innerHTML =
      '<div id="offline">The map needs an internet connection.<br>' +
      'Everything else below still works.</div>';
    return;
  }

  var map = L.map('map', { zoomControl: true, attributionControl: true });

  L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Imagery &copy; Esri' }
  ).addTo(map);

  L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, opacity: 0.9 }
  ).addTo(map);

  var bounds = [];

  // Each segment is drawn separately. Joining them would draw a route across a
  // gap the phone never reported, which would be a small lie on a screen whose
  // entire purpose is showing people what was really recorded.
  D.segments.forEach(function (seg) {
    var line = seg.map(function (p) { return [p.lat, p.lon]; });
    if (line.length > 1) {
      L.polyline(line, { color: '#4da3ff', weight: 4, opacity: 0.85 }).addTo(map);
    }
    line.forEach(function (p) { bounds.push(p); });
  });

  D.stops.forEach(function (s) {
    L.circleMarker([s.lat, s.lon], {
      radius: Math.min(30, 8 + Math.sqrt(s.observed_minutes) * 2.2),
      color: '#ffb454', weight: 3, fillColor: '#ffb454', fillOpacity: 0.32
    }).bindPopup(
      '<b>' + (s.poi_name || 'Unidentified stop') + '</b><br>' +
      (s.poi_kind_label || '') + '<br>' +
      s.observed_minutes + ' minutes'
    ).addTo(map);
    bounds.push([s.lat, s.lon]);
  });

  if (bounds.length) {
    map.fitBounds(L.latLngBounds(bounds).pad(0.2));
  } else {
    map.setView([0, 0], 2);
  }
})();
</script>
</body>
</html>`;
}
