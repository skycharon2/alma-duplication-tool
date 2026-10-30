/* Single Pointing ICRS coordinates: detect typed notation and link both format selectors. */
(() => {
  const initialized = new WeakSet();
  function initializeCoordinateFormatSync(form) {
    if (!form || initialized.has(form)) return;
    const raFormat = form.querySelector('[name="ra_format"]');
    const decFormat = form.querySelector('[name="dec_format"]');
    const ra = form.querySelector('[name="ra"]');
    const dec = form.querySelector('[name="dec"]');
    if (!raFormat || !decFormat || !ra || !dec) return; // Mosaic OT positions
    initialized.add(form);

    // Keep server-retained formats (including legacy mixed pairs) until user input.
    let previous = {ra: raFormat.value, dec: decFormat.value};
    const SEXAGESIMAL = /^([+-]?)(\d{1,3}):(\d{1,2}):(\d{1,2}(?:\.\d*)?)$/;
    const DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
    const pair = decimal => decimal ? {ra: 'DEG', dec: 'DEG'} : {ra: 'HMS', dec: 'DMS'};

    // The backend accepts colon-separated HMS/DMS and decimal degrees, not
    // space-separated or partially entered coordinates. Detect only valid values.
    function interpret(text, isRa) {
      const input = text.trim();
      if (DECIMAL.test(input)) {
        const value = Number(input);
        if (Number.isFinite(value) && (isRa ? 0 <= value && value < 360
          : -90 <= value && value <= 90)) return {format: 'DEG', degrees: value};
        return null;
      }
      const parts = SEXAGESIMAL.exec(input);
      if (!parts) return null;
      const major = Number(parts[2]), minute = Number(parts[3]), second = Number(parts[4]);
      const max = isRa ? 24 : 90;
      if (minute >= 60 || second >= 60 || major > max ||
          (major === max && (minute !== 0 || second !== 0)) ||
          (isRa && (parts[1] === '-' || major === 24))) return null;
      const degrees = (major + minute / 60 + second / 3600) * (isRa ? 15 : 1);
      return {format: isRa ? 'HMS' : 'DMS', degrees: parts[1] === '-' ? -degrees : degrees};
    }

    function sexagesimal(value, isRa) {
      const sign = isRa || value >= 0 ? '' : '-';
      const max = isRa ? 24 : 90;
      const scale = 1e8;
      const total = Math.round(Math.abs(value) / (isRa ? 15 : 1) * 3600 * scale);
      const units = Math.floor(total / (3600 * scale));
      const minutes = Math.floor((total - units * 3600 * scale) / (60 * scale));
      const sec = (total - units * 3600 * scale - minutes * 60 * scale) / scale;
      if (units > max || (isRa && units === max)) return null;
      const pad = n => String(n).padStart(2, '0');
      return `${sign}${pad(units)}:${pad(minutes)}:${sec.toFixed(8).padStart(11, '0')}`;
    }

    function convert(text, format, isRa) {
      if (!text.trim()) return text;
      const parsed = interpret(text, isRa);
      if (!parsed) return null;
      if (parsed.format === format) return text;
      return format === 'DEG' ? String(parsed.degrees) : sexagesimal(parsed.degrees, isRa);
    }

    function applyPair(target, active = null) {
      // Compute both before writing either: an incomplete or invalid coordinate
      // must never be reinterpreted merely because its selector changed.
      const nextRa = active === ra ? ra.value : convert(ra.value, target.ra, true);
      const nextDec = active === dec ? dec.value : convert(dec.value, target.dec, false);
      if (nextRa === null || nextDec === null) return nextRa === null ? ra : dec;
      ra.value = nextRa;
      dec.value = nextDec;
      raFormat.value = target.ra;
      decFormat.value = target.dec;
      previous = target;
      form.dispatchEvent(new Event('input', {bubbles: true}));
      return null;
    }

    function formatChanged(source) {
      const target = pair((source === raFormat ? raFormat : decFormat).value === 'DEG');
      const invalid = applyPair(target);
      if (invalid) {
        raFormat.value = previous.ra;
        decFormat.value = previous.dec;
        invalid.focus();
      }
    }

    function typed(input, isRa, event) {
      if (event?.isComposing) return;
      const parsed = interpret(input.value, isRa);
      if (!parsed) return; // Never guess from incomplete or out-of-range text.
      const selector = isRa ? raFormat : decFormat;
      // '18' could be the beginning of '18:33:39'. Delay switching away
      // from HMS/DMS until the text is committed, except for a full paste.
      if (parsed.format === 'DEG' && selector.value !== 'DEG' &&
          event?.type === 'input' && event.inputType !== 'insertFromPaste') return;
      const counterpart = isRa ? dec : ra;
      const other = interpret(counterpart.value, !isRa);
      const otherSelector = isRa ? decFormat : raFormat;
      // If the other field's complete sexagesimal input was waiting for this
      // field to become valid, finish that pending switch instead of leaving
      // colon text under a DEG selector.
      const pending = other && other.format !== 'DEG' && otherSelector.value !== other.format;
      const preferred = pending ? other : parsed;
      const target = pair(preferred.format === 'DEG');
      if (raFormat.value === target.ra && decFormat.value === target.dec) return;
      // Preserve the active input only when it already has the chosen notation.
      // Otherwise convert both together, or neither, so the sky position stays fixed.
      applyPair(target, parsed.format === (isRa ? target.ra : target.dec) ? input : null);
    }

    ra.addEventListener('input', event => typed(ra, true, event));
    dec.addEventListener('input', event => typed(dec, false, event));
    ra.addEventListener('change', event => typed(ra, true, event));
    dec.addEventListener('change', event => typed(dec, false, event));
    raFormat.addEventListener('change', () => formatChanged(raFormat));
    decFormat.addEventListener('change', () => formatChanged(decFormat));
  }
  window.initializeCoordinateFormatSync = initializeCoordinateFormatSync;
  initializeCoordinateFormatSync(document.querySelector('.proposed-form'));
})();
