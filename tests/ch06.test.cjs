'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),M=require('../demo/ch06/math.js'),ctx={window:{}};vm.runInNewContext(fs.readFileSync(path.join(root,'demo/ch06/data.js'),'utf8'),ctx);const D=ctx.window.CH06_DATA;
const pick=o=>M.choose(D,{mode:'scenario',scenario:'typical',policy:'full',head:200,ramp:65,grid:20,terminal:'closed',...o});
test('all 33 stored trajectories have unique identities',()=>{assert.equal(D.runs.length,33);assert.equal(new Set(D.runs.map(r=>r.id)).size,33);});
test('all four laboratory modes resolve every supported setting',()=>{
 for(const scenario of Object.keys(D.names))for(const policy of Object.keys(D.policies))assert.equal(pick({scenario,policy}).scenario,scenario);
 for(const head of [180,200,220])for(const ramp of [40,65,100])assert.equal(pick({mode:'sensitivity',head,ramp}).config.ramp,ramp);
 for(const grid of [20,10,5])for(const ramp of [40,65])assert.equal(pick({mode:'grid',grid,ramp}).config.flow_step,grid);
 assert.equal(pick({mode:'terminal',terminal:'free'}).group,'free_terminal');
});
test('browser recomputes water, energy, cash and physical violations',()=>{for(const r of D.runs){const a=M.audit(r);assert.ok(a.mass<1e-6,r.id);assert.ok(a.residual<1e-5,r.id);assert.ok(Math.abs(a.cash-r.metrics.profit_cny)<.002,r.id);assert.equal(a.violations,r.metrics.violation_count,r.id);}});
test('small-action grid recovers startup under a 40 MW change limit',()=>{const coarse=pick({mode:'grid',grid:20,ramp:40}),fine=pick({mode:'grid',grid:10,ramp:40});assert.equal(coarse.metrics.profit_cny,0);assert.ok(fine.metrics.profit_cny>190000);assert.equal(fine.metrics.violation_count,0);});
test('constant-model violation and identical typical schedules both remain visible',()=>{
 assert.equal(pick({scenario:'solar',policy:'fixed'}).metrics.violation_count,1);
 assert.deepEqual(pick({policy:'fixed'}).flow,pick({policy:'full'}).flow);
 assert.equal(pick({scenario:'solar',policy:'full'}).metrics.violation_count,0);
});
test('free terminal inventory is reported separately from cycle efficiency',()=>{const r=pick({mode:'terminal',terminal:'free'});assert.equal(r.metrics.round_trip_efficiency,null);assert.ok(r.metrics.energy_output_input_ratio>1);assert.ok(r.metrics.delta_storage_mwh<0);assert.ok(Math.abs(r.metrics.pump_energy_mwh-r.metrics.generation_energy_mwh-r.metrics.delta_storage_mwh-r.metrics.hydraulic_loss_mwh-r.metrics.conversion_loss_mwh)<1e-5);});
test('CSV exports 24 complete physical records',()=>{for(const r of D.runs){const rows=M.csv(r).split('\n');assert.equal(rows.length,25);for(const row of rows.slice(1)){const v=row.split(',');assert.equal(v.length,11);assert.ok(Math.abs(+v[6]-v[5]-3600*v[3]*r.config.dt)<1e-6);}}});
test('self-contained HTML embeds sources without external requests',()=>{const h=fs.readFileSync(path.join(root,'demo/ch06/教学演示.html'),'utf8').replaceAll('http://www.w3.org/2000/svg','');assert.ok(h.includes('window.CH06_DATA='));assert.ok(!/<script[^>]+src=|<link[^>]+href=|fetch\(|https?:\/\//i.test(h));});
test('unsupported configuration fails explicitly',()=>{assert.throws(()=>pick({mode:'grid',grid:10,ramp:100}),/Scenario not found/);});
