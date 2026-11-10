'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const geo=require('../../src/alma_duplicate/ui/static/mosaic-sky-geometry.js');

function sample(source) {
  return {available:true,source,proposed:[{id:'P1',center:[0,0]}],
    proposed_beams:[{frequency_ghz:230,radius_arcsec:10}],
    candidate:source==='Archive'?
      {kind:'region',outline:[[359.995,-.005],[.005,-.005],[.005,.005],[359.995,.005]]}:
      {kind:'beams',radius_arcsec:16,beams:[{id:'beam',center:[.001,0]}]}};
}
function svgNodes(scene) {
  const previous=global.document;const nodes=[];
  global.document={createElementNS(_ns,name){const node={name,attrs:{},children:[],textContent:'',
    setAttribute(k,v){this.attrs[k]=String(v);},append(child){this.children.push(child);}};
    nodes.push(node);return node;}};
  try {assert.equal(geo.fallback({replaceChildren(){}},scene),true);return nodes;}
  finally {global.document=previous;}
}
test('Archive and submitted Mosaic geometry use distinct source/meaning encodings',()=>{
  const nodes=svgNodes(sample('Archive'));
  const strokes=nodes.map(n=>n.attrs.stroke);
  assert.ok(strokes.includes('#176fba'),'Archive outline is blue, even selected');
  assert.ok(strokes.includes('#a12b9b'),'Proposed HPBW is magenta, not Archive');
  assert.ok(nodes.some(n=>n.name==='path' && n.attrs.stroke==='#00b9af'),
    'Submitted OT centres are teal crosses');
  assert.ok(nodes.some(n=>n.attrs.stroke==='#ffffff'),
    'Selected record has a non-semantic white highlight halo');
});
test('Queue beams stay amber and dashed even when selected',()=>{
  const nodes=svgNodes(sample('Queue'));
  assert.ok(nodes.some(n=>n.name==='circle' && n.attrs.stroke==='#d88a00'
    && n.attrs['stroke-dasharray']==='6 4'));
  assert.ok(!nodes.some(n=>n.attrs.stroke==='#176fba'));
});
