'use strict';
const clamp=x=>Math.max(0,Math.min(1,x));
const DEFAULT_STORYTELLER_PARAMETERS=Object.freeze({schemaVersion:1,objectives:Object.freeze({fairness:.25,tension:.25,solvability:.25,drama:.25}),temperature:.5,interventionPenalty:.05,historyWindow:8});
function finite(name,value,{min=0,max=1}={}){if(typeof value!=='number'||!Number.isFinite(value)||value<min||value>max)throw new TypeError(`${name} must be a finite number in [${min}, ${max}]`);return value;}
function storytellerParameters(overrides={}){
 if(overrides===null||typeof overrides!=='object'||Array.isArray(overrides))throw new TypeError('storyteller parameters must be an object');
 const knownObjectives=Object.keys(DEFAULT_STORYTELLER_PARAMETERS.objectives);
 for(const name of Object.keys(overrides.objectives||{}))if(!knownObjectives.includes(name))throw new TypeError(`unknown storyteller objective: ${name}`);
 const objectives={...DEFAULT_STORYTELLER_PARAMETERS.objectives,...(overrides.objectives||{})};
 for(const [name,value] of Object.entries(objectives))finite(`objectives.${name}`,value,{min:0,max:Number.MAX_VALUE});
 const total=Object.values(objectives).reduce((sum,value)=>sum+value,0);if(total<=0)throw new TypeError('at least one storyteller objective must have positive weight');
 for(const name of Object.keys(objectives))objectives[name]/=total;
 const result={schemaVersion:1,objectives,temperature:finite('temperature',overrides.temperature??.5,{min:0,max:2}),interventionPenalty:finite('interventionPenalty',overrides.interventionPenalty??.05),historyWindow:overrides.historyWindow??8};
 if(!Number.isInteger(result.historyWindow)||result.historyWindow<0||result.historyWindow>100)throw new TypeError('historyWindow must be an integer in [0, 100]');
 return Object.freeze({...result,objectives:Object.freeze(objectives)});
}
function socialView(store){
 const publicMemory=store.players.get('Storyteller');const claims=publicMemory?.publicClaims||{};const suspicion={};
 for(const seat of Object.keys(claims))suspicion[seat]=clamp(((store.social.nominations[seat]||0)*2+(store.social.votes[seat]||0))/12);
 return {claims,trustGraph:{},suspicion,dominantWorlds:[],likelyExecution:Object.entries(suspicion).sort((a,b)=>b[1]-a[1])[0]?.[0]||null,bluffCoherence:Object.fromEntries(Object.keys(claims).map(s=>[s,{status:'unverified public claim',source:claims[s].source}])),chatEdges:{...store.social.chatEdges},method:'deterministic public-signal heuristic; not calibrated'};
}
function estimateBalance(view){
 if(view.balance)return view.balance;const alive=view.grimoire.filter(p=>p.alive),evil=alive.filter(p=>['imp','poisoner','spy','baron','scarlet_woman'].includes(p.role));
 const demon=evil.find(p=>p.role==='imp'),pressure=demon?(view.social?.suspicion?.[demon.seat]||0):1,ongoingInfo=alive.filter(p=>['empath','fortune_teller','undertaker'].includes(p.role)).length;
 const goodAdvantage=clamp(.42+ongoingInfo*.06+pressure*.18-(evil.length/Math.max(alive.length,1))*.15);
 return {goodAdvantage,evilAdvantage:1-goodAdvantage,confidence:.25,reasons:['alive information roles','public nomination/vote pressure','alive alignment ratio'],calibrated:false};
}
function decisionRequest(view,decision,parameters=storytellerParameters(),recent=[]){
 if(!Array.isArray(decision.legalOptions)||!decision.legalOptions.length)throw Error('Empty legal options');
 const choices=decision.legalOptions.map((value,index)=>({id:String(index),value}));
 const {legalOptions,...description}=decision;
 return {kind:'storyteller_decision',schemaVersion:1,parameters,decision:{...description,choices},context:{grimoire:view.grimoire||[],social:view.social||{},balance:estimateBalance({...view,grimoire:view.grimoire||[]}),recentDecisions:recent},constraints:{chooseExactlyOne:true,legalChoiceIds:choices.map(x=>x.id),engineIsAuthoritative:true}};
}
function parseModelChoice(response,decision){
 if(!response||typeof response!=='object')throw Error('invalid response schema');let index=-1;
 if(typeof response.choiceId==='string'&&/^\d+$/.test(response.choiceId))index=Number(response.choiceId);else if(Object.hasOwn(response,'choice'))index=decision.legalOptions.findIndex(value=>Object.is(value,response.choice));
 if(!Number.isInteger(index)||index<0||index>=decision.legalOptions.length)throw Error('invalid legal choice ID');
 const reasoning=response.reasoning??response.reason;if(typeof reasoning!=='string'||!reasoning.trim())throw Error('missing reasoning');
 return {index,reasoning,reasonCodes:Array.isArray(response.reasonCodes)?response.reasonCodes.filter(x=>typeof x==='string'):[]};
}
class StorytellerAgent{
 constructor({model,log=()=>{},timeoutMs=181000,parameters,failureMode=model?'throw':'first_legal'}={}){if(!['throw','first_legal'].includes(failureMode))throw new TypeError('failureMode must be throw or first_legal');this.model=model;this.log=log;this.timeoutMs=timeoutMs;this.parameters=storytellerParameters(parameters);this.failureMode=failureMode;this.recent=[];}
 request(view,decision){return decisionRequest(view,decision,this.parameters,this.recent);}
 finish(decision,index,reasoning,reasonCodes=[],request){
  const chosen=decision.legalOptions[index],record={schemaVersion:1,decision:decision.type,actor:decision.actor,template:decision.template,legalOptions:decision.legalOptions,chosen,choiceId:String(index),reasoning,reasonCodes,parameters:this.parameters,balance:request.context.balance,modelDriven:!reasoning.startsWith('deterministic legal fallback:')};
  if(this.parameters.historyWindow>0){this.recent.push({decision:decision.type,actor:decision.actor,choiceId:String(index)});this.recent=this.recent.slice(-this.parameters.historyWindow);}else this.recent=[];
  this.log('storyteller_legal_decision',record);return chosen;
 }
 async decide(view,decision){
  const request=this.request(view,decision);if(!this.model)return this.finish(decision,0,'deterministic legal fallback: no model configured',[],request);
  let timer;try{const result=await Promise.race([this.model(request),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('timeout')),this.timeoutMs);})]);const response=typeof result==='string'?JSON.parse(result):result;const parsed=parseModelChoice(response,decision);return this.finish(decision,parsed.index,parsed.reasoning,parsed.reasonCodes,request);}catch(error){this.log('storyteller_model_failure',{schemaVersion:1,decision:decision.type,actor:decision.actor,error:error.message,failureMode:this.failureMode});if(this.failureMode==='throw')throw error;return this.finish(decision,0,'deterministic legal fallback: '+error.message,[],request);}finally{clearTimeout(timer);}
 }
}
module.exports={DEFAULT_STORYTELLER_PARAMETERS,StorytellerAgent,socialView,estimateBalance,storytellerParameters,decisionRequest,parseModelChoice};
