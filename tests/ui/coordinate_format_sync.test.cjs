'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/alma_duplicate/ui/static/coordinate-format-sync.js', 'utf8');

function control(value) {
  const listeners = {};
  return {value, focused: false,
    addEventListener(name, callback) { listeners[name] = callback; },
    change(value) { this.value = value; listeners.change?.(); },
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
  vm.runInNewContext(source, {
    document: {querySelector(name) { return name === '.proposed-form' ? form : null; }},
    Event: class { constructor(name) {this.type = name;} }
  });
  return {raFormat, decFormat, ra, dec, changes: () => changes};
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
