const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise the controller through DOM events with an offline Aladin adapter.
function setup({init=Promise.resolve(),panStarrsAvailable=true}={}) {
  class Element {
    constructor() { this.dataset={aladinModule:"/local/aladin.js"}; this.children=[]; this.handlers={}; this.attrs={}; this.style={}; this.clientWidth=600; this.clientHeight=390; this.scrollLeft=0; }
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
  const layer=id=>({id,name:id,setBrightness(){},setContrast(){},setOpacity(value){this.alpha=value;}});
  let base=layer('https://skies.esac.esa.int/DSSColor/');
  const viewer={addOverlay(){},addCatalog(c){catalogs.push(c);},gotoRaDec(){},setFoV(){},getFov(){return [.1];},getBaseImageLayer(){return base;},setBaseImageLayer(next){base=next;return base;}};
  const A={init,HiPS:id=>({...layer(id),url:id,maxOrder:11,imgFormat:'jpeg',query:
    id.includes('Pan-STARRS') && !panStarrsAvailable
      ? Promise.reject(new Error('Pan-STARRS unavailable')) : Promise.resolve()}),aladin:()=>viewer,catalog:options=>({options,sources:[],removeAll(){this.sources=[];},addSources(rows){this.sources.push(...rows);}}),source:(ra,dec,data)=>({ra,dec,data}),graphicOverlay:()=>({removeAll(){},add(){},show(){}}),circle(){},polyline(){}};
  const rows=['a','b','c'].map((id,i)=>({id,label:id,source:'ARCHIVE',intent:'LINE',spw:i,spatial:{available:true,center:i===2?[11,21]:[10,20],separation_arcsec:0,radius_arcsec:5}}));
  let selected='a', visible=rows, controller;
  const state={origin:[10,20],rows:()=>visible,selected:()=>selected,select:id=>{selected=id;controller.update();}};
  const context={window:{addEventListener(){}},document:{querySelector:s=>get(s.slice(1)),getElementById:get,createElement:()=>new Element()},A,console:{warn(){}},setTimeout,clearTimeout,setInterval,clearInterval,matchMedia:()=>({matches:true}),MutationObserver:class {observe(){}},ResizeObserver:class {observe(){}}};
  context.window.A=A;
  const runtime=require('../../src/alma_duplicate/ui/static/alma-sky-runtime.js');
  context.window.AlmaSkyRuntime={...runtime,load:async()=>{await init;return A;}};
  context.window.renderReportSkyFallback=()=>{get('report-sky-canvas').fallbackRendered=true;};
  vm.runInNewContext(fs.readFileSync('src/alma_duplicate/ui/static/report-sky.js','utf8'),context);
  controller=context.window.createReportSky(state);
  get('position-sky').emit('click');
  return {get,viewer,A,catalogs,rows,state,controller,filter:items=>{visible=items;controller.update();}};
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

test('failed Aladin initialization falls back to saved geometry instead of a black panel', async()=>{
  const h=setup({init:Promise.reject(new Error('WebGL unavailable'))});
  await settle();
  assert.equal(h.get('report-sky-canvas').fallbackRendered,true);
  assert.equal(h.get('sky-retry').hidden,false);
  assert.match(h.get('report-sky-status').textContent,/geometry only/);
  assert.match(h.get('sky-imagery-status').textContent,/No reference image/);
});



test('reference imagery visibility does not change saved evidence', async()=>{
  const h=setup();await settle();
  const saved=JSON.stringify(h.rows);
  h.get('sky-show-imagery').checked=false;h.get('sky-show-imagery').emit('change');
  assert.equal(h.viewer.getBaseImageLayer().alpha,0);
  assert.match(h.get('sky-imagery-status').textContent,/hidden/);
  h.get('sky-show-imagery').checked=true;h.get('sky-show-imagery').emit('change');
  assert.equal(h.viewer.getBaseImageLayer().alpha,1);
  assert.equal(JSON.stringify(h.rows),saved);
});

test('report exposes native layer menu instead of custom survey presets',()=>{
  const html=fs.readFileSync('src/alma_duplicate/ui/templates/visualization.html','utf8');
  assert.doesNotMatch(html,/id="sky-survey-(dss|ps)"/);
  assert.match(html,/layers menu/);
});

test('Mosaic uses saved region polyline without a fabricated circular beam or separation', async()=>{
  const h=setup();await settle();
  const outline=[[9.9,19.9],[10.1,19.9],[10,20.1],[9.9,19.9]];
  const lines=[],circles=[];
  h.A.polyline=(points)=>{lines.push(points);};
  h.A.circle=(...args)=>{circles.push(args);};
  Object.assign(h.rows[0].spatial,{sky_outline:outline,coverage_source:'ARCHIVE_S_REGION',
    point_status:'INSIDE',s_region_sha256:'region1',radius_arcsec:null,separation_arcsec:null});
  h.filter([h.rows[0]]);
  assert.equal(lines.length,1);
  assert.deepEqual(lines[0],outline);
  assert.equal(circles.length,0);
  assert.match(h.get('sky-relationship').textContent,/Mosaic coverage: inside/);
});

test('Queue beam descriptions preserve the saved model status and historical fallback', async () => {
  const h = setup();
  await settle();
  const row = h.rows[0];
  row.source = 'QUEUE';
  row.array_diameter_m = 12;
  row.spatial.beams = [{center:[10,20]}];
  row.spatial.covered_beam_count = 1;
  for (const [kind, saved, expected] of [
    ['rectangle', 'PROJECT_ACCEPTED', 'PROJECT_ACCEPTED'],
    ['rectangle', 'UNRESOLVED', 'UNRESOLVED'],
    ['custom', 'PROJECT_ACCEPTED', 'PROJECT_ACCEPTED'],
    ['custom', 'UNRESOLVED', 'UNRESOLVED'],
    ['custom', 'PROVISIONAL', 'PROVISIONAL'],
    ['rectangle', undefined, 'PROVISIONAL'],
  ]) {
    row.geometry_kind = kind;
    row.spatial.model_status = saved;
    h.controller.update();
    assert.ok(h.get('sky-relationship').textContent.endsWith(`(model: ${expected}).`));
  }
});
