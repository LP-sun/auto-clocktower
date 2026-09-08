const fs=require('node:fs'),path=require('node:path');
const root=__dirname;
const before=fs.readFileSync(path.join(root,'runs/llm-2026-09-08T05-23-05-797Z/model-decisions.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
const byKind={};let input=0,cached=0,output=0,max=0;
for(const d of before){let task;try{task=JSON.parse(d.request.prompt);}catch{task={kind:'unknown'};}const u=d.usage?.usage?.last;if(!u)continue;const b=byKind[task.kind]??={calls:0,input:0,output:0};b.calls++;b.input+=u.inputTokens;b.output+=u.outputTokens;input+=u.inputTokens;cached+=u.cachedInputTokens||0;output+=u.outputTokens;max=Math.max(max,u.inputTokens);}
for(const b of Object.values(byKind))b.averageInput=b.input/b.calls;
const after=JSON.parse(fs.readFileSync(path.join(root,'runs/fixture-2026-09-08T10-42-52-548Z-QIMux3/telemetry.json')));
const result={warning:'Historical real usage and new offline prompt estimates are different measurement types. This is not a measured token saving or a strategy benchmark.',before:{calls:before.length,input,cached,uncached:input-cached,output,maxInput:max,cacheRatio:cached/input,byKind},after:{calls:after.calls,totalEstimatedInput:Object.values(after.byKind).reduce((s,v)=>s+v.estimated,0),actualInput:null,actualUncached:null,actualOutput:null,cacheRatio:null,...after}};
fs.writeFileSync(path.join(root,'validation-v2/context-comparison.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({before:result.before,afterEstimate:result.after.totalEstimatedInput}));
