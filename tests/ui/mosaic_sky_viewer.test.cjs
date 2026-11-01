const { test } = require('node:test');
const assert = require('node:assert/strict');
const { separation, fieldOfView } = require('../../src/alma_duplicate/ui/static/mosaic-aladin.js');
const runtime = require('../../src/alma_duplicate/ui/static/alma-sky-runtime.js');

test('RA crossing 0/360 remains a small field', () => {
  const points = [[359.999, -21], [0.001, -21]];
  const fov = fieldOfView(points, [0, -21], 0, 1);
  assert.ok(fov >= 0.015 && fov < 0.05, fov);
  assert.ok(separation(points[0], points[1]) < 0.003);
});
test('high declination and repeated centres stay finite', () => {
  for (const pts of [[[0, 89.99], [0, 89.99]], [[0, -89.99], [120, -89.99]]]) {
    const fov = fieldOfView(pts, pts[0], 15, 1.5);
    assert.ok(Number.isFinite(fov) && fov >= 0.015 && fov <= 120);
  }
});
test('beam affects field size without changing pointings', () => {
  const points = [[200, -30]];
  const base = fieldOfView(points, points[0]);
  const beam = fieldOfView(points, points[0], 30);
  assert.ok(beam > base);
  assert.deepEqual(points, [[200, -30]]);
});
test('bounded async initialization reports failure without hanging', async () => {
  const never = new Promise(() => {});
  await assert.rejects(runtime.bounded(never, 10, 'Aladin test'), /timed out/);
  assert.equal(await runtime.bounded(Promise.resolve('ready'), 100, 'Aladin test'), 'ready');
});

test('each imported row becomes an overlay source; losing imagery keeps Canvas', async () => {
  const fs = require('node:fs');
  const vm = require('node:vm');
  const source = fs.readFileSync('src/alma_duplicate/ui/static/mosaic-aladin.js', 'utf8');
  const createButton = () => ({hidden: true, textContent: '', handlers: {},
    addEventListener(name, fn) {this.handlers[name] = fn;}});
  const make = shouldFail => {
    const added = [], circles = [], events = {};
    const stackClasses = new Set();
    const stack = {classList: {add: name => stackClasses.add(name),
      remove: name => stackClasses.delete(name),
      toggle: (name, on) => on ? stackClasses.add(name) : stackClasses.delete(name)}};
    const holder = {isConnected: true, dataset: {aladinModule:'/local/aladin.js'},
      clientWidth: 600, clientHeight: 400, replaceChildren() {}};
    const status = {textContent:''}, retry = createButton(), toggle = createButton(), reset = createButton();
    const elements = {
      '[data-mosaic-aladin]': holder,
      '[data-mosaic-points]': {textContent: '[359.999,0.001,0.001]'},
      '[data-mosaic-decs]': {textContent:'[-21,-21,-21]'},
      '[data-mosaic-canvas]': {},
      '[data-mosaic-map-stack]': stack,
      '[data-mosaic-imagery-status]': status,
      '[data-mosaic-imagery-retry]': retry,
      '[data-mosaic-geometry-toggle]': toggle,
      '[data-preview-reset]': reset,
      '[data-preview-frequency]': {value: 'continuum'},
      '[name=frequency_local_redshift]': null
    };
    const form = {isConnected:true, querySelector: selector => elements[selector] ?? null,
      elements: {namedItem: name => ({mosaic_array:'12m',representative:'230',
        representative_unit:'GHz',representative_kind:'SKY'})[name]
        ? {value:{mosaic_array:'12m',representative:'230',representative_unit:'GHz',
          representative_kind:'SKY'}[name]} : null},
      addEventListener: (name, fn) => {events[name] = fn;}};
    const overlay = {removeAll() {circles.length=0;},add(c) {circles.push(c);}};
    const catalog = {addSources(sources) {added.push(...sources);}};
    const viewer = {getBaseImageLayer() {return {query:Promise.resolve()};},
      addCatalog() {},addOverlay() {},gotoRaDec() {},setFoV() {}};
    const A = {aladin: () => viewer, init: Promise.resolve(),
      catalog: () => catalog, graphicOverlay: () => overlay,
      source: (ra,dec,data) => ({ra,dec,data}),circle: (ra,dec,r) => ({ra,dec,r})};
    const window = {MosaicPreviewGeometry: {
      sky: (value, unit, kind) => kind === 'SKY' ? Number(value) : null,
      radius: () => 12
    }, AlmaSkyRuntime: {load: async () => A,
      loadReferenceImagery: async () => {if (shouldFail) throw Error('Survey offline');}}};
    vm.runInNewContext(source, {window,console});
    window.initializeMosaicSkyViewer(form);
    return {added,circles,stackClasses,holder,status,retry,toggle,events};
  };
  const success = make(false);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(success.added.length, 3); // even duplicates remain separate rows
  assert.deepEqual(success.added.map(s => s.data.row), [1,2,3]);
  assert.equal(success.circles.length, 3);
  assert.equal(success.circles[0].r, 12 / 3600);
  assert.ok(success.stackClasses.has('mosaic-sky-active'));
  success.toggle.handlers.click();
  assert.equal(success.stackClasses.has('mosaic-sky-active'), false);
  const failed = make(true);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(failed.stackClasses.has('mosaic-sky-active'), false);
  assert.equal(failed.retry.hidden, false);
  assert.match(failed.status.textContent, /geometry remains visible/);
});

test('base layer may appear asynchronously after viewer construction', async () => {
  let layer;
  setTimeout(() => {layer = {query: Promise.resolve()};}, 5);
  assert.equal(await runtime.waitForImagery({getBaseImageLayer: () => layer}, 200), layer);
});

test('missing layer times out instead of reporting success', async () => {
  await assert.rejects(runtime.waitForImagery({getBaseImageLayer: () => null}, 10), /timed out/);
});

test('failed primary metadata switches survey on the same viewer', async () => {
  let layer = {query: Promise.reject(new Error('ESA offline'))};
  const switched = [];
  const viewer = {
    getBaseImageLayer: () => layer,
    setBaseImageLayer(url) {
      switched.push(url);
      layer = {query: Promise.resolve()};
      return layer;
    }
  };
  assert.equal(await runtime.loadReferenceImagery(viewer), layer);
  assert.deepEqual(switched, ['https://alasky.cds.unistra.fr/DSS/DSSColor/']);
});

test('both metadata failures remain failures with actionable diagnostics', async () => {
  const viewer = {
    getBaseImageLayer: () => ({query: Promise.reject(new Error('primary offline'))}),
    setBaseImageLayer: () => ({query: Promise.reject(new Error('backup offline'))})
  };
  await assert.rejects(runtime.loadReferenceImagery(viewer), /ESA DSS: primary offline; CDS DSS: backup offline/);
});
