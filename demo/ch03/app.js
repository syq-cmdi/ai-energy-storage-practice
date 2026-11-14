'use strict';
const $=id=>document.getElementById(id),D=window.CH03_DATA,M=window.Ch3Math;
const names={normal:'正常运行',load_step:'正常负载突变',voltage_bias:'电压通道偏移',resistance_rise:'内阻代理异常',cooling_loss:'温升代理异常',missing_data:'数据缺失',novel_dual:'未见过的组合异常'};
const methodNames={rule:'稳健残差规则',logistic:'逻辑回归',isolation:'孤立森林'};
let timer=null,currentRows=[],currentEvent=null,lastUrl=null;
function unpack(session){return D.cases[session].map(a=>Object.fromEntries(D.columns.map((k,i)=>[k,a[i]])));}
function defaults(){const p=D.selected[$('method').value],method=$('method').value;$('threshold').min=method==='rule'?1:.1;$('threshold').max=method==='rule'?12:1;$('threshold').step=method==='rule'?.25:.01;$('threshold').value=p.threshold;$('persistence').value=p.persistence;render();}
function esc(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function svgChart(rows,t,event,threshold,method){
 const W=900,H=520,L=74,R=27,plotW=W-L-R,X=x=>L+x/179*plotW,C={teal:'#087f8c',blue:'#3466b0',purple:'#7954a1',amber:'#c17d1f',gray:'#647a89'};
 let s=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="当前回放时刻的残差、分值和告警"><rect width="${W}" height="${H}" fill="white"/><g font-family="PingFang SC, Microsoft YaHei, sans-serif" font-size="12" fill="#4c6577">`;
 const bands=(top,height)=>{let z='';if(event&&$('truth').checked)z+=`<rect x="${X(event.start_min)}" y="${top}" width="${X(event.end_min)-X(event.start_min)}" height="${height}" fill="${C.amber}" opacity=".09"/>`;let start=null;rows.forEach((r,i)=>{if(!r.valid&&start===null)start=i;if(start!==null&&(r.valid||i===rows.length-1)){const end=r.valid?i:i+1;z+=`<rect x="${X(start)}" y="${top}" width="${(end-start)/179*plotW}" height="${height}" fill="#bbc7ce" opacity=".20"/>`;start=null;}});return z;};
 function panel(top,height,title,curves,lo,hi,thresholdLine){
  let z=bands(top,height);const Y=v=>top+height-(v-lo)/(hi-lo)*height;
  for(let i=0;i<3;i++){const v=lo+(hi-lo)*i/2;z+=`<line x1="${L}" x2="${W-R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#dce6ed"/><text x="${L-10}" y="${Y(v)+4}" text-anchor="end">${v.toFixed(hi-lo>10?0:2)}</text>`;}
  z+=`<text x="${L}" y="${top-10}" font-weight="600" fill="#19364a">${esc(title)}</text>`;
  if(thresholdLine!==undefined)z+=`<line x1="${L}" x2="${W-R}" y1="${Y(thresholdLine)}" y2="${Y(thresholdLine)}" stroke="${C.amber}" stroke-dasharray="6 4"/><text x="${W-R-4}" y="${Y(thresholdLine)-5}" fill="${C.amber}" text-anchor="end">阈值 ${thresholdLine.toFixed(2)}</text>`;
  curves.forEach(c=>{let d='',pen=false;rows.forEach((r,i)=>{let value=r[c.key];if(value===null||!r.valid||i>t){pen=false;return;}value*=c.scale||1;d+=`${pen?'L':'M'}${X(i).toFixed(2)},${Y(value).toFixed(2)} `;pen=true;});z+=`<path d="${d}" fill="none" stroke="${c.color}" stroke-width="2" ${c.dash?'stroke-dasharray="5 4"':''}/>`;});
  z+=`<line x1="${X(t)}" x2="${X(t)}" y1="${top}" y2="${top+height}" stroke="#183448" opacity=".55" stroke-dasharray="3 3"/>`;return z;
 }
 const volts=rows.filter(r=>r.valid).flatMap(r=>[r.voltage_residual_v*1000,r.channel_difference_v*1000]),vmax=Math.max(30,...volts.map(Math.abs))*1.18;
 s+=panel(30,102,'电压残差与两通道差 / mV',[{key:'voltage_residual_v',scale:1000,color:C.teal},{key:'channel_difference_v',scale:1000,color:C.blue,dash:true}],-vmax,vmax);
 const ts=rows.filter(r=>r.valid).map(r=>r.temperature_residual_c);s+=panel(172,92,'温度模型残差 / ℃',[{key:'temperature_residual_c',color:C.purple}],Math.min(-.3,...ts)*1.2,Math.max(1,...ts)*1.2);
 const scores=rows.filter(r=>r.valid).map(r=>r[method+'_score']);s+=panel(304,100,methodNames[method]+'异常分值',[{key:method+'_score',color:C.teal}],0,Math.max(threshold*1.2,...scores)*1.05,threshold);
 s+=`<text x="${L}" y="440" font-weight="600">告警状态</text>`;
 rows.forEach((r,i)=>{if(i>t)return;s+=`<rect x="${X(i)}" y="450" width="${plotW/179+0.5}" height="15" fill="${!r.valid?'#bdc8cf':r.alarm?'#c17d1f':'#e4f3f1'}"><title>${i} min：${!r.valid?'不可判定':r.alarm?'告警':'无告警'}</title></rect>`;});
 for(const x of [0,30,60,90,120,150,179])s+=`<text x="${X(x)}" y="488" text-anchor="middle">${x}</text>`;
 s+=`<text x="${(W+L-R)/2}" y="512" text-anchor="middle">会话时刻 / min</text></g></svg>`;return s;
}
function render(){
 const session=$('device').value+'_'+$('scenario').value,method=$('method').value,th=+$('threshold').value,q=+$('persistence').value,t=+$('time').value;
 const rows=M.alarms(unpack(session),method,th,q),event=D.events.find(e=>e.session_id===session)||null;currentRows=rows;currentEvent=event;
 const stat=M.evaluate(rows,event),r=rows[t],diag=M.diagnose(r),frozen=Math.abs(th-D.selected[method].threshold)<1e-8&&q===D.selected[method].persistence;
 $('thresholdValue').textContent=th.toFixed(2);$('qValue').textContent=q+'点';$('timeValue').textContent=t+' min';$('caseTitle').textContent=$('device').value+' · '+names[$('scenario').value];$('modeBadge').textContent=frozen?'冻结参数':'课堂参数探索';$('parameterNote').textContent=frozen?'使用独立验证设备选定的参数。':'已改变告警规则；仅用于课堂探索，不重新选择或训练模型。';
 $('chart').innerHTML=svgChart(rows,t,event,th,method);$('eventMetric').textContent=event?(stat.detected?'命中 1/1':'漏报 1/1'):'无目标事件';$('delayMetric').textContent=event?(stat.delay===null?'未命中':stat.delay+' min'):'—';$('falseMetric').textContent=stat.falseCount+'次';$('falseMetric').title=`正常有效时长${stat.hours.toFixed(3)} h，频率${stat.rate===null?'未知':stat.rate.toFixed(3)}次/h`;$('validMetric').textContent=stat.validCount+'/180';
 $('dv').textContent=r.valid?(1000*r.channel_difference_v).toFixed(1)+' mV':'—';$('vr').textContent=r.valid?(1000*r.voltage_residual_v).toFixed(1)+' mV':'—';$('tr').textContent=r.valid?r.temperature_residual_c.toFixed(2)+' ℃':'—';$('classText').textContent=r.valid?`分类器：${names[r.class_prediction]||r.class_prediction}；最大类别分值 ${r.class_confidence.toFixed(3)}（未作概率校准）`:'当前窗口不完整，停止分类';$('diagnosis').textContent=diag.text;$('nextAction').textContent=diag.action;$('evidenceStatus').textContent=diag.key==='unknown'?'待补充证据':diag.key==='data_unavailable'?'等待数据':'观察状态';
 $('episodeList').textContent='新告警起点：'+(rows.filter(r=>r.onset).map(r=>r.minute+' min').join('、')||'无')+`。正常有效时长 ${stat.hours.toFixed(3)} h，误报频率 ${stat.rate===null?'未知':stat.rate.toFixed(3)} 次/h，事件内额外碎片 ${stat.fragments} 次。`;
}
function stop(){if(timer)clearInterval(timer);timer=null;$('play').textContent='▶ 播放';}
$('play').onclick=()=>{if(timer){stop();return;}if(+$('time').value>=179)$('time').value=0;$('play').textContent='Ⅱ 暂停';timer=setInterval(()=>{if(+$('time').value>=179){stop();return;}$('time').value=+$('time').value+1;render();},180);};
['device','scenario','truth','threshold','persistence'].forEach(id=>$(id).addEventListener('input',render));$('time').addEventListener('input',()=>{stop();render();});$('method').addEventListener('change',defaults);$('reset').onclick=defaults;
$('caseGap').onclick=()=>{stop();$('device').value='D16';$('scenario').value='cooling_loss';$('method').value='logistic';$('time').value=92;$('truth').checked=true;defaults();};
$('caseNovel').onclick=()=>{stop();$('device').value='D13';$('scenario').value='novel_dual';$('method').value='logistic';$('time').value=100;$('truth').checked=true;defaults();};
function download(text,type,name){if(lastUrl)URL.revokeObjectURL(lastUrl);lastUrl=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=lastUrl;a.download=name;a.textContent='再次下载 '+name;$('download').replaceChildren(a);a.click();}
$('csv').onclick=()=>{const keys=['minute','valid','voltage_residual_v','channel_difference_v','temperature_residual_c',$('method').value+'_score','alarm','onset','class_prediction','class_confidence','label'];const lines=[keys.join(','),...currentRows.map(r=>keys.map(k=>r[k]??'').join(','))];download('\ufeff'+lines.join('\r\n'),'text/csv;charset=utf-8','chapter3_'+$('device').value+'_'+$('scenario').value+'.csv');};
$('svg').onclick=()=>download($('chart').innerHTML,'image/svg+xml','chapter3_timeline.svg');
defaults();
