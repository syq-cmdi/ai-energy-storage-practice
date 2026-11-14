'use strict';
const $=id=>document.getElementById(id), data=window.CH04_DATA;
let exactParams=true,current,result,timer=null;
const names={test_nominal:'常规工况',test_loss:'附加散热工况',test_bias:'传感器偏移工况',test_hot:'高温外推工况'};
const lessons={test_nominal:'先选择机理模型，再切换到灰箱模型。记录两种开环误差：在没有附加散热的工况中，训练得到的修正会带来负迁移。',test_loss:'把热容量调高，观察开环曲线响应变慢；再载入辨识参数，比较机理模型与灰箱模型。辨识值只对已覆盖的边界有解释力。',test_bias:'观察 6 h 后创新的持续偏移。把 Q 从 0 改为 0.01，滤波会更快追随传感器，系统偏差也可能传入状态估计。区间变窄不保证误差变小。',test_hot:'高温工况具有开发数据未覆盖的附加散热。观察初段误差和能量累计偏差，说明为什么外推需要新数据与重新检验。'};
function parameters(){const model=$('model').value;return {c:exactParams?data.summary.physical_fit.capacity:+$('capacity').value,ua:exactParams?data.summary.physical_fit.ua:+$('ua').value/1000,beta:model==='gray'?data.summary.beta_fitted:0,q:+$('q').value,r:(+$('noise').value)**2,sigma:+$('noise').value,bias:+$('bias').value};}
function reset(){pause();exactParams=true;$('capacity').value=data.summary.physical_fit.capacity;$('ua').value=data.summary.physical_fit.ua*1000;$('noise').value=.25;$('bias').value=$('scenario').value==='test_bias'?1.2:0;$('q').value=data.summary.chosen_q[$('model').value];$('time').value=180;update();}
function update(){current=data.episodes.find(e=>e.id===$('scenario').value);const p=parameters();result=WH1.calculate(current,p);$('time').max=current.truth.length-1;if(+$('time').value>+$('time').max)$('time').value=$('time').max;
  $('capacityVal').textContent=p.c.toFixed(exactParams?3:0)+' kJ/K';$('uaVal').textContent=(p.ua*1000).toFixed(exactParams?4:1)+' W/K';$('noiseVal').textContent=p.sigma.toFixed(2)+' K';$('biasVal').textContent=(p.bias>=0?'+':'')+p.bias.toFixed(1)+' K';
  $('caseTitle').textContent=names[current.id];$('scenarioNote').textContent=current.id==='test_bias'?'与附加散热测试共用同一真实轨迹和噪声，只改变测量偏移。':current.id==='test_hot'?'初温 78 ℃；超过 65 ℃ 时加入未建模散热项。':'每条工况作为完整轨迹保存，开发阶段不读取测试参考温度。';
  $('modelInfo').textContent=`${p.beta?'灰箱 RK4 + 扩展卡尔曼滤波':'解析机理模型 + 卡尔曼滤波'} · β = ${p.beta.toExponential(3)} kW/K² · Δt = 120 s`;
  $('rmseOpen').textContent=result.openMetrics.rmse.toFixed(3)+' K';$('rmseEst').textContent=result.metrics.rmse.toFixed(3)+' K';$('coverage').textContent=result.coverage.toFixed(1)+' %';$('lesson').textContent=lessons[current.id];draw();
}
function poly(values,x,y,start=0){return values.map((v,i)=>`${i?'L':'M'}${x(i+start).toFixed(2)},${y(v).toFixed(2)}`).join(' ');}
function chart(id,series,opts={}){
  const el=$(id),large=id==='temperatureChart',W=large?900:440,H=large?360:250,m={l:57,r:18,t:22,b:42},n=current.truth.length;
  const start=opts.start||0;let all=series.flatMap(s=>s.values.slice(start));if(opts.band){all=all.concat(opts.band.low.slice(start),opts.band.high.slice(start));}let lo=Math.min(...all),hi=Math.max(...all);if(hi-lo<.01){lo-=.05;hi+=.05;}let pad=(hi-lo)*.13;lo-=pad;hi+=pad;
  const x=i=>m.l+i/(n-1)*(W-m.l-m.r),y=v=>H-m.b-(v-lo)/(hi-lo)*(H-m.t-m.b);
  let h=`<rect width="${W}" height="${H}" fill="white"/><text x="${m.l}" y="12" fill="#627787" font-size="11">${opts.unit||'温度 / ℃'}</text>`;
  for(let j=0;j<5;j++){const v=lo+(hi-lo)*j/4,py=y(v);h+=`<line x1="${m.l}" x2="${W-m.r}" y1="${py}" y2="${py}" stroke="#e3ebef"/><text x="${m.l-9}" y="${py+4}" text-anchor="end" font-size="11" fill="#627787">${v.toFixed(Math.abs(hi-lo)<3?2:1)}</text>`;}
  for(let j=0;j<5;j++){const i=(n-1)*j/4;h+=`<text x="${x(i)}" y="${H-21}" text-anchor="middle" font-size="11" fill="#627787">${(i/30).toFixed(1)}</text>`;}
  h+=`<text x="${W-m.r}" y="${H-3}" text-anchor="end" font-size="11" fill="#627787">时间 / h</text>`;
  if(opts.band){let points=opts.band.high.slice(start).map((v,i)=>`${x(i+start)},${y(v)}`).concat(opts.band.low.slice(start).map((v,i)=>`${x(i+start)},${y(v)}`).reverse());h+=`<polygon points="${points.join(' ')}" fill="#087f8c" opacity=".14"/>`;}
  for(const s of series){if(s.points){h+=s.values.map((v,i)=>(i%2||i<start)?'':`<circle cx="${x(i)}" cy="${y(v)}" r="1.6" fill="${s.color}" opacity=".5"/>`).join('');}else{h+=`<path d="${poly(s.values.slice(start),x,y,start)}" fill="none" stroke="${s.color}" stroke-width="${s.width||1.8}" stroke-linejoin="round"/>`;}}
  const k=+$('time').value;h+=`<line x1="${x(k)}" x2="${x(k)}" y1="${m.t}" y2="${H-m.b}" stroke="#7954a1" stroke-width="1.2" stroke-dasharray="4 4"/>`;
  el.innerHTML=h;
}
function draw(){const show=$('truth').checked,k=+$('time').value,series=[{values:result.y,color:'#c17d1f',points:true},{values:result.open,color:'#3268b2'},{values:result.estimate,color:'#087f8c',width:2.2}];if(show)series.unshift({values:current.truth,color:'#183448',width:1.4});chart('temperatureChart',series);
  const err=result.estimate.map((v,i)=>v-current.truth[i]),sd=result.variance.map(v=>1.96*Math.sqrt(v));chart('errorChart',[{values:err,color:'#087f8c'}],{unit:'估计−参考 / K（20 min 后）',start:10,band:{low:sd.map(x=>-x),high:sd}});chart('energyChart',[{values:result.energy.map(v=>v/1000),color:'#3268b2'}],{unit:'开环累计偏差 / MJ'});
  $('timeVal').textContent=(k/30).toFixed(2)+' h';$('tankTemp').textContent=result.estimate[k].toFixed(2)+' ℃';$('prior').textContent=result.prior[k].toFixed(3)+' ℃';$('innovation').textContent=(result.innovation[k]>=0?'+':'')+result.innovation[k].toFixed(3)+' K';$('gain').textContent='增益 K = '+result.gain[k].toFixed(5);$('posterior').textContent=result.estimate[k].toFixed(3)+' ℃';$('uncertainty').textContent='后验标准差 '+Math.sqrt(result.variance[k]).toFixed(4)+' K';
}
function pause(){if(timer)clearInterval(timer);timer=null;$('play').textContent='播放状态更新';}
function download(content,type,name){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);$('status').textContent='已生成 '+name;}
$('scenario').addEventListener('change',reset);$('model').addEventListener('change',()=>{$('q').value=data.summary.chosen_q[$('model').value];update();});
for(const id of ['capacity','ua'])$(id).addEventListener('input',()=>{exactParams=false;update();});
for(const id of ['noise','bias','q'])$(id).addEventListener('input',update);
$('truth').addEventListener('change',draw);$('time').addEventListener('input',draw);$('reset').addEventListener('click',reset);
$('calibrate').addEventListener('click',()=>{exactParams=true;$('capacity').value=data.summary.physical_fit.capacity;$('ua').value=data.summary.physical_fit.ua*1000;update();$('status').textContent='已载入离线辨识值（保留完整精度）';});
$('play').addEventListener('click',()=>{if(timer){pause();return;}if(+$('time').value>=+$('time').max)$('time').value=1;$('play').textContent='暂停回放';timer=setInterval(()=>{let k=+$('time').value+3;$('time').value=Math.min(k,+$('time').max);draw();if(k>=+$('time').max)pause();},180);});
$('exportCsv').addEventListener('click',()=>download(WH1.csv(current,result),'text/csv;charset=utf-8','W-H1_'+current.id+'.csv'));
$('exportSvg').addEventListener('click',()=>{const svg=$('temperatureChart').cloneNode(true);svg.setAttribute('xmlns','http://www.w3.org/2000/svg');svg.setAttribute('font-family','Arial, Microsoft YaHei, sans-serif');download(new XMLSerializer().serializeToString(svg),'image/svg+xml','W-H1_'+current.id+'.svg');});
reset();
