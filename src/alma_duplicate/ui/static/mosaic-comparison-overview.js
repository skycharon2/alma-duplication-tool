/* ALMA Mosaic: read-only cross-comparison overview over SAVED evidence.
 * Independent of the science evaluator; one shared chart per dimension,
 * matching Single Pointing's selection, grouping, and viewport semantics.
 * Clicking an overview item selects/highlights it; ONLY the explicit
 * 'Only selected' filters the shared axes; it never switches plot engines.
 */
(() => {
  'use strict';
  const root = document.querySelector('.mosaic-explorer');
  const payload = document.getElementById('mosaic-overview-data');
  const positionPanel = root?.querySelector('#mosaic-overview-position');
  const frequencyPanel = root?.querySelector('#mosaic-overview-frequency');
  if (!root || !payload || !positionPanel || !frequencyPanel) return;
  let records;
  try { records = JSON.parse(payload.textContent); } catch (_) { return; }
  if (!Array.isArray(records)) return;
  const positionSvg = positionPanel.querySelector('svg');
  const frequencySvg = frequencyPanel.querySelector('svg');
  if (!positionSvg || !frequencySvg) return;

  const NS = 'http://www.w3.org/2000/svg';
  const finite = n => typeof n === 'number' && Number.isFinite(n);
  // Same object-identity palette as visualization_view.js (Single Pointing).
  // One color per candidate object, stable across array branches and SPWs.
  const palette = ['#2474b5', '#c07816', '#27834b', '#7954b3', '#cb512b', '#557580', '#8c7130'];
  const objectKey = row => JSON.stringify([row.source, row.project||null, row.candidate||null]);
  const keys=[...new Set(records.map(objectKey))].sort();
  const colors=new Map(keys.map((key,i)=>[key,palette[i]||`hsl(${(i*137.508)%360},58%,43%)`]));
  const magenta = '#a62c83';
  const posView = {zoom:1, panX:0, panY:0};
  const freqView = {zoom:1, panX:0};
  let current = {visible:[], selected:-1, isolated:false};
  let lastFilter = null;
  const expandedSetups = new Set();
  function element(name, attrs={}, parent=null, value=undefined) {
    const node = document.createElementNS(NS,name);
    for (const [key,val] of Object.entries(attrs)) node.setAttribute(key,String(val));
    if (value !== undefined) node.textContent=String(value);
    parent?.append(node);
    return node;
  }
  function text(svg,x,y,value,attrs={}) {
    return element('text',{x,y,fill:'#526b7e','font-size':10,...attrs},svg,value);
  }
  function clear(svg,w,h,title) {
    svg.replaceChildren();
    svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
    svg.setAttribute('role','group');
    svg.setAttribute('aria-label',title);
  }
  function colorFor(row) { return colors.get(objectKey(row))||palette[0]; }
  for (const node of root.querySelectorAll('[data-row], [data-evidence]')) {
    const row = records[Number(node.dataset.row ?? node.dataset.evidence)];
    if (row) node.style.setProperty('--comparison-color', colorFor(row));
  }
  positionSvg.setAttribute('tabindex','0');
  function itemName(i) {
    const row=records[i];
    const target=row.target||row.candidate||'Unrecorded target';
    return `#${i+1} ${target} · ${row.source} · ${row.intent}${row.array?' · '+row.array:''}`;
  }
  const findButton = i => [...root.querySelectorAll('[data-row]')]
    .find(node=>node.dataset.row===String(i));
  function select(i) {
    const button=findButton(i);
    if (button) button.click(); // Use the existing controller; NEVER auto-click Only selected.
  }
  function activate(node,caption,action) {
    node.setAttribute('role','button');node.setAttribute('tabindex','0');
    node.setAttribute('aria-label',caption);
    node.classList?.add('mosaic-overview-hit');
    node.addEventListener('click',action);
    node.addEventListener('keydown',event=>{
      if(event.key==='Enter'||event.key===' '){event.preventDefault();action();}
    });
  }
  function polygonPoints(source) {
    if(typeof source!=='string')return null;
    const pts=source.trim().split(/\s+/).map(part=>part.split(',').map(Number));
    return pts.length>=3&&pts.every(p=>p.length===2&&p.every(finite))?pts:null;
  }
  // Exact inverse of mosaic_visualization.position_chart's equal-angular-scale
  // projection. The world X axis is WEST-positive (sky_offset's convention),
  // therefore east-positive tick LABELS are -worldX. Never alter saved positions.
  function unproject(chart,p) {
    const semi=chart?.scale,first=chart?.ticks?.[0];
    if(!finite(semi)||semi<=0||!finite(first?.east)||!finite(first?.north)
       ||!Array.isArray(p)||p.length!==2||!p.every(finite))return null;
    const x0=semi-first.east,y0=first.north-semi;
    return [x0+(p[0]-245)*semi/150,y0+(210-p[1])*semi/150];
  }
  const positions=records.map(row=>{
    const c=row.position;
    if(!c||!Array.isArray(c.outlines))return null;
    const outlines=c.outlines.map(value=>{
      const parsed=polygonPoints(value);
      return parsed?.map(p=>unproject(c,p))||null;
    }).filter(p=>p&&p.length>=3&&p.every(q=>q?.every(finite)));
    const points=(c.points||[]).map(p=>unproject(c,p.xy)).filter(p=>p?.every(finite));
    // These are already saved DISPLAY-ONLY proposed FWHM outlines, generated
    // from the proposal array and each saved matching requested frequency.
    // Never generate missing beam evidence on the client.
    const beams=(c.proposal_beams||[]).flatMap(beam=>(beam.outlines||[]).map(value=>{
      const parsed=polygonPoints(value);
      return parsed?.map(p=>unproject(c,p))||null;
    })).filter(p=>p&&p.length>=3&&p.every(q=>q?.every(finite)));
    return outlines.length?{outlines,points,beams}:null;
  });
  const proposal=positions.find(p=>p?.points.length)?.points||[];
  // Identical saved footprints can represent different recorded SPWs. Render
  // the shape once, but retain ALL comparison IDs in the chooser and list.
  function footprintGroups(ids) {
    const groups=new Map();
    for(const i of ids){
      const pos=positions[i];if(!pos)continue;
      const sig=pos.outlines.map(outline=>outline.map(p=>p.map(n=>n.toFixed(3)).join(','))
        .join(' ')).sort().join('|');
      // A coincident footprint is one shape, not one comparison verdict.
      const group=groups.get(sig);
      if(group)group.ids.push(i);
      else groups.set(sig,{ids:[i],outlines:pos.outlines});
    }
    return [...groups.values()];
  }
  const chooser=document.createElement('div');
  chooser.className='mosaic-overview-chooser';
  chooser.hidden=true;
  chooser.setAttribute('role','dialog');
  chooser.setAttribute('aria-label','Overlapping comparisons');
  (document.body || positionPanel).append(chooser);
  let previewed=null, chooserReturn=null, previewScroll=null;
  const status=root.querySelector('#mosaic-preview-status');
  function preview(i){
    if(previewed===i)return;
    const scroller=frequencyPanel.querySelector('.mosaic-frequency-all');
    if(previewScroll===null)previewScroll=scroller?.scrollTop||0;
    previewed=i;
    draw();
    const row=frequencySvg.querySelector(`[data-comparison-select="${i}"]`);
    // Scroll only the frequency viewport; moving the document under the
    // pointer can accidentally preview a different chooser entry.
    const box=row?.getBoundingClientRect?.(),viewport=scroller?.getBoundingClientRect?.();
    if(box&&viewport){
      if(box.top<viewport.top)scroller.scrollTop-=viewport.top-box.top;
      else if(box.bottom>viewport.bottom)scroller.scrollTop+=box.bottom-viewport.bottom;
    }
    if(status)status.textContent=`Preview ${itemName(i)}. Click to select; current selection is unchanged.`;
  }
  function clearPreview(){
    if(previewed===null)return;
    previewed=null;draw();
    const scroller=frequencyPanel.querySelector('.mosaic-frequency-all');
    if(scroller&&previewScroll!==null)scroller.scrollTop=previewScroll;
    previewScroll=null;
    if(status)status.textContent='';
  }
  function hideChooser(restore=false){
    chooser.hidden=true;clearPreview();chooser.replaceChildren();
    if(restore)chooserReturn?.focus?.({preventScroll:true});
  }
  function chooseGroup(ids,event={},trigger=null){
    if(ids.length===1){hideChooser();select(ids[0]);return;}
    hideChooser();chooserReturn=positionSvg;
    chooser.hidden=false;
    const heading=document.createElement('strong');
    heading.textContent=`${ids.length} comparisons share this footprint`;
    chooser.append(heading);
    const hint=document.createElement('p');
    hint.textContent='Hover or focus to preview both plots. Click to select.';
    chooser.append(hint);
    const list=document.createElement('div');list.className='mosaic-overlap-list';chooser.append(list);
    for(const i of ids){
      const rec=records[i],button=document.createElement('button');button.type='button';
      button.setAttribute('aria-pressed',String(i===current.selected));
      const title=document.createElement('strong');title.textContent=`#${i+1} ${rec.target||rec.candidate}${rec.project?' · '+rec.project:''}`;
      title.style.borderLeft=`5px solid ${colorFor(rec)}`;title.style.paddingLeft='8px';
      const description=document.createElement('small');
      const spws=[...new Set((frequencies[i]?.matching||[]).map(m=>m.spw).filter(v=>v!==null&&v!==undefined))];
      description.textContent=[rec.source,rec.intent,spws.length?'SPW '+spws.join(', '):null,rec.array||null].filter(Boolean).join(' · ');
      const identity=document.createElement('small');
      identity.textContent=[rec.candidate,rec.identity?.ASDM].filter(Boolean).join(' · ');
      button.append(title,description,identity);
      button.addEventListener('pointerenter',e=>{if(e.pointerType!=='touch')preview(i);});
      button.addEventListener('pointerleave',()=>{if(document.activeElement!==button)clearPreview();});
      button.addEventListener('focus',()=>preview(i));
      button.addEventListener('blur',clearPreview);
      button.addEventListener('click',()=>{hideChooser();select(i);positionSvg.focus?.({preventScroll:true});});
      list.append(button);
    }
    const close=document.createElement('button');close.type='button';close.className='mosaic-overlap-close';
    close.textContent='Close';close.setAttribute('aria-label','Close overlapping comparisons');
    close.addEventListener('click',()=>hideChooser(true));chooser.append(close);
    const bounds=chooser.getBoundingClientRect?.()||{width:390,height:440};
    const anchor=trigger?.getBoundingClientRect?.()||{left:16,top:80};
    const viewport=document.documentElement;
    chooser.style.left=`${Math.max(8,Math.min((event.clientX||anchor.left)+12,(viewport?.clientWidth||800)-bounds.width-8))}px`;
    chooser.style.top=`${Math.max(8,Math.min((event.clientY||anchor.top)+12,(viewport?.clientHeight||600)-bounds.height-8))}px`;
    close.focus?.({preventScroll:true});
  }
  document.addEventListener?.('keydown',event=>{
    if(event.key==='Escape'&&!chooser.hidden){event.preventDefault();hideChooser(true);}
  });
  document.addEventListener?.('pointerdown',event=>{
    if(!chooser.hidden&&!chooser.contains(event.target))hideChooser();
  });
  if(typeof window!=='undefined')window.addEventListener('resize',()=>hideChooser());

  function plotFrame(svg, width, height, clipName, x,y,w,h) {
    const defs=element('defs',{},svg),clip=element('clipPath',{id:clipName},defs);
    element('rect',{x,y,width:w,height:h},clip);
    return element('g',{'clip-path':`url(#${clipName})`},svg);
  }
  function positionPlot(ids,selected) {
    const groups=footprintGroups(ids);
    clear(positionSvg,460,460,'Saved Mosaic spatial comparisons; east left, north up');
    const coords=[...proposal];
    for(const group of groups)for(const outline of group.outlines)coords.push(...outline);
    for(const i of ids)for(const beam of positions[i]?.beams||[])coords.push(...beam);
    const caption=positionPanel.querySelector('.chart-caption');
    if(caption)caption.textContent=`${groups.length} distinct saved footprints · ${ids.length} visible comparisons · ${proposal.length} submitted pointings (◆)`;
    if(!coords.length){text(positionSvg,240,220,'No verified position evidence for the current view.',{'text-anchor':'middle'});return;}
    let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for(const [x,y] of coords){minX=Math.min(minX,x);maxX=Math.max(maxX,x);
      minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
    const baseSpan=Math.max(maxX-minX,maxY-minY,1)*1.16;
    const span=baseSpan/posView.zoom;
    const cx=(minX+maxX)/2+posView.panX*baseSpan;
    const cy=(minY+maxY)/2+posView.panY*baseSpan;
    const pt=p=>[240+(p[0]-cx)*370/span,220-(p[1]-cy)*370/span];
    for(let t=0;t<=4;t++){
      const x=55+92.5*t,y=35+92.5*t;
      element('line',{x1:x,y1:35,x2:x,y2:405,stroke:'#dce5ec','stroke-width':1},positionSvg);
      element('line',{x1:55,y1:y,x2:425,y2:y,stroke:'#dce5ec','stroke-width':1},positionSvg);
      const west=cx+(t-2)*span/4,north=cy-(t-2)*span/4;
      text(positionSvg,x,425,Number((-west).toPrecision(4)),{'text-anchor':'middle'});
      text(positionSvg,46,y+3,Number(north.toPrecision(4)),{'text-anchor':'end'});
    }
    text(positionSvg,240,450,'East offset (arcsec) ←',{'text-anchor':'middle'});
    text(positionSvg,13,220,'North offset (arcsec)',{transform:'rotate(-90 13 220)','text-anchor':'middle'});
    const clipped=plotFrame(positionSvg,460,460,'mosaic-overview-position-clip',55,35,370,370);
    const sorted=[...groups].sort((a,b)=>Number(a.ids.includes(selected))-Number(b.ids.includes(selected)));
    for(const group of sorted){
      const active=group.ids.includes(selected),rec=records[active?selected:group.ids[0]];
      const mixed=group.ids.some(i=>records[i].source!==rec.source);
      const stroke=mixed&&!active?'#557580':colorFor(rec);
      const layer=element('g',{'data-overview-row':group.ids.join(','),'data-shared-count':group.ids.length},clipped);
      for(const outline of group.outlines){
        const value=outline.map(p=>pt(p).map(v=>v.toFixed(3)).join(',')).join(' ');
        const polygon=element('polygon',{points:value,fill:stroke,'fill-opacity':active?.09:.035,
          stroke,'stroke-opacity':active?1:.60,'stroke-width':active?3:1.6,
          'stroke-dasharray':mixed?'4 3':rec.source==='Queue'?'6 4':'none'},layer);
        // The structured chooser replaces the unreadable native multi-row tooltip.
        activate(polygon,`Select from ${group.ids.length} saved comparison(s) sharing this footprint`,event=>chooseGroup(group.ids,event,polygon));
      }
    }
    // Never derive or invent request beams in the browser. These outlines are
    // serialized from the saved, selected frequency comparison only.
    for(const beam of positions[selected]?.beams||[]){
      const value=beam.map(p=>pt(p).map(v=>v.toFixed(3)).join(',')).join(' ');
      element('polyline',{points:value,fill:'none',stroke:magenta,'stroke-width':1.8,
        'stroke-dasharray':'6 4','pointer-events':'none','data-proposed-beam':'true'},clipped);
    }
    for(const point of proposal){
      const [x,y]=pt(point);
      element('path',{d:`M${x.toFixed(2)} ${(y-5).toFixed(2)}l5 5 -5 5 -5 -5Z`,
        fill:magenta,stroke:'#fff','stroke-width':1.1,'pointer-events':'none'},clipped);
    }
  }

    function numberAtTick(chart,pixel){
    const t=chart?.ticks;
    if(!Array.isArray(t)||t.length<2)return null;
    const a=t[0],b=t[t.length-1];
    if(![a.x,b.x,a.value,b.value,pixel].every(finite)||a.x===b.x)return null;
    return a.value+(pixel-a.x)*(b.value-a.value)/(b.x-a.x);
  }
  const frequencies=records.map(row=>{
    const f=row.frequency;if(!f)return null;
    // Preserve every recorded component, including a component whose interval
    // is unavailable. Missing evidence must remain visible in the disclosure.
    const setup=(f.setup||[]).map((c,index)=>{
      const valid=finite(c.raw_low)&&finite(c.raw_high)&&c.raw_low<c.raw_high;
      return {low:valid?c.raw_low:null,high:valid?c.raw_high:null,
        usableLow:c.usable_low,usableHigh:c.usable_high,
        label:c.label||(row.source==='Queue'?'SPW ID unavailable':'Component ID unavailable'),
        status:c.status||'UNRECORDED'};
    });
    const matching=(f.matching||[]).map(c=>({
      start:numberAtTick(f,c.low),end:numberAtTick(f,c.high),
      request:numberAtTick(f,c.proposed),kind:c.kind,spw:c.spw,
      coverage:(c.coverage||[]).map(interval=>({...interval,
        low:numberAtTick(f,interval.low),high:numberAtTick(f,interval.high)}))
        .filter(interval=>finite(interval.low)&&finite(interval.high)&&interval.low>0&&interval.high>interval.low)
    })).filter(c=>[c.start,c.end,c.request].every(finite));
    return {setup,matching,setupId:f.setup_id||null,setupLabel:f.setup_label||'Recorded setup'};
  });
  // Same row rules as Single Pointing's visualization.js:spectralChart():
  //   - Archive: collapsed setup -> matching comparison rows when expanded.
  //     Archive frequency_support components remain summarized in the setup
  //     interval bars/tooltips, NOT additional rows pretending to be SPWs.
  //   - Queue CONTINUUM: expanded setup shows window references plus each saved
  //     aggregate comparison once; windows are never independent matches.
  //   - Queue LINE: expanded setup -> SPW coverage rows + evaluated LINE pairs.
  //   - No usable setup interval: stand-alone comparison (do not invent setup).
  const hasInterval = c => finite(c?.low) && finite(c?.high) && c.low < c.high;
  const isLine = row => String(row?.intent||'').toUpperCase()==='LINE';
  function frequencyEntries(ids) {
    const groups=new Map(),ordered=[];
    for(const i of ids){
      const data=frequencies[i],row=records[i];
      if(!data?.setupId || !data.setup.some(hasInterval)){
        ordered.push({kind:'comparison',i});continue;
      }
      // A missing source-bound setup ID MUST NOT be reconstructed from
      // frequency overlap or coincident components. Keep candidate, array, and setup provenance scoped.
      const key=JSON.stringify([row.source,row.project,row.candidate,row.array,row.intent,
        data.setupId,data.setup]);
      if(!groups.has(key)){
        const group={kind:'setup',key,i,members:[i]};
        groups.set(key,group);ordered.push(group);
      } else groups.get(key).members.push(i);
    }
    const entries=[];
    for(const entry of ordered){
      entries.push(entry);
      if(entry.kind!=='setup'||!expandedSetups.has(entry.key)&&!entry.members.includes(previewed))continue;
      const row=records[entry.i],data=frequencies[entry.i];
      if(row.source==='Queue'){
        // Coverage references are not matching comparisons.
        data.setup.forEach((component,index)=>
          entries.push({kind:'component',i:entry.i,index,component}));
        entry.members.forEach(i=>entries.push({kind:'comparison',i}));
      } else {
        // Archive: exactly the matching rows, NOT raw Component 1..N rows.
        entry.members.forEach(i=>entries.push({kind:'comparison',i}));
      }
    }
    return entries;
  }
  function frequencyPlot(ids,selected) {
    const entries=frequencyEntries(ids);
    const values=ids.flatMap(i=>{
      const data=frequencies[i];
      return data?[...data.setup.flatMap(c=>[c.low,c.high]),
        ...data.matching.flatMap(c=>[c.start,c.end,c.request,...c.coverage.flatMap(v=>[v.low,v.high])])].filter(finite):[];
    });
    // A scrolling plot keeps desktop panel height stable with 42+ comparisons.
    const height=Math.max(330,90+entries.length*40);
    clear(frequencySvg,600,height,'Recorded spectral setup and selectable comparisons on a shared GHz axis');
    const caption=frequencyPanel.querySelector('.chart-caption');
    if(caption){
      const withEvidence=ids.filter(i=>frequencies[i]?.matching.length).length;
      caption.textContent=`${withEvidence} / ${ids.length} visible comparisons have frequency evidence · `+
        '◆ Requested SKY frequency · ▸ Expand recorded setup to inspect saved ' +
        'SPWs or matching rows. Shaded bars show bound coverage; dots show representative frequencies. '+
        'Queue nominal intervals are reference evidence, not additional matches. Gaps are preserved.';
    }
    if(!values.length){
      text(frequencySvg,350,105,'No numerical frequency evidence in this selection.',{'text-anchor':'middle'});
      return;
    }
    const low=Math.min(...values),high=Math.max(...values);
    const pad=Math.max((high-low)*.08,Math.abs(high)*1e-6,1e-8),base=high-low+2*pad;
    const span=base/freqView.zoom,center=(high+low)/2+freqView.panX*base;
    const fx=n=>135+(n-center+span/2)/span*430;
    const bottom=height-40;
    for(let t=0;t<=4;t++){
      const value=center+(t-2)*span/4,x=135+t*107.5;
      element('line',{x1:x,y1:30,x2:x,y2:bottom,stroke:'#dce5ec','stroke-width':1},frequencySvg);
      text(frequencySvg,x,20,Number(value.toPrecision(7)),{'text-anchor':'middle'});
      text(frequencySvg,x,bottom+16,Number(value.toPrecision(7)),{'text-anchor':'middle'});
    }
    text(frequencySvg,350,height-3,'Frequency (GHz)',{'text-anchor':'middle'});
    // Paint order is critical: group BACKGROUNDS must precede the clipped
    // frequency intervals. In V7 each opaque Setup background was appended
    // after the clipped layer, covering the saved intervals and request
    // diamonds even though they existed in the DOM. Keep interactive labels
    // above the plot, but their hit areas must remain transparent.
    const backgrounds=element('g',{'data-frequency-row-backgrounds':'true'},frequencySvg);
    // Highlights go below interval bars, but above the grid background.
    for(let index=0;index<entries.length;index++){
      const entry=entries[index];
      if(entry.kind==='comparison'&&entry.i===selected){
        const y=48+index*40;
        element('rect',{x:5,y:y-16,width:585,height:32,fill:'#e9f4fa'},frequencySvg);
      }
    }
    const clipped=plotFrame(frequencySvg,600,height,'mosaic-overview-frequency-clip',135,30,430,bottom-30);
    for(let index=0;index<entries.length;index++){
      const entry=entries[index],i=entry.i,rec=records[i],data=frequencies[i];
      const active=entry.kind==='comparison'&&i===selected,y=48+index*40;
      const ink=colorFor(rec);
      if(entry.kind==='setup'){
        const expanded=expandedSetups.has(entry.key)||entry.members.includes(previewed);
        const groupActive=entry.members.includes(selected);
        const action=()=>{
          if(expandedSetups.has(entry.key))expandedSetups.delete(entry.key);
          else expandedSetups.add(entry.key);
          frequencyPlot(ids,selected); // do not alter selection/isolation/viewport
          // Redrawing replaces the focused SVG group; restore keyboard focus.
          [...frequencySvg.querySelectorAll('[data-setup-toggle]')]
            .find(node=>node.getAttribute('data-setup-toggle')===entry.key)?.focus?.({preventScroll:true});
        };
        const button=element('g',{'data-setup-toggle':entry.key,
          'aria-expanded':String(expanded)},frequencySvg);
        // Visible background lives UNDER the interval layer. A transparent
        // full-width hit target ABOVE it provides the same row click behavior
        // without hiding the recorded SPW bars or requested markers.
        element('rect',{x:5,y:y-17,width:585,height:34,rx:3,
          fill:groupActive?'#e9f4fa':'#f0f6fb'},backgrounds);
        const hitArea=element('g',{},button);
        element('rect',{x:5,y:y-17,width:585,height:34,rx:3,
          fill:'transparent','data-setup-hit-area':'true'},hitArea);
        // This grouping/title is intentionally identical in meaning to
        // Single Pointing: Archive setup counts matched rows; Queue setup
        // counts SPW coverage components, not aggregate continuum matches.
        const sourceKind=rec.source==='Queue'?'SPWs':'matching rows';
        const groupLabel=rec.source==='Queue' ?
          `Queue · ${data.setup.length} SPWs · ${rec.array||'Array unrecorded'}` :
          `Archive · ${entry.members.length} row${entry.members.length===1?'':'s'}`;
        text(button,12,y+3,`${expanded?'▾':'▸'} ${groupLabel}`,
          {fill:'#27475d','font-weight':600});
        activate(button,`${expanded?'Collapse':'Expand'} recorded ${rec.source} ${sourceKind} for ${rec.target||'candidate'}`,action);
        const group=element('g',{},clipped);
        data.setup.forEach(({low,high},j)=>{
          if(![low,high].every(finite))return;
          const interval=element('line',{x1:fx(low),x2:fx(high),y1:y-6+(j%2)*7,y2:y-6+(j%2)*7,
            stroke:ink,'stroke-width':6,opacity:.48,'pointer-events':'none'},group);
          const component=data.setup[j];
          element('title',{},interval,`${component.label} · ${low.toPrecision(9)}–${high.toPrecision(9)} GHz · ${component.status}`);
        });
        const requests=[...new Set(entry.members.flatMap(id=>
          (frequencies[id]?.matching||[]).map(m=>m.request)).filter(finite))];
        requests.forEach(value=>{
          const x=fx(value);
          element('path',{d:`M${x} ${y-7}l5 7 -5 7 -5 -7Z`,fill:magenta,
            stroke:'#fff','stroke-width':1,'pointer-events':'none'},group);
        });
        continue;
      }
      if(entry.kind==='component'){
        const comp=entry.component,{low,high}=comp;
        const label=comp.label||`Component ${entry.index+1}`;
        // Queue 'SPW N' identifiers are source-bound; Archive 'Component N'
        // identifiers must NEVER be presented as validated SPW numbers.
        text(frequencySvg,12,y+3,`${label} · coverage`);
        if(![low,high].every(finite)){
          text(frequencySvg,145,y+3,`Interval unavailable · ${comp.status}`);
          continue;
        }
        const kind=rec.source==='Queue'?'Queue nominal SKY interval':'Archive recorded component';
        const interval=element('line',{x1:fx(low),x2:fx(high),y1:y,y2:y,stroke:ink,
          'stroke-width':10,opacity:.25},clipped);
        element('title',{},interval,`${label} · ${low.toPrecision(9)}–${high.toPrecision(9)} GHz · ${kind}`);
        if(rec.source==='Queue'){
          if(finite(comp.usableLow)&&finite(comp.usableHigh)&&comp.usableLow>0&&comp.usableHigh>comp.usableLow){
            const usable=element('line',{x1:fx(comp.usableLow),x2:fx(comp.usableHigh),y1:y,y2:y,
              stroke:ink,'stroke-width':6,opacity:.7,'data-usable-coverage':'true'},clipped);
            element('title',{},usable,`Saved usable interval ${comp.usableLow}–${comp.usableHigh} GHz`);
          }
          const centre=element('circle',{cx:fx((low+high)/2),cy:y,r:4,fill:'#fff',stroke:ink,
            'stroke-width':1.5,'data-window-midpoint':'true'},clipped);
          element('title',{},centre,`Nominal window midpoint ${(low+high)/2} GHz; not a representative frequency`);
          [...new Set((data.matching||[]).map(m=>m.request).filter(finite))].forEach(value=>{
            const x=fx(value);
            element('path',{d:`M${x} ${y-6}l5 6 -5 6 -5 -6Z`,fill:magenta,stroke:'#fff'},clipped);
          });
        }

        continue;
      }
      const match=data?.matching||[];
      const isContinuum=/^CONT/i.test(rec.intent||'');
      const spws=[...new Set(match.map(m=>m.spw).filter(v=>v!==null&&v!==undefined&&v!==''))];
      // Archive CONTINUUM is a context-level comparison with a recorded
      // SPW identity when supplied by its Archive display_identity. It is NOT
      // a Queue CONTINUUM aggregate over nominal CSV SPWs. Never manufacture
      // an SPW when the source-bound context did not record one.
      const meaning=spws.length?`SPW ${spws.join(', ')}`:
        rec.source==='Queue'&&isContinuum?'aggregate comparison':
        isContinuum?'SPW not recorded':'SPW unrecorded';
      const rowLabel=`#${i+1} ${isContinuum?'CONT':'LINE'} · ${meaning}`;
      // Whole row selection, as in Single Pointing. Never toggle Setup or
      // activate Only selected when a matching row is clicked.
      const button=element('g',{'data-comparison-select':i},frequencySvg);
      element('rect',{x:5,y:y-17,width:585,height:34,fill:'transparent'},button);
      text(button,12,y+3,rowLabel,{fill:active?'#27475d':'#526b7e',
        'font-weight':active?700:400});
      activate(button,`Select ${itemName(i)} · ${meaning}`,()=>select(i));
      if(!match.length){text(frequencySvg,145,y+3,'Comparison frequency unavailable');continue;}
      const layer=element('g',{'data-overview-row':i},clipped);
      for(const m of match){
        for(const interval of m.coverage){
          const bar=element('line',{x1:fx(interval.low),x2:fx(interval.high),y1:y,y2:y,
            stroke:ink,'stroke-width':10,'stroke-opacity':.25,'data-comparison-coverage':'true'},layer);
          element('title',{},bar,`SPW ${m.spw??'not recorded'} · Coverage ${interval.low.toPrecision(9)}–${interval.high.toPrecision(9)} GHz`);
        }
        if(m.kind==='interval'&&m.end>m.start){
          const bar=element('line',{x1:fx(m.start),x2:fx(m.end),y1:y,y2:y,
            stroke:ink,'stroke-width':active?9:7,'stroke-opacity':active?1:.65},layer);
          activate(bar,`Select ${itemName(i)} matching frequency interval`,()=>select(i));
        }else{
          const dot=element('circle',{cx:fx(m.start),cy:y,r:5,fill:ink},layer);
          activate(dot,`Select ${itemName(i)} recorded representative frequency`,()=>select(i));
        }
        const x=fx(m.request);
        const marker=element('path',{d:`M${x} ${y-7}l6 7 -6 7 -6 -7Z`,fill:magenta,
          stroke:'#fff','stroke-width':1},layer);
        activate(marker,`Select ${itemName(i)} requested frequency`,()=>select(i));
      }
    }
  }

    function toolbar(target,kind){
    const host=root.querySelector(kind==='position'?'#mosaic-position-tools':'#mosaic-frequency-tools');
    if(!host)return null;
    const bar=document.createElement('div');bar.className='chart-tools mosaic-plot-tools mosaic-overview-tools';
    bar.setAttribute('data-overview-controls','');bar.setAttribute('aria-label',kind+' overview controls');
    function add(caption,handler){
      const button=document.createElement('button');button.type='button';button.textContent=caption;
      button.setAttribute('aria-label',caption==='+'?'Zoom in':caption==='−'?'Zoom out':
        caption==='Reset'?'Reset overview zoom':`Export ${kind} overview SVG`);
      button.addEventListener('click',handler);bar.append(button);
    }
    const state=kind==='position'?posView:freqView;
    add('+',()=>{state.zoom=Math.min(16,state.zoom*1.6);draw();});
    add('−',()=>{state.zoom=Math.max(1,state.zoom/1.6);draw();});
    add('Reset',()=>{state.zoom=1;state.panX=0;if(kind==='position')state.panY=0;draw();});
    add('SVG',()=>{
      const svg=kind==='position'?positionSvg:frequencySvg;
      if(typeof XMLSerializer==='undefined'||typeof Blob==='undefined'||typeof URL==='undefined')return;
      const clone=svg.cloneNode(true);clone.setAttribute('xmlns',NS);
      element('desc',{},clone,JSON.stringify({report:document.title,
        url:typeof location==='undefined'?null:location.href,chart:kind,
        selected:current.selected+1,visible:current.visible.map(i=>({number:i+1,
          source:records[i].source,project:records[i].project,candidate:records[i].candidate,
          target:records[i].target,array:records[i].array,intent:records[i].intent,
          identity:records[i].identity})),viewport:state}));
      const blob=new Blob([new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml'});
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download=`mosaic-${kind}-overview.svg`;link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    host.append(bar);return bar;
  }
  const pTools=toolbar(positionSvg,'position'),fTools=toolbar(frequencySvg,'frequency');
  function draw(){const highlighted=previewed??current.selected;
    positionPlot(current.visible,highlighted);frequencyPlot(current.visible,highlighted);}
  function enablePan(svg,kind){
    svg.setAttribute('tabindex','0');
    svg.addEventListener('keydown',event=>{
      if(event.target!==svg||event.ctrlKey||event.metaKey||event.altKey)return;
      const state=kind==='position'?posView:freqView;
      const step=.1/state.zoom;
      if(event.key==='+'||event.key==='=')state.zoom=Math.min(16,state.zoom*1.6);
      else if(event.key==='-')state.zoom=Math.max(1,state.zoom/1.6);
      else if(event.key==='Home'){state.zoom=1;state.panX=0;if(kind==='position')state.panY=0;}
      else if(event.key==='ArrowLeft')state.panX-=step;
      else if(event.key==='ArrowRight')state.panX+=step;
      else if(kind==='position'&&event.key==='ArrowUp')state.panY+=step;
      else if(kind==='position'&&event.key==='ArrowDown')state.panY-=step;
      else return;
      event.preventDefault();event.stopPropagation();draw();
    });
    let drag=null, suppressClick=false;
    svg.style.touchAction='none';
    svg.addEventListener('click',event=>{
      if(suppressClick){event.preventDefault();event.stopImmediatePropagation();suppressClick=false;}
    },true);
    svg.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;
      // Footprints fill the plot when zoomed: they must allow dragging too.
      // Delay capture until movement, so a stationary click still selects.
      suppressClick=false;
      drag={x:event.clientX,y:event.clientY,moved:false};
    });
    svg.addEventListener('pointermove',event=>{
      if(!drag)return;
      if(!drag.moved&&Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<4)return;
      svg.setPointerCapture?.(event.pointerId);
      suppressClick=true;
      event.preventDefault();
      const rect=svg.getBoundingClientRect?.();
      if(!rect?.width)return;
      const dx=(event.clientX-drag.x)/rect.width*(kind==='position'?460:600);
      const dy=(event.clientY-drag.y)/rect.height*(kind==='position'?460:0);
      drag={x:event.clientX,y:event.clientY,moved:true};
      const state=kind==='position'?posView:freqView;
      state.panX-=dx/((kind==='position'?370:430)*state.zoom);
      if(kind==='position')state.panY+=dy/(370*state.zoom);
      draw();
    });
    const done=event=>{drag=null;if(svg.hasPointerCapture?.(event.pointerId))svg.releasePointerCapture?.(event.pointerId);};
    svg.addEventListener('pointerup',done);svg.addEventListener('pointercancel',done);
    svg.addEventListener('wheel',event=>{
      if(!(event.ctrlKey||event.metaKey))return;
      event.preventDefault();const state=kind==='position'?posView:freqView;
      state.zoom=Math.min(16,Math.max(1,state.zoom*(event.deltaY<0?1.15:1/1.15)));draw();
    },{passive:false});
  }
  enablePan(positionSvg,'position');enablePan(frequencySvg,'frequency');
  root.mosaicOverviewRender=({visible,selected,isolated})=>{
    const ids=[...new Set(visible.map(Number))].filter(i=>Number.isInteger(i)&&i>=0&&i<records.length);
    const signature=ids.join(',');
    if(lastFilter!==signature){posView.zoom=freqView.zoom=1;
      posView.panX=posView.panY=freqView.panX=0;lastFilter=signature;hideChooser();}
    current={visible:ids,selected:Number(selected),isolated:Boolean(isolated)};
    const enabled=ids.length>0;
    positionPanel.hidden=!enabled;frequencyPanel.hidden=!enabled;
    if(pTools)pTools.hidden=!enabled;if(fTools)fTools.hidden=!enabled;
    for(const controls of root.querySelectorAll('[data-plot-controls]'))controls.hidden=true;
    for(const pane of root.querySelectorAll('#charts [data-evidence]')){
      const section=pane.closest?.('section.visual-panel');
      if(section?.querySelector('#mosaic-position-title')) {
        // Keep the selected saved coverage verdict caption, not its old SVG.
        const caption=pane.classList?.contains('chart-caption');
        pane.hidden=!caption||!enabled||pane.dataset.evidence!==String(selected);
      }
      if(section?.querySelector('#mosaic-frequency-title')){
        pane.setAttribute('data-overview-detail','');
        // Keep original saved SPW parameter disclosures for the selected row,
        // but never show a second independent SVG plot with different axes.
        pane.hidden=!enabled||pane.dataset.evidence!==String(selected);
      }
    }
    if(!enabled){hideChooser();return;}
    draw();
  };
  root.mosaicOverviewFocus=()=>{
    // Single Pointing semantics: retain selection/isolation and refit the
    // shared viewports to selected evidence, never swap chart engines.
    const i=current.selected,geo=positions[i];
    if(geo){
      const subset=[...proposal,...geo.outlines.flat(),...(geo.beams||[]).flat()];
      const all=[...proposal,...current.visible.flatMap(j=>[
        ...(positions[j]?.outlines.flat()||[]),...(positions[j]?.beams||[]).flat()])];
      if(subset.length&&all.length){
        const bounds=pts=>{
          const x=pts.map(p=>p[0]),y=pts.map(p=>p[1]);
          return {cx:(Math.min(...x)+Math.max(...x))/2,
                  cy:(Math.min(...y)+Math.max(...y))/2,
                  span:Math.max(Math.max(...x)-Math.min(...x),Math.max(...y)-Math.min(...y),1)*1.16};
        };
        const selectedBox=bounds(subset),allBox=bounds(all);
        posView.zoom=Math.max(1,Math.min(16,allBox.span/selectedBox.span));
        posView.panX=(selectedBox.cx-allBox.cx)/allBox.span;
        posView.panY=(selectedBox.cy-allBox.cy)/allBox.span;
      }
    }
    const values=indices=>indices.flatMap(j=>{
      const f=frequencies[j];
      return f?[...f.setup.flatMap(c=>[c.low,c.high]),
        ...f.matching.flatMap(m=>[m.start,m.end,m.request,...m.coverage.flatMap(v=>[v.low,v.high])])].filter(finite):[];
    });
    const allFreq=values(current.visible),selectedFreq=values([i]);
    if(allFreq.length&&selectedFreq.length){
      const lo=Math.min(...allFreq),hi=Math.max(...allFreq);
      const pad=Math.max((hi-lo)*.08,Math.abs(hi)*1e-6,1e-8);
      const base=hi-lo+2*pad,small=Math.max(Math.max(...selectedFreq)-Math.min(...selectedFreq),base/16);
      freqView.zoom=Math.max(1,Math.min(16,base/(small*1.15)));
      freqView.panX=((Math.max(...selectedFreq)+Math.min(...selectedFreq))/2-(hi+lo)/2)/base;
    }
    draw();
  };
})();
