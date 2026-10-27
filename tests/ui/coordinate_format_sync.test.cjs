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
