import type { NightGameCtx } from '../roles/types';
import type { NightOutcomeDraft } from './types';
import { legalRegistrations } from '../utils/roleDetection';
type Choice = Record<string,string|number|boolean>;
let policy: ((ctx:NightGameCtx, choices:Choice[])=>Promise<number>)|undefined;
export function setInformationGenerator(next:typeof policy){policy=next;}
async function choose(ctx:NightGameCtx,choices:Choice[]):Promise<Choice>{
 if(!choices.length)throw Error('No legal information options');
 if(choices.length===1)return choices[0];
 const index=await policy!(ctx,choices);
 if(!Number.isInteger(index)||index<0||index>=choices.length)throw Error('ST selected invalid information');
 return choices[index];
}
function rolesFor(ctx:NightGameCtx,targetId:string){
 const p=ctx.state.runtime.playerStates.find(p=>p.player.userId===targetId)!;
 const cats=legalRegistrations(p.role,p.tags.has('poisoned')).map(x=>x.split('_')[1]);
 return ctx.night.scriptRoles.filter(r=>r.id===p.role.id||((p.role.id==='spy'||p.role.id==='recluse')&&r.category!==p.role.category&&cats.includes(r.category.toLowerCase()))).map(r=>r.id);
}
export async function generateRoleInformation(ctx:NightGameCtx,target:string):Promise<string|undefined>{
 if(!policy)return undefined;
 const self=ctx.state.runtime.playerStates.find(p=>p.player.userId===ctx.night.player.userId)!;
 const ids=self.role.id==='drunk'||self.tags.has('poisoned')?ctx.night.scriptRoles.map(r=>r.id):rolesFor(ctx,target);
 return String((await choose(ctx,ids.map(role=>({target,role})))).role);
}
export async function generatePair(ctx:NightGameCtx):Promise<NightOutcomeDraft|null|undefined>{
 if(!policy)return undefined;
 const self=ctx.state.runtime.playerStates.find(p=>p.player.userId===ctx.night.player.userId)!;
 const category=({washerwoman:'Townsfolk',librarian:'Outsider',investigator:'Minion'} as Record<string,string>)[self.effectiveRole.id];
 const falseInfo=self.role.id==='drunk'||self.tags.has('poisoned');
 if(!category){
  const roster=ctx.state.runtime.playerStates;
  const id=self.effectiveRole.id;
  const result=(templateId:NightOutcomeDraft['templateId'],fields:Choice):NightOutcomeDraft=>({templateId,fields,fieldTypes:{},allowArbitraryOverride:false});
  const alignments=(p:typeof self)=>[...new Set(legalRegistrations(p.role,p.tags.has('poisoned')).map(x=>x.startsWith('evil_')))];
  if(id==='undertaker'){
   const target=roster.find(p=>p.death?.byExecution&&p.death.dayNumber===ctx.state.runtime.daySession?.dayNumber);
   if(!target)return null;
   return result('undertaker_role',{role:(await generateRoleInformation(ctx,target.player.userId))!});
  }
  if(id==='spy'){
   const fields:Choice={};
   for(const p of roster)fields[p.player.displayName]=falseInfo?String((await choose(ctx,ctx.night.scriptRoles.map(r=>({seat:p.player.userId,role:r.id})))).role):p.role.id;
   return result('grimoire',fields);
  }
  if(id==='fortune_teller'){
   const targets=(ctx.night.responses.get(self.player.userId)||[]).filter(Boolean) as string[];
   const flags=targets.map(t=>{const p=roster.find(p=>p.player.userId===t)!;return p.tags.has('red_herring')?[true]:[...new Set(legalRegistrations(p.role,p.tags.has('poisoned')).map(x=>x==='evil_demon'))];});
   let values=[false];for(const f of flags)values=[...new Set(values.flatMap(a=>f.map(b=>a||b)))];
   return result('fortune_result',await choose(ctx,(falseInfo?[false,true]:values).map(yes=>({yes}))));
  }
  if(id==='chef'||id==='empath'){
   let sets:boolean[][]=[[]];let subjects=roster;const fixed:Choice={};
   if(id==='empath'){
    const ix=roster.indexOf(self),neighbor=(dir:number)=>{for(let n=1;n<roster.length;n++){const p=roster[(ix+dir*n+roster.length)%roster.length];if(p.alive)return p;}return self;};
    subjects=[neighbor(-1),neighbor(1)];fixed.left=subjects[0].player.userId;fixed.right=subjects[1].player.userId;
   }
   for(const p of subjects)sets=sets.flatMap(a=>alignments(p).map(b=>[...a,b]));
   const counts=[...new Set(sets.map(a=>id==='empath'?a.filter(Boolean).length:a.filter((v,i)=>v&&a[(i+1)%a.length]).length))];
   const values=falseInfo?Array.from({length:id==='empath'?3:roster.length+1},(_,i)=>i):counts;
   return result(id==='chef'?'chef_count':'empath_count',{...fixed,...await choose(ctx,values.map(count=>({count})))});
  }
  throw Error('Information generator missing for '+id);
 }
 const roles=ctx.night.scriptRoles.filter(r=>r.category===category);
 const roster=ctx.state.runtime.playerStates;
 const choices:Choice[]=[];
 for(let i=0;i<roster.length;i++)for(let j=i+1;j<roster.length;j++)for(const role of roles){
  const pair=[roster[i],roster[j]];
  const canMatch=(p:typeof self)=>p.role.id===role.id||((p.role.id==='spy'||p.role.id==='recluse')&&legalRegistrations(p.role,p.tags.has('poisoned')).some(r=>r.endsWith('_'+category.toLowerCase())));
  if(falseInfo||pair.some(canMatch))choices.push({p1:pair[0].player.userId,p2:pair[1].player.userId,role:role.id});
 }
 if(category==='Outsider'&&(falseInfo||!roster.some(p=>p.role.category==='Outsider')))choices.push({noOutsiders:true});
 if(!choices.length)throw Error('No legal pair information');
 const selected=await choose(ctx,choices);
 if(selected.noOutsiders)return null;
 return {templateId:'pair_role_info',fields:{...selected},fieldTypes:{},constraints:{pairCategory:category},allowArbitraryOverride:false,reasonKey:falseInfo?'nightReasonFalseInfo':'nightReasonDecoyPair'};
}
