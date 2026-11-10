import { request, type AuthoringFeature, type GraphSummary, type RecordValue } from '@/api/workbench'
export interface CandidateConditionFeature extends AuthoringFeature { allowed_operators:string[]; subject_kind:'variable'|'focus' }
export interface CandidateConditionInput {
  candidate_id:string; label:string; feature_id:string; op:string; operand:RecordValue
  subject_entity_id:string|null; zone:string|null; mode:'necessary'|'expected'|'possible'
  description:string; source_assertion_ids:string[]
}
export interface CandidateCondition extends CandidateConditionInput {
  condition_id:string; predicate_id:string; pattern_id:string; expectation_rule_id:string
  anomaly_gate_id:string; can_delete:boolean; delete_blocker:string|null
}
export interface CandidateConditionCatalog {
  conditions:CandidateCondition[]; features:CandidateConditionFeature[]
  subjects:Array<{entity_id:string;label:string;external_id:string}>; zones:string[]
}
export function candidateConditionsApi(base:string, graphId:string) {
  const path=`/api/kg/working-graphs/${encodeURIComponent(graphId)}/candidate-conditions`
  return {
    catalog:()=>request<CandidateConditionCatalog>(base,path),
    add:(body:CandidateConditionInput)=>request<{graph:GraphSummary;conditions:CandidateCondition[]}>(base,path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
    remove:(id:string)=>request<{graph:GraphSummary;conditions:CandidateCondition[]}>(base,`${path}/${encodeURIComponent(id)}`,{method:'DELETE'}),
  }
}
