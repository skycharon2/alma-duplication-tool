'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,
  '../../src/alma_duplicate/ui/static/mosaic-visualization.js'),'utf8');
const start=source.indexOf('  const pages = [...root.querySelectorAll(".evidence-pager button")];');
const end=source.indexOf('  for (const toggle of root.querySelectorAll("[data-layer]"))',start);
assert.ok(start>=0 && end>start,'Production pager code must be present');
const pagerSource=source.slice(start,end);

function setup() {
  function element() {
    const handlers={};
    return {attrs:{},hidden:false,inert:false,textContent:'',style:{},
      addEventListener(type,fn){(handlers[type] ||= []).push(fn);},
      emit(type,event={}){for(const fn of handlers[type]||[]) fn({target:this,preventDefault(){this.prevented=true;},...event});},
      setAttribute(key,val){this.attrs[key]=String(val);},
      getAttribute(key){return this.attrs[key]??null;},
      getBoundingClientRect(){return {height:this.height||400};}};
  }
  const charts=element(),sky=element(),counter=element(),gallery=element();
  charts.height=840;sky.height=620;gallery.clientWidth=1000;gallery.scrollLeft=0;
  gallery.scrollTo=function({left}){this.scrollLeft=left;this.emit('scroll');};
  const first=element(),second=element();
  first.setAttribute('aria-controls','charts');second.setAttribute('aria-controls','sky');
  const tabs=[first,second];
  const nodes={'#mosaic-evidence-gallery':gallery,'#charts':charts,'#sky':sky,
    '#evidence-page-number':counter};
  const root={querySelectorAll:key=>key==='.evidence-pager button'?tabs:[],
    querySelector:key=>nodes[key]||null};
  vm.runInNewContext(`(()=>{${pagerSource}})();`,{root});
  return {charts,sky,counter,gallery,tabs};
}

test('Mosaic Sky Preview shares a two-slide native horizontally swipeable gallery',()=>{
  const h=setup();
  assert.equal(h.charts.hidden,false);
  assert.equal(h.sky.hidden,false,'inactive slide must remain in scroll layout');
  assert.equal(h.sky.inert,true);
  assert.equal(h.counter.textContent,'1 / 2');
  assert.equal(h.gallery.style.height,'840px');
  h.tabs[1].emit('click');
  assert.equal(h.gallery.scrollLeft,1000);
  assert.equal(h.tabs[1].attrs['aria-pressed'],'true');
  assert.equal(h.charts.inert,true);
  assert.equal(h.sky.inert,false);
  assert.equal(h.gallery.style.height,'620px');
  h.gallery.scrollLeft=0;h.gallery.emit('scroll');
  assert.equal(h.counter.textContent,'1 / 2');
  assert.equal(h.charts.inert,false);
  assert.equal(h.sky.inert,true);
});

test('gallery keyboard navigation offers an alternative to swipe gestures',()=>{
  const h=setup();
  let prevented=false;
  h.gallery.emit('keydown',{key:'ArrowRight',preventDefault(){prevented=true;}});
  assert.equal(prevented,true);
  assert.equal(h.counter.textContent,'2 / 2');
  h.gallery.emit('keydown',{key:'ArrowLeft'});
  assert.equal(h.counter.textContent,'1 / 2');
});
