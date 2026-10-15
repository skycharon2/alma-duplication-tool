const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise the controller through DOM events with an offline Aladin adapter.
function setup() {
  class Element {
    constructor() { this.children=[]; this.handlers={}; this.attrs={}; this.style={}; this.clientWidth=600; this.clientHeight=390; this.scrollLeft=0; }
    addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
    emit(type) { for (const fn of this.handlers[type] || []) fn({target:this}); }
    replaceChildren() { this.children=[]; }
    append(...children) { this.children.push(...children); }
    setAttribute(key,value) { this.attrs[key]=value; }
    querySelector() { return this.children.find(c=>c.attrs['aria-pressed']==='true'); }
    focus() { this.focused=true; }
    getBoundingClientRect() { return {height:600}; }
    scrollTo({left}) { this.scrollLeft=left; this.emit('scroll'); }
  }
  const elements=new Map();
  const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  for (const id of ['sky-show-beams','sky-show-imagery']) get(id).checked=true;
  const catalogs=[];
  const layer=id=>({id,name:id,setBrightness(){},setContrast(){},setAlpha(value){this.alpha=value;}});
  let base=layer('P/DSS2/color');
  const viewer={addOverlay(){},addCatalog(c){catalogs.push(c);},gotoRaDec(){},setFoV(){},getFov(){return [.1];},getBaseImageLayer(){return base;},setBaseImageLayer(id){base=layer(id);return Promise.resolve(base);}};
  const A={init:Promise.resolve(),aladin:()=>viewer,catalog:options=>({options,sources:[],removeAll(){this.sources=[];},addSources(rows){this.sources.push(...rows);}}),source:(ra,dec,data)=>({ra,dec,data}),graphicOverlay:()=>({removeAll(){},add(){},show(){}}),circle(){},polyline(){}};
  const rows=['a','b','c'].map((id,i)=>({id,label:id,source:'ARCHIVE',intent:'LINE',spw:i,spatial:{available:true,center:i===2?[11,21]:[10,20],separation_arcsec:0,radius_arcsec:5}}));
  let selected='a', visible=rows, controller;
  const state={origin:[10,20],rows:()=>visible,selected:()=>selected,select:id=>{selected=id;controller.update();}};
  const context={window:{addEventListener(){}},document:{querySelector:s=>get(s.slice(1)),getElementById:get,createElement:()=>new Element()},A,setTimeout,clearTimeout,setInterval,clearInterval,matchMedia:()=>({matches:true}),MutationObserver:class {observe(){}},ResizeObserver:class {observe(){}}};
  context.window.A=A;
  vm.runInNewContext(fs.readFileSync('src/alma_duplicate/ui/static/report-sky.js','utf8'),context);
  controller=context.window.createReportSky(state);
  get('position-sky').emit('click');
  return {get,viewer,catalogs,rows,state,controller,filter:items=>{visible=items;controller.update();}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('selected coincident records remain selectable with other candidates hidden', async()=>{
  const h=setup();await settle();
  const selected=h.catalogs.find(c=>c.options.name==='Selected candidate center');
  assert.deepEqual(Array.from(selected.sources[0].data.ids),['b','a']);
  selected.options.onClick(selected.sources[0]);
  const buttons=h.get('report-sky-choices').children.filter(c=>c.type==='button');
  assert.equal(buttons.length,2);
  buttons.find(b=>b.attrs['aria-pressed']==='false').onclick();
  assert.equal(h.state.selected(),'b');
  assert.equal(h.get('report-sky-choices').querySelector().focused,true);
  h.filter([h.rows[1]]);
  assert.equal(h.get('report-sky-choices').children.length,0);
});

test('target marker at the same position also opens all coincident records', async()=>{
  const h=setup();await settle();
  h.catalogs.find(c=>c.options.name==='Your proposed target').options.onClick();
  assert.equal(h.get('report-sky-choices').children.length,3);
});

test('relationship metrics handle inside, boundary, outside and missing evidence', async()=>{
  const h=setup();await settle();
  for (const [separation,label,ratio] of [[0,'Inside','0.0%'],[5,'On','100.0%'],[7,'Outside','140.0%']]) {
    h.rows[0].spatial.separation_arcsec=separation;h.controller.update();
    assert.ok(h.get('sky-relationship').textContent.startsWith(label));
    assert.equal(h.get('sky-radius-ratio').textContent,ratio);
  }
  h.rows[0].spatial.radius_arcsec=null;h.controller.update();
  assert.equal(h.get('sky-relationship').textContent,'Position relationship unknown');
  assert.equal(h.get('sky-radius-ratio').textContent,'Not available');
});

test('survey controls show active, loading, failed and hidden states without changing evidence', async()=>{
  const h=setup();await settle();
  const saved=JSON.stringify(h.rows);
  assert.equal(h.get('sky-survey-dss').attrs['aria-pressed'],'true');
  h.get('sky-survey-ps').emit('click');
  assert.match(h.get('sky-imagery-status').textContent,/Loading/);
  await settle();
  assert.equal(h.get('sky-survey-ps').attrs['aria-pressed'],'true');
  assert.equal(h.get('sky-survey-dss').attrs['aria-pressed'],'false');
  assert.match(h.get('sky-imagery-status').textContent,/Coverage not verified/);
  h.viewer.setBaseImageLayer=()=>Promise.reject(new Error('offline'));
  h.get('sky-survey-dss').emit('click');await settle();
  assert.match(h.get('sky-imagery-status').textContent,/could not be loaded/);
  h.get('sky-show-imagery').checked=false;h.get('sky-show-imagery').emit('change');
  assert.equal(h.viewer.getBaseImageLayer().alpha,0);
  assert.match(h.get('sky-imagery-status').textContent,/hidden/);
  assert.equal(JSON.stringify(h.rows),saved);
});


test('an immediately returned HiPS does not report completion before activation', async()=>{
  const h=setup();await settle();
  let resolveQuery;
  const pending={...h.viewer.getBaseImageLayer(),id:'P/PanSTARRS/DR1/color-z-zg-g',query:new Promise(resolve=>{resolveQuery=resolve;})};
  h.viewer.setBaseImageLayer=()=>pending;
  h.get('sky-survey-ps').emit('click');await settle();
  assert.match(h.get('sky-imagery-status').textContent,/Loading/);
  resolveQuery();await settle();
  assert.match(h.get('sky-imagery-status').textContent,/Loading/);
  h.viewer.getBaseImageLayer=()=>pending;
  await new Promise(resolve=>setTimeout(resolve,120));
  assert.match(h.get('sky-imagery-status').textContent,/Coverage not verified/);
});
