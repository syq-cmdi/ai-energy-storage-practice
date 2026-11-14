'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),math=require('../demo/ch05/math.js');
const box={window:{}};vm.runInNewContext(fs.readFileSync(path.join(root,'demo/ch05/data.js'),'utf8'),box);
const data=box.window.CH05_DATA;
const pick=(scenario='hot',volume=20,policy='mpc',horizon=24,bias=0,mode='normal')=>math.choose(data,{scenario,volume,policy,horizon,bias,mode});
test('113 unique trajectories and all 105 capacity/strategy selections',()=>{
 assert.equal(data.runs.length,113);assert.equal(new Set(data.runs.map(r=>r.id)).size,113);
 for(const s of Object.keys(data.scenarios))for(const v of [0,10,20,30,40,50,60])for(const p of ['rule','perfect','mpc']){
  const r=pick(s,v,p);assert.equal(r.load.length,24);assert.equal(r.energy.length,25);
 }
});
test('all nine forecast choices preserve the same actual load',()=>{
 const base=pick('heatwave');
 for(const h of [6,12,24])for(const b of [-.15,0,.15]){
  const r=pick('ignored',0,'rule',h,b,'forecast');assert.deepEqual(r.load,base.load);
  assert.equal(r.horizon,h);assert.equal(r.bias,b);assert.equal(r.volume,20);
 }
 assert.ok(pick('',0,'',6,0,'forecast').metrics.unmet_kwh>base.metrics.unmet_kwh+24);
});
test('browser recomputation agrees with Python energy, costs and service',()=>{
 for(const r of data.runs){const m=math.metrics(r);
  assert.ok(Math.abs(m.cost-r.metrics.electricity_cost_cny)<2e-5,r.id);
  assert.ok(Math.abs(m.unmet-r.metrics.unmet_kwh)<2e-5,r.id);
  assert.ok(m.balance<2e-6,r.id);assert.ok(m.flow<=r.config.loop_flow+2e-6,r.id);
 }
});
test('capacity-free and disqualified storage keep charging and discharging at zero',()=>{
 for(const r of data.runs.filter(r=>r.volume===0||r.scenario==='quality')){
  for(const arr of [r.c,r.d,r.energy])assert.ok(arr.every(v=>Math.abs(v)<2e-6),r.id);
 }
 assert.ok(pick('quality').metrics.unmet_kwh>31);
 assert.equal(pick('quality').metrics.max_supply_c,6);
});
test('CSV contains complete numeric replay with independently balanced load',()=>{
 for(const r of data.runs){const rows=math.csv(r).split('\n');assert.equal(rows.length,25);
  assert.equal(rows[0].split(',').length,12);
  for(const row of rows.slice(1)){const v=row.split(',');assert.equal(v.length,12);
   assert.ok(Math.abs(+v[2]-v[3]-v[5]-v[6])<2e-6);
  }
 }
});
test('published plans start with the known current request and inventory',()=>{
 for(const r of data.runs.filter(r=>r.policy==='mpc'))for(const p of r.plans){
  assert.equal(p.forecast[0],r.load[p.k]);assert.equal(p.energy[0],r.energy[p.k]);
  assert.equal(p.forecast.length,Math.min(r.horizon,24-p.k));
  assert.ok(Math.abs(p.energy.at(-1))<2e-6);
 }
});
test('annual scenario weights and capacity results retain service limits',()=>{
 assert.equal(Object.values(data.annual.weights).reduce((a,b)=>a+b,0),365);
 const rows=data.annual.rows.filter(r=>r.policy==='mpc');
 const best=rows.reduce((a,b)=>a.weighted_total_cost_cny<b.weighted_total_cost_cny?a:b);
 assert.equal(best.volume,40);assert.ok(best.weighted_unmet_kwh>218);
});
test('standalone HTML embeds sources without network dependencies',()=>{
 const html=fs.readFileSync(path.join(root,'demo/ch05/教学演示.html'),'utf8');
 assert.ok(html.includes('window.CH05_DATA='));assert.ok(html.includes('function choose('));
 assert.ok(!/<script[^>]+src=|<link[^>]+href=|fetch\(|https?:\/\//i.test(html.replaceAll('http://www.w3.org/2000/svg','')));
 assert.ok(html.includes('储罐容积 / m³'));
});
test('invalid combinations fail explicitly instead of changing the requested case',()=>{
 assert.throws(()=>pick('hot',11,'mpc'),/Scenario not found/);
});
