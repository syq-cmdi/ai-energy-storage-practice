/* Offline forward dynamics: exported Python weights, independent JavaScript arithmetic. */
(function(root){
'use strict';
const DT=120;
function linearStep(T,u,Ta,C,UA){
 if(![T,u,Ta,C,UA].every(Number.isFinite)||C<=0||UA<0)throw Error('invalid physical input');
 return UA===0?T+u*DT/C:T-Math.expm1(-UA*DT/C)*(Ta+u/UA-T);
}
function predict(model,T,u,Ta){
 if(model.kind==='physical')return linearStep(T,u,Ta,model.capacity,model.ua);
 let x=[T,Ta,u].map((v,i)=>(v-model.x_mean[i])/model.x_scale[i]);
 for(let layer=0;layer<model.coefs.length;layer++){
  const w=model.coefs[layer],b=model.biases[layer];
  x=b.map((v,j)=>v+w.reduce((s,row,i)=>s+row[j]*x[i],0));
  if(layer<model.coefs.length-1)x=x.map(Math.tanh);
 }
 const correction=x[0]*model.y_scale+model.y_mean;
 return (model.kind==='residual'?linearStep(T,u,Ta,model.capacity,model.ua):T)+correction;
}
function rollout(model,T,power,ambient){
 if(power.length!==ambient.length)throw Error('trajectory length mismatch');
 const states=[T];for(let i=0;i<power.length;i++)states.push(predict(model,states[states.length-1],power[i],ambient[i]));return states;
}
function inDomain(domain,T,u,Ta){return [[T,domain.temperature],[Ta,domain.ambient],[u,domain.power]].every(([v,b])=>Number.isFinite(v)&&v>=b[0]-1e-10&&v<=b[1]+1e-10);}
function errors(prediction,truth){if(prediction.length!==truth.length||!prediction.length)throw Error('comparison length mismatch');const e=prediction.map((x,i)=>x-truth[i]);return {rmse:Math.sqrt(e.reduce((s,x)=>s+x*x,0)/e.length),mae:e.reduce((s,x)=>s+Math.abs(x),0)/e.length,bias:e.reduce((s,x)=>s+x,0)/e.length};}
function windowForecast(model,episode,start,horizon){if(!Number.isInteger(start)||start<0||start>=episode.power.length||!Number.isInteger(horizon)||horizon<1)throw Error('invalid forecast window');const n=Math.min(horizon,episode.power.length-start),p=episode.power.slice(start,start+n),a=episode.ambient.slice(start,start+n),forecast=rollout(model,episode.temperature[start],p,a),truth=episode.temperature.slice(start,start+n+1);return {time:episode.t_s.slice(start,start+n+1).map(t=>t/3600),prediction:forecast,truth,power:p,ambient:a,metrics:errors(forecast.slice(1),truth.slice(1)),horizon:n};}
function empiricalBand(model,episodes,horizon){
 const errors=[];for(const ep of episodes){for(let start=0;start<=ep.power.length-horizon;start++){let state=ep.temperature[start];for(let j=0;j<horizon;j++)state=predict(model,state,ep.power[start+j],ep.ambient[start+j]);errors.push(Math.abs(state-ep.temperature[start+horizon]));}}
 if(!errors.length)throw Error('no validation windows');errors.sort((a,b)=>a-b);return {halfWidth:errors[Math.ceil(.95*(errors.length-1))],nWindows:errors.length};
}
const api={DT,linearStep,predict,rollout,inDomain,errors,windowForecast,empiricalBand};if(typeof module!=='undefined')module.exports=api;root.Lesson10=api;
})(typeof globalThis!=='undefined'?globalThis:this);
