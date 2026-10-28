'use strict';
(() => {
const guides = {
 coordinates: ['Target coordinates','Enter the proposed target position in ICRS. This input is not a search by name.','Formats','RA: DEG or HMS. Dec: DEG or DMS.','Example','18:33:39.920 / −21:03:39.900','Use colons for HMS and DMS. The target name is an optional label for fixed targets.'],
 angular: ['Planned angular resolution','The angular resolution requested for this observation. It is compared with the candidate’s recorded angular resolution.','Units','arcsec or mas','Example','3.573980180426332 arcsec','Angular resolution is distinct from the primary-beam footprint used for the position criterion.'],
 line: ['Spectral line requirements','Enter one requested frequency, planned spectral resolution and RMS at that resolution. You do not need to reproduce the candidate’s SPW configuration.','Frequency','REST / laboratory frequency with source redshift, or observed SKY frequency.','Candidate data','Archive and Queue supply their own SPW coverage, resolution and sensitivity.','These values describe the requested line check. Each additional requested window keeps its own frequency, resolution and RMS. Results apply to the submitted requirements. Physical SPW inventory completeness is separate in the Archive requirements form.'],
 frequency: ['Requested line frequency','The central frequency of the requested correlator window. Use observed SKY frequency, or REST / laboratory frequency with source redshift.','Units','GHz, MHz, kHz or Hz','Example','230.53800141830845 GHz · SKY','The connected backend prepares REST inputs using the supplied redshift. The original input and converted frequency remain traceable in the report; no observing frame is inferred.'],
 resolution: ['Planned spectral resolution','The spectral resolution requested for this window. Enter the RMS at this same resolution.','Units','km/s, m/s, GHz, MHz, kHz or Hz','Example','1 km/s','Spectral resolution, channel spacing and noise bandwidth are distinct. The backend owns the conversion used in assessment.'],
 rms: ['Planned RMS','The requested noise level per beam, at this window’s planned spectral resolution.','Units','mJy/beam or Jy/beam','Example','19.92234925906079 mJy/beam at 1 km/s','This is a per-window LINE input. It does not supply the continuum aggregate RMS.'],
 mode: ['Correlator mode','Declare the mode of the proposed window. The LINE frequency condition requires FDM on both sides of the comparison.','Options','FDM, TDM or UNKNOWN','Example','FDM','Selecting Spectral line does not independently establish FDM. Retain UNKNOWN if the mode is not known.'],
 bandwidth: ['Window bandwidth','Declare whether the entered width is nominal or already usable. The connected backend applies the approved mapping to supported nominal widths.','Units','MHz, GHz, kHz or Hz','Method example','500 MHz nominal → 468.8 MHz usable','The backend applies the approved mapping during assessment. Unrecognized widths must not be silently treated as usable.'],
 continuum: ['Continuum requirements','Provide a SKY representative frequency, or REST representative frequency with source redshift, and RMS over the aggregate bandwidth.','Setup qualification','At least two distinct windows, each wider than 1.8 GHz usable.','Evidence','Use a setup declaration or qualifying window details.','Exactly 1.8 GHz does not qualify. The combined Continuum choice records your confirmation, not an independent measurement. Conflicting complete window evidence is still flagged.'],
 sources: ['Data sources','Archive and Queue are assessed as separate sources. Source availability is controlled by the connected application.','Archive','TAP retrieval with source-bound AQ evidence when configured.','Queue','A server-managed CSV snapshot; its date belongs in the report.','Automatic retrieval selects the search scope. Candidate position is evaluated separately. Selecting a source does not access it until you run assessment.']
};
guides.redshift = ['Source redshift', 'This default is used for REST frequencies. In the Archive requirements form, each LINE requirement can override it with its own redshift.', 'Conversion', 'Observed frequency = REST frequency / (1 + z).', 'Example', '460 GHz REST at z = 1 corresponds to 230 GHz SKY.', 'Leave blank if unknown. No z = 0 is assumed. SKY inputs are already observed frequencies.'];
const illustrations = {
frequency: `<figure class="help-figure"><figcaption>Window centre <span>Illustration</span></figcaption>
<svg viewBox="0 0 320 190" role="img" aria-labelledby="frequency-illustration-title frequency-illustration-desc">
<title id="frequency-illustration-title">A requested window with its centre marked</title><desc id="frequency-illustration-desc">A blue frequency interval extends equally on either side of its centre, labelled nu zero. This schematic does not show observed data or assess coverage.</desc>
<line x1="24" y1="144" x2="294" y2="144" stroke="#a7bac8"/><path d="M288 140 L294 144 L288 148" fill="none" stroke="#a7bac8"/>
<rect x="55" y="67" width="210" height="45" rx="4" fill="#e3f1f9" stroke="#6c9ebd"/>
<line x1="160" y1="39" x2="160" y2="145" stroke="#006d9e" stroke-width="2"/>
<circle cx="160" cy="89" r="4" fill="#006d9e"/>
<text x="160" y="27" text-anchor="middle" fill="#234b65">Centre ν₀</text>
<text x="55" y="57" fill="#47677e" font-size="11">Requested window</text>
<text x="55" y="134" text-anchor="middle" fill="#637b8b" font-size="11">Lower edge</text><text x="265" y="134" text-anchor="middle" fill="#637b8b" font-size="11">Upper edge</text>
<text x="293" y="168" text-anchor="end" fill="#637b8b" font-size="12">Frequency</text>
</svg><p class="figure-caption">Enter the centre, not an interval endpoint. Schematic only; no candidate data.</p></figure>`,
bandwidth: `<figure class="help-figure"><figcaption>Width comparison <span>Illustration</span></figcaption>
<svg viewBox="0 0 320 190" role="img" aria-labelledby="bandwidth-illustration-title bandwidth-illustration-desc">
<title id="bandwidth-illustration-title">500 MHz nominal compared with 468.8 MHz usable</title><desc id="bandwidth-illustration-desc">Two centred bars share a width scale. The usable bar is 93.76 percent of the nominal bar. The centred placement is illustrative and does not specify measured band edges.</desc>
<text x="30" y="31" fill="#526e82" font-size="12">Nominal</text><text x="290" y="31" text-anchor="end" fill="#234b65" font-size="13">500 MHz</text>
<rect x="32" y="43" width="256" height="24" rx="3" fill="#e5ebef" stroke="#a7bac8"/>
<path d="M32 72 V137 M288 72 V137" stroke="#c2ced7" stroke-dasharray="3 4"/>
<text x="30" y="103" fill="#006d9e" font-size="12">Usable</text><text x="290" y="103" text-anchor="end" fill="#006d9e" font-size="13">468.8 MHz</text>
<rect x="39.9872" y="115" width="240.0256" height="24" rx="3" fill="#007bb1"/>
<text x="160" y="172" text-anchor="middle" fill="#637b8b" font-size="11">Same width scale · illustrative placement</text>
</svg><p class="figure-caption">One approved mapping example. Do not apply this ratio to other nominal widths.</p></figure>`
};
const guideContent=document.querySelector('#guide-content');
const guide=document.querySelector('#field-guide');
const close=document.querySelector('#close-guide');
let activeHelp=null, pinned=false, openTimer, closeTimer, suppressHover=null;
function dismissHelp(restore=false){
  clearTimeout(openTimer); clearTimeout(closeTimer);
  const previous=activeHelp;
  guide.getAnimations().forEach(animation=>animation.cancel());
  guide.hidden=true; pinned=false; activeHelp=null;
  if(previous){previous.setAttribute('aria-expanded','false');suppressHover=previous;}
  if(restore && previous)previous.focus({preventScroll:true});
}
function positionHelp(){
  if(!activeHelp || guide.hidden)return;
  const r=activeHelp.getBoundingClientRect(), edge=12, gap=12;
  const vp=window.visualViewport;
  const vw=vp?vp.width:window.innerWidth, vh=vp?vp.height:window.innerHeight;
  const ox=vp?vp.offsetLeft:0, oy=vp?vp.offsetTop:0;
  if(r.bottom<oy || r.top>oy+vh || !activeHelp.getClientRects().length){dismissHelp();return;}
  guide.style.width=Math.min(guide.classList.contains('has-illustration')?700:420,vw-2*edge)+'px';
  guide.style.maxHeight=(vh-2*edge)+'px';
  const height=guide.getBoundingClientRect().height;
  const below=oy+vh-r.bottom-gap-edge, above=r.top-oy-gap-edge;
  const side=below>=height || below>=above?'below':'above';
  const left=Math.max(ox+edge,Math.min(r.left-28,ox+vw-guide.offsetWidth-edge));
  const top=Math.max(oy+edge,Math.min(side==='below'?r.bottom+gap:r.top-gap-height,oy+vh-height-edge));
  guide.style.left=left+'px';guide.style.top=top+'px';guide.dataset.side=side;
  guide.style.setProperty('--pointer-x',Math.max(20,Math.min(r.left+r.width/2-left,guide.offsetWidth-20))+'px');
}
function showHelp(button,lock=false){
  clearTimeout(openTimer);clearTimeout(closeTimer);
  if(activeHelp && activeHelp!==button)activeHelp.setAttribute('aria-expanded','false');
  activeHelp=button;pinned=lock;button.setAttribute('aria-expanded','true');
  const data=guides[button.dataset.help];
  document.querySelector('#guide-title').textContent=data[0];
  guideContent.replaceChildren();
  const layout=document.createElement('div');layout.className='help-layout';
  const text=document.createElement('div');text.className='help-copy';
  const description=document.createElement('p');description.className='popover-description';description.textContent=data[1];text.append(description);
  const grid=document.createElement('div');grid.className='popover-facts';
  for(const i of [2,4]){const cell=document.createElement('div');const heading=document.createElement('h3');heading.textContent=data[i];const body=document.createElement('p');body.textContent=data[i+1];if(i===4)body.className='example';cell.append(heading,body);grid.append(cell);}
  text.append(grid);layout.append(text);
  const illustration=illustrations[button.dataset.help];
  guide.classList.toggle('has-illustration',Boolean(illustration));
  if(illustration){
    // The template is a fixed local illustration; form input is never used as HTML.
    const template=document.createElement('template');template.innerHTML=illustration;
    layout.append(template.content.cloneNode(true));
  }
  guideContent.append(layout);
  const foot=document.createElement('p');foot.className='popover-note';foot.textContent=data[6];guideContent.append(foot);
  guide.hidden=false;positionHelp();
  guide.getAnimations().forEach(animation=>animation.cancel());
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches){
    const offset=guide.dataset.side==='above'?3:-3;
    guide.animate([{opacity:0,transform:'translateY('+offset+'px)'},{opacity:1,transform:'translateY(0)'}],{duration:140,easing:'ease-out'});
  }
}
function scheduleClose(){
  clearTimeout(closeTimer);
  if(!pinned)closeTimer=setTimeout(()=>dismissHelp(),220);
}
function registerHelp(root){root.querySelectorAll('[data-help]').forEach(button=>{
  button.setAttribute('aria-expanded','false');button.setAttribute('aria-haspopup','dialog');
  button.addEventListener('pointerenter',event=>{
    if(event.pointerType!=='mouse' || suppressHover===button || pinned)return;
    clearTimeout(closeTimer);clearTimeout(openTimer);
    openTimer=setTimeout(()=>showHelp(button),160);
  });
  button.addEventListener('pointerleave',()=>{clearTimeout(openTimer);if(suppressHover===button)suppressHover=null;scheduleClose();});
  button.addEventListener('click',event=>{
    if(activeHelp===button && pinned){dismissHelp(true);return;}
    showHelp(button,true);
    if(event.detail===0)close.focus({preventScroll:true});
  });
});}

guide.addEventListener('pointerenter',()=>clearTimeout(closeTimer));
guide.addEventListener('pointerleave',scheduleClose);
close.addEventListener('click',()=>dismissHelp(true));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!guide.hidden){dismissHelp(true);event.preventDefault();}});
document.addEventListener('pointerdown',event=>{if(!guide.hidden&&!guide.contains(event.target)&&!activeHelp?.contains(event.target))dismissHelp();});
document.addEventListener('focusin',event=>{if(!guide.hidden&&!guide.contains(event.target)&&event.target!==activeHelp)dismissHelp();});
window.addEventListener('scroll',positionHelp,{passive:true});window.addEventListener('resize',positionHelp);
window.visualViewport?.addEventListener('resize',positionHelp);
window.visualViewport?.addEventListener('scroll',positionHelp);

let currentForm = null;
let sectionFrame = null;
function markSection() {
  sectionFrame = null;
  if (!currentForm?.isConnected) return;
  const links = [...currentForm.querySelectorAll('.proposal-sections a')];
  let active = links[0];
  for (const link of links) {
    const section = currentForm.querySelector(link.getAttribute('href'));
    if (section?.getClientRects().length && section.getBoundingClientRect().top <= 120) active = link;
  }
  for (const link of links) {
    if (link === active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  }
}
window.addEventListener('scroll', () => {
  if (sectionFrame === null) sectionFrame = requestAnimationFrame(markSection);
}, {passive: true});
window.addEventListener('resize', markSection);

window.initializeProposalWorkbench = function(form) {
  if (form.dataset.workbenchReady) return;
  form.dataset.workbenchReady = 'true';
  currentForm = form;
  dismissHelp();
  registerHelp(form);
  const value = name => form.elements.namedItem(name)?.value?.trim() || '';
  const selected = name => [...form.querySelectorAll(`input[name="${name}"]:checked`)].map(el => el.value);
  const labels = {LINE:'Spectral line', CONTINUUM:'Continuum', ARCHIVE:'Archive', QUEUE:'Queue CSV', FIXED:'Fixed target', MOVING:'Moving target', SUN:'Sun', SINGLE_POINTING:'Single pointing', MOSAIC:'Mosaic'};
  const write = (key, text) => {const el=form.querySelector(`[data-summary="${key}"]`); if(el) el.textContent=text;};
  const redshift = form.querySelector('#shared-redshift');
  const lineGrid = form.querySelector('#line-requirements:not([hidden]) .line-frequency-grid');
  const continuumGrid = form.querySelector('#sensitivities:not([hidden]) .continuum-frequency-grid');
  const separateRecords = !!form.querySelector('[name=normal_line_records]');
  if (lineGrid && !separateRecords) lineGrid.insertBefore(redshift, lineGrid.querySelector('.mode-control'));
  else if (continuumGrid && !separateRecords) continuumGrid.insertBefore(redshift, continuumGrid.lastElementChild);
  if (redshift) {
    redshift.querySelector('label').textContent=separateRecords ? 'Default source redshift z' : 'Source redshift z';
    const help=redshift.querySelector('[data-help]');
    if(help) help.setAttribute('aria-label','Help with source redshift');
  }
  function update() {
    if (redshift) redshift.hidden = selected('intents').length === 0;
    write('target', value('target_name') || 'Unnamed target');
    write('position', `RA ${value('ra') || '—'} ${value('ra_format')} / Dec ${value('dec') || '—'} ${value('dec_format')}`);
    write('scope', `${labels[value('target_kind')] || value('target_kind')} / ${labels[value('geometry')] || value('geometry')}`);
    for(const [key, field] of [['purposes','intents'],['sources','sources']]) write(key, selected(field).map(v=>labels[v]||v).join(' + ') || 'Not selected');
  }
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
  markSection();
};
})();
