"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

// Exercise the production Mosaic-only controller through DOM events. No
// browser, source network, Aladin, or scientific evaluator is required.
const SOURCE = fs.readFileSync(path.resolve(__dirname,
  "../../src/alma_duplicate/ui/static/mosaic-visualization.js"), "utf8");

class Element {
  constructor(tag = "div", dataset = {}) {
    this.tag = tag;
    this.dataset = dataset;
    this.events = {};
    this.attrs = {};
    this.children = [];
    this.hidden = false;
    this.checked = true;
    this.open = false;
    this.value = "";
    this.textContent = "";
    this.classNames = new Set();
    this.classList = {
      add: name => this.classNames.add(name),
      remove: name => this.classNames.delete(name),
      toggle: (name, on) => on ? this.classNames.add(name) : this.classNames.delete(name),
      contains: name => this.classNames.has(name)
    };
  }
  addEventListener(type, callback) { (this.events[type] ||= []).push(callback); }
  emit(type, options = {}) {
    const event = {button: 0, pointerId: 1, clientX: 200, clientY: 200,
      key: "", deltaY: -1, ctrlKey: false, metaKey: false,
      defaultPrevented: false, preventDefault() {this.defaultPrevented = true;},
      ...options};
    for (const callback of this.events[type] || []) callback(event);
    return event;
  }
  setAttribute(name, value) {this.attrs[name] = String(value);}
  getAttribute(name) {return this.attrs[name] ?? null;}
  hasAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attrs, name);
  }
  toggleAttribute(name, force) {if (name === "hidden") this.hidden = force;}
  append(...children) {this.children.push(...children);}
  prepend(...children) {this.children.unshift(...children);}
  before(element) {this.toolbar = element;}
  closest(selector) {return selector === "[data-evidence]" ? this.evidence : null;}
  querySelectorAll(selector) {
    if (selector === "[data-pair]") return this.pairs || [];
    if (selector === "[data-select-pair]") return this.pairLabels || [];
    // The SVG harness contains no text axes or scientific shapes. It tests the
    // interaction transforms, not a second implementation of geometry.
    return [];
  }
  getScreenCTM() {return {inverse: () => ({})};}
  setPointerCapture(id) {this.captured = id;}
  hasPointerCapture(id) {return this.captured === id;}
  releasePointerCapture() {this.captured = undefined;}
}

function setup({empty = false} = {}) {
  const rows = empty ? [] : [
    new Element("button", {row: "0", source: "Archive", candidate: "Member-A", array: "12 m"}),
    new Element("button", {row: "1", source: "Queue", candidate: "Config-B", array: "7 m"})
  ];
  const filters = ["source", "candidate", "array"].map(key => new Element("select", {filter: key}));
  const evidences = rows.flatMap(row => ["position", "frequency", "details"].map(() =>
    new Element("div", {evidence: row.dataset.row})));
  const layer = new Element("input", {layer: "candidate"});
  layer.evidence = evidences[0] || new Element("div", {evidence:"0"});
  const pairPanel = evidences[1] || new Element("div", {evidence:"0"});
  const pairDetails = [new Element("details", {pair: "1"}), new Element("details", {pair: "3"})];
  pairPanel.pairs = pairDetails;
  const pairLabels = [new Element("text", {selectPair: "1"}), new Element("text", {selectPair: "3"})];
  pairPanel.pairLabels = pairLabels;
  for (const label of pairLabels) label.evidence = pairPanel;
  const chart = new Element("div");
  const sky = new Element("section"); sky.hidden = true;
  const tabs = [new Element("button"), new Element("button")];
  tabs[0].setAttribute("aria-controls", "charts");
  tabs[1].setAttribute("aria-controls", "sky");
  const clear = new Element("button"), count = new Element("output");
  const spatial = new Element("svg"), frequency = new Element("svg");
  spatial.viewBox = {baseVal: {width: 490, height: 425}};
  frequency.viewBox = {baseVal: {width: 600, height: 180}};
  const selectorLists = {
    "[data-filter]": filters, "[data-row]": rows, "[data-evidence]": evidences,
    ".evidence-pager button": tabs, "[data-layer]": [layer],
    "[data-select-pair]": empty ? [] : pairLabels, "#charts svg": [spatial, frequency]
  };
  const root = {
    querySelectorAll: selector => selectorLists[selector] || [],
    querySelector(selector) {
      return {"#comparison-count": count, "#clear-filters": clear,
        "#charts": chart, "#sky": sky}[selector] || null;
    }
  };
  const document = {
    querySelector: selector => selector === ".mosaic-explorer" ? root : null,
    createElement: tag => new Element(tag),
    createElementNS: (_ns, tag) => new Element(tag)
  };
  class DOMPoint {
    constructor(x, y) {this.x = x; this.y = y;}
    matrixTransform() {return this;}
  }
  vm.runInNewContext(SOURCE, {document, DOMPoint}, {filename: "mosaic-visualization.js"});
  const tools = svg => svg.toolbar.children.filter(node => node.tag === "button");
  const transform = svg => svg.children.find(node => node.tag === "g")?.children[0]?.attrs.transform;
  return {rows, filters, evidences, layer, pairLabels, pairDetails,
    chart, sky, tabs, clear, count, spatial, frequency, tools, transform};
}

test("source and candidate filters select only eligible comparisons and restore the list", () => {
  const h = setup();
  assert.equal(h.count.textContent, "2 of 2 comparisons");
  h.filters[0].value = "Queue";
  h.filters[0].emit("change");
  assert.deepEqual(h.rows.map(row => row.hidden), [true, false]);
  assert.equal(h.rows[1].attrs["aria-pressed"], "true");
  assert.equal(h.count.textContent, "1 of 2 comparisons");
  assert.ok(h.evidences.filter(node => node.dataset.evidence === "0").every(node => node.hidden));
  h.filters[1].value = "Member-A";
  h.filters[1].emit("change");
  assert.equal(h.count.textContent, "No comparisons match these filters. Clear filters to see all comparisons.");
  assert.ok(h.evidences.every(node => node.hidden));
  h.clear.emit("click");
  assert.deepEqual(h.rows.map(row => row.hidden), [false, false]);
  assert.equal(h.count.textContent, "2 of 2 comparisons");
  h.rows[0].emit("click");
  assert.equal(h.rows[0].attrs["aria-pressed"], "true");
  assert.equal(h.rows[1].attrs["aria-pressed"], "false");
});

test("position layer switches and tabs do not mutate source candidate records", () => {
  const h = setup();
  const before = JSON.stringify(h.rows.map(row => row.dataset));
  h.layer.checked = false;
  h.layer.emit("change");
  assert.ok(h.evidences[0].classList.contains("hide-candidate"));
  h.layer.checked = true;
  h.layer.emit("change");
  assert.equal(h.evidences[0].classList.contains("hide-candidate"), false);
  h.tabs[1].emit("click");
  assert.equal(h.chart.hidden, true);
  assert.equal(h.sky.hidden, false);
  assert.equal(h.tabs[1].attrs["aria-pressed"], "true");
  h.tabs[0].emit("click");
  assert.equal(h.chart.hidden, false);
  assert.equal(h.sky.hidden, true);
  assert.equal(JSON.stringify(h.rows.map(row => row.dataset)), before);
});

test("SPW label selection opens the matching saved-parameter disclosure", () => {
  const h = setup();
  h.pairLabels[1].emit("click");
  assert.deepEqual(h.pairDetails.map(d => d.open), [false, true]);
  assert.equal(h.pairLabels[1].attrs["aria-pressed"], "true");
  const press = h.pairLabels[0].emit("keydown", {key: "Enter"});
  assert.equal(press.defaultPrevented, true);
  assert.deepEqual(h.pairDetails.map(d => d.open), [true, false]);
  assert.equal(h.pairLabels[0].attrs["aria-pressed"], "true");
  h.pairLabels[1].emit("keydown", {key: " "});
  assert.deepEqual(h.pairDetails.map(d => d.open), [false, true]);
});

test("spatial and frequency chart controls keep their independent pan and zoom state", () => {
  const h = setup();
  const spatialButtons = h.tools(h.spatial), frequencyButtons = h.tools(h.frequency);
  assert.deepEqual(spatialButtons.map(b => b.textContent), ["+", "−", "Reset"]);
  assert.deepEqual(frequencyButtons.map(b => b.textContent), ["+", "−", "Reset"]);
  const initial = h.transform(h.spatial);
  spatialButtons[0].emit("click");
  assert.notEqual(h.transform(h.spatial), initial);
  const zoomed = h.transform(h.spatial);
  const plainScroll = h.spatial.emit("wheel", {deltaY: -1});
  assert.equal(plainScroll.defaultPrevented, false);
  assert.equal(h.transform(h.spatial), zoomed);
  const ctrlScroll = h.spatial.emit("wheel", {ctrlKey: true, deltaY: -1});
  assert.equal(ctrlScroll.defaultPrevented, true);
  assert.notEqual(h.transform(h.spatial), zoomed);
  h.spatial.emit("pointerdown", {clientX: 200, clientY: 200});
  h.spatial.emit("pointermove", {clientX: 220, clientY: 190});
  h.spatial.emit("pointerup");
  assert.equal(h.spatial.captured, undefined);
  h.spatial.emit("keydown", {key: "ArrowLeft"});
  assert.notEqual(h.transform(h.spatial), initial);
  spatialButtons[2].emit("click");
  assert.equal(h.transform(h.spatial), initial);
  const frequencyInitial = h.transform(h.frequency);
  frequencyButtons[0].emit("click");
  assert.notEqual(h.transform(h.frequency), frequencyInitial);
  const zoomFrequency = h.transform(h.frequency);
  h.frequency.emit("keydown", {key: "ArrowUp"});
  assert.equal(h.transform(h.frequency), zoomFrequency);
  h.frequency.emit("keydown", {key: "ArrowRight"});
  assert.notEqual(h.transform(h.frequency), zoomFrequency);
  frequencyButtons[2].emit("click");
  assert.equal(h.transform(h.frequency), frequencyInitial);
});

test("empty saved comparison page reports zero without phantom evidence", () => {
  const h = setup({empty: true});
  assert.equal(h.count.textContent, "No matching comparisons on this report page.");
  assert.deepEqual(h.evidences, []);
  assert.deepEqual(h.rows, []);
});
