'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const geom=require('../../src/alma_duplicate/ui/static/mosaic-sky-geometry.js');

const entry={available:true, source:'Archive', proposed:[
  {id:'p1',center:[359.999,0]}, {id:'p2',center:[.001,0]}],
  proposed_beams:[{frequency_ghz:690,radius_arcsec:8}],
  candidate:{kind:'region',outline:[[359.99,-.01],[.01,-.01],[.01,.01],[359.99,.01]]}};

test('ICRS wrap and north-up/east-left remain finite',()=>{
  const p=geom.offset([359.999,0],[.001,0]);
  assert.ok(p[0]<0&&Math.abs(p[0])<9);
  assert.ok(geom.offset([0,0],[0,.001])[1]<0);
  assert.equal(geom.offset([0,0],[180,0]),null);
});
test('fit bounds include the entire saved region and do not infer an observation centre',()=>{
  const view=geom.extent(entry);
  assert.ok(view && view.arcsec>10 && view.fov>0 && view.fov<.08);
  assert.deepEqual(view.origin,[359.999,0]);
  assert.equal(Object.hasOwn(entry.candidate,'center'),false);
});
test('missing candidate geometry does not create an artificial beam',()=>{
  const missing={...entry,candidate:null,reason:'unavailable'};
  assert.equal(geom.coordinates(missing).length,2);
  assert.equal(geom.extent({available:false,proposed:[]}),null);
});
test('fallback keeps proposed points and archived polygon but no optical pixels',()=>{
  const previous=global.document;
  const tags=[];
  const element=name=>({name,attrs:{},children:[],setAttribute(k,v){this.attrs[k]=String(v);},
    append(x){this.children.push(x);},textContent:''});
  global.document={createElementNS(_ns,name){tags.push(name);return element(name);}};
  const canvas={replaceChildren(node){this.svg=node;}};
  try {
    assert.equal(geom.fallback(canvas,entry),true);
    assert.ok(tags.includes('polyline'));
    assert.equal(tags.includes('image'),false);
    assert.ok(canvas.svg.attrs['aria-label'].includes('optical imagery unavailable'));
    const texts=canvas.svg.children.filter(x=>x.name==='text').map(x=>x.textContent);
    assert.ok(texts.some(x=>x.includes('no optical imagery')));
  } finally {global.document=previous;}
});
test('Queue saved beam radius is retained without turning a representative point into coverage',()=>{
  const queue={...entry,source:'Queue',candidate:{kind:'beams',
    radius_arcsec:18,beams:[{id:'b1',center:[0,0]},{id:'b2',center:[.001,0]}]}};
  assert.equal(geom.coordinates(queue).length,4);
  assert.ok(geom.extent(queue).arcsec>=18);
});

test('fit includes offset plus radius and is independent of candidate order',()=>{
  const base={available:true,proposed:[{center:[0,0]},{center:[.02,0]}],
    proposed_beams:[{radius_arcsec:72}],candidate:null};
  const view=geom.extent(base);
  assert.ok(view.arcsec>=144 && view.arcsec<145);
  const candidate=(radius)=>({...base,proposed_beams:[],candidate:{kind:'beams',radius_arcsec:radius,
    beams:[{center:[.02,0],radius_arcsec:radius}]}});
  const a=candidate(100),b=candidate(2);
  assert.equal(geom.extent(base,[a,b]).arcsec,geom.extent(base,[b,a]).arcsec);
  assert.ok(geom.extent(base,[a,b]).arcsec<173);
});
