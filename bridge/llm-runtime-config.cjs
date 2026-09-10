const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const personalityDefaults = Object.freeze({
  activity: .50, openness: .50, aggression: 2.5 / 6, riskTolerance: 2.5 / 5.5,
  deceptionTendency: 2 / 6, trustPropensity: 3.5 / 6.5, conformity: .50,
  stubbornness: 2.5 / 5.5, confidence: .50, socialInitiative: .50,
});
const skillPresets = Object.freeze({
  beginner: { score:.25, beliefAccuracy:.60, decisionTemperature:1.8, memoryRetention:.65, votingDiscipline:.45, bluffConsistency:.45 },
  intermediate: { score:.50, beliefAccuracy:.78, decisionTemperature:1.2, memoryRetention:1, votingDiscipline:.70, bluffConsistency:.70 },
  experienced: { score:.75, beliefAccuracy:.90, decisionTemperature:.8, memoryRetention:1.35, votingDiscipline:.88, bluffConsistency:.88 },
  expert: { score:.95, beliefAccuracy:.98, decisionTemperature:.5, memoryRetention:1.8, votingDiscipline:.98, bluffConsistency:.96 },
});
const defaults = Object.freeze({
  protocolVersion:'semantic-v3',
  models:{ player:'gpt-5.6-luna', storyteller:'gpt-6-astra' },
  reasoningEffort:{ player:'medium', storyteller:'high' },
  generation:{ temperature:.7, topP:.95, topK:40, maxOutputTokens:1200 },
  storyteller:{objectives:{fairness:.25,tension:.25,solvability:.25,drama:.25},temperature:.5,interventionPenalty:.05,historyWindow:8},
  limits:{ maxCalls:1000, maxAttempts:3, timeoutMs:180000, contextTokens:{ light:4000, player:12000, storyteller:14000 } },
  population:{ dispersionKappa:6, personality:personalityDefaults, skillWeights:{ beginner:.20, intermediate:.45, experienced:.25, expert:.10 } },
});
function merge(base, extra) {
  if (!extra || typeof extra !== 'object' || Array.isArray(extra)) return extra === undefined ? base : extra;
  const out={...(base||{})}; for(const [k,v] of Object.entries(extra))out[k]=v&&typeof v==='object'&&!Array.isArray(v)?merge(out[k],v):v; return out;
}
function number(value,label,min,max){assert(Number.isFinite(value)&&value>=min&&value<=max,`${label} must be in [${min}, ${max}]`);}
function validate(config){
  const allowed={protocolVersion:1,models:{player:1,storyteller:1},reasoningEffort:{player:1,storyteller:1},generation:{temperature:1,topP:1,topK:1,maxOutputTokens:1},limits:{maxCalls:1,maxAttempts:1,timeoutMs:1,contextTokens:{light:1,player:1,storyteller:1}},population:{dispersionKappa:1,personality:Object.fromEntries(Object.keys(personalityDefaults).map(k=>[k,1])),skillWeights:Object.fromEntries(Object.keys(skillPresets).map(k=>[k,1]))},storyteller:{objectives:{fairness:1,tension:1,solvability:1,drama:1},temperature:1,interventionPenalty:1,historyWindow:1},players:1};
  function strict(value,schema,label){assert(value&&typeof value==='object'&&!Array.isArray(value),`${label} must be an object`);for(const key of Object.keys(value)){assert(!['__proto__','prototype','constructor'].includes(key),`unsafe key ${label}.${key}`);assert(key in schema,`unknown config key ${label}.${key}`);if(schema[key]&&typeof schema[key]==='object')strict(value[key],schema[key],`${label}.${key}`);}}
  strict(config,allowed,'config');
  assert.equal(config.protocolVersion,'semantic-v3','unsupported protocolVersion');
  for(const k of ['player','storyteller']){assert(typeof config.models[k]==='string'&&config.models[k],`models.${k} required`);assert(['low','medium','high','xhigh'].includes(config.reasoningEffort[k]),`invalid reasoningEffort.${k}`);}
  number(config.generation.temperature,'generation.temperature',0,2);number(config.generation.topP,'generation.topP',0,1);number(config.generation.topK,'generation.topK',1,1000);number(config.generation.maxOutputTokens,'generation.maxOutputTokens',64,65536);
  for(const k of ['maxCalls','maxAttempts','timeoutMs'])assert(Number.isInteger(config.limits[k]),`limits.${k} must be an integer`);for(const [k,v] of Object.entries(config.limits.contextTokens))assert(Number.isInteger(v),`limits.contextTokens.${k} must be an integer`);
  number(config.limits.maxCalls,'limits.maxCalls',1,100000);number(config.limits.maxAttempts,'limits.maxAttempts',1,10);number(config.limits.timeoutMs,'limits.timeoutMs',1000,900000);
  for(const [k,v] of Object.entries(config.limits.contextTokens))number(v,`limits.contextTokens.${k}`,500,200000);
  number(config.population.dispersionKappa,'population.dispersionKappa',1.5,100);
  for(const [k,v] of Object.entries(config.population.personality))number(v,`population.personality.${k}`,0.01,.99);
  let total=0;for(const [k,v] of Object.entries(config.population.skillWeights)){assert(skillPresets[k],`unknown skill level ${k}`);number(v,`population.skillWeights.${k}`,0,1);total+=v;}assert(total>0,'skill weights must have positive mass');
  let objectiveTotal=0;for(const [k,v] of Object.entries(config.storyteller.objectives)){number(v,`storyteller.objectives.${k}`,0,1);objectiveTotal+=v;}assert(Math.abs(objectiveTotal-1)<1e-9,'storyteller objectives must sum to 1');number(config.storyteller.temperature,'storyteller.temperature',0,2);number(config.storyteller.interventionPenalty,'storyteller.interventionPenalty',0,1);number(config.storyteller.historyWindow,'storyteller.historyWindow',1,100);assert(Number.isInteger(config.storyteller.historyWindow),'storyteller.historyWindow must be integer');
  if(config.players)for(const [actor,p] of Object.entries(config.players)){assert(/^P\d{2}$/.test(actor),`invalid player override ${actor}`);assert(p&&typeof p==='object'&&!Array.isArray(p),`${actor} override must be object`);for(const k of Object.keys(p))assert(['skillLevel','personality','skill'].includes(k),`unknown ${actor}.${k}`);if(p.skillLevel)assert(skillPresets[p.skillLevel],`invalid ${actor}.skillLevel`);if(p.personality)for(const [k,v] of Object.entries(p.personality)){assert(k in personalityDefaults,`unknown personality ${k}`);number(v,`${actor}.${k}`,0,1);}if(p.skill)for(const [k,v] of Object.entries(p.skill)){assert(k in skillPresets.expert,`unknown ${actor}.skill.${k}`);number(v,`${actor}.skill.${k}`,k==='decisionTemperature'?.2:k==='memoryRetention'?.3:.2,k==='decisionTemperature'?3:k==='memoryRetention'?2:1);}}
  return config;
}
function loadRuntimeConfig(env=process.env){
  let file={};if(env.BOTC_LLM_CONFIG){const filename=path.resolve(env.BOTC_LLM_CONFIG);file=JSON.parse(fs.readFileSync(filename,'utf8'));const scan=(v,label='config')=>{if(!v||typeof v!=='object')return;for(const k of Object.keys(v)){assert(!['__proto__','prototype','constructor'].includes(k),`unsafe key ${label}.${k}`);scan(v[k],`${label}.${k}`);}};scan(file);}
  const overrides={models:{player:env.BOTC_PLAYER_MODEL,storyteller:env.BOTC_ST_MODEL},reasoningEffort:{player:env.BOTC_PLAYER_EFFORT,storyteller:env.BOTC_ST_EFFORT},limits:{maxCalls:env.BOTC_MAX_CALLS&&Number(env.BOTC_MAX_CALLS),maxAttempts:env.BOTC_MODEL_ATTEMPTS&&Number(env.BOTC_MODEL_ATTEMPTS),timeoutMs:env.BOTC_CODEX_TIMEOUT_MS&&Number(env.BOTC_CODEX_TIMEOUT_MS)}};
  function clean(x){if(!x||typeof x!=='object')return x;for(const k of Object.keys(x)){if(x[k]===undefined)delete x[k];else clean(x[k]);}return x;}
  return validate(merge(merge(merge({},defaults),file),clean(overrides)));
}
function rngFor(seed,label){let state=crypto.createHash('sha256').update(`${seed}:${label}`).digest().readUInt32LE(0);return()=>{state=(Math.imul(1664525,state)+1013904223)>>>0;return (state+.5)/4294967296;};}
function normal(r){const u=Math.max(Number.EPSILON,r()),v=r();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);}
function gamma(shape,r){if(shape<1)return gamma(shape+1,r)*Math.pow(r(),1/shape);const d=shape-1/3,c=1/Math.sqrt(9*d);for(;;){let x=normal(r),v=1+c*x;if(v<=0)continue;v=v*v*v;const u=r();if(u<1-.0331*x*x*x*x||Math.log(u)<.5*x*x+d*(1-v+Math.log(v)))return d*v;}}
function beta(mean,kappa,r){const a=Math.max(.1,mean*kappa),b=Math.max(.1,(1-mean)*kappa),x=gamma(a,r);return x/(x+gamma(b,r));}
function createPlayerProfiles(config,actors,seed){
  const out={};for(const actor of actors){const r=rngFor(seed,actor),override=config.players?.[actor]||{},weights=config.population.skillWeights,roll=r()*Object.values(weights).reduce((a,b)=>a+b,0);let sum=0,level='intermediate';for(const [k,v] of Object.entries(weights)){sum+=v;if(roll<=sum){level=k;break;}}level=override.skillLevel||level;
    const personality={};for(const [k,mu] of Object.entries(config.population.personality))personality[k]=Number((override.personality?.[k]??beta(mu,config.population.dispersionKappa,r)).toFixed(3));
    out[actor]={personality,skill:{level,...skillPresets[level],...(override.skill||{})}};
  }return out;
}
module.exports={defaults,skillPresets,loadRuntimeConfig,createPlayerProfiles,validate};
