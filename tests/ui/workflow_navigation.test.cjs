const {test} = require('node:test');
const assert = require('node:assert/strict');
const {maybeNavigateToMosaic, maybeNavigateToSingle, confirmLeavingWorkflow} = require('../../src/alma_duplicate/ui/static/workflow-navigation.js');

function form({workflow='single', kind='FIXED', entries={}, rows=false}={}) {
  const controls = {target_kind:{value:kind}, ...Object.fromEntries(
    Object.entries(entries).map(([name,value]) => [name, {value}]))};
  return {dataset:{workflow,mosaicUrl:'/proposed/mosaic',singleUrl:'/proposed'},
    elements:{namedItem:name=>controls[name] || null},
    querySelector:()=>rows ? {} : null};
}

test('blank Single Pointing Mosaic selection navigates without source mutation', () => {
  const f=form(), field={name:'geometry',value:'MOSAIC'};
  let url='', confirms=0;
  assert.equal(maybeNavigateToMosaic(f,field,value=>{url=value;},()=>{confirms++;return true;}),true);
  assert.equal(url,'/proposed/mosaic');assert.equal(confirms,0);
});

test('populated Single Pointing requires confirmation and cancel restores geometry', () => {
  const f=form({entries:{ra:'18:33:39.920',aggregate:'0.01'}});
  const field={name:'geometry',value:'MOSAIC'};
  let redirects=0, prompts=0;
  assert.equal(maybeNavigateToMosaic(f,field,()=>redirects++,()=>{prompts++;return false;}),true);
  assert.equal(field.value,'SINGLE_POINTING');assert.equal(redirects,0);assert.equal(prompts,1);
});

test('confirmed switch starts fresh Mosaic input', () => {
  const f=form({rows:true}), field={name:'geometry',value:'MOSAIC'};
  let url='';
  assert.equal(maybeNavigateToMosaic(f,field,value=>{url=value;},()=>true),true);
  assert.equal(url,'/proposed/mosaic');
});

test('moving and solar targets keep existing server scope handling', () => {
  for(const kind of ['MOVING','SUN']) {
    const field={name:'geometry',value:'MOSAIC'};
    assert.equal(maybeNavigateToMosaic(form({kind}),field,()=>assert.fail('redirected'),()=>true),false);
  }
});

test('dedicated Mosaic and unrelated form controls do not navigate', () => {
  assert.equal(maybeNavigateToMosaic(form({workflow:'mosaic'}),{name:'geometry',value:'MOSAIC'},
    ()=>assert.fail('redirected'),()=>true),false);
  assert.equal(maybeNavigateToMosaic(form(),{name:'sources',value:'QUEUE'},
    ()=>assert.fail('redirected'),()=>true),false);
});

test('tab switch also prompts when input exists', () => {
  let prompts=0;
  const populated=form({entries:{target_name:'My target'}});
  assert.equal(confirmLeavingWorkflow(populated,()=>{prompts++;return false;}),false);
  assert.equal(prompts,1);
  assert.equal(confirmLeavingWorkflow(form(),()=>assert.fail('unexpected prompt')),true);
});

test('Mosaic geometry selector navigates back to Single Pointing', () => {
  const f=form({workflow:'mosaic'}), field={name:'geometry',value:'SINGLE_POINTING'};
  let destination='';
  assert.equal(maybeNavigateToSingle(f,field,url=>{destination=url;},()=>assert.fail('unexpected prompt')),true);
  assert.equal(destination,'/proposed');
});

test('Mosaic switch cancellation retains original geometry and uploaded OT evidence', () => {
  const f=form({workflow:'mosaic',entries:{mosaic_upload_token:'retained-token'}});
  const field={name:'geometry',value:'SINGLE_POINTING'};
  let redirects=0, prompts=0;
  assert.equal(maybeNavigateToSingle(f,field,()=>redirects++,()=>{prompts++;return false;}),true);
  assert.equal(field.value,'MOSAIC');
  assert.equal(prompts,1);
  assert.equal(redirects,0);
});

test('Mosaic switch confirmation navigates to a fresh Single Pointing form', () => {
  const f=form({workflow:'mosaic',entries:{mosaic_upload_token:'retained-token'}});
  let destination='';
  assert.equal(maybeNavigateToSingle(f,{name:'geometry',value:'SINGLE_POINTING'},
    url=>{destination=url;},()=>true),true);
  assert.equal(destination,'/proposed');
});

test('Single Pointing and unrelated selections do not trigger reverse navigation', () => {
  assert.equal(maybeNavigateToSingle(form(),{name:'geometry',value:'SINGLE_POINTING'},
    ()=>assert.fail('redirected'),()=>true),false);
  assert.equal(maybeNavigateToSingle(form({workflow:'mosaic'}),{name:'sources',value:'ARCHIVE'},
    ()=>assert.fail('redirected'),()=>true),false);
});
