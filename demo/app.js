/* UI reads frozen SOH results; only the SOC integration is recomputed. */
(function(){'use strict';
const D=window.LESSON_DATA,M=window.LessonMath,$=id=>document.getElementById(id);
const C={teal:'#087f8c',blue:'#3466b0',amber:'#c17d1f',purple:'#7954a1',ink:'#183448',muted:'#6b8390',grid:'#dce6eb',red:'#bb4d4d'};
const names={window_mlp:'窗口网络',ridge:'岭回归',forest:'随机森林',persistence:'持久性基线'};
let timer=null,tab='soc',activeCell='C09',revealed=false,socData;
const fmt=(n,d=2)=>Number(n).toFixed(d),sign=(n,d=2)=>(n>=0?'+':'')+fmt(n,d);
function metric(label,value,unit=''){return `<div class="metric"><small>${label}</small><strong>${value}<span>${unit}</span></strong></div>`;}
function svgStart(title){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 414" role="img"><title>${title}</title><rect width="880" height="414" fill="white"/><g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif" font-size="13" fill="${C.muted}">`;}
function axis(box,xlim,ylim,xt,yt,ylabel){const [l,t,w,h]=box,x=v=>l+(v-xlim[0])/(xlim[1]-xlim[0])*w,y=v=>t+h-(v-ylim[0])/(ylim[1]-ylim[0])*h;let s='';
 for(const v of yt){s+=`<path d="M${l},${y(v)}h${w}" stroke="${C.grid}" stroke-width="1"/><text x="${l-11}" y="${y(v)+4}" text-anchor="end">${v}</text>`;}
 for(const v of xt){s+=`<text x="${x(v)}" y="${t+h+22}" text-anchor="middle">${v}</text>`;}
 s+=`<text x="${l}" y="${t-13}" font-size="12" fill="${C.ink}">${ylabel}</text>`;return {x,y,s};}
function line(x,y,ax,color,width=2,dash=''){return `<path d="${x.map((v,i)=>(i?'L':'M')+ax.x(v).toFixed(2)+','+ax.y(y[i]).toFixed(2)).join(' ')}" fill="none" stroke="${color}" stroke-width="${width}" ${dash?'stroke-dasharray="'+dash+'"':''} stroke-linejoin="round"/>`;}
function legend(x,y,color,label,dash=''){return `<path d="M${x},${y-4}h24" stroke="${color}" stroke-width="2" ${dash?'stroke-dasharray="'+dash+'"':''}/><text x="${x+32}" y="${y}">${label}</text>`;}
function bounds(a,pad=.1){const lo=Math.min(...a),hi=Math.max(...a),r=Math.max(hi-lo,.01);return [lo-r*pad,hi+r*pad];}
function renderSoc(){const bias=+$('bias').value,capacity=+$('capacity').value,initial=+$('initial').value,k=+$('time').value;socData=M.soc({bias,capacity,initial});
 $('bias-v').textContent=sign(bias,3)+' A';$('capacity-v').textContent=fmt(capacity)+' A·h';$('initial-v').textContent=fmt(initial*100,1)+'%';$('time-v').textContent=fmt(k/6,1)+' min';
 $('soc-metrics').innerHTML=metric('当前参考 SOC',fmt(socData.reference[k]*100,1),'%')+metric('当前估计误差',sign(socData.error[k]),'百分点')+metric('60分钟末误差',sign(socData.error[360]),'百分点');
 let s=svgStart('SOC轨迹和有符号误差');const a=axis([68,62,760,176],[0,60],[.3,1.05],[0,15,30,45,60],[.4,.6,.8,1],'SOC');s+=a.s;
 const range=bounds([...socData.error,0],.18),lim=Math.max(1,Math.ceil(Math.max(Math.abs(range[0]),Math.abs(range[1]))));const b=axis([68,302,760,62],[0,60],[-lim,lim],[0,15,30,45,60],[-lim,0,lim],'误差 / 百分点');s+=b.s;
 for(const [i,label] of ['放电 0.6 A','放电 1.2 A','充电 0.4 A','静置'].entries()){s+=`<rect x="${a.x(i*15)}" y="62" width="190" height="176" fill="${i===2?C.blue:C.teal}" opacity="${i%2?.02:.045}"/><text x="${a.x(i*15+7.5)}" y="56" text-anchor="middle" font-size="12">${label}</text>`;}
 s+=line(socData.t,socData.reference,a,C.teal,2.7)+line(socData.t,socData.estimate,a,C.amber,2.2,'6 4')+line(socData.t,socData.error,b,C.amber,2);
 s+=`<path d="M${a.x(k/6)},62V364" stroke="${C.ink}" stroke-dasharray="3 4" opacity=".5"/>`;
 for(const [vals,color] of [[socData.reference,C.teal],[socData.estimate,C.amber]])s+=`<circle cx="${a.x(k/6)}" cy="${a.y(vals[k])}" r="4.5" fill="${color}" stroke="white" stroke-width="2"/>`;
 s+=legend(68,24,C.teal,'参考轨迹')+legend(215,24,C.amber,'当前参数估计','6 4')+`<text x="828" y="405" text-anchor="end">时间 / min</text></g></svg>`;$('soc-chart').innerHTML=s;
 $('soc-note').textContent=`观察时刻 ${fmt(k/6,1)} min：真实电流 ${fmt(socData.current[k],1)} A；估计器读数 ${fmt(socData.current[k]+bias,3)} A。参考初值80%，参考容量1.8 A·h。`;
}
function stop(){if(timer!==null)clearInterval(timer);timer=null;$('play').textContent='播放过程';$('play').setAttribute('aria-pressed','false');}
$('play').onclick=()=>{if(timer!==null){stop();return;}if(+$('time').value>=360)$('time').value=0;$('play').textContent='暂停';$('play').setAttribute('aria-pressed','true');timer=setInterval(()=>{const k=Math.min(360,+$('time').value+3);$('time').value=k;renderSoc();if(k===360)stop();},80);};
for(const id of ['bias','capacity','initial','time'])$(id).addEventListener('input',renderSoc);
document.querySelectorAll('[data-preset]').forEach(button=>button.onclick=()=>{stop();$('bias').value=0;$('capacity').value=1.8;$('initial').value=.8;const p=button.dataset.preset;if(p==='bias')$('bias').value=.02;if(p==='capacity')$('capacity').value=2;if(p==='initial')$('initial').value=.85;renderSoc();});
function renderSoh(){const cell=$('cell').value,f=$('model').value,r=D.cells[cell],score=M.score(r.target_soh,r[f],f===D.selected?D.radius:null),zoom=$('zoom').checked,show=f===D.selected&&$('band').checked;
 $('band').disabled=f!==D.selected;$('band-help').textContent=f===D.selected?`C08校准半宽 ±${fmt(D.radius,4)} 个百分点。红色空心点为带外目标。`:'此方法未单独校准误差带；不套用窗口网络的带宽。';$('soh-title').textContent=cell+' · '+names[f];
 $('soh-metrics').innerHTML=metric('全部目标 MAE',fmt(score.mae,3),'百分点')+metric('全部目标 RMSE',fmt(score.rmse,3),'百分点')+metric('经验带覆盖率',score.coverage===null?'—':fmt(score.coverage*100,1),score.coverage===null?'未校准':'%');
 const indices=r.target_cycle.map((v,i)=>i).filter(i=>!zoom||r.target_cycle[i]>=140),x=indices.map(i=>r.target_cycle[i]),y=indices.map(i=>r.target_soh[i]),p=indices.map(i=>r[f][i]),lo=indices.map(i=>r.lower_soh[i]),hi=indices.map(i=>r.upper_soh[i]),err=p.map((v,i)=>(v-y[i])*100),xr=zoom?[140,160]:[6,160],xt=zoom?[140,145,150,155,160]:[6,40,80,120,160],yr=bounds(show?[...y,...lo,...hi]:[...y,...p],.08),yt=[0,1,2,3].map(i=>+(yr[0]+(yr[1]-yr[0])*i/3).toFixed(3));
 let s=svgStart(cell+' SOH测试轨迹和残差'),a=axis([68,62,760,176],xr,yr,xt,yt,'容量型 SOH'),limit=Math.max(.5,Math.ceil(Math.max(...err.map(Math.abs),D.radius)*2)/2),b=axis([68,302,760,62],xr,[-limit,limit],xt,[-limit,0,limit],'残差 / 百分点');s+=a.s+b.s;
 if(show){s+=`<path d="${x.map((v,i)=>(i?'L':'M')+a.x(v)+','+a.y(hi[i])).join(' ')} ${x.map((v,i)=>'L'+a.x(v)+','+a.y(lo[i])).reverse().join(' ')}Z" fill="${C.teal}" opacity=".16"/><rect x="68" y="${b.y(D.radius)}" width="760" height="${b.y(-D.radius)-b.y(D.radius)}" fill="${C.teal}" opacity=".09"/>`;for(const v of [-D.radius,D.radius])s+=`<path d="M68,${b.y(v)}H828" stroke="${C.teal}" stroke-dasharray="5 4"/>`;}
 s+=line(x,y,a,C.amber,1.5,'5 3')+line(x,p,a,C.teal,2);
 x.forEach((v,i)=>{const outside=show&&Math.abs(err[i])>D.radius;s+=`<circle cx="${b.x(v)}" cy="${b.y(err[i])}" r="${outside?3.5:2}" fill="${outside?'white':C.teal}" stroke="${outside?C.red:C.teal}" stroke-width="1.2"/>`;});
 s+=legend(68,24,C.amber,'容量标签','5 3')+legend(215,24,C.teal,'冻结模型预测')+`<text x="828" y="405" text-anchor="end">目标循环</text></g></svg>`;$('soh-chart').innerHTML=s;
}
for(const id of ['cell','model','zoom','band'])$(id).onchange=renderSoh;
const groups=[['train','训练组','拟合模型与标准化器',6,C.teal],['validation','验证组','选择模型与超参数',1,C.blue],['calibration','校准组','确定经验带宽',1,C.purple],['test','测试组','冻结后报告表现',4,C.amber]];
let n=1;$('groups').innerHTML=groups.map(([key,name,role,count,color])=>{let buttons='';for(let i=0;i<count;i++,n++){const cell='C'+String(n).padStart(2,'0');buttons+=`<button data-cell="${cell}" data-role="${name} · ${role}" style="--group-color:${color}" aria-pressed="false">${cell}</button>`;}return `<div class="group" style="--group-color:${color}"><h3>${name}</h3><p>${role} · ${count*155}个窗口</p>${buttons}</div>`;}).join('');
function renderWindow(){const n=+$('cycle').value,rows=D.cycles[activeCell],history=rows.slice(n-5,n),target=rows[n];$('cycle-v').textContent=n;$('window-title').textContent=activeCell+' · 五循环历史';let role='';document.querySelectorAll('[data-cell]').forEach(b=>{const active=b.dataset.cell===activeCell;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));if(active)role=b.dataset.role;});$('role-name').textContent=role;
 $('matrix').innerHTML='<table><thead><tr><th>循环</th><th>容量型 SOH</th><th>内阻 / mΩ</th><th>温度 / ℃</th></tr></thead><tbody>'+history.map(r=>`<tr><td>${r[0]}</td><td>${fmt(r[1],4)}</td><td>${fmt(r[2]*1000,2)}</td><td>${fmt(r[3],2)}</td></tr>`).join('')+`</tbody></table><div class="target-box"><small>下一循环 ${target[0]} 的标签</small><strong>${revealed?fmt(target[1],4):'?'}</strong><p>${revealed?'评测时才能与预测配对':'先观察输入，再揭示未来'}</p></div>`;$('reveal').textContent=revealed?'隐藏下一循环标签':'揭示下一循环标签';$('reveal').setAttribute('aria-pressed',String(revealed));}
$('cycle').oninput=()=>{revealed=false;renderWindow();};$('reveal').onclick=()=>{revealed=!revealed;renderWindow();};document.querySelectorAll('[data-cell]').forEach(b=>b.onclick=()=>{activeCell=b.dataset.cell;revealed=false;renderWindow();});
const tabs=[...document.querySelectorAll('[data-tab]')];function selectTab(id){stop();tab=id;tabs.forEach(b=>{const active=b.dataset.tab===id;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;$(b.dataset.tab).hidden=!active;});if(id==='soh')renderSoh();if(id==='window')renderWindow();}
tabs.forEach((b,i)=>{b.onclick=()=>selectTab(b.dataset.tab);b.onkeydown=e=>{let j;if(e.key==='ArrowRight')j=(i+1)%3;if(e.key==='ArrowLeft')j=(i+2)%3;if(e.key==='Home')j=0;if(e.key==='End')j=2;if(j!==undefined){e.preventDefault();selectTab(tabs[j].dataset.tab);tabs[j].focus();}};});
let exportUrl=null;
function download(name,text,type){
 if(exportUrl)URL.revokeObjectURL(exportUrl);
 exportUrl=URL.createObjectURL(new Blob([text],{type}));
 const status=$(tab==='soh'?'soh-export':'soc-export');status.textContent='已生成 '+name+'。';
 const link=document.createElement('a');link.href=exportUrl;link.download=name;link.textContent=' 如未自动保存，点击下载';status.appendChild(link);link.click();
}
document.querySelectorAll('[data-export]').forEach(b=>b.onclick=()=>{if(b.dataset.export==='soc'){const rows=socData.t.map((t,i)=>[t,socData.current[i],socData.current[i]+Number($("bias").value),Number($("capacity").value),Number($("initial").value),socData.reference[i],socData.estimate[i],socData.error[i]]);download('soc_experiment.csv','time_min,current_a,measured_current_a,assumed_capacity_ah,initial_soc,reference_soc,estimated_soc,error_pp\n'+rows.map(r=>r.join(',')).join('\n'),'text/csv;charset=utf-8');}else{const cell=$('cell').value,f=$('model').value,r=D.cells[cell];let keys=['target_cycle','target_soh',f];if(f===D.selected)keys.push('lower_soh','upper_soh');download(cell+'_'+f+'.csv',keys.join(',')+'\n'+r.target_cycle.map((_,i)=>keys.map(k=>r[k][i]).join(',')).join('\n'),'text/csv;charset=utf-8');}});
document.querySelectorAll('[data-svg]').forEach(b=>b.onclick=()=>download(b.dataset.svg+'.svg',$(b.dataset.svg).querySelector('svg').outerHTML,'image/svg+xml;charset=utf-8'));
renderSoc();renderSoh();renderWindow();
})();
