/* Pure causal alarm and event accounting; shared by browser and Node tests. */
(function(root){
'use strict';
function alarms(rows,method,threshold,q){
 if(!Number.isFinite(threshold)||!Number.isInteger(q)||q<1)throw Error('invalid parameters');
 let up=0,down=0,on=false;
 return rows.map(r=>{let was=on;if(!r.valid){up=down=0;on=false;}else{const high=r[method+'_score']>=threshold;up=high?up+1:0;down=high?0:down+1;if(!on&&up>=q)on=true;if(on&&down>=2)on=false;}return {...r,alarm:on,onset:on&&!was};});
}
function evaluate(rows,event){
 const inside=r=>!!event&&r.minute>=event.start_min&&r.minute<event.end_min;
 const hits=rows.filter(r=>r.onset&&inside(r)),falseCount=rows.filter(r=>r.onset&&!inside(r)).length;
 const hours=rows.filter(r=>r.valid&&!inside(r)).length/60;
 return {detected:event?hits.length>0:null,delay:event&&hits.length?hits[0].minute-event.start_min:null,missed:event?Number(!hits.length):0,falseCount,hours,rate:hours?falseCount/hours:null,fragments:Math.max(0,hits.length-1),validCount:rows.filter(r=>r.valid).length};
}
function diagnose(r){
 if(!r.valid)return {key:'data_unavailable',text:'数据不可判定',action:'等待完整5点窗口恢复'};
 if(!r.alarm)return {key:'no_alarm',text:'当前无告警',action:'继续观察；无告警不等于已证明设备正常'};
 const signals=[];
 if(Math.abs(r.channel_difference_v)>.025)signals.push('voltage_bias');
 if(r.voltage_residual_v<-.030&&Math.abs(r.channel_difference_v)<.020)signals.push('resistance_rise');
 if(r.temperature_residual_c>.8)signals.push('cooling_loss');
 if(signals.length!==1||r.class_confidence<.8||r.class_prediction!==signals[0])return {key:'unknown',text:'证据不足或冲突',action:'保留未知；安排独立电压和温度复测'};
 const names={voltage_bias:'电压通道偏移线索',resistance_rise:'内阻代理异常线索',cooling_loss:'温升代理异常线索'};
 return {key:signals[0],text:names[signals[0]],action:'待核查假设；用独立测量确认原因'};
}
const api={alarms,evaluate,diagnose};if(typeof module!=='undefined')module.exports=api;root.Ch3Math=api;
})(typeof window==='undefined'?globalThis:window);
