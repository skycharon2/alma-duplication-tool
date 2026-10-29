/* Offline-only geometry context when Aladin/CDS imagery cannot initialize.
 * Spherical gnomonic projection; no optical pixels or scientific judgement. */
(function(root) {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const RAD = Math.PI / 180;
  const ARCSEC = 180 * 3600 / Math.PI;
  function offset(origin, center) {
    if (!Array.isArray(origin) || !Array.isArray(center)) return null;
    if (![...origin, ...center].every(Number.isFinite)) return null;
    const ra0 = origin[0] * RAD, dec0 = origin[1] * RAD;
    const ra = center[0] * RAD, dec = center[1] * RAD;
    const dra = Math.atan2(Math.sin(ra - ra0), Math.cos(ra - ra0));
    const cosine = Math.sin(dec0) * Math.sin(dec) + Math.cos(dec0) * Math.cos(dec) * Math.cos(dra);
    if (cosine <= 0) return null; // outside this local tangent plane
    return [-(Math.cos(dec) * Math.sin(dra) / cosine) * ARCSEC,
            -(Math.cos(dec0) * Math.sin(dec) - Math.sin(dec0) * Math.cos(dec) * Math.cos(dra)) / cosine * ARCSEC];
  }
  function render(container, state, options = {}) {
    const rows = state.rows().filter(row => row.spatial?.available && row.spatial.center);
    const positions = rows.map(row => ({row, xy: offset(state.origin, row.spatial.center)}))
      .filter(item => item.xy && item.xy.every(Number.isFinite));
    const selected = state.selected();
    const shown = positions.filter(item => options.others || item.row.id === selected);
    const maxExtent = Math.max(10, ...shown.map(({row, xy}) =>
      Math.hypot(...xy) + (Number.isFinite(row.spatial.radius_arcsec) ? Math.max(0, row.spatial.radius_arcsec) : 0)));
    const width = 600, height = 390, scale = 0.39 * Math.min(width, height) / maxExtent;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Geometry only: saved target and candidate beam locations; no optical reference image');
    function shape(name, attributes, parent = svg) {
      const node = document.createElementNS(NS, name);
      for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
      parent.append(node);
      return node;
    }
    shape('rect', {x: 0, y: 0, width, height, fill: '#071016'});
    const cx = width / 2, cy = height / 2;
    const sorted = shown.sort((a, b) => Number(a.row.id === selected) - Number(b.row.id === selected));
    for (const {row, xy} of sorted) {
      const x = cx + xy[0] * scale, y = cy + xy[1] * scale;
      const highlight = row.id === selected;
      const color = highlight ? '#ff525e' : row.source === 'QUEUE' ? '#d78b36' : '#45a9eb';
      const radius = row.spatial.radius_arcsec;
      if (options.beams && Number.isFinite(radius) && radius > 0) {
        shape('circle', {cx:x, cy:y, r:radius * scale, fill:'none', stroke:color,
                         'stroke-width':highlight ? 2 : 1.25});
      }
      shape('circle', {cx:x, cy:y, r:highlight ? 4 : 3, fill:color});
    }
    // Central cross is the proposed target, never a candidate detection.
    shape('path', {d:`M ${cx-8} ${cy} H ${cx+8} M ${cx} ${cy-8} V ${cy+8}`,
                   stroke:'#30eee2', 'stroke-width':2, fill:'none'});
    const legend = shape('text', {x:14, y:24, fill:'#e4eff7', 'font-size':14});
    legend.textContent = 'Recorded geometry only · optical image unavailable';
    const note = shape('text', {x:14, y:height-15, fill:'#afc2ce', 'font-size':12});
    note.textContent = `Tangent-plane view (ICRS) · not a substitute for recorded numerical evidence`;
    container.replaceChildren(svg);
    return shown.length;
  }
  root.renderReportSkyFallback = render;
  if (typeof module !== 'undefined' && module.exports) module.exports = {offset, render};
})(typeof window === 'undefined' ? globalThis : window);
