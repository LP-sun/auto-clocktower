import type { GameState, NightOutcomeDraft } from "./types";
import { getScript } from "./roles";
export type LegalValue = string | number | boolean;
export interface LegalDecision { type: "misinformation" | "death_redirect"; actor: string; field?: string; template?: string; legalOptions: LegalValue[]; }
let policy: ((state: GameState, decision: LegalDecision) => Promise<LegalValue>) | undefined;
export function setDiscretionPolicy(next?: typeof policy): void {policy=next;}
export async function decideLegal(state: GameState, decision: LegalDecision): Promise<LegalValue> {
 if(!decision.legalOptions.length)throw new Error("Empty legal decision");
 if(policy){try{const value=await policy(state,{...decision,legalOptions:[...decision.legalOptions]});if(decision.legalOptions.includes(value))return value;}catch{ /* deterministic legal fallback */ }}
 return decision.legalOptions[0];
}
/** Only values the engine marks editable; fixed information never enters the override. */
export function informationDecisions(state: GameState, actor: string, draft: NightOutcomeDraft): LegalDecision[] {
 const p=state.runtime?.playerStates.find(p=>p.player.userId===actor);
 if(!p || !(p.role.id==='drunk'||p.tags.has('poisoned')) || !draft.allowArbitraryOverride)return [];
 const out:LegalDecision[]=[];
 for(const [field,type] of Object.entries(draft.fieldTypes)){
  let options:LegalValue[]=[];
  if(type==='boolean')options=[false,true];
  if(type==='number')options=draft.templateId==='empath_count'?[0,1,2]:Array.from({length:state.players.length+1},(_,i)=>i);
  if(type==='role')options=getScript().roles.filter(r=>!draft.constraints?.pairCategory||r.category===draft.constraints.pairCategory).map(r=>r.id);
  if(type==='player')options=state.players.filter(p=>!(['p1','p2'].includes(field)&&p.userId===draft.fields[field==='p1'?'p2':'p1'])).map(p=>p.userId);
  if(options.length)out.push({type:'misinformation',actor,field,template:draft.templateId,legalOptions:options});
 }
 return out;
}
