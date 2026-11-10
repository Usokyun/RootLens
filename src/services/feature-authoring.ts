import type { AuthoringCapability, AuthoringFeature, RecordValue } from '@/api/workbench'
import { clone, featureNames, friendly, record, rows, text, texts } from '@/services/presentation'

export interface FeatureChoice extends AuthoringFeature { producerDeclared: boolean; registered: boolean; allowed_operators?: string[] }
export function featureChoices(knowledge: RecordValue, capability: AuthoringCapability | null): FeatureChoice[] {
  const registered = rows(knowledge.feature_registry)
  const choices = new Map<string, FeatureChoice>()
  registered.forEach((feature) => choices.set(text(feature.feature_id), { ...feature, producerDeclared:false, registered:true } as FeatureChoice))
  capability?.features.forEach((feature) => choices.set(feature.feature_id, { ...feature, producerDeclared:true, registered:registered.some((row) => row.feature_id === feature.feature_id) }))
  return [...choices.values()]
}
export function featureLabel(feature: Pick<AuthoringFeature,'feature_id'|'value_kind'|'unit'>) {
  const kind = ({number:'数值',boolean:'是 / 否',category:'类别',candidate_set:'候选集合',interval:'区间',array_ref:'数组引用'} as Record<string,string>)[feature.value_kind] ?? feature.value_kind
  return `${featureNames[feature.feature_id] ?? friendly(feature.feature_id)} · ${kind}${feature.unit && feature.unit !== '1' ? ` / ${feature.unit}` : ''}`
}
export function operatorsFor(feature?: Pick<AuthoringFeature,'value_kind'>): string[] {
  return ({number:['gte','lte','abs_gte','eq'],boolean:['bool_eq','eq'],category:['eq','in'],candidate_set:['candidate_contains','intersects']} as Record<string,string[]>)[feature?.value_kind ?? ''] ?? []
}
export function operandFor(feature: AuthoringFeature, op: string): RecordValue {
  if (op === 'in' || op === 'intersects') return {kind:'candidate_set',items:[],exhaustive:true}
  if (feature.value_kind === 'number') return {kind:'number',number:null,unit:feature.unit ?? '1'}
  if (feature.value_kind === 'boolean') return {kind:'boolean',boolean:true}
  return {kind:'category',category:''}
}
export function registerFeature(knowledge: RecordValue, feature: FeatureChoice) {
  if (!feature.producerDeclared) return
  const definition = {feature_id:feature.feature_id,value_kind:feature.value_kind,unit:feature.unit,definition:feature.definition,requires_reference:feature.requires_reference,allowed_values:feature.allowed_values ?? null}
  const registered = rows(knowledge.feature_registry), index = registered.findIndex((row) => row.feature_id === feature.feature_id)
  if (index < 0) registered.push(definition)
  else registered[index] = definition
  knowledge.feature_registry = registered
}
export function conditionIssues(condition: RecordValue, feature?: AuthoringFeature): string[] {
  if (!feature) return ['找不到这个测量特征的定义。']
  const issues:string[] = [], op = text(condition.op), operand = record(condition.operand)
  if (!operatorsFor(feature).includes(op)) issues.push('当前判断方式不适用于这个特征类型。')
  if (operand.kind === 'number') {
    if (typeof operand.number !== 'number' || !Number.isFinite(operand.number)) issues.push('请输入有效的数值条件。')
    if (operand.unit !== feature.unit) issues.push('条件单位必须与特征单位一致。')
  } else if (operand.kind === 'boolean') {
    if (typeof operand.boolean !== 'boolean') issues.push('请选择“是”或“否”。')
  } else {
    const values = operand.kind === 'candidate_set' ? texts(operand.items) : [text(operand.category)]
    if (!values.length || values.some((value) => !value.trim())) issues.push('请填写或选择条件值。')
    if (new Set(values).size !== values.length) issues.push('条件集合不能重复同一个值。')
    if (Array.isArray(feature.allowed_values)) {
      const invalid = values.filter((value) => value && !feature.allowed_values!.includes(value))
      if (invalid.length) issues.push(`不在后端允许值中：${invalid.join('、')}。请选择目录值。`)
    }
  }
  return issues
}
export function categoricalFeatures(features: FeatureChoice[]) { return features.filter((feature) => ['category','candidate_set'].includes(feature.value_kind)) }
export function newValueBinding(featureId: string): RecordValue {
  return {binding_id:`binding:${crypto.randomUUID()}`,feature_id:featureId,external_value:'',canonical_value:'',procedure_model_id:null,source_assertion_ids:[]}
}
export function valueBindingIssues(binding: RecordValue, features: FeatureChoice[], knowledge: RecordValue): string[] {
  const issues:string[] = [], feature = features.find((row) => row.feature_id === binding.feature_id)
  if (!feature || !['category','candidate_set'].includes(feature.value_kind)) issues.push('请选择类别或候选集合特征。')
  const external = text(binding.external_value).trim(), canonical = text(binding.canonical_value).trim()
  if (!external) issues.push('请填写外部词汇。')
  if (!canonical) issues.push('请填写或选择对应的标准词汇。')
  if (canonical && Array.isArray(feature?.allowed_values) && !feature.allowed_values.includes(canonical)) issues.push('标准词汇不在后端允许值中。')
  const sources = texts(binding.source_assertion_ids)
  if (!sources.length) issues.push('请至少选择一项等价关系的来源依据。')
  if (sources.some((id) => !rows(knowledge.source_assertions).some((source) => source.assertion_id === id))) issues.push('所选来源已不在当前图谱中。')
  const model = binding.procedure_model_id || null
  const others = rows(knowledge.value_bindings).filter((row) => row.binding_id !== binding.binding_id && row.feature_id === binding.feature_id && row.external_value === binding.external_value)
  if (others.some((row) => (row.procedure_model_id || null) === model)) issues.push('这个特征与模型范围内已存在同名外部词汇。')
  if (others.some((row) => (!model || !row.procedure_model_id) && row.canonical_value !== binding.canonical_value)) issues.push('全局映射与模型限定映射的标准词汇冲突。')
  return issues
}
export function canonicalSuggestions(knowledge: RecordValue, featureId: unknown): string[] {
  return [...new Set(rows(knowledge.observable_definitions).filter((row) => row.feature_id === featureId).flatMap((row) => {
    const value = record(row.operand)
    return value.kind === 'category' ? [text(value.category)] : value.kind === 'candidate_set' ? texts(value.items) : []
  }))]
}
export function updateBindingField(binding: RecordValue, field: string, value: unknown) { return {...clone(binding),[field]:value} }
