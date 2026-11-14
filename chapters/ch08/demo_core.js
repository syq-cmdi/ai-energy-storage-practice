(function(root){
'use strict';
function pressure(m,c,temp=25,z=1){return m*c.gas_constant*(temp+273.15)*z/c.volume/1e5;}
function step(request,m,previousOn,r,d,gcap,c){
 let p=Math.max(0,Math.min(request,c.pmax));
 p=Math.min(p,Math.max(0,(r+gcap-c.auxiliary)/(1+c.compressor/c.sec)));
 p=Math.min(p,Math.max(0,((c.mmax-(1-c.loss*c.dt)*m)/c.dt+d)*c.sec));
 if(p<c.pmin-1e-6)p=0;
 const on=Number(p>1e-8),q=p/c.sec,served=Math.max(0,Math.min(d,((1-c.loss*c.dt)*m-c.mmin)/c.dt+q));
 const compressor=c.compressor*q,auxiliary=c.auxiliary*on,total=p+compressor+auxiliary,used=Math.min(r,total);
 return {p,on,start:Number(on>previousOn),q,served,shortage:d-served,m_after:(1-c.loss*c.dt)*m+(q-served)*c.dt,compressor,auxiliary,total,grid:Math.max(0,total-r),renewable_used:used,curtailment:r-used};
}
function csv(rows){const keys=Object.keys(rows[0]);return '\ufeff'+keys.join(',')+'\r\n'+rows.map(r=>keys.map(k=>String(r[k])).join(',')).join('\r\n');}
const api={pressure,step,csv};if(typeof module!=='undefined')module.exports=api;root.HydrogenLab=api;
})(typeof globalThis!=='undefined'?globalThis:this);
