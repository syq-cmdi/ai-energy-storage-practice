/* Pure teaching engine. The offline bundle contains synthetic examples only. */
(function(root){
'use strict';
const tokenise=s=>{const c=Array.from(s.toLowerCase().replace(/\s+/g,''));return c.concat(c.slice(0,-1).map((v,i)=>v+c[i+1]));};
const counts=s=>{const r={};for(const t of tokenise(s))r[t]=(r[t]||0)+1;return r;};
const dot=(a,b)=>a.reduce((sum,x,i)=>sum+x*b[i],0);
const norm=a=>{const n=Math.sqrt(dot(a,a))||1;return a.map(x=>x/n);};
const eligible=(m,q)=>m.authorized&&m.status==='released'&&m.asset===q.asset&&m.group===q.group&&m.valid_from<=q.as_of&&q.as_of<=m.valid_to;
function search(index,q,method='bm25',k=3){
 const ct=counts(q.text),qv=norm(index.vocab.map((t,j)=>(ct[t]||0)*index.idf[j]));let scores;
 if(method==='tfidf')scores=index.tfidf.map(v=>dot(v,qv));
 else if(method==='lsa'){const z=norm(index.components.map(c=>dot(c,qv)));scores=index.lsa.map(v=>dot(v,z));}
 else if(method==='bm25')scores=index.counts.map((c,i)=>Object.keys(ct).reduce((sum,t)=>{const j=index.lookup[t];if(j===undefined)return sum;const f=c[t]||0,df=index.df[j];return sum+Math.log(1+(index.chunks.length-df+.5)/(df+.5))*f*2.2/(f+1.2*(.25+.75*index.lengths[i]/index.avg_length));},0));
 else throw Error('unknown method');
 return index.chunks.map((chunk,i)=>({chunk,score:scores[i]})).filter(h=>eligible(h.chunk.meta,q)&&h.score>1e-10).sort((a,b)=>b.score-a.score||a.chunk.id.localeCompare(b.chunk.id)).slice(0,k);
}
function answer(index,q,method='bm25',k=3){
 const hits=search(index,q,method,k),chosen=hits.filter(h=>h.chunk.fact&&h.chunk.fact.metric===q.metric);
 if(!chosen.length)return {status:'needs_evidence',evidence:[],text:'当前范围与前k项中尚缺目标属性证据。请查看检索缺口或补充资料。'};
 const facts=index.chunks.filter(c=>eligible(c.meta,q)&&c.fact&&c.fact.metric===q.metric);
 if(new Set(facts.map(c=>JSON.stringify([c.fact.value,c.fact.unit]))).size>1)return {status:'conflict',evidence:facts.map(c=>c.id),text:'有效资料出现同属性数值冲突。请核对下方两份原文，由资料负责人确定采用版本。'};
 const c=chosen[0].chunk;return {status:'grounded',evidence:[c.id],text:`教学语料记录：${c.fact.value} ${c.fact.unit}。出处 ${c.id}，第${c.line_start}—${c.line_end}行。`};
}
function runtime(energy,power,soc,floor,eta){if(![energy,power,soc,floor,eta].every(Number.isFinite)||energy<=0||power<=0||floor<0||floor>soc||soc>1||eta<=0||eta>1)throw Error('参数超出范围');return energy*(soc-floor)*eta/power;}
function heat(volume,density,cp,delta){if(![volume,density,cp,delta].every(x=>Number.isFinite(x)&&x>0))throw Error('参数超出范围');return volume*density*cp*delta/3600;}
const api={tokenise,eligible,search,answer,runtime,heat};if(typeof module!=='undefined')module.exports=api;root.Lesson09=api;
})(typeof globalThis!=='undefined'?globalThis:this);
