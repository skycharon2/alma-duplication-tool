/* Link Single Pointing coordinate representations without changing sky positions. */
(() => {
  const form = document.querySelector('.proposed-form');
  if (!form) return;
  const raFormat = form.querySelector('[name="ra_format"]');
  const decFormat = form.querySelector('[name="dec_format"]');
  const ra = form.querySelector('[name="ra"]');
  const dec = form.querySelector('[name="dec"]');
  if (!raFormat || !decFormat || !ra || !dec) return; // Mosaic OT positions

  // Preserve legacy mixed selections on initial load. Only a user change links them.
  let previous = { ra: raFormat.value, dec: decFormat.value };
  const SEXAGESIMAL = /^([+-]?)(\d{1,3}):(\d{1,2}):(\d{1,2}(?:\.\d*)?)$/;
  const DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

  function degrees(text, format, isRa) {
    const input = text.trim();
    if (format === 'DEG') {
      if (!DECIMAL.test(input)) return null;
      const number = Number(input);
      return Number.isFinite(number) && (isRa ? 0 <= number && number < 360
        : -90 <= number && number <= 90) ? number : null;
    }
    const parts = SEXAGESIMAL.exec(input);
    if (!parts) return null;
    const major = Number(parts[2]), minute = Number(parts[3]), second = Number(parts[4]);
    const max = isRa ? 24 : 90;
    if (minute >= 60 || second >= 60 || major > max ||
        (major === max && (minute !== 0 || second !== 0)) ||
        (isRa && (parts[1] === '-' || major === 24))) return null;
    const value = (major + minute / 60 + second / 3600) * (isRa ? 15 : 1);
    return parts[1] === '-' ? -value : value;
  }

  function sexagesimal(value, isRa) {
    const sign = isRa || value >= 0 ? '' : '-';
    const max = isRa ? 24 : 90;
    // Integer nanoseconds of arc/time avoid 59.99999999 second rollover.
    const scale = 1e8;
    const total = Math.round(Math.abs(value) / (isRa ? 15 : 1) * 3600 * scale);
    const units = Math.floor(total / (3600 * scale));
    const minutes = Math.floor((total - units * 3600 * scale) / (60 * scale));
    const sec = (total - units * 3600 * scale - minutes * 60 * scale) / scale;
    if (units > max || (isRa && units === max)) return null;
    const pad = n => String(n).padStart(2, '0');
    const seconds = sec.toFixed(8).padStart(11, '0');
    return `${sign}${pad(units)}:${pad(minutes)}:${seconds}`;
  }

  function convert(value, oldFormat, newFormat, isRa) {
    if (!value.trim() || oldFormat === newFormat) return value;
    const decimalDegrees = degrees(value, oldFormat, isRa);
    if (decimalDegrees === null) return null;
    return newFormat === 'DEG' ? String(decimalDegrees) : sexagesimal(decimalDegrees, isRa);
  }

  function changed(source) {
    const target = source === raFormat
      ? (raFormat.value === 'DEG' ? {ra: 'DEG', dec: 'DEG'} : {ra: 'HMS', dec: 'DMS'})
      : (decFormat.value === 'DEG' ? {ra: 'DEG', dec: 'DEG'} : {ra: 'HMS', dec: 'DMS'});
    const nextRa = convert(ra.value, previous.ra, target.ra, true);
    const nextDec = convert(dec.value, previous.dec, target.dec, false);
    if (nextRa === null || nextDec === null) {
      // Reject a representation switch if entered text cannot be converted;
      // never reinterpret an existing coordinate in the other unit.
      raFormat.value = previous.ra;
      decFormat.value = previous.dec;
      (nextRa === null ? ra : dec).focus();
      return;
    }
    ra.value = nextRa;
    dec.value = nextDec;
    raFormat.value = target.ra;
    decFormat.value = target.dec;
    previous = target;
    form.dispatchEvent(new Event('input', {bubbles: true}));
  }

  raFormat.addEventListener('change', () => changed(raFormat));
  decFormat.addEventListener('change', () => changed(decFormat));
})();
