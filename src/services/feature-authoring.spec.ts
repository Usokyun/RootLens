import { describe, expect, it } from 'vitest'
import type { AuthoringCapability, AuthoringFeature } from '@/api/workbench'
import { canonicalSuggestions, conditionIssues, featureChoices, newValueBinding, operandFor, operatorsFor, registerFeature, valueBindingIssues } from '@/services/feature-authoring'

const morphology:AuthoringFeature = {feature_id:'geometry.morphology',value_kind:'category',unit:null,definition:'Actual producer values',requires_reference:false,allowed_values:['line','spot','aggregate']}
const appearance:AuthoringFeature = {feature_id:'appearance.semantic_candidates',value_kind:'candidate_set',unit:null,definition:'Open observed vocabulary',requires_reference:false,allowed_values:null}
const manifest:AuthoringCapability = {capability_id:'visual-region-v2',features:[morphology,appearance],scopes:['task_scope'],zones:[],notes:'Producer contract'}
function knowledge() {return {feature_registry:[{...morphology,allowed_values:null,definition:'Old definition'},appearance],source_assertions:[{assertion_id:'source-a',text:'Actual source'}],observable_definitions:[{feature_id:appearance.feature_id,operand:{kind:'category',category:'cracked_glass'}}],value_bindings:[] as Record<string,unknown>[]}}

describe('shared feature authoring contract',()=>{
  it('uses the backend directory values and definition instead of a frontend enum table',()=>{
    const features=featureChoices(knowledge(),manifest)
    expect(features[0]?.allowed_values).toEqual(['line','spot','aggregate'])
    expect(features[0]?.definition).toBe('Actual producer values')
    expect(features[0]?.producerDeclared).toBe(true)
  })
  it('keeps explicitly open vocabulary distinct from a missing catalog',()=>{
    expect(featureChoices(knowledge(),manifest).find(f=>f.feature_id===appearance.feature_id)?.allowed_values).toBeNull()
    expect(featureChoices({feature_registry:[{feature_id:'legacy',value_kind:'category'}]},null)[0]?.allowed_values).toBeUndefined()
  })
  it('persists the selected registered feature without editing other knowledge content',()=>{
    const data=knowledge(),features=featureChoices(data,manifest)
    registerFeature(data,features[0]!)
    expect(data.feature_registry[0]?.allowed_values).toEqual(morphology.allowed_values)
    expect(data.source_assertions).toEqual([{assertion_id:'source-a',text:'Actual source'}])
  })
  it('limits operators by actual value kinds and changes the operand shape with the operator',()=>{
    expect(operatorsFor(morphology)).toEqual(['eq','in'])
    expect(operatorsFor(appearance)).toEqual(['candidate_contains','intersects'])
    expect(operandFor(morphology,'in')).toEqual({kind:'candidate_set',items:[],exhaustive:true})
    expect(operatorsFor({value_kind:'array_ref'})).toEqual([])
  })
  it('rejects an invalid finite category while permitting a declared open term',()=>{
    expect(conditionIssues({op:'eq',operand:{kind:'category',category:'made-up'}},morphology)).toContain('不在后端允许值中：made-up。请选择目录值。')
    expect(conditionIssues({op:'candidate_contains',operand:{kind:'category',category:'explicit-new-term'}},appearance)).toEqual([])
  })
})
describe('explicit equivalent vocabulary',()=>{
  it('creates a blank mapping without guessing values, sources or model identity',()=>{
    const binding=newValueBinding(appearance.feature_id)
    expect(binding).toEqual(expect.objectContaining({feature_id:appearance.feature_id,external_value:'',canonical_value:'',procedure_model_id:null,source_assertion_ids:[]}))
  })
  it('requires an actual source and prevents duplicate/global-overlap ambiguity',()=>{
    const data=knowledge(),features=featureChoices(data,manifest)
    const binding={binding_id:'binding-a',feature_id:appearance.feature_id,external_value:'外部词',canonical_value:'cracked_glass',procedure_model_id:null,source_assertion_ids:[]}
    expect(valueBindingIssues(binding,features,data)).toContain('请至少选择一项等价关系的来源依据。')
    expect(valueBindingIssues({...binding,source_assertion_ids:['source-a']},features,data)).toEqual([])
    data.value_bindings=[{...binding,binding_id:'other',procedure_model_id:'actual-model',canonical_value:'another-meaning'}]
    expect(valueBindingIssues({...binding,source_assertion_ids:['source-a']},features,data)).toContain('全局映射与模型限定映射的标准词汇冲突。')
  })
  it('constrains a finite canonical target but leaves the external synonym editable',()=>{
    const data=knowledge(),features=featureChoices(data,manifest)
    const binding={binding_id:'a',feature_id:morphology.feature_id,external_value:'外部斑点词',canonical_value:'spot',source_assertion_ids:['source-a']}
    expect(valueBindingIssues(binding,features,data)).toEqual([])
    expect(valueBindingIssues({...binding,canonical_value:'unknown'},features,data)).toContain('标准词汇不在后端允许值中。')
  })
  it('suggests only terms already used by conditions of the same feature',()=>{
    expect(canonicalSuggestions(knowledge(),appearance.feature_id)).toEqual(['cracked_glass'])
    expect(canonicalSuggestions(knowledge(),morphology.feature_id)).toEqual([])
  })
})
