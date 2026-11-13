/* Numerical core, shared by the offline UI and Node tests. Positive I = discharge. */
(function(root){
  'use strict';
  function soc({bias=0,capacity=1.8,initial=.8}={}) {
    if(!Number.isFinite(capacity)||capacity<=0||!Number.isFinite(bias)||!Number.isFinite(initial)) throw new Error('Invalid SOC parameter');
    const t=[],reference=[],estimate=[],current=[],error=[];let integral=0;
    for(let k=0;k<=360;k++) {
      if(k>0) integral += [.6,1.2,-.4,0][Math.floor((k-1)/90)]*10;
      const ref=.8-integral/(3600*1.8), est=initial-(integral+bias*k*10)/(3600*capacity);
      t.push(k/6);reference.push(ref);estimate.push(est);error.push((est-ref)*100);
      current.push([.6,1.2,-.4,0][Math.min(3,Math.floor(k/90))]);
    }
    return {t,reference,estimate,current,error};
  }
  function score(y,p,radius=null){
    if(!y.length||y.length!==p.length)throw new Error('Paired, nonempty observations required');
    const e=p.map((v,i)=>(v-y[i])*100);
    return {mae:e.reduce((s,v)=>s+Math.abs(v),0)/e.length,
      rmse:Math.sqrt(e.reduce((s,v)=>s+v*v,0)/e.length),
      coverage:radius===null?null:e.filter(v=>Math.abs(v)<=radius).length/e.length};
  }
  const api={soc,score};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.LessonMath=api;
})(typeof window==='object'?window:this);
