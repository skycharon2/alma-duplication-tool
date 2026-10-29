const {test} = require('node:test');
const assert = require('node:assert/strict');
const {offset, render} = require('../../src/alma_duplicate/ui/static/report-sky-fallback.js');

test('ICRS tangent-plane fallback respects east-left, north-up, and RA wrap', () => {
  const east = offset([359.999, 0], [0.001, 0]);
  assert.ok(Math.abs(east[0] + 7.2) < 0.0001);
  assert.ok(Math.abs(east[1]) < 0.0001);
  const north = offset([10, 20], [10, 20 + 1 / 3600]);
  assert.ok(Math.abs(north[0]) < 0.0001);
  assert.ok(Math.abs(north[1] + 1) < 0.0001);
  assert.equal(offset([0, 0], [180, 0]), null);
});

test('fallback shows saved beam and target with explicit no-imagery label', () => {
  const prior = global.document;
  const elements = [];
  global.document = {createElementNS(ns, tag) {
    assert.equal(ns, 'http://www.w3.org/2000/svg');
    const node = {tag, attrs: {}, children: [], setAttribute(k, v) {this.attrs[k] = v;},
      append(child) {this.children.push(child);}};
    elements.push(node);
    return node;
  }};
  try {
    const rows = [
      {id: 'a', source:'ARCHIVE', spatial:{available:true,center:[10,20],radius_arcsec:10}},
      {id: 'b', source:'QUEUE', spatial:{available:true,center:[10.001,20],radius_arcsec:7}},
    ];
    const original = JSON.stringify(rows);
    const container = {replaceChildren(...kids) {this.children = kids;}};
    const state = {origin:[10,20], selected:()=> 'a', rows:()=>rows};
    assert.equal(render(container, state, {beams:true,others:false}), 1);
    const svg = container.children[0];
    assert.equal(svg.tag, 'svg');
    assert.match(svg.attrs['aria-label'], /no optical/);
    assert.equal(svg.children.filter(n=>n.tag==='circle').length, 2);
    assert.ok(svg.children.some(n=>n.tag==='text' && /geometry only/i.test(n.textContent)));
    assert.equal(render(container, state, {beams:false,others:true}), 2);
    assert.equal(container.children[0].children.filter(n=>n.tag==='circle').length, 2);
    assert.equal(JSON.stringify(rows), original);
  } finally {
    global.document = prior;
  }
});
