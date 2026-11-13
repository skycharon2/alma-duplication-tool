'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.resolve('src/alma_duplicate/ui/static/mosaic-comparison-overview.js'),'utf8');

class Element {
  constructor(tag='div') {
    this.tag=tag;this.children=[];this.attrs={};this.dataset={};this.style={setProperty(k,v){this[k]=v;}};
    this.hidden=false;this.textContent='';this.callbacks={};this.parentElement=null;
    this.classList={add(){},remove(){},contains(){return false;}};
  }
  append(...nodes){for(const node of nodes){node.parentElement=this;this.children.push(node);}}
  replaceChildren(...nodes){this.children=[];this.append(...nodes);}
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k]??null;}
  addEventListener(k,fn){(this.callbacks[k]||=[]).push(fn);}
  emit(k,props={}){
    const event={key:'',button:0,pointerId:1,ctrlKey:false,metaKey:false,
      clientX:0,clientY:0,deltaY:0,preventDefault(){this.prevented=true;},...props};
    for(const f of this.callbacks[k]||[])f(event);return event;
  }
  click(){this.emit('click');}
  querySelector(s){return s==='svg'?this.children.find(n=>n.tag==='svg'):null;}
  querySelectorAll(s){return s==='[data-setup-toggle]'?nodes(this,'g').filter(n=>n.attrs['data-setup-toggle']!==undefined):[];}
  focus(){this.focused=true;}
  closest(){return null;}
}
const nodes=(root,tag)=>[root,...root.children.flatMap(n=>nodes(n,tag))]
  .filter(n=>!tag||n.tag===tag);
function fixture({count=3,duplicates=true,continuum=false,missingSpw=false,
  invalidComponent=false,missingComponentLabel=false,sameSetupId=false,queueLine=false,withoutSetup=false,noSetupId=false,boundCoverage=false}={}){
  const items=[];
  for(let i=0;i<count;i++){
    const same=duplicates&&i===1;
    const x=same?245:245+i*17;
    items.push({source:i>=2?'Queue':'Archive',candidate:i<2?'uid://a/b':'hash:single:abcdefghijklmnopqrstuvwxyz',
      target:i>=2?'V462_Lup':'NGC253',array:i>=2?'7 m':'12 m',
      position:{outlines:[`${x},190 ${x+38},190 ${x+38},230 ${x},230`],
        points:[{xy:[245,210]},{xy:[265,213]},{xy:[235,225]}],
        proposal_beams:[{outlines:['220,180 280,180 280,240 220,240']}],
        ticks:[{east:50,north:50}],scale:50},
      intent:i>=2?(queueLine?'LINE':'CONTINUUM'):(continuum?'CONTINUUM':'LINE'), project:i<2?'2018.1.00294.S':'2024.A.00044.T',
      frequency:{setup_id:withoutSetup||noSetupId?null:sameSetupId?'shared-id':i<2?'archive-setup-1':'queue-setup-1',setup_label:i<2?'Archive recorded setup':'Queue nominal setup',ticks:[{x:135,value:89},{x:565,value:110}],
        setup:withoutSetup?[]:[{label:missingComponentLabel?null:i<2?'Component 1':'SPW 1',
          raw_low:invalidComponent?null:i>=2?93:94,
          raw_high:invalidComponent?null:i>=2?94:95,
          usable_low:i>=2?93.1:null,usable_high:i>=2?93.9:null,
          status:invalidComponent?'NOT_RECORDED':'RECORDED'}],
        matching:[{low:215+i*20,high:225+i*20,proposed:220+i*20,spw:missingSpw?null:i+1,kind:boundCoverage?'representative':'interval',coverage:boundCoverage?[{low:190,high:260,bandwidth_ghz:3.4}]:[]}]}
    });
  }
  return items;
}
function setup(options={}){
  const spatial=new Element('section'),frequency=new Element('section');
  spatial.hidden=true;frequency.hidden=true;
  spatial.append(new Element('svg'));frequency.append(new Element('svg'));
  const rows=fixture(options).map((_,i)=>{const e=new Element('button');e.dataset.row=String(i);return e;});
  const posTools=new Element('div'),freqTools=new Element('div');
  const oldTools=[new Element('div'),new Element('div')];
  let selected=0,isolated=false,clicks=0;
  const root={
    querySelector(s){return {
      '#mosaic-overview-position':spatial,'#mosaic-overview-frequency':frequency,
      '#mosaic-position-tools':posTools,'#mosaic-frequency-tools':freqTools
    }[s]||null;},
    querySelectorAll(s){return {'[data-row], [data-evidence]':rows,'[data-row]':rows,'#charts [data-evidence]':[],
      '[data-plot-controls]':oldTools}[s]||[];}
  };
  rows.forEach((button,i)=>button.addEventListener('click',()=>{
    selected=i;clicks++;
    root.mosaicOverviewRender({visible:rows.map(r=>r.dataset.row),selected:String(selected),isolated});
  }));
  const data=fixture(options);
  const document={
    querySelector:s=>s==='.mosaic-explorer'?root:null,
    getElementById:s=>s==='mosaic-overview-data'?{textContent:JSON.stringify(data)}:null,
    createElement:tag=>new Element(tag),createElementNS:(_ns,tag)=>new Element(tag)
  };
  vm.runInNewContext(source,{document,URL:undefined}, {filename:'mosaic-comparison-overview.js'});
  const render=(ids=rows.map(r=>r.dataset.row),single=isolated)=>{
    isolated=single;root.mosaicOverviewRender({visible:ids,selected:String(selected),isolated:single});};
  render();
  return {root,spatial,frequency,rows,posTools,freqTools,oldTools,
    render,selected:()=>selected,isolated:()=>isolated,clicks:()=>clicks};
}


const toggles=h=>nodes(h.frequency,'g').filter(g=>g.attrs['data-setup-toggle']!==undefined);
const freqTexts=h=>nodes(h.frequency,'text').map(t=>t.textContent);
const detailRows=h=>nodes(h.frequency,'g').filter(g=>g.attrs['data-overview-row']!==undefined);

test('Single parity: collapsed grouped setups are compact and draw no matching rows',()=>{
  const h=setup();
  assert.equal(h.spatial.hidden,false);assert.equal(h.frequency.hidden,false);
  assert.equal(h.oldTools.every(tool=>tool.hidden),true);
  assert.equal(nodes(h.spatial,'path').length,3);
  assert.equal(nodes(h.spatial,'polygon').length,2);
  assert.equal(nodes(h.spatial,'polyline').length,1);
  assert.equal(toggles(h).length,2);
  assert.equal(detailRows(h).length,0);
  assert.equal(nodes(h.frequency,'path').length,3); // 2 archive markers + 1 queue marker
  assert.equal(nodes(h.spatial,'svg')[0].attrs.viewBox,'0 0 460 460');
  assert.equal(nodes(h.frequency,'svg')[0].attrs.viewBox,'0 0 600 330');
});
test('collapsed Setup bars and diamonds paint ABOVE their row background',()=>{
  const h=setup(),svg=nodes(h.frequency,'svg')[0];
  const bg=svg.children.findIndex(n=>n.attrs['data-frequency-row-backgrounds']==='true');
  const clipped=svg.children.findIndex(n=>n.attrs['clip-path']==='url(#mosaic-overview-frequency-clip)');
  const togglesOnTop=svg.children.filter(n=>n.attrs['data-setup-toggle']!==undefined);
  assert.ok(bg>=0&&clipped>bg,'background layer must precede clipped frequency evidence');
  assert.equal(togglesOnTop.length,2);
  assert.ok(togglesOnTop.every(g=>svg.children.indexOf(g)>clipped));
  // The visible opaque fill is NOT inside the interactive layer; it used to
  // hide every recorded SPW bar in V7 on first load.
  for(const toggle of togglesOnTop){
    const hit=nodes(toggle,'rect').filter(r=>r.attrs['data-setup-hit-area']==='true');
    assert.equal(hit.length,1);
    assert.equal(hit[0].attrs.fill,'transparent');
    assert.equal(toggle.children.some(c=>c.tag==='rect'&&c.attrs.fill!=='transparent'),false);
  }
  assert.equal(nodes(svg.children[bg],'rect').filter(r=>r.attrs.fill==='#f0f6fb').length,1);
  assert.ok(nodes(svg.children[clipped],'line').filter(n=>n.attrs.stroke!=='#dce5ec').length>=2);
  assert.ok(nodes(svg.children[clipped],'path').length>=2,'requested markers must be above backgrounds');
});

test('Setup intervals remain above background after expansion and collapse',()=>{
  const h=setup(),get=()=>toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1'));
  for(const step of [false,true,false]){
    if(step===true)get().click();
    else if(get().attrs['aria-expanded']==='true')get().click();
    const svg=nodes(h.frequency,'svg')[0];
    const bg=svg.children.findIndex(n=>n.attrs['data-frequency-row-backgrounds']==='true');
    const clip=svg.children.findIndex(n=>n.attrs['clip-path']==='url(#mosaic-overview-frequency-clip)');
    assert.ok(bg>=0&&clip>bg);
    assert.ok(nodes(svg.children[clip],'line').length>=2);
    assert.ok(toggles(h).every(g=>nodes(g,'rect').find(r=>r.attrs['data-setup-hit-area'])?.attrs.fill==='transparent'));
  }
});

test('Archive setup expands to matching comparison rows, not Component detail rows',()=>{
  const h=setup(),archive=()=>toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1'));
  assert.equal(archive().attrs['aria-expanded'],'false');
  assert.equal(detailRows(h).length,0);
  archive().click();
  assert.equal(archive().attrs['aria-expanded'],'true');
  assert.equal(detailRows(h).length,2);
  assert.deepEqual(freqTexts(h).filter(t=>/^#\d+ LINE/.test(t)),['#1 LINE · SPW 1','#2 LINE · SPW 2']);
  assert.equal(freqTexts(h).includes('Component 1 · coverage'),false);
  assert.ok(nodes(h.frequency,'title').some(t=>t.textContent.includes('Component 1')));
  archive().emit('keydown',{key:'Enter'});
  assert.equal(archive().attrs['aria-expanded'],'false');
  assert.equal(detailRows(h).length,0);
  archive().emit('keydown',{key:' '});
  assert.equal(detailRows(h).length,2);
});
test('selecting an expanded matching row preserves shared plot and Only selected state',()=>{
  const h=setup(),oldPosition=nodes(h.spatial,'svg')[0].attrs.viewBox;
  const archive=()=>toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1'));
  archive().click();
  const row=nodes(h.frequency,'g').find(t=>t.attrs['data-comparison-select']==='1');
  assert.ok(row);row.click();
  assert.equal(h.selected(),1);assert.equal(h.isolated(),false);assert.equal(h.clicks(),1);
  assert.equal(nodes(h.spatial,'svg')[0].attrs.viewBox,oldPosition);
  assert.equal(nodes(h.spatial,'polygon').length,2);
});
test('Queue CONTINUUM expands reference windows and one saved aggregate comparison',()=>{
  const h=setup({continuum:true,missingSpw:true});
  const queue=()=>toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('queue-setup-1'));
  assert.equal(detailRows(h).length,0);
  queue().click();
  assert.ok(freqTexts(h).some(t=>t==='SPW 1 · coverage'));
  assert.equal(detailRows(h).length,1);
  assert.equal(freqTexts(h).some(t=>t.includes('SPW ?')),false);
  assert.equal(freqTexts(h).some(t=>t.includes('aggregate comparison')),true);
  assert.equal(h.selected(),0);
});
test('each Archive spectral comparison retains its true SPW when present',()=>{
  const h=setup();toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1')).click();
  assert.ok(freqTexts(h).includes('#1 LINE · SPW 1'));
  assert.ok(freqTexts(h).includes('#2 LINE · SPW 2'));
});

test('missing LINE SPW ID is disclosed explicitly, never replaced with a made-up number',()=>{
  const h=setup({missingSpw:true});
  toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1')).click();
  assert.ok(freqTexts(h).includes('#1 LINE · SPW unrecorded'));
});

test('coincident footprints remain selectable independently by comparison ID',()=>{
  const h=setup();const polygon=nodes(h.spatial,'polygon').find(p=>p.parentElement?.attrs['data-shared-count']==='2');
  assert.ok(polygon);polygon.click();
  const chooser=nodes(h.spatial,'div').find(n=>n.className==='mosaic-overview-chooser');
  assert.equal(chooser.hidden,false);
  assert.equal(nodes(chooser,'button').length,3); // comparisons 1,2 + close
  nodes(chooser,'button')[1].click();
  assert.equal(h.selected(),1);assert.equal(h.isolated(),false);
  assert.equal(chooser.hidden,true);
});

test('Only selected filters the SAME shared axes, without switching renderer',()=>{
  const h=setup();
  const a=nodes(h.spatial,'svg')[0].attrs.viewBox,b=nodes(h.frequency,'svg')[0].attrs.viewBox;
  h.render(['1'],true);
  assert.equal(nodes(h.spatial,'svg')[0].attrs.viewBox,a);
  assert.equal(nodes(h.frequency,'svg')[0].attrs.viewBox,b);
  assert.equal(nodes(h.spatial,'polygon').length,1);
  assert.equal(toggles(h).length,1);
  h.render(['0','1','2'],false);
  assert.equal(nodes(h.spatial,'polygon').length,2);
  assert.equal(toggles(h).length,2);
});

test('candidate colors follow Single Pointing object identity without a chart legend card',()=>{
  const h=setup();
  assert.equal(nodes(h.spatial,'div').filter(d=>d.className==='mosaic-shared-chart-legend').length,0);
  const strokes=[...new Set(nodes(h.frequency,'line').map(n=>n.attrs.stroke)
    .filter(v=>v&&v!=='#dce5ec'))];
  assert.equal(strokes.length,2);
});

test('42 comparisons remain compact under setup grouping, with no replicated proposals',()=>{
  const h=setup({count:42,duplicates:false});
  assert.equal(nodes(h.spatial,'path').length,3);
  assert.equal(toggles(h).length,2);
  assert.equal(detailRows(h).length,0);
  assert.equal(nodes(h.frequency,'path').length,42);
  assert.equal(nodes(h.frequency,'svg')[0].attrs.viewBox,'0 0 600 330');
  toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1')).click();
  assert.equal(detailRows(h).length,2);
  toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('queue-setup-1')).click();
  assert.equal(detailRows(h).length,42); // Each saved aggregate appears once, not once per SPW
  assert.ok(freqTexts(h).some(t=>t==='SPW 1 · coverage'));
});
test('selection background is below matching bar after opening setup',()=>{
  const h=setup();toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1')).click();
  const svg=nodes(h.frequency,'svg')[0];
  const hi=svg.children.findIndex(n=>n.tag==='rect'&&n.attrs.fill==='#e9f4fa');
  const clip=svg.children.findIndex(n=>n.tag==='g'&&n.attrs['clip-path']);
  assert.ok(hi>=0&&clip>=0&&hi<clip);
});

test('focus and zoom preserve candidates and isolation',()=>{
  const h=setup();const original=freqTexts(h).join('|');
  const buttons=nodes(h.posTools,'button');
  assert.deepEqual(buttons.map(n=>n.textContent),['+','−','Reset','SVG']);
  buttons[0].click();buttons[2].click();
  assert.equal(h.isolated(),false);
  h.rows[2].click();h.root.mosaicOverviewFocus();
  assert.equal(h.isolated(),false);
  assert.equal(nodes(h.spatial,'polygon').length,2);
  assert.equal(toggles(h).length,2);
});

test('missing or filtered evidence never creates phantom footprints or extra setup rows',()=>{
  const h=setup();h.render(['2'],false);
  assert.equal(nodes(h.spatial,'polygon').length,1);
  assert.equal(toggles(h).length,1);
  h.render([],false);
  assert.equal(h.spatial.hidden,true);assert.equal(h.frequency.hidden,true);
});

// Static template-level contract: legend is at the SAME report-wide scope as
// Single Pointing, above filters, not inserted into the chart gallery.
test('Mosaic report-wide legend matches Single Pointing placement and has no extra color card',()=>{
  const template=fs.readFileSync(path.resolve('src/alma_duplicate/ui/templates/mosaic_visualization.html'),'utf8');
  const scope=template.indexOf('<div class="visual-scope">');
  const controls=template.indexOf('<section class="visual-controls"');
  const gallery=template.indexOf('<div class="evidence-gallery-heading">');
  assert.ok(scope>0&&controls>scope&&gallery>controls);
  const block=template.slice(scope,controls);
  assert.match(block,/class="visual-legend"/);
  assert.match(block,/class="legend-proposed"/);
  assert.match(block,/One color per candidate object/);
  assert.equal((template.match(/class="visual-scope"/g)||[]).length,1);
  assert.equal(template.includes('Candidate color key'),false);
});


test('Archive Setup toggle changes only frequency disclosure, never selection or Position',()=>{
  const h=setup(),get=()=>toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1'));
  const oldPosition=h.spatial.children[0].attrs.viewBox;
  const selected=h.selected();
  assert.equal(detailRows(h).length,0);
  get().click();
  assert.equal(h.selected(),selected);
  assert.equal(h.spatial.children[0].attrs.viewBox,oldPosition);
  assert.equal(detailRows(h).length,2);
  assert.equal(freqTexts(h).some(t=>t==='Component 1 · coverage'),false);
  get().click();
  assert.equal(h.selected(),selected);
  assert.equal(detailRows(h).length,0);
});
test('matching row click is available after expanding Archive Setup',()=>{
  const h=setup();
  toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1')).click();
  const row=nodes(h.frequency,'g').find(g=>g.attrs['data-comparison-select']==='1');
  assert.ok(row);assert.equal(row.attrs.tabindex,'0');
  row.emit('keydown',{key:'Enter'});
  assert.equal(h.selected(),1);
  assert.equal(h.isolated(),false);
  assert.equal(detailRows(h).length,2);
});
test('source-bound components are reference coverage; Archive displays only match rows',()=>{
  const h=setup({continuum:true,missingSpw:true});
  assert.equal(detailRows(h).length,0);
  toggles(h).forEach(t=>t.click());
  assert.equal(freqTexts(h).includes('Component 1 · coverage'),false);
  assert.ok(freqTexts(h).includes('SPW 1 · coverage'));
  assert.ok(freqTexts(h).includes('#1 CONT · SPW not recorded'));
  assert.equal(freqTexts(h).some(t=>t.includes('SPW ?')),false);
  assert.equal(detailRows(h).length,3);
});
test('frequency captions follow Single Pointing evidence language without an in-chart color key',()=>{
  const h=setup();
  const caption=h.frequency.children.find(n=>n.className==='chart-caption');
  // Minimal DOM mock does not include a caption, but static source contract
  // prevents the return of the old duplicate candidate-color legend.
  assert.equal(nodes(h.frequency,'div').some(n=>n.className==='mosaic-shared-chart-legend'),false);
  assert.match(source,/visible comparisons have frequency evidence/);
  assert.match(source,/Requested SKY frequency/);
  assert.match(source,/Queue nominal/);
});


test('all invalid setup intervals do not invent a Setup and still expose comparisons',()=>{
  const h=setup({invalidComponent:true});
  assert.equal(toggles(h).length,0);
  assert.equal(detailRows(h).length,3);
  assert.equal(freqTexts(h).some(t=>t.includes('Component 1 · coverage')),false);
  assert.ok(freqTexts(h).includes('#1 LINE · SPW 1'));
});
test('missing source SPW label is explicit; Archive components stay in setup tooltip',()=>{
  const h=setup({missingComponentLabel:true});
  toggles(h).forEach(t=>t.click());
  assert.ok(freqTexts(h).some(t=>t==='SPW ID unavailable · coverage'));
  assert.equal(freqTexts(h).some(t=>t==='Component ID unavailable · coverage'),false);
  assert.ok(nodes(h.frequency,'title').some(t=>t.textContent.includes('Component ID unavailable')));
  assert.equal(freqTexts(h).some(t=>/^SPW [1-9]$/.test(t)),false);
});
test('identical setup IDs across distinct candidates cannot merge',()=>{
  const h=setup({sameSetupId:true});
  assert.equal(toggles(h).length,2);
  assert.equal(detailRows(h).length,0);
  assert.ok(freqTexts(h).some(t=>t.includes('Archive · 2 rows')));
  assert.ok(freqTexts(h).some(t=>t.includes('Queue · 1 SPWs')));
});

// Direct behavioral parity cases derived from visualization.js:spectralChart().
test('Queue LINE expanded setup has BOTH SPW coverage and evaluated LINE match rows',()=>{
  const h=setup({queueLine:true});
  const queue=()=>toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('queue-setup-1'));
  assert.ok(freqTexts(h).some(t=>t.includes('Queue · 1 SPWs')));
  assert.equal(detailRows(h).length,0);
  queue().click();
  assert.ok(freqTexts(h).includes('SPW 1 · coverage'));
  assert.ok(freqTexts(h).includes('#3 LINE · SPW 3'));
  assert.equal(detailRows(h).length,1);
  const match=nodes(h.frequency,'g').find(g=>g.attrs['data-comparison-select']==='2');
  match.emit('keydown',{key:'Enter'});
  assert.equal(h.selected(),2);
  assert.equal(h.isolated(),false);
  queue().click();
  assert.equal(detailRows(h).length,0);
});

test('no verified setup: show standalone comparison, not a phantom Setup row',()=>{
  const h=setup({withoutSetup:true});
  assert.equal(toggles(h).length,0);
  assert.equal(detailRows(h).length,3);
  assert.ok(freqTexts(h).includes('#1 LINE · SPW 1'));
});

test('collapsed Archive label counts matching rows rather than frequency_support components',()=>{
  const h=setup();
  assert.ok(freqTexts(h).includes('▸ Archive · 2 rows'));
  assert.ok(freqTexts(h).includes('▸ Queue · 1 SPWs · 7 m'));
  assert.equal(freqTexts(h).some(t=>t.includes('Archive setup · 1 components')),false);
});

test('valid-looking intervals without source-bound setup ID must NOT be grouped',()=>{
  const h=setup({noSetupId:true});
  assert.equal(toggles(h).length,0);
  assert.equal(detailRows(h).length,3);
});

test('Archive continuum matching is a comparison, not an extra raw Component row',()=>{
  const h=setup({continuum:true,missingSpw:true});
  toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1')).click();
  assert.ok(freqTexts(h).includes('#1 CONT · SPW not recorded'));
  assert.ok(freqTexts(h).includes('#2 CONT · SPW not recorded'));
  assert.equal(freqTexts(h).includes('Component 1 · coverage'),false);
  assert.equal(detailRows(h).length,2);
});

test('Archive CONTINUUM retains source-bound SPW labels, never Queue aggregate labels',()=>{
  const h=setup({continuum:true}),archive=()=>toggles(h)
    .find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1'));
  archive().click();
  const labels=freqTexts(h);
  assert.ok(labels.some(s=>s.includes('#1 CONT · SPW 1')));
  assert.ok(labels.some(s=>s.includes('#2 CONT · SPW 2')));
  assert.ok(!labels.some(s=>s.includes('#1 CONT · aggregate comparison')));
});
test('Archive CONTINUUM without a stored SPW identifies it as missing, not an aggregate',()=>{
  const h=setup({continuum:true,missingSpw:true}),archive=()=>toggles(h)
    .find(g=>g.attrs['data-setup-toggle'].includes('archive-setup-1'));
  archive().click();
  const labels=freqTexts(h);
  assert.ok(labels.some(s=>s.includes('#1 CONT · SPW not recorded')));
  assert.ok(labels.some(s=>s.includes('#2 CONT · SPW not recorded')));
  assert.ok(!labels.some(s=>s.includes('#1 CONT · aggregate comparison')));
});

 test('bound continuum intervals paint behind dots and share identity colors',()=>{
  const h=setup({count:2,continuum:true,boundCoverage:true,withoutSetup:true});
  for(const layer of detailRows(h)){
    const bar=layer.children.find(n=>n.attrs['data-comparison-coverage']==='true');
    const dot=layer.children.find(n=>n.tag==='circle');
    assert.ok(bar && dot);
    assert.ok(layer.children.indexOf(bar)<layer.children.indexOf(dot));
    assert.ok(Number(bar.attrs.x1)<Number(dot.attrs.cx));
    assert.ok(Number(bar.attrs.x2)>Number(dot.attrs.cx));
    assert.equal(bar.attrs.stroke,dot.attrs.fill);
    assert.equal(h.rows[0].style['--comparison-color'],dot.attrs.fill);
  }
  h.rows[1].click(); h.render(['1'],true);
  assert.equal(detailRows(h).length,1);
  assert.equal(detailRows(h)[0].children.filter(n=>n.attrs['data-comparison-coverage']).length,1);
});

 test('overlap hover previews both plots without committing selection or expansion',()=>{
  const h=setup();
  nodes(h.spatial,'polygon').find(p=>p.parentElement.attrs['data-shared-count']==='2').click();
  const chooser=nodes(h.spatial,'div').find(n=>n.className==='mosaic-overview-chooser');
  const second=nodes(chooser,'button')[1];
  second.emit('pointerenter',{pointerType:'mouse'});
  assert.equal(h.selected(),0);
  assert.equal(h.clicks(),0);
  assert.equal(detailRows(h).length,2);
  assert.ok(freqTexts(h).some(t=>t.includes('#2 LINE')));
  second.emit('pointerleave');
  assert.equal(detailRows(h).length,0);
  second.emit('focus');
  assert.equal(h.selected(),0);
  second.click();
  assert.equal(h.selected(),1);
  assert.equal(chooser.hidden,true);
  assert.equal(detailRows(h).length,0);
  assert.equal(nodes(h.spatial,'polygon').some(p=>nodes(p,'title').length),false);
});

 test('keyboard chart controls preserve selection and Home restores the axis',()=>{
  const h=setup(),svg=nodes(h.frequency,'svg')[0];
  const original=freqTexts(h).join('|');
  const key=key=>svg.emit('keydown',{key,target:svg,stopPropagation(){}});
  key('+');assert.notEqual(freqTexts(h).join('|'),original);
  key('ArrowRight');assert.equal(h.selected(),0);assert.equal(h.isolated(),false);
  key('Home');assert.equal(freqTexts(h).join('|'),original);
  const ignored=svg.emit('keydown',{key:'ArrowRight',target:new Element('g'),stopPropagation(){}});
  assert.equal(ignored.prevented,undefined);
  assert.equal(freqTexts(h).join('|'),original);
});

 test('drag starts on a clickable footprint and suppresses selection after movement',()=>{
  const h=setup(),svg=nodes(h.spatial,'svg')[0];
  svg.getBoundingClientRect=()=>({width:460,height:460});
  const target={closest:()=>true}; // A candidate covers the entire zoomed plot.
  const points=()=>nodes(h.spatial,'polygon')[0].attrs.points;
  const before=points();
  svg.emit('pointerdown',{target,clientX:100,clientY:100});
  svg.emit('pointermove',{clientX:102,clientY:101});
  assert.equal(points(),before);
  svg.emit('pointermove',{clientX:160,clientY:130});
  assert.notEqual(points(),before);
  svg.emit('pointerup');
  const click=svg.emit('click',{stopImmediatePropagation(){this.stopped=true;}});
  assert.equal(click.stopped,true);assert.equal(h.selected(),0);
  svg.emit('pointerdown',{target});svg.emit('pointerup');
  assert.equal(svg.emit('click').prevented,undefined);
 });

test('Queue windows show distinct usable bars and hollow midpoints beside the saved comparison',()=>{
  const h=setup({continuum:true,missingSpw:true});
  toggles(h).find(g=>g.attrs['data-setup-toggle'].includes('queue-setup-1')).click();
  assert.equal(nodes(h.frequency).filter(n=>n.attrs['data-usable-coverage']).length,1);
  const dot=nodes(h.frequency).find(n=>n.attrs['data-window-midpoint']);
  assert.equal(dot.attrs.fill,'#fff');
  assert.ok(nodes(dot,'title')[0].textContent.includes('not a representative frequency'));
  assert.equal(detailRows(h).length,1);
});
