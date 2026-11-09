const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('Mosaic Setup disclosure resizes the same frequency chart and hides every SPW interval', () => {
  const source = fs.readFileSync('src/alma_duplicate/ui/static/mosaic-visualization.js', 'utf8');
  const listeners = {};
  const state = {'aria-expanded':'true'};
  const title = {textContent:''};
  const detail = {style:{display:''}, querySelectorAll: () => [{}, {}, {}]};
  const shapes = [{style:{}}, {style:{}}, {style:{}}];
  const axis = {setAttribute(name,v){this[name]=v;}};
  const grid = {setAttribute(name,v){this[name]=v;}};
  const rect = {setAttribute(name,v){this[name]=v;}};
  const svg = {
    dataset:{collapsedHeight:'154',expandedHeight:'384'},
    querySelector(s){return {'[data-setup-details]':detail,'[data-frequency-axis-label]':axis,'clipPath rect':rect}[s] || null;},
    querySelectorAll(s){return {'[data-frequency-detail]':shapes,'.plot-grid':[grid]}[s] || [];},
    setAttribute(name,v){this[name]=v;},
    addEventListener(name,fn){listeners[name]=fn;},
  };
  const toggle = {
    dataset:{componentCount:'2'},
    closest(s){return s==='svg'?svg:null;},
    querySelector(s){return s==='[data-setup-title]'?title:null;},
    getAttribute(s){return state[s];},
    setAttribute(s,v){state[s]=v;},
    addEventListener(name,fn){listeners[name]=fn;},
  };
  const root = {
    querySelectorAll(s){return s==='[data-toggle-setup]'?[toggle]:[];},
    querySelector(s){return {'#comparison-count':{textContent:''},'#clear-filters':{addEventListener(){}}}[s]||null;},
  };
  vm.runInNewContext(source, {document:{querySelector:()=>root},console});
  assert.equal(state['aria-expanded'],'false');
  assert.equal(detail.style.display,'none');
  assert(shapes.every(node=>node.style.display==='none'));
  assert.equal(svg.viewBox,'0 0 600 154');
  assert.equal(rect.height,'74');
  listeners.click({stopPropagation(){}});
  assert.equal(state['aria-expanded'],'true');
  assert.equal(detail.style.display,'');
  assert(shapes.every(node=>node.style.display===''));
  assert.equal(svg.viewBox,'0 0 600 384');
  assert.equal(rect.height,'304');
  listeners.keydown({key:'Enter',preventDefault(){}});
  assert.equal(state['aria-expanded'],'false');
});
