(() => {
  const root = document.querySelector(".mosaic-explorer");
  const filters = [...root.querySelectorAll("[data-filter]")];
  const rows = [...root.querySelectorAll("[data-row]")];
  let selected = rows[0]?.dataset.row;

  function render() {
    const visible = rows.filter(row => filters.every(filter =>
      !filter.value || row.dataset[filter.dataset.filter] === filter.value));
    if (!visible.some(row => row.dataset.row === selected)) selected = visible[0]?.dataset.row;
    for (const row of rows) {
      row.hidden = !visible.includes(row);
      row.setAttribute("aria-pressed", String(row.dataset.row === selected));
    }
    for (const panel of root.querySelectorAll("[data-evidence]")) {
      panel.toggleAttribute("hidden", panel.dataset.evidence !== selected);
    }
    // Each saved comparison owns independent zoom state. Show the matching
    // toolbar in the shared card header, not every candidate's toolbar.
    for (const controls of root.querySelectorAll('[data-plot-controls]')) {
      controls.hidden = controls.dataset.evidence !== selected;
    }
    root.querySelector("#comparison-count").textContent = visible.length
      ? `${visible.length} of ${rows.length} comparisons`
      : !rows.length ? "No matching comparisons on this report page."
      : "No comparisons match these filters. Clear filters to see all comparisons.";
  }

  for (const filter of filters) filter.addEventListener("change", render);
  for (const row of rows) row.addEventListener("click", () => {
    selected = row.dataset.row;
    render();
  });
  root.querySelector("#clear-filters").addEventListener("click", () => {
    for (const filter of filters) filter.value = "";
    render();
  });
  const pages = [...root.querySelectorAll(".evidence-pager button")];
  const gallery = root.querySelector('#mosaic-evidence-gallery');
  if (gallery && pages.length === 2) {
    // Match Single Pointing: two full-width snap slides, not hidden tabs.
    // Native horizontal trackpad/touch scrolling also changes the active page.
    const slides = pages.map(button => root.querySelector('#' + button.getAttribute('aria-controls')));
    const counter = root.querySelector('#evidence-page-number');
    let current = 0;
    function syncHeight() {
      const measured = slides[current]?.getBoundingClientRect?.().height;
      if (Number.isFinite(measured) && measured > 0)
        gallery.style.height = `${Math.ceil(measured)}px`;
    }
    function activate(index) {
      current = index;
      pages.forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
      slides.forEach((slide, i) => {
        slide.hidden = false; // Both slides must remain laid out for a swipe.
        slide.inert = i !== index;
      });
      if (counter) counter.textContent = `${index + 1} / 2`;
      syncHeight();
    }
    function go(index) {
      activate(index);
      const reduced = typeof matchMedia === 'function' &&
        matchMedia('(prefers-reduced-motion: reduce)').matches;
      const left = index * gallery.clientWidth;
      if (gallery.scrollTo) gallery.scrollTo({left, behavior:reduced?'instant':'smooth'});
      else gallery.scrollLeft = left;
    }
    pages.forEach((button, i) => button.addEventListener('click', () => go(i)));
    gallery.addEventListener('scroll', () => {
      if (gallery.clientWidth > 0)
        activate(gallery.scrollLeft >= gallery.clientWidth / 2 ? 1 : 0);
    }, {passive:true});
    gallery.addEventListener('keydown', event => {
      if (event.target !== gallery || !['ArrowLeft','ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      go(event.key === 'ArrowRight' ? 1 : 0);
    });
    if (typeof ResizeObserver === 'function') {
      const observer = new ResizeObserver(syncHeight);
      for (const slide of slides) observer.observe(slide);
    }
    if (typeof window !== 'undefined' && window.addEventListener)
      window.addEventListener('resize', () => {gallery.scrollLeft = current * gallery.clientWidth;syncHeight();});
    activate(0);
  } else {
    // Lightweight pre-P1 DOM fixtures retain the original tab behavior.
    for (const button of pages) button.addEventListener("click", () => {
      for (const page of pages) {
        const active = button === page;
        root.querySelector("#" + page.getAttribute("aria-controls")).hidden = !active;
        page.setAttribute("aria-pressed", String(active));
      }
      const counter = root.querySelector('#evidence-page-number');
      if (counter) counter.textContent = `${pages.indexOf(button) + 1} / ${pages.length}`;
    });
  }
  for (const toggle of root.querySelectorAll("[data-layer]")) {
    toggle.addEventListener("change", () => {
      toggle.closest("[data-evidence]").classList.toggle(`hide-${toggle.dataset.layer}`, !toggle.checked);
    });
  }
  for (const label of root.querySelectorAll('[data-select-pair]')) {
    function selectPair() {
      const panel=label.closest('[data-evidence]');
      for(const detail of panel.querySelectorAll('[data-pair]')) detail.open=detail.dataset.pair===label.dataset.selectPair;
      for(const item of panel.querySelectorAll('[data-select-pair]')) item.setAttribute('aria-pressed',String(item===label));
    }
    label.addEventListener('click',selectPair);
    label.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectPair();}});
    // A clickable SPW label must not start the SVG's drag-to-pan gesture.
    label.addEventListener('pointerdown',event=>event.stopPropagation());
  }
  // Single Pointing-style Setup disclosure. SVG <g hidden> is unreliable in
  // Safari; use display:none and resize the viewBox/clip on every transition.
  // Labels stay outside the pan/zoom geometry layer.
  for (const toggle of root.querySelectorAll('[data-toggle-setup]')) {
    const svg = toggle.closest('svg');
    const detailLabels = svg?.querySelector('[data-setup-details]');
    if (!svg || !detailLabels) continue;
    const geometry = [...svg.querySelectorAll('[data-frequency-detail]')];
    const title = toggle.querySelector('[data-setup-title]');
    const fullHeight = Number(svg.dataset.expandedHeight);
    const compactHeight = Number(svg.dataset.collapsedHeight);
    if (!(fullHeight > compactHeight && compactHeight >= 100)) continue;
    function showSetup(expanded) {
      toggle.setAttribute('aria-expanded', String(expanded));
      toggle.setAttribute('aria-label', `${expanded ? 'Collapse' : 'Expand'} Setup and its SPW comparisons`);
      if (title) title.textContent = `${expanded ? '▾' : '▸'} Setup · ${toggle.dataset.componentCount} components`;
      detailLabels.style.display = expanded ? '' : 'none';
      for (const node of geometry) node.style.display = expanded ? '' : 'none';
      const height = expanded ? fullHeight : compactHeight;
      svg.setAttribute('viewBox', `0 0 600 ${height}`);
      for (const grid of svg.querySelectorAll('.plot-grid')) grid.setAttribute('y2', String(height - 45));
      svg.querySelector('[data-frequency-axis-label]')?.setAttribute('y', String(height - 12));
      svg.querySelector('clipPath rect')?.setAttribute('height', String(height - 80));
    }
    const flip = () => showSetup(toggle.getAttribute('aria-expanded') !== 'true');
    toggle.addEventListener('pointerdown', event => event.stopPropagation());
    toggle.addEventListener('click', event => {event.stopPropagation(); flip();});
    toggle.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); flip();}
    });
    // SSR includes all science evidence; JS starts collapsed as Single Pointing does.
    showSetup(false);
  }
  // Fixed plot bounds: transform data only and recompute tick labels.
  for (const [index, svg] of [...root.querySelectorAll('#charts svg')].entries()) {
    const spatial = svg.viewBox.baseVal.width === 490;
    if (![490, 600].includes(svg.viewBox.baseVal.width)) continue;
    const NS = 'http://www.w3.org/2000/svg';
    const box = spatial ? {x:80,y:45,w:330,h:330,cx:245,cy:210} :
      {x:135,y:35,w:430,h:svg.viewBox.baseVal.height-80,cx:350,cy:0};
    const toolbar = document.createElement('div');
    toolbar.className = 'chart-tools mosaic-plot-tools';
    toolbar.setAttribute('role', 'group');
    toolbar.setAttribute('aria-label', spatial ? 'Position zoom' : 'Frequency zoom');
    const owner = svg.closest('[data-evidence]');
    const header = root.querySelector(spatial ? '#mosaic-position-tools' : '#mosaic-frequency-tools');
    if (header && owner) {
      toolbar.dataset.evidence = owner.dataset.evidence;
      toolbar.setAttribute('data-plot-controls', '');
      header.append(toolbar);
      toolbar.hidden = toolbar.dataset.evidence !== selected;
    } else {
      // Keep preview pages and lightweight DOM fixtures backward compatible.
      svg.before(toolbar);
    }
    const defs = document.createElementNS(NS, 'defs');
    const clip = document.createElementNS(NS, 'clipPath');
    clip.id = `mosaic-plot-clip-${index}`;
    const rect = document.createElementNS(NS, 'rect');
    for (const key of ['x','y']) rect.setAttribute(key, box[key]);
    rect.setAttribute('width', box.w); rect.setAttribute('height',box.h);
    clip.append(rect); defs.append(clip); svg.prepend(defs);
    const clipped = document.createElementNS(NS, 'g');
    clipped.setAttribute('clip-path', `url(#${clip.id})`);
    const layer = document.createElementNS(NS, 'g'); clipped.append(layer);
    const selector = spatial ? ':scope > g' : svg.hasAttribute('data-mosaic-frequency')
      ? 'g.mosaic-setup-summary-interval, g.mosaic-setup-interval, g.candidate-spectrum, circle.frequency, path.proposed-marker'
      : ':scope > g, :scope > path, :scope > circle, :scope > .requested-guide, :scope > .axis';
    for (const element of [...svg.querySelectorAll(selector)]) layer.append(element);
    svg.append(clipped);
    const ticks = [...svg.querySelectorAll(':scope > text')].filter(t =>
      t.textContent.trim() !== '' && Number.isFinite(Number(t.textContent))).map(t => ({
        node:t, value:Number(t.dataset.value ?? t.textContent), vertical:spatial && Number(t.getAttribute('x'))===72,
        pixel:Number(t.getAttribute(spatial && Number(t.getAttribute('x'))===72 ? 'y':'x'))-(spatial && Number(t.getAttribute('x'))===72 ? 4:0)
      }));
    const slopes = {};
    for (const vertical of [false,true]) {
      const group = ticks.filter(t=>t.vertical===vertical);
      const a=group[0], b=group.find(t=>t.pixel!==a?.pixel);
      if (a && b) slopes[vertical]=(b.value-a.value)/(b.pixel-a.pixel);
    }
    const markers = [...layer.querySelectorAll('path.pointing')].map(node=>({node,d:node.getAttribute('d')}));
    let k=1, tx=0, ty=0;
    function draw() {
      layer.setAttribute('transform', `translate(${box.cx+tx} ${spatial?box.cy+ty:0}) scale(${k} ${spatial?k:1}) translate(${-box.cx} ${spatial?-box.cy:0})`);
      for (const tick of ticks) {
        const center=tick.vertical?box.cy:box.cx, shift=tick.vertical?ty:tx;
        const original=center+(tick.pixel-center-shift)/k;
        tick.node.textContent=Number((tick.value+(original-tick.pixel)*slopes[tick.vertical]).toPrecision(5)).toString();
      }
      for (const marker of markers) {
        let axis=0;
        marker.node.setAttribute('d',marker.d.replace(/-?\d+(?:\.\d+)?/g,v=>String(Number(v)/((axis++%2===0||spatial)?k:1))));
      }
      for (const label of layer.querySelectorAll('text')) label.style.fontSize=`${10/k}px`;
      controls.in.disabled=k>=16; controls.out.disabled=k<=.5;
    }
    function zoom(factor, point={x:box.cx,y:box.cy}) {
      const next=Math.max(.5,Math.min(16,k*factor)), ratio=next/k;
      tx=point.x-box.cx-(point.x-box.cx-tx)*ratio;
      if(spatial) ty=point.y-box.cy-(point.y-box.cy-ty)*ratio;
      k=next;draw();
    }
    const controls={};
    for (const [action,label] of [['in','+'],['out','−'],['reset','Reset']]) {
      const button=document.createElement('button');button.type='button';button.textContent=label;
      button.setAttribute('aria-label',action==='reset'?'Reset chart zoom':`Zoom ${action}`);
      button.addEventListener('click',()=>{if(action==='reset'){k=1;tx=ty=0;draw();}else zoom(action==='in'?1.6:1/1.6);});
      controls[action]=button;toolbar.append(button);
    }
    const hint=document.createElement('span');hint.textContent='Drag to pan · Ctrl/⌘ + scroll to zoom';toolbar.append(hint);
    svg.setAttribute('tabindex','0');svg.classList.add('mosaic-interactive-chart');
    function point(event) { const p=new DOMPoint(event.clientX,event.clientY);return p.matrixTransform(svg.getScreenCTM().inverse()); }
    function inside(p){
      const h = !spatial && svg.hasAttribute('data-mosaic-frequency') ? svg.viewBox.baseVal.height-80 : box.h;
      return p.x>=box.x&&p.x<=box.x+box.w&&p.y>=box.y&&p.y<=box.y+h;
    }
    let drag=null;
    svg.addEventListener('pointerdown',event=>{const p=point(event);if(event.button!==0||!inside(p))return;drag={p,tx,ty};svg.setPointerCapture(event.pointerId);svg.classList.add('is-panning');});
    svg.addEventListener('pointermove',event=>{if(!drag)return;const p=point(event);tx=drag.tx+p.x-drag.p.x;if(spatial)ty=drag.ty+p.y-drag.p.y;draw();});
    function end(event){if(event.type==='pointercancel'&&drag){tx=drag.tx;ty=drag.ty;draw();}drag=null;svg.classList.remove('is-panning');if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);}
    svg.addEventListener('pointerup',end);svg.addEventListener('pointercancel',end);
    svg.addEventListener('wheel',event=>{const p=point(event);if(!(event.ctrlKey||event.metaKey)||!inside(p))return;event.preventDefault();zoom(event.deltaY<0?1.15:1/1.15,p);},{passive:false});
    svg.addEventListener('keydown',event=>{
      if(['+','=','-','Home'].includes(event.key)){event.preventDefault();if(event.key==='Home'){k=1;tx=ty=0;draw();}else zoom(event.key==='-'?1/1.6:1.6);}
      const pan={ArrowLeft:[24,0],ArrowRight:[-24,0],ArrowUp:[0,24],ArrowDown:[0,-24]}[event.key];
      if(pan&&(spatial||!pan[1])){event.preventDefault();tx+=pan[0];ty+=pan[1];draw();}
    });
    draw();
  }
  render();
})();
