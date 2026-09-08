const clamp=x=>Math.max(0,Math.min(1,x));
function socialView(store){
 const publicMemory=store.players.get('Storyteller');const claims=publicMemory?.publicClaims||{};
 const suspicion={};for(const seat of Object.keys(claims))suspicion[seat]=clamp(((store.social.nominations[seat]||0)*2+(store.social.votes[seat]||0))/12);
 return {claims,trustGraph:{},suspicion,dominantWorlds:[],likelyExecution:Object.entries(suspicion).sort((a,b)=>b[1]-a[1])[0]?.[0]||null,bluffCoherence:Object.fromEntries(Object.keys(claims).map(s=>[s,{status:'unverified public claim',source:claims[s].source}])),chatEdges:{...store.social.chatEdges},method:'deterministic public-signal heuristic; not calibrated'};
}
function estimateBalance(view){
 if(view.balance)return view.balance;
 const alive=view.grimoire.filter(p=>p.alive),evil=alive.filter(p=>['imp','poisoner','spy','baron','scarlet_woman'].includes(p.role));
 const demon=evil.find(p=>p.role==='imp'),pressure=demon?(view.social?.suspicion?.[demon.seat]||0):1;
 const ongoingInfo=alive.filter(p=>['empath','fortune_teller','undertaker'].includes(p.role)).length;
 const goodAdvantage=clamp(.42+ongoingInfo*.06+pressure*.18-(evil.length/Math.max(alive.length,1))*.15);
 return {goodAdvantage,evilAdvantage:1-goodAdvantage,confidence:.25,reasons:['alive information roles','public nomination/vote pressure','alive alignment ratio'],calibrated:false};
}
function scoreChoices(view,decision,recent=[]){
 const balance=estimateBalance(view),demon=view.grimoire.find(p=>p.alive&&p.role==='imp');
 const alive=view.grimoire.filter(p=>p.alive),index=alive.findIndex(p=>p.seat===decision.actor);
 const adjacent=index>=0?[alive[(index+alive.length-1)%alive.length]?.seat,alive[(index+1)%alive.length]?.seat]:[];
 const bluffSupported=demon&&view.social?.claims?.[demon.seat]?.role==='monk'&&adjacent.includes(demon.seat);
 return decision.legalOptions.map((option,index)=>{
  const supports=decision.template==='empath_count'&&option===0&&bluffSupported;
  const helpsWeaker=!!supports&&balance.goodAdvantage>.5;
  const balanceScore=helpsWeaker?.25:0,coherence=supports?.12:0,overIntervention=recent.filter(r=>r.actor===decision.actor).length*.05;
  return {option,score:balanceScore+coherence-overIntervention-index*.001,dimensions:{balance:balanceScore,coherence,ambiguity:.1,playerAgency:.1,hardConfirmation:0,overIntervention},predictedEffect:{supports_demon_bluff:!!supports,hard_confirmation:false,helps_weaker_team:helpsWeaker}};
 });
}
class StorytellerAgent{
 constructor({model,log=()=>{},timeoutMs=181000}={}){this.model=model;this.log=log;this.timeoutMs=timeoutMs;this.recent=[];}
 chooseSync(view,decision){return this.finish(view,decision,null,'deterministic policy');}
 finish(view,decision,modelChoice,reason){
  if(!Array.isArray(decision.legalOptions)||!decision.legalOptions.length)throw Error('Empty legal options');
  const scores=scoreChoices(view,decision,this.recent).sort((a,b)=>b.score-a.score);
  const selected=decision.legalOptions.includes(modelChoice)?scores.find(s=>s.option===modelChoice):scores[0];
  const record={decision:decision.type,actor:decision.actor,template:decision.template,legalOptions:decision.legalOptions,chosen:selected.option,reason,balance:estimateBalance(view),scores,predictedEffect:selected.predictedEffect};
  this.recent.push({actor:decision.actor,chosen:selected.option});this.recent=this.recent.slice(-8);this.log('storyteller_legal_decision',record);return selected.option;
 }
 async decide(view,decision){
  if(!this.model)return this.chooseSync(view,decision);
  let timer;try{
   const result=await Promise.race([this.model(view,decision),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('timeout')),this.timeoutMs);})]);
   const response=typeof result==='string'?JSON.parse(result):result;
   if(!response||!decision.legalOptions.includes(response.choice)||typeof response.reason!=='string')throw Error('invalid choice/schema');
   return this.finish(view,decision,response.choice,response.reason);
  }catch(error){return this.finish(view,decision,null,'legal deterministic fallback: '+error.message);}finally{clearTimeout(timer);}
 }
}
module.exports={StorytellerAgent,socialView,estimateBalance,scoreChoices};
