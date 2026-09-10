const fs=require('node:fs');
const names=require('./role-names.zh.json');
const clone=x=>JSON.parse(JSON.stringify(x));
class SemanticStore {
 constructor(){this.events=[];this.players=new Map();this.nextId=1;this.social={chatEdges:{},nominations:{},votes:{}};}
  register(seat){if(this.players.has(seat))throw Error('Duplicate memory');this.players.set(seat,{identity:{seat},privateFacts:[],publicClaims:{},privateConversations:[],privateClaims:{},sharedInformation:[],whisperHistory:[],trust:{},beliefs:{},contradictions:[],worlds:[],plan:[],importantEvents:[],currentDayState:{},recent:[],summaries:[],ability:{},bluff:{claimed_role:null,claim_started_day:null,public_commitments:[],fake_night_history:[],desired_world:null}});}
 observe(event){
  const e={...event,id:this.nextId++};if(!['public','private'].includes(e.visibility))throw Error('Visibility required');
  if(e.visibility==='private'&&(!Array.isArray(e.audience)||!e.audience.length))throw Error('Private audience required');
  this.events.push(e);
  for(const [seat,m] of this.players){
   if(e.visibility==='private'&&!e.audience.includes(seat))continue;
   const fact={id:e.id,day:e.day,night:e.night,type:e.type,text:e.text,actor:e.actor,...(e.visibility==='private'?{epistemicStatus:'received_not_verified'}:{})};
   if(e.visibility==='private'){
    if(e.type==='whisper')m.privateConversations.push(fact);
    else if(!m.privateFacts.some(f=>f.text===e.text))m.privateFacts.push(fact);
   }else{
    m.recent.push(fact);m.recent=m.recent.slice(-15);
    if(['death','execution','ability','nomination','vote','phase'].includes(e.type)){m.importantEvents.push(fact);m.importantEvents=m.importantEvents.slice(-24);}
    if(e.type==='chat'&&e.actor){
     const claim=Object.entries(names).find(([id,name])=>new RegExp('(?:我是|自称|声称|跳|claim(?: to be)?(?: the)? )\\s*'+name).test(e.text));
     if(claim){const old=m.publicClaims[e.actor];if(old&&old.role!==claim[0]){m.contradictions.push({actor:e.actor,oldRole:old.role,newRole:claim[0],oldSource:old.source,newSource:e.id,kind:'claim_change_not_proof'});m.contradictions=m.contradictions.slice(-12);}
      if(!m.publicClaims[e.actor]?.structured)m.publicClaims[e.actor]={role:claim[0],kind:'claim',confirmed:false,source:e.id,day:e.day,text:e.text.slice(0,300),structured:false};
      if(e.actor===seat){m.bluff.claimed_role=claim[0];m.bluff.claim_started_day??=e.day;}
     }
     if(e.actor===seat){m.bluff.public_commitments.push(fact);m.bluff.public_commitments=m.bluff.public_commitments.slice(-8);if(/首夜|昨夜|第.*夜|保护|得知/.test(e.text)){m.bluff.fake_night_history.push(fact);m.bluff.fake_night_history=m.bluff.fake_night_history.slice(-8);}}
    }
   }
  }
  if(e.type==='whisper_contact'){const pair=[e.actor,e.peer].sort().join(':');this.social.chatEdges[pair]=(this.social.chatEdges[pair]||0)+1;const m=this.players.get(e.actor);if(m){m.whisperHistory.push({day:e.day,topic:e.topic||'other',summary:e.text?.slice(0,240)||''});m.whisperHistory=m.whisperHistory.slice(-20);} }
  if(e.type==='trust_update'&&this.players.has(e.actor)){const m=this.players.get(e.actor);m.trust[e.target]={score:e.score,reasons:[...(m.trust[e.target]?.reasons||[]),e.reason].slice(-6),last_updated:e.day};}
  if(e.type==='nomination')this.social.nominations[e.target]=(this.social.nominations[e.target]||0)+1;
  if(e.type==='vote'&&e.accepted)this.social.votes[e.target]=(this.social.votes[e.target]||0)+1;
  return e;
 }
 recordChoice(seat,task,response){
  const m=this.players.get(seat);if(!m)throw Error('Unknown seat');
  const communication=response.communication;
  if(communication!=null){
   if(typeof communication!=='object'||Array.isArray(communication))throw Error('Invalid communication metadata');
   const allowed=new Set(['intent','identityClaims','evidenceRefs']);for(const key of Object.keys(communication))if(!allowed.has(key))throw Error('Invalid communication field');
   const refs=communication.evidenceRefs||[];if(!Array.isArray(refs)||refs.length>8||refs.some(id=>!Number.isInteger(id)))throw Error('Invalid communication evidence');
   const visibleIds=new Set(this.lookup(seat).map(e=>e.id));if(refs.some(id=>!visibleIds.has(id)))throw Error('Communication cites non-visible evidence');
   const claims=communication.identityClaims||[];if(!Array.isArray(claims)||claims.length>4)throw Error('Invalid identity claims');
   const publicAction=['announcement','nominate','slay'].includes(response.action)||task.kind==='defense';
   const privateAction=response.action==='whisper'||task.kind==='whisper_reply';
   if((claims.length||refs.length)&&!publicAction&&!privateAction)throw Error('Communication metadata requires a delivered message action');
   const target=response.players?.[0]||task.recipient;
   for(const claim of claims){
    if(!claim||typeof claim!=='object'||!this.players.has(claim.subject)||!Object.hasOwn(names,claim.claimedRole))throw Error('Invalid structured identity claim');
   }
   if(claims.length){
    const event=this.observe({visibility:publicAction?'public':'private',...(privateAction?{audience:[seat,target].filter((x,i,a)=>x&&a.indexOf(x)===i)}:{}),type:'structured_communication',actor:seat,day:task.day,night:task.night,text:String(response.message||'').slice(0,300),communication:{intent:String(communication.intent||'none').slice(0,80),identityClaims:claims,evidenceRefs:refs}});
    for(const [viewer,vm] of this.players){
     if(event.visibility==='private'&&!event.audience.includes(viewer))continue;
     for(const claim of claims){
      const value={role:claim.claimedRole,kind:'claim',confirmed:false,source:event.id,day:task.day,text:event.text,structured:true};
      if(publicAction)vm.publicClaims[claim.subject]=value;else vm.privateClaims[claim.subject]={...value,context:communication.intent||'none'};
     }
    }
   }
  }
  if(task.kind==='night'){
   m.ability.lastNightChoice={night:task.night,targets:response.players||[]};
   this.observe({visibility:'private',audience:[seat],type:'choice',actor:seat,night:task.night,text:`N${task.night}: selected ${(response.players||[]).join(',')}`});
  }
  if(response.action==='slay')m.ability.slayerUsed=true;
  if(task.kind==='discussion'&&response.action==='whisper'&&response.communicationIntent){m.privateClaims[response.players?.[0]]={day:task.day,claimed_role:response.communicationIntent.claimed_role||null,claimed_role_type:response.communicationIntent.claimed_role_type||null,exact_or_partial:response.communicationIntent.exact_or_partial||'partial',context:response.communicationIntent.intent};}
  // Only explicit bounded memory updates are retained; reasoning and control JSON are audit-only.
  const patch=response.memoryUpdate;if(patch){
   if(!Array.isArray(patch.beliefs)||patch.beliefs.length>12||!Array.isArray(patch.plan)||patch.plan.length>5||!Array.isArray(patch.worlds)||patch.worlds.length>5)throw Error('Invalid memory update');
   for(const b of patch.beliefs){if(!this.players.has(b.player)||typeof b.summary!=='string'||b.summary.length>240)throw Error('Invalid belief');m.beliefs[b.player]={kind:'belief',summary:b.summary};}
   for(const k of ['plan','worlds']){if(patch[k].some(x=>typeof x!=='string'||x.length>240))throw Error('Invalid memory text');m[k]=[...patch[k]];}
  }
 }
 compact(day){for(const [seat,m] of this.players){
  const visible=this.lookup(seat,{day}).filter(e=>['death','execution','ability','nomination','vote'].includes(e.type));
  m.summaries=m.summaries.filter(s=>s.day!==day);
  m.summaries.push({day,eventIds:visible.map(e=>e.id),deaths:visible.filter(e=>['death','execution'].includes(e.type)).map(e=>e.text),nominations:visible.filter(e=>e.type==='nomination').map(e=>e.text)});
  m.summaries=m.summaries.slice(-6);m.privateConversations=m.privateConversations.slice(-5);
 }}
 lookup(seat,{type,actor,day,limit}={}){
  if(!this.players.has(seat))throw Error('Unknown requesting seat');
  let list=this.events.filter(e=>(e.visibility==='public'||e.audience.includes(seat))&&(!type||e.type===type)&&(!actor||e.actor===actor)&&(day===undefined||e.day===day));
  return clone(limit?list.slice(-Math.min(limit,30)):list);
 }
 snapshot(){return clone({version:2,nextId:this.nextId,events:this.events,players:[...this.players],social:this.social});}
 restore(s){if(s.version!==2)throw Error('Unsupported snapshot');this.nextId=s.nextId;this.events=clone(s.events);this.players=new Map(clone(s.players));this.social=clone(s.social);}
 save(file){fs.writeFileSync(file,JSON.stringify(this.snapshot()));}
}
module.exports={SemanticStore};
