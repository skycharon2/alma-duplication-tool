/* Preview is deliberately separate from assessment and source selection. */
window.initializeSkyPreview = function(form) {
  const panel = form.querySelector('.sky-preview');
  if (!panel) return;
  const open = panel.querySelector('[data-sky-open]');
  const content = panel.querySelector('#sky-preview-content');
  const status = panel.querySelector('[data-sky-status]');
  const frame = panel.querySelector('[data-sky-frame]');
  let generation = 0;
  let controller;
  function clear() {
    generation++; controller?.abort(); frame.replaceChildren(); content.hidden = true;
    open.disabled = false; open.setAttribute('aria-expanded', 'false');
  }
  panel.querySelector('[data-sky-close]').addEventListener('click', () => {
    clear(); status.textContent = ''; open.focus();
  });
  form.addEventListener('input', event => {
    if (['ra','dec','ra_format','dec_format','target_kind'].includes(event.target.name)) {
      const hadPreview = !content.hidden || open.disabled;
      clear(); status.textContent = hadPreview ? 'Coordinates changed. Open preview again to update the target.' : '';
    }
  });
  open.addEventListener('click', async () => {
    clear(); const current = generation; controller = new AbortController();
    open.disabled = true; status.textContent = 'Checking coordinates…';
    const body = new URLSearchParams();
    for (const key of ['ra','dec','ra_format','dec_format','target_kind']) body.set(key, form.elements.namedItem(key)?.value || '');
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(panel.dataset.url, {method:'POST', body, signal:controller.signal});
      const result = await response.json();
      if (current !== generation || !panel.isConnected) return;
      if (!response.ok) {
        status.replaceChildren();
        for (const error of result.errors || []) {
          const link = document.createElement('a'); link.href = '#' + error.field;
          link.textContent = error.message + ' '; status.append(link);
        }
        return;
      }
      const iframe = document.createElement('iframe');
      iframe.title = 'Sky preview of entered ICRS coordinates';
      iframe.setAttribute('sandbox','allow-scripts allow-same-origin allow-popups');
      iframe.referrerPolicy = 'no-referrer'; iframe.srcdoc = result.html;
      frame.append(iframe); content.hidden = false; open.setAttribute('aria-expanded','true');
      status.textContent = '';
    } catch (_) {
      if (current === generation) status.textContent = 'Preview unavailable. Select Sky preview to retry; you can continue using the form.';
    } finally {
      clearTimeout(timer); if (current === generation) open.disabled = false;
    }
  });
};
