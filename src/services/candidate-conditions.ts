import type { CandidateConditionCatalog, CandidateConditionInput } from '@/api/candidate-conditions'
import { conditionIssues, operandFor } from '@/services/feature-authoring'
export function emptyCandidateCondition(candidateId:string):CandidateConditionInput {
  return {candidate_id:candidateId,label:'',feature_id:'',op:'',operand:{},subject_entity_id:null,zone:null,mode:'expected',description:'',source_assertion_ids:[]}
}
export function selectConditionFeature(input:CandidateConditionInput, featureId:string, catalog:CandidateConditionCatalog):CandidateConditionInput {
  const feature=catalog.features.find(row=>row.feature_id===featureId)
  if (!feature) return {...input,feature_id:featureId,op:'',operand:{},subject_entity_id:null}
  const op=feature.allowed_operators[0]??''
  return {...input,feature_id:featureId,op,operand:operandFor(feature,op),subject_entity_id:feature.subject_kind==='variable'?input.subject_entity_id:null}
}
export function candidateConditionIssues(input:CandidateConditionInput,catalog:CandidateConditionCatalog):string[] {
  const issues:string[]=[], feature=catalog.features.find(row=>row.feature_id===input.feature_id)
  if (!input.label.trim()) issues.push('请给这个诊断条件一个可读名称。')
  if (!feature) return [...issues,'请选择本图可用的测量特征。']
  issues.push(...conditionIssues(input as unknown as Record<string,unknown>,feature))
  if (!feature.allowed_operators.includes(input.op)) issues.push('该判断方式不在后端允许范围内。')
  if (feature.subject_kind==='variable' && !catalog.subjects.some(row=>row.entity_id===input.subject_entity_id)) issues.push('请选择图谱中已绑定的变量；未知变量不能自动创建绑定。')
  if (feature.subject_kind==='focus' && input.subject_entity_id) issues.push('这个特征使用当前关注对象，不需要指定过程变量。')
  if (catalog.zones.length && !catalog.zones.includes(input.zone??'')) issues.push('请选择这个条件适用的晶圆区域。')
  if (!['expected','necessary','possible'].includes(input.mode)) issues.push('请选择已有的期待关系模式。')
  return [...new Set(issues)]
}
