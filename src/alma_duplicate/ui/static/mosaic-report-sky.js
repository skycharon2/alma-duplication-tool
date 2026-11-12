/* Lazy, read-only Aladin preview of the saved Mosaic Explorer result page. */
(() => {
  'use strict';
  const root=document.querySelector('.mosaic-explorer');
  const canvas=root?.querySelector('#mosaic-sky-canvas');
  const payload=document.getElementById('mosaic-sky-data');
  if (!canvas || !payload) return;
  let scenes;
  try { scenes=JSON.parse(payload.textContent); }
  catch (_) {canvas.textContent='Saved sky display data unavailable.';return;}
  if (!Array.isArray(scenes)) return;
  const geo=window.MosaicSkyGeometry;
  const rows=[...root.querySelectorAll('[data-row]')];
  const panel=root.querySelector('#sky');
  const status=root.querySelector('#mosaic-sky-status');
  const imageStatus=root.querySelector('#mosaic-imagery-status');
  const retry=root.querySelector('#mosaic-sky-retry');
  const propose=root.querySelector('#mosaic-sky-proposed');
  const candidate=root.querySelector('#mosaic-sky-candidates');
  const others=root.querySelector('#mosaic-sky-others');
  const imagery=root.querySelector('#mosaic-sky-imagery');
  const identities=root.querySelector('#mosaic-sky-identities');

  let A,viewer,proposedCatalog,proposedLayer,haloLayer;
  const candidateLayers={}, candidateCatalogs={};
  let loading=false,viewerReady=false,imageReady=false;
  let overlayLimitNotice='';

  function selectedIndex() {
    const button=rows.find(r=>!r.hidden&&r.getAttribute('aria-pressed')==='true');
    return button ? Number(button.dataset.row) : -1;
  }
  function visibleScenes() {
    return rows.filter(r=>!r.hidden).map(r=>({index:Number(r.dataset.row),scene:scenes[Number(r.dataset.row)]}))
      .filter(r=>r.scene?.available);
  }
  function selectedScene() {const i=selectedIndex();return i < 0 ? null : scenes[i];}
  function visibleOthers() {
    const candidates=visibleScenes().filter(r=>r.index!==selectedIndex());
    const beams=candidates.reduce((total,r)=>total+(r.scene.candidate?.beams?.length||0),0);
    // Do not silently render an incomplete subset of an oversized result page.
    const withinBudget=candidates.length<=80 && beams<=800;
    overlayLimitNotice=withinBudget?'':`Additional overlays omitted: ${candidates.length} comparisons / ${beams} beams exceed the display limit (80 / 800). `;
    return withinBudget ? candidates : [];
  }
  // Preserve provenance colors even for selected records: color cannot imply a verdict.
  const color=entry=>entry.source==='Queue'?'#d88a00':'#176fba';
  function clearGeometry() {
    proposedCatalog?.removeAll();proposedLayer?.removeAll();haloLayer?.removeAll();
    for(const layer of Object.values(candidateLayers))layer.removeAll();
    for(const catalog of Object.values(candidateCatalogs))catalog.removeAll();
  }
  function drawCandidate(entry,selected,rowIndex) {
    if(!entry.candidate || !candidate.checked)return;
    const col=color(entry),c=entry.candidate;
    const source=entry.source==='Queue'?'Queue':'Archive';
    const candidateLayer=candidateLayers[source], candidateCatalog=candidateCatalogs[source];
    const lineStyle={color:col,lineWidth:selected?2.9:1.6,opacity:selected?1:.75};
    if(c.kind==='region') {
      if(selected) haloLayer.add(A.polyline(c.outline,{color:'#ffffff',lineWidth:5.5,opacity:.95}));
      candidateLayer.add(A.polyline(c.outline,lineStyle));
      // A saved region outline does not imply an observed centre.
    } else if(c.kind==='beams') {
      for (const beam of c.beams) {
        const radius=beam.radius_arcsec ?? c.radius_arcsec;
        if(selected) haloLayer.add(A.circle(...beam.center,radius/3600,
          {color:'#ffffff',lineWidth:5.3,opacity:.95}));
        candidateLayer.add(A.circle(...beam.center,radius/3600,lineStyle));
        candidateCatalog.addSources([A.source(...beam.center,{rowIndex,
          label:selected?'Selected candidate beam':'Candidate beam'})]);
      }
    }
  }
  function draw() {
    const selected=selectedScene();
    const othersVisible=others.checked?visibleOthers():[];
    identities.replaceChildren();
    if(!selected?.available) {
      status.textContent='No saved, valid ICRS Mosaic geometry for this selection.';
      if(viewerReady)clearGeometry();else canvas.replaceChildren();
      return;
    }
    const summary=document.createElement('p');
    summary.textContent=`${selected.label || 'Candidate'} · ${selected.source || 'Source unrecorded'} · `+
      `Project ${selected.project || 'not recorded'}`;
    identities.append(summary);
    const explanation=document.createElement('p');
    explanation.textContent=selected.candidate ? (selected.source === 'Queue' ? 'Candidate beam coverage reconstructed from the observation settings.' : 'Candidate coverage from the Archive.') :
      `Candidate outline unavailable: ${selected.reason || 'no validated footprint'}`;
    identities.append(explanation);
    status.textContent=`${selected.proposed.length} submitted pointings · `+
      `${selected.candidate ? 'verified saved candidate outline' : 'no candidate outline'} · `+
      `${othersVisible.length} additional visible comparisons selected for optional overlay. `+
      (others.checked?overlayLimitNotice:'')+
      'Coordinates are ICRS; optical imagery is not an ALMA detection.';
    if(!viewerReady) {
      geo.fallback(canvas,selected,othersVisible.map(item=>item.scene),{
        proposed:propose.checked,candidates:candidate.checked,others:others.checked});
      return;
    }
    clearGeometry();
    if(others.checked)for(const item of othersVisible) drawCandidate(item.scene,false,item.index);
    drawCandidate(selected,true,selectedIndex());
    if(propose.checked) {
      for(const point of selected.proposed)
        proposedCatalog.addSources([A.source(...point.center,{label:point.id})]);
      for(const beam of selected.proposed_beams)
        for(const point of selected.proposed)
          proposedLayer.add(A.circle(...point.center,beam.radius_arcsec/3600,
            {color:'#a12b9b',lineWidth:1.7}));
    }
  }
  function fit(extra=false) {
    const selected=selectedScene();if(!selected?.available || !viewerReady)return;
    const rest=extra?visibleOthers().map(x=>x.scene):[];
    const view=geo.extent(selected,rest);
    if(!view)return;
    const aspect=Math.max(1, (canvas.clientWidth||1)/(canvas.clientHeight||1));
    viewer.gotoRaDec(...view.origin);viewer.setFoV(Math.min(120,view.fov*aspect));
  }
  function onCandidateClick(source) {
    const index=source?.data?.rowIndex;
    const button=rows.find(r=>Number(r.dataset.row)===index && !r.hidden);
    if(button)button.click(); // Use the existing Mosaic filter/selection controller.
  }
  async function load() {
    if(loading)return;
    if(viewerReady) {draw();fit(others.checked);return;}
    if(!selectedScene()?.available) {draw();return;}
    loading=true;retry.hidden=true;
    imageStatus.textContent='Loading local Aladin Lite and DSS optical reference imagery…';
    try {
      A=await window.AlmaSkyRuntime.load(canvas.dataset.aladinModule);
      // A retry after an offline SVG must start with an empty host element.
      const selected=selectedScene();
      if(!selected?.available || !skyActive()) {
        draw();
        imageStatus.textContent='Sky loading paused; select a valid comparison and open Sky preview.';
        return;
      }
      canvas.replaceChildren();
      const origin=selected.proposed[0].center;
      viewer=A.aladin('#mosaic-sky-canvas',{
        target:origin.join(' '),cooFrame:'ICRS',
        survey:window.AlmaSkyRuntime.surveys.dss,fov:.1,
        showReticle:false,showLayersControl:true,showFullscreenControl:true,
        showSettingsControl:true,showCooGridControl:true
      });
      haloLayer=A.graphicOverlay({name:'Selected footprint highlight',color:'#ffffff'});
      viewer.addOverlay(haloLayer);
      for(const source of ['Archive','Queue']) {
        const col=color({source});
        candidateLayers[source]=A.graphicOverlay({name:`${source} saved footprints`,color:col,
          lineDash:source==='Queue'?[6,4]:[]});
        candidateCatalogs[source]=A.catalog({name:`${source} beam centres`,color:col,
          sourceSize:8,onClick:onCandidateClick});
        viewer.addOverlay(candidateLayers[source]);viewer.addCatalog(candidateCatalogs[source]);
      }
      proposedLayer=A.graphicOverlay({name:'Submitted Mosaic half-power beams',color:'#a12b9b',lineDash:[6,5]});
      viewer.addOverlay(proposedLayer);
      proposedCatalog=A.catalog({name:'Submitted OT pointing centres',color:'#00b9af',
        shape:'cross',sourceSize:14});
      viewer.addCatalog(proposedCatalog);
      viewerReady=true;draw();fit(others.checked);
      await loadImage();
    } catch(err) {
      console.warn('Mosaic Aladin preview unavailable; retaining saved geometry:',err);
      viewerReady=false;viewer=null;
      imageReady=false;
      draw();retry.hidden=false;
      imageStatus.textContent='Optical viewer unavailable. Displaying saved geometry only. Retry is available.';
    } finally {loading=false;}
  }
  async function loadImage() {
    try {
      await window.AlmaSkyRuntime.loadReferenceImagery(viewer);
      imageReady=true;
      viewer.getBaseImageLayer()?.setOpacity(imagery.checked?1:0);
      imageStatus.textContent='Optical DSS reference imagery · use the native Aladin layers menu to change survey.';
      retry.hidden=true;
    } catch(err) {
      imageReady=false;
      imageStatus.textContent='Reference imagery unavailable; saved geometry remains visible. '+String(err.message||err);
      retry.hidden=false;
    }
  }
  retry.addEventListener('click',()=>{
    if(viewerReady)loadImage();else load();
  });
  for(const toggle of [propose,candidate,others])toggle.addEventListener('change',()=>{
    draw();if(viewerReady)fit(others.checked);
  });
  imagery.addEventListener('change',()=>{
    if(viewerReady && imageReady)viewer.getBaseImageLayer()?.setOpacity(imagery.checked?1:0);
    imageStatus.textContent=imagery.checked?'Optical reference imagery requested.':'Optical imagery hidden; geometry unchanged.';
  });
  root.querySelector('#mosaic-sky-overview').addEventListener('click',()=>fit(true));
  root.querySelector('#mosaic-sky-selected').addEventListener('click',()=>fit(false));
  const tab=root.querySelector('.evidence-pager [aria-controls="sky"]');
  const gallery=root.querySelector('#mosaic-evidence-gallery');
  // Gallery slides remain in the DOM for native horizontal scrolling. The
  // pager owns which slide is active; `hidden` no longer identifies that page.
  function skyActive() {
    return gallery ? tab?.getAttribute('aria-pressed')==='true' : !panel.hidden;
  }
  for(const row of rows)row.addEventListener('click',()=>{if(skyActive()) {if(!viewerReady)load();else {draw();fit(false);}}});
  for(const filter of root.querySelectorAll('[data-filter]'))filter.addEventListener('change',()=>{
    if(skyActive()){if(!viewerReady)load();else {draw();fit(false);}}
  });
  root.querySelector('#mosaic-isolate')?.addEventListener('click',()=>{
    if(skyActive()){if(!viewerReady)load();else {draw();fit(false);}}
  });
  root.querySelector('#clear-filters').addEventListener('click',()=>{
    if(skyActive()){if(!viewerReady)load();else {draw();fit(false);}}
  });
  tab?.addEventListener('click',()=>{if(skyActive())load();});
  // Touchpad/touch/keyboard swipes use the gallery's native scroll position.
  // Do not load Aladin until the Sky slide becomes the active page.
  gallery?.addEventListener('scroll',()=>{if(skyActive() && !viewerReady && !loading)load();},
    {passive:true});
  // No imaging service, Aladin module, or network request until Sky is opened.
})();
