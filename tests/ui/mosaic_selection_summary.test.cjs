'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('src/alma_duplicate/ui/static/mosaic-visualization.js','utf8');
function setup() {
  function el(dataset={}) {
    return {dataset, hidden:false, attrs:{}, handlers:{}, textContent:'',
      addEventListener(t,f){this.handlers[t]=f;},
      click(){this.handlers.click?.();},
      setAttribute(k,v){this.attrs[k]=v;},
      toggleAttribute(k,v){this[k]=v;}};
  }
  const rows=[el({row:'0',project:'P',candidate:'A',array:'12 m'}),
    el({row:'1',project:'P',candidate:'B',array:'7 m'})];
  const panels=Array.from({length:8},(_,i)=>el({evidence:String(i%2)}));
  const filter=el({filter:'array'});filter.value='';
  const count=el(),clear=el(),isolate=el(),focus=el();
  const root={querySelectorAll(s){return {'[data-row]':rows,'[data-filter]':[filter],
    '[data-evidence]':panels,'[data-plot-controls]':[]}[s]||[];},
    querySelector(s){return {'#comparison-count':count,'#clear-filters':clear,
      '#mosaic-isolate':isolate,'#mosaic-focus':focus}[s]||null;}};
  vm.runInNewContext(source.slice(0,source.indexOf('  const pages ='))+'render();})();',
    {document:{querySelector:()=>root}});
  return {rows,panels,filter,count,clear,isolate,focus};
}
test('Mosaic list selection switches summary, charts and details together',()=>{
  const h=setup();h.rows[1].click();
  assert.equal(h.rows[1].attrs['aria-pressed'],'true');
  assert.equal(h.rows[0].attrs['aria-pressed'],'false');
  h.panels.forEach(p=>assert.equal(p.hidden,p.dataset.evidence!=='1'));
  h.isolate.click();assert.equal(h.rows[0].hidden,true);
  assert.equal(h.count.textContent,'Showing 1 of 2 loaded comparisons');
  h.clear.click();assert.equal(h.rows[0].hidden,false);
  assert.equal(h.isolate.attrs['aria-pressed'],'false');
});
test('array filter selects a visible comparison and empty results hide all evidence',()=>{
  const h=setup();h.filter.value='7 m';h.filter.handlers.change();
  h.panels.forEach(p=>assert.equal(p.hidden,p.dataset.evidence!=='1'));
  h.filter.value='missing';h.filter.handlers.change();
  assert.ok(h.panels.every(p=>p.hidden));assert.equal(h.focus.disabled,true);
  h.clear.click();assert.equal(h.rows[0].attrs['aria-pressed'],'true');
});
