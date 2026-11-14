/* Pure numerical kernel, shared by the browser and Node verification. */
(function(root){
  'use strict';
  function step(t,u,ta,c,ua,beta,dt=120){
    if(!(c>0 && ua>=0 && beta>=0 && dt>0)) throw Error('Invalid physical parameters');
    if(beta===0) return ua===0 ? t+u*dt/c : t-Math.expm1(-ua*dt/c)*(ta+u/ua-t);
    const f=x=>(u-ua*(x-ta)-beta*(x-ta)*Math.abs(x-ta))/c;
    const a=f(t), b=f(t+dt*a/2), d=f(t+dt*b/2), e=f(t+dt*d);
    return t+dt*(a+2*b+2*d+e)/6;
  }
  function metrics(actual,reference,start=10,end=actual.length-1){
    const n=end-start+1;if(n<1)return {rmse:null,mae:null,bias:null,n:0};
    let square=0,absolute=0,bias=0;
    for(let k=start;k<=end;k++){const e=actual[k]-reference[k];square+=e*e;absolute+=Math.abs(e);bias+=e;}
    return {rmse:Math.sqrt(square/n),mae:absolute/n,bias:bias/n,n};
  }
  function calculate(ep,p){
    if(!(p.q>=0 && p.sigma>0 && p.r>0)) throw Error('Positive noise variance required');
    const n=ep.truth.length, y=ep.truth.map((t,k)=>t+ep.noise[k]*p.sigma/.25+(k*120>=21600?p.bias:0));
    const open=[y[0]], estimate=[y[0]+2], variance=[4], innovation=[0],gain=[0],prior=[y[0]+2],energy=[0];
    for(let k=0;k<n-1;k++){
      const args=[ep.power[k],ep.ambient[k],p.c,p.ua,p.beta];
      open.push(step(open[k],...args));
      const predicted=step(estimate[k],...args);
      const a=(step(estimate[k]+1e-4,...args)-step(estimate[k]-1e-4,...args))/2e-4;
      const pm=a*a*variance[k]+p.q,g=pm/(pm+p.r),v=y[k+1]-predicted;
      prior.push(predicted);gain.push(g);innovation.push(v);estimate.push(predicted+g*v);
      variance.push((1-g)*(1-g)*pm+g*g*p.r);
      energy.push(energy[k]+418*(open[k+1]-open[k])-ep.energy_ref[k]);
    }
    const m=metrics(estimate,ep.truth), mo=metrics(open,ep.truth);let covered=0;
    for(let k=10;k<n;k++)if(Math.abs(estimate[k]-ep.truth[k])<=1.96*Math.sqrt(variance[k])) covered++;
    return {y,open,estimate,variance,innovation,gain,prior,energy,metrics:m,openMetrics:mo,coverage:100*covered/(n-10)};
  }
  function csv(ep,r){
    const lines=['time_s,T_ref_C,observation_C,open_loop_C,estimate_C,std_K,gain,innovation_K,cumulative_energy_kJ'];
    for(let k=0;k<ep.truth.length;k++) lines.push([k*120,ep.truth[k],r.y[k],r.open[k],r.estimate[k],Math.sqrt(r.variance[k]),r.gain[k],r.innovation[k],r.energy[k]].join(','));
    return '\uFEFF'+lines.join('\n');
  }
  const api={step,metrics,calculate,csv};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.WH1=api;
})(typeof window!=='undefined'?window:globalThis);
