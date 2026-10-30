'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/alma_duplicate/ui/static/coordinate-format-sync.js', 'utf8');

function control(value) {
  const listeners = {};
  return {value, focused: false,
    addEventListener(name, callback) { (listeners[name] ??= []).push(callback); },
    change(value) { this.value = value; listeners.change?.forEach(callback => callback()); },
    type(value, event = {}) { this.value = value; listeners.input?.forEach(callback => callback({type: 'input', ...event})); },
    commit() { listeners.change?.forEach(callback => callback({type: 'change'})); },
    focus() { this.focused = true; }};
}
function initialize(withInputs = true) {
  const raFormat = control('DEG');
  const decFormat = control('DEG');
  const ra = control('11.887184566666667');
  const dec = control('-25.288874822222223');
  let changes = 0;
  const inputs = {'[name="ra_format"]': raFormat, '[name="dec_format"]': decFormat,
    '[name="ra"]': ra, '[name="dec"]': dec};
  const form = {
    querySelector(name) { return withInputs ? inputs[name] : null; },
    dispatchEvent() { changes++; }
  };
  const window = {};
  vm.runInNewContext(source, {
    window,
    document: {querySelector(name) { return name === '.proposed-form' ? form : null; }},
    Event: class { constructor(name) {this.type = name;} }
  });
  return {form, window, raFormat, decFormat, ra, dec, changes: () => changes};
}

test('changing RA or Dec representation links the counterpart and preserves sky coordinates', () => {
  const p = initialize();
  p.raFormat.change('HMS');
  assert.equal(p.decFormat.value, 'DMS');
  assert.match(p.ra.value, /^00:47:32/);
  assert.match(p.dec.value, /^-25:17:/);
  p.decFormat.change('DEG');
  assert.equal(p.raFormat.value, 'DEG');
  assert.ok(Math.abs(Number(p.ra.value) - 11.887184566666667) < 1e-9);
  assert.ok(Math.abs(Number(p.dec.value) + 25.288874822222223) < 1e-9);
  assert.equal(p.changes(), 2);
});

test('bad coordinate input is not silently reinterpreted', () => {
  const p = initialize();
  p.ra.value = 'invalid';
  p.decFormat.change('DMS');
  assert.equal(p.raFormat.value, 'DEG');
  assert.equal(p.decFormat.value, 'DEG');
  assert.equal(p.ra.value, 'invalid');
  assert.equal(p.ra.focused, true);
});

test('empty coordinates and Mosaic views remain safe', () => {
  const p = initialize();
  p.ra.value = '';
  p.dec.value = '';
  p.raFormat.change('HMS');
  assert.equal(p.decFormat.value, 'DMS');
  initialize(false);
});


test('replacement forms initialize once and preserve conversion after validation errors', () => {
  const original = initialize();
  // Use fresh controls to represent the replacement parsed from server HTML.
  const inputs = {
    '[name="ra_format"]': control('DEG'), '[name="dec_format"]': control('DEG'),
    '[name="ra"]': control('15'), '[name="dec"]': control('-30')
  };
  let events = 0;
  const form = {querySelector: name => inputs[name], dispatchEvent: () => events++};
  original.window.initializeCoordinateFormatSync(form);
  original.window.initializeCoordinateFormatSync(form);
  inputs['[name="ra_format"]'].change('HMS');
  assert.equal(inputs['[name="ra"]'].value, '01:00:00.00000000');
  assert.equal(inputs['[name="dec_format"]'].value, 'DMS');
  assert.equal(events, 1);
  assert.match(fs.readFileSync('src/alma_duplicate/ui/static/proposed.js', 'utf8'),
    /window\.initializeCoordinateFormatSync\?\.\(form\)/);
});


test('pasting HMS RA automatically selects HMS/DMS and converts existing decimal Dec', () => {
  const p = initialize();
  p.ra.type('18:33:39.920');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
  assert.equal(p.ra.value, '18:33:39.920'); // Do not replace the edited field.
  assert.match(p.dec.value, /^-25:17:/);
  assert.equal(p.changes(), 1);
});

test('pasting DMS Dec automatically selects HMS/DMS and converts existing decimal RA', () => {
  const p = initialize();
  p.dec.type('-21:03:39.900');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
  assert.equal(p.dec.value, '-21:03:39.900');
  assert.match(p.ra.value, /^00:47:32/);
});

test('typing decimal RA after HMS/DMS switches both back to degrees without changing Dec position', () => {
  const p = initialize();
  p.raFormat.change('HMS');
  const before = p.dec.value;
  p.ra.type('278.416333333');
  assert.equal(p.raFormat.value, 'HMS'); // Decimal input may still become HMS while typing.
  p.ra.commit();
  assert.equal(p.raFormat.value, 'DEG');
  assert.equal(p.decFormat.value, 'DEG');
  assert.equal(p.ra.value, '278.416333333');
  assert.ok(Math.abs(Number(p.dec.value) + 25.288874822222223) < 1e-9);
  assert.notEqual(p.dec.value, before);
});

test('manual format change accepts a pasted coordinate already written in target notation', () => {
  const p = initialize();
  // Simulate a value restored by the browser without a preceding input event.
  p.ra.value = '18:33:39.920';
  p.decFormat.change('DMS');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
  assert.equal(p.ra.value, '18:33:39.920');
  assert.match(p.dec.value, /^-25:17:/);
  p.raFormat.change('DEG');
  assert.ok(Math.abs(Number(p.ra.value) - 278.4163333333333) < 1e-9);
});

test('invalid and partial coordinate entries are not silently converted or reinterpreted', () => {
  const p = initialize();
  p.ra.type('18:33:');
  assert.equal(p.raFormat.value, 'DEG');
  p.ra.type('25:00:00'); // RA > 24 hours.
  assert.equal(p.raFormat.value, 'DEG');
  p.ra.type('18:33:39.920');
  assert.equal(p.raFormat.value, 'HMS');
  p.dec.type('91'); // Declination outside [-90, 90].
  assert.equal(p.decFormat.value, 'DMS');
  assert.equal(p.dec.value, '91');
  p.raFormat.change('DEG');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
  assert.equal(p.dec.focused, true);
});

test('an unfinished other coordinate defers automatic format changes', () => {
  const p = initialize();
  p.dec.value = '-25:';
  p.ra.type('18:33:39.920');
  assert.equal(p.raFormat.value, 'DEG');
  assert.equal(p.ra.value, '18:33:39.920');
  assert.equal(p.dec.value, '-25:');
  p.dec.type('-25:17:19.950');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
  assert.equal(p.ra.value, '18:33:39.920');
});

test('composition events do not change format while the user is editing', () => {
  const p = initialize();
  p.ra.type('18:33:39.920', {isComposing: true});
  assert.equal(p.raFormat.value, 'DEG');
  p.ra.type('18:33:39.920', {isComposing: false});
  assert.equal(p.raFormat.value, 'HMS');
});

test('empty counterpart and repeated edits work without changing Single Pointing science fields', () => {
  const p = initialize();
  p.dec.value = '';
  p.ra.type('01:00:00');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
  p.dec.type('-30:00:00');
  p.decFormat.change('DEG');
  assert.equal(p.ra.value, '15');
  assert.equal(p.dec.value, '-30');
});


test('completing a decimal counterpart finishes an earlier pending sexagesimal conversion', () => {
  const p = initialize();
  p.dec.value = '-';
  p.ra.type('18:33:39.920');
  assert.equal(p.raFormat.value, 'DEG');
  p.dec.type('-21.061083333');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
  assert.match(p.dec.value, /^-21:03:39/);
});

test('pasted decimal values switch out of HMS immediately', () => {
  const p = initialize();
  p.raFormat.change('HMS');
  p.ra.type('278.416333333', {inputType: 'insertFromPaste'});
  assert.equal(p.raFormat.value, 'DEG');
  assert.equal(p.decFormat.value, 'DEG');
});

test('sexagesimal typing does not flicker into DEG on partial decimal digits', () => {
  const p = initialize();
  p.raFormat.change('HMS');
  p.dec.type('-21');
  assert.equal(p.raFormat.value, 'HMS');
  p.dec.type('-21:03:39.900');
  assert.equal(p.raFormat.value, 'HMS');
  assert.equal(p.decFormat.value, 'DMS');
});
