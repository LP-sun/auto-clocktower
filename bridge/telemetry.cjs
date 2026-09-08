const fs=require('node:fs');
class Telemetry{
 constructor(log=()=>{}){this.rows=[];this.log=log;}
 record(metrics,usage){const u=usage?.last||{};const row={...metrics,actualInputTokens:u.inputTokens??null,cachedInputTokens:u.cachedInputTokens??null,outputTokens:u.outputTokens??null};this.rows.push(row);this.log('context_telemetry',row);}
 aggregate(){const byKind={};for(const r of this.rows){const a=byKind[r.kind]??={calls:0,chars:0,estimated:0,maxEstimated:0,actualInput:0,cached:0,output:0,measuredCalls:0};a.calls++;a.chars+=r.contextChars;a.estimated+=r.estimatedInputTokens;a.maxEstimated=Math.max(a.maxEstimated,r.estimatedInputTokens);if(r.actualInputTokens!==null){a.measuredCalls++;a.actualInput+=r.actualInputTokens;a.cached+=r.cachedInputTokens||0;a.output+=r.outputTokens||0;}}
 for(const a of Object.values(byKind)){a.averageChars=a.chars/a.calls;a.averageEstimated=a.estimated/a.calls;a.cacheRatio=a.measuredCalls&&a.actualInput?a.cached/a.actualInput:null;if(!a.measuredCalls){a.actualInput=null;a.cached=null;a.output=null;}}
 const days={};for(const r of this.rows){const d=days[r.day]??={calls:0,sum:0,max:0};d.calls++;d.sum+=r.estimatedInputTokens;d.max=Math.max(d.max,r.estimatedInputTokens);}for(const d of Object.values(days))d.average=d.sum/d.calls;
 return {calls:this.rows.length,byKind,days,actualMeasurementAvailable:this.rows.some(r=>r.actualInputTokens!==null)};}
 save(file){fs.writeFileSync(file,JSON.stringify(this.aggregate(),null,2));}
}
module.exports={Telemetry};
