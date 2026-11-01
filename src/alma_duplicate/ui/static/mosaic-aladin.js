/* Optional OT-style sky context for the proposed Mosaic. This never edits OT rows,
   performs an Archive query, or contributes to the scientific assessment. */
(function (root) {
  'use strict';
  const RAD = Math.PI / 180;
  const DSS = 'https://skies.esac.esa.int/DSSColor/';
  function separation(a, b) {
    const d1 = a[1] * RAD, d2 = b[1] * RAD;
    const delta = (a[0] - b[0]) * RAD;
    return Math.acos(Math.max(-1, Math.min(1,
      Math.sin(d1) * Math.sin(d2) + Math.cos(d1) * Math.cos(d2) * Math.cos(delta)
    ))) / RAD;
  }
  function fieldOfView(points, centre, radiusArcsec = 0, aspect = 1) {
    const edge = Math.max(0.002, ...points.map(point => separation(point, centre)));
    return Math.min(120, Math.max(0.015,
      2.8 * (edge + radiusArcsec / 3600) * Math.max(1, aspect)));
  }
  function frequency(form, geometry) {
    const selected = form.querySelector('[data-preview-frequency]')?.value;
    if (!selected) return null;
    const value = name => form.elements.namedItem(name)?.value ?? '';
    if (selected === 'continuum') {
      const z = form.querySelector('[name=frequency_local_redshift]')
        ? value('continuum_redshift') : value('redshift');
      return geometry.sky(value('representative'), value('representative_unit') || 'GHz',
        value('representative_kind'), z);
    }
    const z = form.querySelector('[name=frequency_local_redshift]')
      ? value(selected + '_redshift') : value(selected + '_redshift') || value('redshift');
    return geometry.sky(value(selected + '_center'), value(selected + '_center_unit') || 'GHz',
      value(selected + '_center_kind'), z);
  }
  function calculateBeam(form, geometry) {
    const f = frequency(form, geometry);
    const diameter = form.elements.namedItem('mosaic_array')?.value === '7m' ? 7 : 12;
    const result = f ? geometry.radius(f, diameter) : 0;
    return Number.isFinite(result) && result > 0 && result < 90 * 3600 ? result : 0;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {separation, fieldOfView};
  }
  if (typeof window === 'undefined') return;
  root.initializeMosaicSkyViewer = function (form) {
    const holder = form.querySelector('[data-mosaic-aladin]');
    if (!holder || holder.dataset.initialized) return;
    holder.dataset.initialized = '1';
    const ras = JSON.parse(form.querySelector('[data-mosaic-points]').textContent);
    const decs = JSON.parse(form.querySelector('[data-mosaic-decs]').textContent);
    const points = ras.map((ra, i) => [ra, decs[i]]);
    if (!points.length) return; // Do not initialize WebGL for an empty upload.
    const canvas = form.querySelector('[data-mosaic-canvas]');
    const stack = form.querySelector('[data-mosaic-map-stack]');
    const status = form.querySelector('[data-mosaic-imagery-status]');
    const retry = form.querySelector('[data-mosaic-imagery-retry]');
    const toggle = form.querySelector('[data-mosaic-geometry-toggle]');
    const geometry = root.MosaicPreviewGeometry;
    if (!geometry) { status.textContent = 'Geometry preview is available; map helpers unavailable.'; return; }
    const rad = Math.PI / 180;
    const vector = points.reduce((sum, [a, d]) => [
      sum[0] + Math.cos(d * rad) * Math.cos(a * rad),
      sum[1] + Math.cos(d * rad) * Math.sin(a * rad),
      sum[2] + Math.sin(d * rad)
    ], [0, 0, 0]);
    const centre = Math.hypot(...vector) > 1e-8
      ? [Math.atan2(vector[1], vector[0]) / rad, Math.atan2(vector[2], Math.hypot(vector[0], vector[1])) / rad]
      : points[0];
    const normalizedCentre = [((centre[0] % 360) + 360) % 360, centre[1]];
    let viewer, A, beams, catalog, loading = false, visible = false;
    const valid = () => holder.isConnected && form.isConnected;
    const fit = () => fieldOfView(points, centre, calculateBeam(form, geometry),
      Math.max(1, holder.clientWidth / Math.max(1, holder.clientHeight)));
    function update() {
      if (!viewer || !valid()) return;
      beams.removeAll();
      const r = calculateBeam(form, geometry);
      if (r) for (const point of points) beams.add(A.circle(point[0], point[1], r / 3600, {
        color: '#ff4545', lineWidth: 1.6
      }));
    }
    async function load() {
      if (loading || !valid()) return;
      loading = true;
      retry.hidden = true;
      status.textContent = 'Loading local Aladin and DSS reference imagery… Geometry remains available.';
      try {
        A = await root.AlmaSkyRuntime.load(holder.dataset.aladinModule);
        if (!valid()) return;
        holder.replaceChildren();
        viewer = A.aladin('#mosaic-aladin', {
          target: normalizedCentre.join(' '), cooFrame: 'ICRS', survey: DSS,
          fov: fit(), showReticle: false, showLayersControl: true,
          showFullscreenControl: true, showCooGridControl: true
        });
        catalog = A.catalog({name: 'Proposed OT pointing centres', color: '#32f4c7',
          shape: 'cross', sourceSize: 10});
        viewer.addCatalog(catalog);
        // Duplicate input rows remain distinct sources, even when markers overlap.
        catalog.addSources(points.map(([ra, dec], i) =>
          A.source(ra, dec, {row: i + 1, label: `Pointing ${i + 1}`})));
        beams = A.graphicOverlay({name: 'Proposed HPBW boundaries', color: '#ff4545'});
        viewer.addOverlay(beams);
        update();
        await root.AlmaSkyRuntime.loadReferenceImagery(viewer);
        if (!valid()) return;
        visible = true;
        stack.classList.add('mosaic-sky-active');
        toggle.hidden = false;
        toggle.textContent = 'Geometry only';
        status.textContent = 'DSS reference layer ready · cyan centres / red proposed HPBW circles. '
          + 'If image tiles remain blank, use Geometry only.';
      } catch (error) {
        console.warn('Mosaic sky layer unavailable; geometry preview retained:', error);
        visible = false;
        stack.classList.remove('mosaic-sky-active');
        retry.hidden = false;
        status.textContent = 'Reference sky image unavailable. The complete pointing geometry remains visible. Retry or continue assessment. ' + String(error.message || error);
      } finally { loading = false; }
    }
    retry.addEventListener('click', load);
    toggle.addEventListener('click', () => {
      visible = !visible;
      stack.classList.toggle('mosaic-sky-active', visible);
      toggle.textContent = visible ? 'Geometry only' : 'Show sky image';
    });
    // Limit expensive overlay regeneration when a large OT list is present.
    let redrawPending = false;
    function scheduleUpdate() {
      if (redrawPending) return;
      redrawPending = true;
      root.requestAnimationFrame(() => {redrawPending = false; update();});
    }
    form.addEventListener('input', scheduleUpdate);
    form.addEventListener('change', scheduleUpdate);
    form.querySelector('[data-preview-reset]').addEventListener('click', () => {
      if (viewer) {viewer.gotoRaDec(...normalizedCentre); viewer.setFoV(fit());}
    });
    load();
  };
})(typeof window !== 'undefined' ? window : globalThis);
