/* Proposed geometry preview only; no candidate query or scientific verdict. */
(() => {
const rad = Math.PI / 180;
function sky(value, unit, kind, z) {
  const scale = {GHz:1, MHz:1e-3, kHz:1e-6, Hz:1e-9}[unit];
  let frequency = Number(value) * scale;
  if (!String(value).trim() || !Number.isFinite(frequency) || frequency <= 0) return null;
  if (kind === 'REST') {
    if (!String(z).trim() || !Number.isFinite(Number(z)) || Number(z) <= -1) return null;
    frequency /= 1 + Number(z);
  } else if (kind !== 'SKY') return null;
  return Number.isFinite(frequency) && frequency > 0 ? frequency : null;
}
function project(ra, dec, ra0, dec0) {
  const delta = (ra - ra0) * rad, d = dec * rad, d0 = dec0 * rad;
  const cosc = Math.max(-1, Math.min(1, Math.sin(d0)*Math.sin(d)+Math.cos(d0)*Math.cos(d)*Math.cos(delta)));
  const c = Math.acos(cosc);
  if (c > Math.PI - 1e-6) return null;
  const k = c < 1e-8 ? 1 : c / Math.sin(c);
  return [-k*Math.cos(d)*Math.sin(delta)/rad*3600,
    -k*(Math.cos(d0)*Math.sin(d)-Math.sin(d0)*Math.cos(d)*Math.cos(delta))/rad*3600];
}
function radius(frequency, diameter) {return 1.13*299792458/(frequency*1e9*diameter)/rad*3600/2;}
function destination(ra, dec, distance, bearing) {
  const d=dec*rad, a=distance/3600*rad;
  const lat=Math.asin(Math.max(-1,Math.min(1,Math.sin(d)*Math.cos(a)+Math.cos(d)*Math.sin(a)*Math.cos(bearing))));
  const lon=ra*rad+Math.atan2(Math.sin(bearing)*Math.sin(a)*Math.cos(d),Math.cos(a)-Math.sin(d)*Math.sin(lat));
  return [lon/rad, lat/rad];
}
if (typeof module !== 'undefined') module.exports={sky,project,radius,destination};
if (typeof window === 'undefined') return;
window.initializeMosaicPreview = form => {
  const canvas=form.querySelector('[data-mosaic-canvas]'); if (!canvas) return;
  const ctx=canvas.getContext('2d'), select=form.querySelector('[data-preview-frequency]');
  const status=form.querySelector('[data-map-status]');
  const ras=JSON.parse(form.querySelector('[data-mosaic-points]').textContent);
  const decs=JSON.parse(form.querySelector('[data-mosaic-decs]').textContent);
  const points=ras.map((ra,i)=>[ra,decs[i]]);
  const file=form.querySelector('#ot_pointings'), upload=form.querySelector('[value="preview-pointings"]');
  file.addEventListener('change',()=>{if(file.files.length){status.textContent='Importing pointings…';form.requestSubmit(upload);}});
  upload.hidden=true; // Native upload remains available when JavaScript is disabled.
  const value=name=>form.elements.namedItem(name)?.value ?? '';
  let zoom=1, pan=[0,0], options=[], drag=null, autoFrequency=true;
  const vector=points.reduce((sum,[a,d])=>[sum[0]+Math.cos(d*rad)*Math.cos(a*rad),sum[1]+Math.cos(d*rad)*Math.sin(a*rad),sum[2]+Math.sin(d*rad)],[0,0,0]);
  const centre=points.length && Math.hypot(...vector)>1e-8 ? [Math.atan2(vector[1],vector[0])/rad,Math.atan2(vector[2],Math.hypot(vector[0],vector[1]))/rad] : points[0] || [0,0];
  const projected=points.map(p=>project(...p,...centre));
  function refresh() {
    const previous=select.value; options=[];
    if(form.querySelector('[name=intents][value=LINE]:checked')) {
      [...form.querySelectorAll('[name=rows]')].forEach((el,i)=>{
        const row=el.value;
        const z=form.querySelector('[name=frequency_local_redshift]') ? value(row+'_redshift') : value(row+'_redshift') || value('redshift');
        const f=sky(value(row+'_center'),value(row+'_center_unit')||'GHz',value(row+'_center_kind'),z);
        if(f)options.push({id:row,label:`LINE ${i+1} · ${f.toPrecision(6)} GHz SKY`,f});
      });
    }
    if(form.querySelector('[name=intents][value=CONTINUUM]:checked')) {
      const z=form.querySelector('[name=frequency_local_redshift]') ? value('continuum_redshift') : value('redshift');
      const f=sky(value('representative'),value('representative_unit')||'GHz',value('representative_kind'),z);
      if(f)options.push({id:'continuum',label:`Continuum · ${f.toPrecision(6)} GHz SKY`,f});
    }
    select.replaceChildren(new Option('Pointing centres only',''),...options.map(o=>new Option(o.label,o.id)));
    select.value=options.some(o=>o.id===previous)?previous:(!autoFrequency && previous===''?'':(options[0]?.id||''));
    draw();
  }
  function draw() {
    const width=canvas.clientWidth||500,height=canvas.clientHeight||360,dpr=window.devicePixelRatio||1;
    canvas.width=width*dpr;canvas.height=height*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
    ctx.font='12px system-ui';ctx.fillStyle='#496879';
    if(!points.length){ctx.textAlign='center';ctx.fillText('Your pointing pattern will appear here',width/2,height/2);ctx.textAlign='left';return;}
    if(projected.some(p=>!p)){status.textContent='This list spans the projection antipode. Review the coordinate table.';return;}
    const freq=options.find(o=>o.id===select.value)?.f, diameter=value('mosaic_array')==='7m'?7:12;
    const beam=freq?radius(freq,diameter):0;
    // Do not render unphysical all-sky circles from an invalid preview frequency.
    const validBeam=Number.isFinite(beam)&&beam>0&&beam<90*3600?beam:0;
    const extent=Math.max(5,...projected.map(p=>Math.max(Math.abs(p[0]),Math.abs(p[1]))));
    const scale=Math.min(width,height)*.40/(extent+validBeam)*zoom;
    const px=p=>[width/2+pan[0]+p[0]*scale,height/2+pan[1]+p[1]*scale];
    ctx.strokeStyle='#d4e5ee';ctx.lineWidth=1;
    for(let x=0;x<width;x+=50){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,height);ctx.stroke();}
    for(let y=0;y<height;y+=50){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(width,y);ctx.stroke();}
    if(validBeam){ctx.strokeStyle='#168ab4';ctx.lineWidth=1;points.forEach(p=>{
      ctx.beginPath();for(let j=0;j<=48;j++){const projectedCircle=project(...destination(...p,validBeam,j*Math.PI/24),...centre);if(!projectedCircle)return;const q=px(projectedCircle);if(j===0)ctx.moveTo(...q);else ctx.lineTo(...q);}ctx.stroke();
    });}
    projected.forEach((p,i)=>{const [x,y]=px(p);ctx.fillStyle='#134d69';ctx.beginPath();ctx.arc(x,y,3,0,2*Math.PI);ctx.fill();if(points.length<=100){ctx.fillText(String(i+1),x+6,y-6);}});
    ctx.fillStyle='#345c70';ctx.fillText('N ↑   E ←',12,20);
    const bar=80/scale;ctx.strokeStyle='#345c70';ctx.beginPath();ctx.moveTo(14,height-22);ctx.lineTo(94,height-22);ctx.stroke();ctx.fillText(`${bar.toPrecision(3)}″ (map centre)`,14,height-30);
    status.textContent=`${points.length} pointings · ICRS · ${((centre[0]+360)%360).toFixed(6)}°, ${centre[1].toFixed(6)}°`+(validBeam?` · HPBW ${(validBeam*2).toPrecision(5)}″ at ${freq.toPrecision(6)} GHz`:' · Enter a valid SKY frequency, or REST frequency and z, to show beams.');
    const summary=form.querySelector('[data-summary=position]');if(summary)summary.textContent=`${points.length} imported pointings · ICRS`;
  }
  select.addEventListener('change',()=>{autoFrequency=false;draw();});
  form.addEventListener('input',refresh);form.addEventListener('change',refresh);
  form.querySelector('[data-preview-reset]').addEventListener('click',()=>{zoom=1;pan=[0,0];draw();});
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.1,Math.min(100,zoom*Math.exp(-e.deltaY*.002)));draw();},{passive:false});
  canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(drag){pan[0]+=e.clientX-drag[0];pan[1]+=e.clientY-drag[1];drag=[e.clientX,e.clientY];draw();}});
  canvas.addEventListener('pointerup',()=>{drag=null;});canvas.addEventListener('pointercancel',()=>{drag=null;});
  canvas.addEventListener('keydown',e=>{if(['+','=','-','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();if(e.key==='+'||e.key==='=')zoom=Math.min(100,zoom*1.2);else if(e.key==='-')zoom=Math.max(.1,zoom/1.2);else {pan[0]+=e.key==='ArrowLeft'?-20:e.key==='ArrowRight'?20:0;pan[1]+=e.key==='ArrowUp'?-20:e.key==='ArrowDown'?20:0;}draw();}});
  const resize=()=>{if(canvas.isConnected)draw();else window.removeEventListener('resize',resize);};
  window.addEventListener('resize',resize);
  refresh();
};
})();
