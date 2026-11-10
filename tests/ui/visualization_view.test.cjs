const {test} = require('node:test');
const assert = require('node:assert/strict');
const view = require('../../src/alma_duplicate/ui/static/visualization_view.js');
const near = (a,b) => assert.ok(Math.abs(a-b)<1e-9, `${a} != ${b}`);

test('zoom preserves the evidence point beneath the pointer after a pan', () => {
  const before={x:42,y:-18,k:2}, origin=[240,220], pointer=[380,130];
  const after=view.zoom(before,1.6,pointer,origin);
  for (const [i,axis] of ['x','y'].entries()) {
    const data=(pointer[i]-origin[i]-before[axis])/before.k;
    near(origin[i]+data*after.k+after[axis],pointer[i]);
  }
  assert.deepEqual(before,{x:42,y:-18,k:2});
});
test('zoom limits and reverse zoom retain anchor and do not drift', () => {
  let v=view.fresh();
  for (let i=0;i<20;i++) v=view.zoom(v,1.6,[51,81],[240,220]);
  assert.equal(v.k,64);
  assert.deepEqual(view.zoom(v,2,[12,52],[240,220]),v);
  const base={x:25,y:30,k:3};
  const back=view.zoom(view.zoom(base,1.6,[55,85],[240,220]),1/1.6,[55,85],[240,220]);
  near(back.x,base.x); near(back.y,base.y); near(back.k,base.k);
  assert.equal(view.zoom(view.fresh(),.001,[0,0],[0,0]).k,.25);
});
test('frequency panning and zoom leave row positions unchanged', () => {
  const p=view.pan(view.fresh(),27,44,true);
  assert.deepEqual(p,{x:27,y:0,k:1});
  assert.equal(view.zoom(p,2,[180,300],[350,0],true).y,0);
});
test('overlap picking returns every coincident comparison without changing geometry', () => {
  const shape=[[0,0],[10,0],[10,10],[0,10]], saved=JSON.stringify(shape);
  const rows=[{id:'a',polygon:shape},{id:'b',polygon:shape}];
  assert.deepEqual(rows.filter(r=>view.hits([5,5],r.polygon,[5,5],.5)).map(r=>r.id),['a','b']);
  assert.equal(view.hits([10.3,7],shape,[5,5],.5),true);
  assert.equal(view.hits([12,7],shape,[5,5],.5),false);
  assert.equal(JSON.stringify(shape),saved);
});
test('missing outlines remain point targets, not invented beam areas', () => {
  assert.equal(view.hits([7,5],[],[5,5],3),true);
  assert.equal(view.hits([9,5],[],[5,5],3),false);
});

const comparisons = [
  {id:'a',source:'ARCHIVE',identity:{Project:'P1','Member OUS':'m1'},spw:25},
  {id:'b',source:'ARCHIVE',identity:{Project:'P1','Member OUS':'m1'},spw:27},
  {id:'c',source:'ARCHIVE',identity:{Project:'P1','Member OUS':'m2'},spw:25},
  {id:'d',source:'QUEUE',identity:{Project:'P1'},spw:1},
  {id:'e',source:'ARCHIVE',identity:{Project:'P2','Member OUS':'m1'},spw:25},
  {id:'f',source:'QUEUE',identity:{},spw:1},
];
test('project and Member filters preserve separate SPWs, contexts and input', () => {
  const before=JSON.stringify(comparisons);
  const filtered=view.filter(comparisons,view.projectKey(comparisons[0]),view.memberKey(comparisons[0]));
  assert.deepEqual(filtered.map(r=>r.id),['a','b']);
  assert.equal(filtered[0],comparisons[0]);
  assert.deepEqual(view.filter(comparisons,view.projectKey(comparisons[3]),view.memberKey(comparisons[3])).map(r=>r.id),['d']);
  assert.deepEqual(view.filter(comparisons,view.projectKey(comparisons[5])).map(r=>r.id),['f']);
  assert.equal(JSON.stringify(comparisons),before);
});
test('selection survives matching filters and moves to an eligible row otherwise', () => {
  const filtered=view.filter(comparisons,view.projectKey(comparisons[0]),view.memberKey(comparisons[0]));
  assert.equal(view.selection(filtered,'b'),'b');
  assert.equal(view.selection(filtered,'e'),'a');
  assert.equal(view.selection([],'a'),null);
  assert.deepEqual(view.visible(filtered,'b',true).map(r=>r.id),['b']);
  assert.deepEqual(view.visible(filtered,'b',false),filtered);
  assert.deepEqual(view.visible([],null,true),[]);
});
test('focus fits both proposed position and complete candidate boundary at equal scale', () => {
  const origin=[240,220], points=[[240,220],[310,180],[350,180],[350,240],[310,240]];
  const before=JSON.stringify(points), fitted=view.fit(points,origin,185,185);
  for (const p of points) {
    const x=origin[0]+(p[0]-origin[0])*fitted.k+fitted.x;
    const y=origin[1]+(p[1]-origin[1])*fitted.k+fitted.y;
    assert.ok(x>=55 && x<=425); assert.ok(y>=35 && y<=405);
  }
  assert.equal(JSON.stringify(points),before);
});
test('frequency focus contains proposed marker plus both ends of a LINE interval', () => {
  const points=[[500,0],[140,0],[190,0]], fitted=view.fit(points,[350,0],215,1,true);
  for (const [p] of points) {
    const x=350+(p-350)*fitted.k+fitted.x;
    assert.ok(x>=135 && x<=565);
  }
  assert.equal(fitted.y,0);
});
test('coincident markers focus finitely and unavailable geometry has no invented fit', () => {
  assert.deepEqual(view.fit([], [240,220],185,185),null);
  const f=view.fit([[200,0],[200,0]],[350,0],215,1,true);
  assert.equal(f.k,64); assert.ok(Number.isFinite(f.x));
});

test('display relationships preserve signed LINE edge distances and input evidence', () => {
  const row={spatial:{available:true,separation_arcsec:5,radius_arcsec:10},spectral:{available:true,kind:'interval',proposed:99,low:100,high:110}};
  const before=JSON.stringify(row);
  assert.deepEqual(view.relationships(row),{radiusRatio:.5,lowerMarginGHz:-1,upperMarginGHz:11});
  assert.equal(JSON.stringify(row),before);
  row.spectral.proposed=110;
  assert.equal(view.relationships(row).upperMarginGHz,0);
  row.spectral.proposed=111;
  assert.equal(view.relationships(row).upperMarginGHz,-1);
});
test('missing evidence and continuum representatives never invent interval coverage', () => {
  for (const radius of [0,null,undefined,Infinity,-1]) {
    const result=view.relationships({spatial:{available:true,separation_arcsec:0,radius_arcsec:radius},spectral:{available:true,kind:'representative',proposed:100,candidate:101}});
    assert.deepEqual(result,{radiusRatio:null,lowerMarginGHz:null,upperMarginGHz:null});
  }
  assert.deepEqual(view.relationships({spatial:{available:false},spectral:{available:false}}),{radiusRatio:null,lowerMarginGHz:null,upperMarginGHz:null});
  assert.equal(view.relationships({spatial:{available:true,separation_arcsec:null,radius_arcsec:10},spectral:{available:true,kind:'interval',proposed:100,low:110,high:90}}).lowerMarginGHz,null);
});


test('object colors remain shared across arrays/SPWs and stable through filtering', () => {
  const rows = [
    {id:'q-12-spw1',source:'QUEUE',identity:{Project:'P','Queue candidate':'q'}},
    {id:'q-7-spw2',source:'QUEUE',identity:{Project:'P','Queue candidate':'q'}},
    {id:'other',source:'QUEUE',identity:{Project:'P','Queue candidate':'other'}},
    {id:'a1',source:'ARCHIVE',identity:{Project:'P','Member OUS':'member'}},
    {id:'a2',source:'ARCHIVE',identity:{Project:'P','Member OUS':'member'}},
  ];
  view.assignColors(rows);
  assert.equal(rows[0].plot_color,rows[1].plot_color);
  assert.equal(rows[3].plot_color,rows[4].plot_color);
  assert.equal(new Set(rows.map(r=>r.plot_color)).size,3);
  assert.ok(rows.every(r=>r.plot_color !== '#983b64'));
  const colors=rows.map(r=>r.plot_color);
  assert.equal(view.filter(rows,view.projectKey(rows[0]))[0].plot_color,colors[0]);
  view.assignColors([...rows].reverse());
  assert.deepEqual(rows.map(r=>r.plot_color),colors);
});


test('array filter separates matching branches without changing their object colors', () => {
  const rows = [7,12].map(d=>({id:String(d),source:'QUEUE',array_diameter_m:d,
    identity:{Project:'P','Queue candidate':'same'}}));
  view.assignColors(rows);
  assert.deepEqual(view.filter(rows,'','','7-m').map(r=>r.id), ['7']);
  assert.deepEqual(view.filter(rows,'','','12-m').map(r=>r.id), ['12']);
  assert.equal(view.filter(rows).length,2);
  assert.equal(rows[0].plot_color, rows[1].plot_color);
});


test('Queue setup exposes saved SPWs separately without creating matching comparisons', () => {
  const row={id:'q12',source:'QUEUE',spectral:{coverage:[
    {spw:1,low:210,high:211},{spw:3,low:230,high:231}]}};
  const before=JSON.stringify(row);
  const setup=view.queueSetup(row);
  assert.equal(setup.queue,true);
  assert.deepEqual(setup.components.map(c=>c.index),[1,3]);
  assert.deepEqual(setup.components.map(c=>c.interval),row.spectral.coverage);
  assert.equal(JSON.stringify(row),before);
  assert.notEqual(view.queueSetup({...row,id:'q7'}).id,setup.id);
  assert.equal(view.queueSetup({source:'QUEUE',spectral:{}}),null);
  assert.equal(view.queueSetup({...row,source:'ARCHIVE'}),null);
});
