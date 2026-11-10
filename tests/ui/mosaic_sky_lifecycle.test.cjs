'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,
  '../../src/alma_duplicate/ui/static/mosaic-report-sky.js'),'utf8');
function control() {
  const handlers={};
  return {hidden:false,checked:true,attrs:{},dataset:{},textContent:'',
    addEventListener(type,fn){(handlers[type] ||= []).push(fn);},
    emit(type){for (const fn of handlers[type]||[]) fn({});},
    getAttribute(name){return this.attrs[name]||null;},
    replaceChildren(...children){this.children=children;},
    append(...children){this.children=(this.children||[]).concat(children);}};
}
test('Aladin is lazy and error fallback keeps saved geometry without image requests',async()=>{
  const payload={textContent:JSON.stringify([{
    available:true,source:'Archive',label:'NGC253',proposed:[{id:'P1',center:[201.36,-43.01]}],
    proposed_beams:[],candidate:{kind:'region',outline:[[201.35,-43.02],[201.37,-43.02],
      [201.37,-43],[201.35,-43]]}}
  ])};
  const elems={};for(const name of [
    '#mosaic-sky-canvas','#sky','#mosaic-sky-status','#mosaic-imagery-status',
    '#mosaic-sky-retry','#mosaic-sky-proposed','#mosaic-sky-candidates',
    '#mosaic-sky-others','#mosaic-sky-imagery','#mosaic-sky-identities',
    '#mosaic-sky-overview','#mosaic-sky-selected','#clear-filters',
    '.evidence-pager [aria-controls="sky"]']) elems[name]=control();
  elems['#sky'].hidden=true;
  elems['#mosaic-sky-canvas'].dataset.aladinModule='/static/aladin.js';
  const row=control();row.dataset.row='0';row.attrs['aria-pressed']='true';
  const root={querySelector:s=>elems[s],querySelectorAll:s=>
    s==='[data-row]'?[row]:s==='[data-filter]'?[]:[]};
  let loads=0,fallbacks=0;
  const document={querySelector:s=>s==='.mosaic-explorer'?root:null,
    getElementById:s=>s==='mosaic-sky-data'?payload:null,
    createElement:()=>control()};
  const window={MosaicSkyGeometry:{fallback(){fallbacks++;return true;},extent(){
    return {origin:[201.36,-43.01],fov:.1};}},
    AlmaSkyRuntime:{async load(){loads++;throw new Error('offline');}}};
  vm.runInNewContext(source,{document,window,console});
  assert.equal(loads,0,'opening Charts must not download an astronomical viewer');
  elems['#sky'].hidden=false;
  elems['.evidence-pager [aria-controls="sky"]'].emit('click');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(loads,1);
  assert.ok(fallbacks>=1);
  assert.equal(elems['#mosaic-sky-retry'].hidden,false);
  assert.ok(elems['#mosaic-imagery-status'].textContent.includes('geometry'));
});

test('deferred loading survives empty filters and creates source-specific overlays on recovery',async()=>{
  const elems={};for(const name of [
    '#mosaic-sky-canvas','#sky','#mosaic-sky-status','#mosaic-imagery-status',
    '#mosaic-sky-retry','#mosaic-sky-proposed','#mosaic-sky-candidates',
    '#mosaic-sky-others','#mosaic-sky-imagery','#mosaic-sky-identities',
    '#mosaic-sky-overview','#mosaic-sky-selected','#clear-filters',
    '.evidence-pager [aria-controls="sky"]']) elems[name]=control();
  const row=control();row.dataset.row='0';row.attrs['aria-pressed']='true';
  const filter=control();
  const root={querySelector:s=>elems[s],querySelectorAll:s=>s==='[data-row]'?[row]:s==='[data-filter]'?[filter]:[]};
  const overlays=[],catalogs=[];let creations=0,resolve;
  const pending=new Promise(r=>{resolve=r;});
  const viewer={addOverlay(){},addCatalog(){},gotoRaDec(){},setFoV(){},getBaseImageLayer(){return {setOpacity(){}};}};
  const A={aladin(){creations++;return viewer;},
    graphicOverlay(options){const layer={options,items:[],add(x){this.items.push(x);},removeAll(){this.items=[];}};overlays.push(layer);return layer;},
    catalog(options){const catalog={options,addSources(){},removeAll(){}};catalogs.push(catalog);return catalog;},
    source(){return {};},circle(...args){return args;},polyline(...args){return args;}};
  const scene={available:true,source:'Archive',proposed:[{id:'P1',center:[0,0]}],
    proposed_beams:[{radius_arcsec:10}],candidate:{kind:'beams',radius_arcsec:10,beams:[{center:[0,0]}]}};
  const document={querySelector:()=>root,getElementById:()=>({textContent:JSON.stringify([scene])}),createElement:()=>control()};
  const window={MosaicSkyGeometry:{fallback(){},extent(){return {origin:[0,0],fov:.01};}},
    AlmaSkyRuntime:{load:()=>pending,surveys:{dss:'dss'},async loadReferenceImagery(){}}};
  vm.runInNewContext(source,{document,window,console});
  elems['.evidence-pager [aria-controls="sky"]'].emit('click');
  row.hidden=true;resolve(A);await new Promise(r=>setImmediate(r));
  assert.equal(creations,0);
  assert.match(elems['#mosaic-imagery-status'].textContent,/paused/);
  row.hidden=false;filter.emit('change');await new Promise(r=>setImmediate(r));
  assert.equal(creations,1);
  assert.equal(JSON.stringify(overlays.find(x=>x.options.name==='Submitted Mosaic half-power beams').options.lineDash),'[6,5]');
  assert.equal(JSON.stringify(overlays.find(x=>x.options.name==='Queue saved footprints').options.lineDash),'[6,4]');
  assert.equal(JSON.stringify(overlays.find(x=>x.options.name==='Archive saved footprints').options.lineDash),'[]');
  assert.equal(catalogs.find(x=>x.options.name==='Archive beam centres').options.color,'#176fba');
  assert.equal(catalogs.find(x=>x.options.name==='Queue beam centres').options.color,'#d88a00');
});
