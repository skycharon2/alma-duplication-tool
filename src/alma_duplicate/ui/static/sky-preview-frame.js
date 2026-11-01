/* Fixed target sky context: local Aladin, immediate coordinate-only fallback. */
(async () => {
  const panel = document.querySelector('#sky');
  if (!panel) return;
  const ra = Number(panel.dataset.ra), dec = Number(panel.dataset.dec);
  const status = document.querySelector('#status');
  const canvas = document.querySelector('#sky-geometry');
  const reset = document.querySelector('#reset');
  const retry = document.querySelector('#retry');
  const DSS = 'https://skies.esac.esa.int/DSSColor/';
  let viewer, loading = false;
  function geometry() {
    const w = canvas.clientWidth || 480, h = canvas.clientHeight || 310;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#e8f2fa'; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#bdd2e2';
    for (let i = 1; i < 6; i++) {
      ctx.beginPath(); ctx.moveTo(i * w / 6, 0); ctx.lineTo(i * w / 6, h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, i * h / 6); ctx.lineTo(w, i * h / 6); ctx.stroke();
    }
    ctx.strokeStyle = '#087d8b'; ctx.lineWidth = 2;
    ctx.beginPath();ctx.moveTo(w / 2 - 13, h / 2);ctx.lineTo(w / 2 + 13, h / 2);
    ctx.moveTo(w / 2, h / 2 - 13);ctx.lineTo(w / 2, h / 2 + 13);ctx.stroke();
    ctx.fillStyle = '#274d65';ctx.font = '13px system-ui';ctx.textAlign = 'center';
    ctx.fillText(`ICRS ${ra.toFixed(6)}°, ${dec.toFixed(6)}°`, w / 2, h / 2 + 30);
    ctx.fillText('Geometry only · no optical image', w / 2, h - 16);
  }
  geometry();
  window.addEventListener('resize', () => {if (!canvas.hidden) geometry();});
  async function load() {
    if (loading) return;
    loading = true; retry.hidden = true;
    status.textContent = 'Loading local Aladin and DSS reference image…';
    try {
      const A = await window.AlmaSkyRuntime.load(panel.dataset.aladinModule);
      panel.replaceChildren();
      viewer = A.aladin('#sky', {target: `${ra} ${dec}`, cooFrame: 'ICRS',
        survey: DSS, fov: 0.25, showReticle: true, showFullscreenControl: false});
      const catalog = A.catalog({name: 'Entered target', color: '#00e5e5', sourceSize: 14});
      viewer.addCatalog(catalog);catalog.addSources([A.source(ra, dec, {label: 'Entered target'})]);
      await window.AlmaSkyRuntime.loadReferenceImagery(viewer);
      panel.classList.add('sky-ready');
      reset.disabled = false;
      status.textContent = 'DSS reference layer ready · cyan marker: entered ICRS target. '
        + 'If tiles remain blank, use the geometry view.';
    } catch (error) {
      console.warn('Single Pointing sky imagery unavailable:', error);
      panel.classList.remove('sky-ready');
      retry.hidden = false;
      status.textContent = 'Sky imagery unavailable. The ICRS coordinate fallback is shown. Retry or continue without a map.';
    } finally {loading = false;}
  }
  reset.addEventListener('click', () => {if (viewer) {viewer.gotoRaDec(ra, dec);viewer.setFoV(0.25);}});
  retry.addEventListener('click', load);
  await load();
})();
