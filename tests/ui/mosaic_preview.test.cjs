const assert=require('node:assert/strict');
const {sky,project,radius,destination}=require('../../src/alma_duplicate/ui/static/mosaic-preview.js');
assert.equal(sky('460','GHz','REST','1'),230);
assert.equal(sky('230000','MHz','SKY','99'),230);
assert.equal(sky('230','GHz','REST',''),null);
assert.equal(sky('230','GHz','REST','0'),230);
assert.equal(sky('230','GHz','REST','-1'),null);
assert.equal(sky('0','GHz','SKY',''),null);
assert.ok(Math.abs(radius(230,7)/radius(230,12)-12/7)<1e-12);
assert.ok(Math.abs(project(.001,0,359.999,0)[0]+7.2)<1e-6);
for(const centre of [[0,89.99],[359.999,-25],[180,-89.99]]){
 for(let j=0;j<8;j++){
 const p=project(...destination(...centre,30,j*Math.PI/4),...centre);
 assert.ok(Math.abs(Math.hypot(...p)-30)<1e-4);
 }
}
assert.equal(project(180,0,0,0),null);
console.log('Geometry and frequency checks passed');
