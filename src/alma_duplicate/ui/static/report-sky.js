/* Optional image context; all plotted positions/radii come from the saved report. */
window.createReportSky = function(state) {
  const panel = document.querySelector('#report-sky-panel');
  const skyButton = document.querySelector('#position-sky');
  const offsets = document.querySelector('#position-offsets');
  const gallery = document.querySelector('#evidence-gallery');
  const charts = document.querySelector('#evidence-charts');
  const beams = document.querySelector('#sky-show-beams');
  const others = document.querySelector('#sky-show-others');
  const imagery = document.querySelector('#sky-show-imagery');
  let page = 0;
  const status = document.querySelector('#report-sky-status');
  const choices = document.querySelector('#report-sky-choices');
  let viewer, catalog, boundary, reference, selectedCenter, target, loading = false, signature = '';
  const available = () => state.rows().filter(r => r.spatial.available && r.spatial.center);
  const color = r => r.source === 'QUEUE' ? '#d78b36' : '#45a9eb';
  const radius = r => Number.isFinite(r.spatial.radius_arcsec) && r.spatial.radius_arcsec > 0 ? r.spatial.radius_arcsec / 3600 : 0;
  function distance(a,b) {
    const rad = Math.PI/180, d=(b[1]-a[1])*rad, r=(b[0]-a[0])*rad;
    return 2*Math.asin(Math.min(1,Math.sqrt(Math.sin(d/2)**2+Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin(r/2)**2)))/rad;
  }
  function fit(selectedOnly=false,padding=2.6) {
    if (!viewer) return;
    const rows = selectedOnly ? available().filter(r=>r.id===state.selected()) : available();
    const span = Math.max(0.005,...rows.map(r=>distance(state.origin,r.spatial.center)+radius(r)))*padding;
    // Include vertical extent in a wide panel as well as the horizontal extent.
    const canvas=document.querySelector('#report-sky-canvas');
    viewer.gotoRaDec(...state.origin);
    const fittedWidth = span*Math.max(1,canvas.clientWidth/canvas.clientHeight);
    viewer.setFoV(Math.min(180,fittedWidth));
  }
  function overview() {
    if (!viewer) return;
    fit(true,4);
    // Finder-scale context comparable to the reference; retain larger footprints.
    viewer.setFoV(Math.max(4.69/60,viewer.getFov()[0]));
  }
  function describe() {
    const selected=available().find(r=>r.id===state.selected());
    const facts=document.querySelector('#sky-parameters');facts.replaceChildren();
    const spatial=selected?.spatial;
    const explanation=document.querySelector('#sky-relationship');
    const separation=spatial?.separation_arcsec, halfPower=spatial?.radius_arcsec;
    document.querySelector('#sky-separation').textContent=Number.isFinite(separation)&&separation>=0 ? separation.toFixed(2)+'″' : 'Not recorded';
    document.querySelector('#sky-radius-ratio').textContent=Number.isFinite(separation)&&separation>=0&&Number.isFinite(halfPower)&&halfPower>0 ? (100*separation/halfPower).toFixed(1)+'%' : 'Not available';
    if (Number.isFinite(separation) && separation>=0 && Number.isFinite(halfPower) && halfPower>0) {
      const location=separation<halfPower?'inside':separation===halfPower?'on':'outside';
      explanation.textContent={inside:'Inside half-power boundary',on:'On half-power boundary',outside:'Outside half-power boundary'}[location];
    } else {
      explanation.textContent='Position relationship unknown';
    }
    document.querySelector('#sky-comparison-name').textContent=selected ? selected.label+' · '+selected.source+' · SPW '+selected.spw : 'No confirmed candidate position';
    const format=(value,unit='')=>Number.isFinite(value)?Number(value.toPrecision(7))+' '+unit:'Not recorded';
    for(const [label,value] of [
      ['Selected comparison',selected?selected.label+' · '+selected.source+' · SPW '+selected.spw:'No confirmed position selected'],
      ['Candidate frequency',format(spatial?.frequency_ghz,'GHz')],
      ['Recorded dish diameter',format(spatial?.diameter_m,'m')],
      ['Half-power radius',format(spatial?.radius_arcsec,'arcsec')],
      ['Full beam width (2 × radius)',format(spatial?.radius_arcsec == null ? null : spatial.radius_arcsec*2,'arcsec')],
      ['Target separation',format(spatial?.separation_arcsec,'arcsec')]
    ]) {const cell=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;cell.append(dt,dd);facts.append(cell);}

  }
  function update() {
    describe();
    if (!viewer || page !== 1) return;
    const rows = available();
    const next = JSON.stringify([rows.map(r=>r.id),state.selected(),beams.checked,others.checked]);
    if (signature===next) return;
    signature=next;
    catalog.removeAll(); selectedCenter.removeAll(); boundary.removeAll(); reference.removeAll(); choices.replaceChildren();
    const grouped=new Map(), outlines=new Set();
    // Draw the selected boundary last so coincident candidates cannot cover it.
    const drawOrder = [...rows].sort((a,b)=>Number(a.id===state.selected())-Number(b.id===state.selected()));
    for (const row of drawOrder) {
      const key=row.spatial.center.join(',');
      if (!grouped.has(key)) grouped.set(key,[]);
      grouped.get(key).push(row);
      if (!others.checked && row.id!==state.selected()) continue;
      const outlineKey = [row.source,...row.spatial.center,radius(row)].join(',');
      if (beams.checked && radius(row) && (!outlines.has(outlineKey) || row.id===state.selected())) boundary.add(A.circle(...row.spatial.center,radius(row),{
        color:row.id===state.selected()?'#ff525e':color(row),lineWidth:row.id===state.selected()?1.5:1,opacity:row.id===state.selected()?1:0.4
      }));
      outlines.add(outlineKey);
    }
    for (const group of grouped.values()) {
      const row=group.find(r=>r.id===state.selected()) || group[0];
      if (others.checked && !group.some(r=>r.id===state.selected())) catalog.addSources([A.source(...row.spatial.center,{ids:group.map(r=>r.id)}, {color:color(row)})]);
    }
    const selected=rows.find(r=>r.id===state.selected());
    if(selected) {
      selectedCenter.addSources([A.source(...selected.spatial.center,{label:'Candidate center',ids:grouped.get(selected.spatial.center.join(',')).map(r=>r.id)})]);
      const coincident=grouped.get(selected.spatial.center.join(',')).map(r=>r.id);
      if(coincident.length>1)renderChoices(coincident);
      reference.add(A.polyline([state.origin,selected.spatial.center],{color:'#f5e4a6',lineWidth:2}));
    }
    boundary.show(); reference.show();
    const missing=state.rows().length-rows.length;
    const noRadius=rows.filter(r=>!radius(r)).length;
    const shown=others.checked?rows.length:Number(Boolean(selected));
    status.textContent=`Displayed candidate records: ${shown}; identical boundaries are drawn together. ${rows.length} / ${state.rows().length} visible comparisons have confirmed positions. ${noRadius} have unknown boundaries; ${missing} cannot be plotted. Click a marker to select. If imagery stays blank, use Charts to inspect the recorded geometry.`;
  }
  function choosePosition(source) {
    const ids=source.data.ids || [];
    if(ids.length===1) {state.select(ids[0]);return;}
    renderChoices(ids, true);
  }
  function renderChoices(ids, focus=false) {
    choices.replaceChildren();
    const heading=document.createElement('strong');
    heading.textContent=`${ids.length} comparisons at this position`;
    choices.append(heading);
    for (const id of ids) {
      const row=state.rows().find(r=>r.id===id);if(!row)continue;
      const button=document.createElement('button');button.type='button';
      button.textContent=`${row.label} · ${row.source} · ${row.intent} · SPW ${row.spw}`;
      button.setAttribute('aria-pressed',String(id===state.selected()));
      button.onclick=()=>{state.select(id);renderChoices(ids,true);};
      choices.append(button);
    }
    if(focus) choices.querySelector('[aria-pressed="true"]')?.focus({preventScroll:true});
  }
  let displayedSurvey, surveyRequest=0, surveyPending=false;
  const surveyStatus=document.querySelector('#sky-imagery-status');
  const presets=[['sky-survey-dss','P/DSS2/color'],['sky-survey-ps','P/PanSTARRS/DR1/color-z-zg-g']];
  function imageryStatus(message) {
    surveyStatus.textContent=imagery.checked ? message : 'Reference image hidden · geometry remains visible.';
  }
  function coverageStatus() {
    imageryStatus('Coverage not verified. A blank field is not a non-detection; try DSS or hide the reference image.');
  }
  async function changeSurvey(survey) {
    const request=++surveyRequest;
    surveyPending=true;
    imagery.checked=true;
    imageryStatus('Loading reference layer…');
    let timer, poll, ended=false;
    try {
      const requested=viewer.setBaseImageLayer(survey);
      // Aladin returns a HiPS object immediately, before its metadata and
      // renderer are ready. Wait for that exact layer to become active.
      const ready=Promise.resolve(requested).then(async layer=>{
        await layer?.query;
        if(ended)return;
        await new Promise(resolve=>{
          const check=()=>{if(viewer.getBaseImageLayer()===layer)resolve();};
          poll=setInterval(check,100);check();
        });
      });
      await Promise.race([
        ready,
        new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('timeout')),20000);})
      ]);
      if(request!==surveyRequest)return;
      syncSurvey();
      viewer.getBaseImageLayer()?.setAlpha(1);
      coverageStatus();
    } catch (_) {
      if(request===surveyRequest) imageryStatus('Reference layer could not be loaded. Retry a survey button, choose DSS, or hide the reference image.');
    } finally {
      ended=true;clearTimeout(timer);clearInterval(poll);
      if(request===surveyRequest)surveyPending=false;
    }
  }
  const brightness=document.querySelector('#sky-brightness');
  const contrast=document.querySelector('#sky-contrast');
  function syncSurvey() {
    if (!viewer) return;
    const layer=viewer.getBaseImageLayer();
    if (!layer) return;
    const id=layer.id;
    for(const [button,survey] of presets) document.getElementById(button).setAttribute('aria-pressed',String(id===survey));
    if (displayedSurvey===id) return;
    displayedSurvey=id;
    if(!surveyPending)coverageStatus();
    document.querySelector('#sky-active-survey').textContent=layer.name || id || 'See layers menu';
    brightness.value=0;contrast.value=0;
    layer.setBrightness(0);layer.setContrast(0);
    for(const control of [brightness,contrast,document.querySelector('#sky-reset-display')]) control.disabled=false;
  }
  function adjustDisplay() {
    if(!viewer)return;
    const layer=viewer.getBaseImageLayer();
    layer.setBrightness(Number(brightness.value));layer.setContrast(Number(contrast.value));
  }
  brightness.addEventListener('input',adjustDisplay);contrast.addEventListener('input',adjustDisplay);
  document.querySelector('#sky-reset-display').addEventListener('click',()=>{brightness.value=0;contrast.value=0;adjustDisplay();});
  // The native layer menu also changes surveys; track its rendered updates.
  new MutationObserver(syncSurvey).observe(document.querySelector('#report-sky-canvas'),{childList:true,subtree:true,attributes:true});
  async function load() {
    describe();
    if (viewer) { signature=''; update(); return; }
    if (loading) return;
    document.querySelector('#sky-retry').hidden=true;
    if (!state.origin) {status.textContent="Confirmed target coordinates unavailable. Use the original charts and report.";return;}
    loading=true; status.textContent='Loading CDS Aladin Lite and DSS2 color imagery…';
    imageryStatus('Loading sky viewer and reference imagery…');
    try {
      if (!window.A) await new Promise((resolve,reject)=>{
        const script=document.createElement('script');
        const timer=setTimeout(()=>{script.remove();reject(new Error('timeout'));},20000);
        script.src='https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js';
        script.onload=()=>{clearTimeout(timer);resolve();};script.onerror=()=>{clearTimeout(timer);script.remove();reject(new Error('load'));};
        document.head.append(script);
      });
      await A.init;
      signature='';displayedSurvey=undefined;
      viewer=A.aladin('#report-sky-canvas',{target:state.origin.join(' '),survey:'P/DSS2/color',fov:0.1,showReticle:false,showFullscreenControl:true,showLayersControl:true,showSettingsControl:true,showCooGridControl:true});
      boundary=A.graphicOverlay({name:'Recorded candidate half-power boundaries'});viewer.addOverlay(boundary);
      reference=A.graphicOverlay({name:'Target–candidate separation'});viewer.addOverlay(reference);
      catalog=A.catalog({name:'Candidate positions',sourceSize:10,onClick:choosePosition});viewer.addCatalog(catalog);
      selectedCenter=A.catalog({name:'Selected candidate center',color:'#ff525e',sourceSize:12,shape:'circle',onClick:choosePosition});viewer.addCatalog(selectedCenter);
      target=A.catalog({name:'Your proposed target',color:'#30eee2',sourceSize:18,shape:'cross',displayLabel:true,labelFont:'12px sans-serif',labelColumn:'label',labelColor:'#7ffff5',onClick:()=>{const row=available().find(r=>r.id===state.selected());if(row && distance(state.origin,row.spatial.center)<1e-10)choosePosition({data:{ids:available().filter(r=>distance(r.spatial.center,row.spatial.center)<1e-10).map(r=>r.id)}});}});
      viewer.addCatalog(target);target.addSources([A.source(...state.origin,{label:'Your target'})]);
      for (const id of ['sky-survey-dss','sky-survey-ps']) document.getElementById(id).disabled=false;
      update();overview();syncSurvey();
      await changeSurvey('P/DSS2/color');
    } catch (_) {viewer=null;document.querySelector('#report-sky-canvas').replaceChildren();document.querySelector('#sky-retry').hidden=false;status.textContent='Sky preview unavailable. Retry loading or return to Charts.';imageryStatus('Viewer could not be loaded. Use Retry loading above.');}
    finally {loading=false;}
  }
  function go(index) {
    gallery.scrollTo({left:index*gallery.clientWidth,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  function observePage() {
    const next = gallery.scrollLeft > gallery.clientWidth/2 ? 1 : 0;
    const changed = page !== next;
    page=next;
    offsets.setAttribute('aria-pressed',String(page===0));skyButton.setAttribute('aria-pressed',String(page===1));
    document.querySelector('#evidence-page-number').textContent=(page+1)+' / 2';
    charts.inert=page!==0;panel.inert=page!==1;
    if(page===1 && changed && !loading) load();
  }
  skyButton.addEventListener('click',()=>go(1));offsets.addEventListener('click',()=>go(0));
  gallery.addEventListener('scroll',observePage,{passive:true});
  gallery.addEventListener('keydown',event=>{if(event.target!==gallery)return;if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();go(event.key==='ArrowRight'?1:0);}});
  window.addEventListener('resize',()=>{gallery.scrollTo({left:page*gallery.clientWidth,behavior:'instant'});});
  panel.inert=true;
  // Match the active page height so a tall hidden chart does not leave empty space.
  const resizeGallery = () => {
    gallery.style.height = Math.ceil((page === 1 ? panel : charts).getBoundingClientRect().height) + 'px';
  };
  const sizeObserver = new ResizeObserver(resizeGallery);
  sizeObserver.observe(charts); sizeObserver.observe(panel);
  gallery.addEventListener('scroll', resizeGallery, {passive:true});
  resizeGallery();
  document.querySelector('#sky-retry').addEventListener('click',load);
  beams.addEventListener('change',update);others.addEventListener('change',update);
  imagery.addEventListener('change',()=>{if(viewer) viewer.getBaseImageLayer()?.setAlpha(imagery.checked?1:0);coverageStatus();});
  for (const [id,survey] of presets) {
    document.getElementById(id).addEventListener('click',()=>{
      if (!viewer) return;
      // Change imagery only: preserve position, zoom, selection and recorded circles.
      changeSurvey(survey);
    });
  }
  document.querySelector('#sky-overview').addEventListener('click',overview);
  document.querySelector('#sky-fit').addEventListener('click',()=>{others.checked=true;update();fit();});
  document.querySelector('#sky-selected').addEventListener('click',()=>fit(true));
  return {update,focus:()=>fit(true)};
};
