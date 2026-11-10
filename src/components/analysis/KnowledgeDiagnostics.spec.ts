import { afterEach, describe, expect, it } from 'vitest'
import { createApp, type App } from 'vue'
import type { RecordValue } from '@/api/workbench'
import Panel from './KnowledgeDiagnostics.vue'
let app:App|null=null
function render(report:RecordValue|null) {const root=document.createElement('div');document.body.append(root);app=createApp(Panel,{result:report?{authoring_diagnostics:report}:{},names:new Map([['a','入口温度扰动'],['b','阀门粘滞']]),selectedCandidateId:'a',graphId:''});app.mount(root);return root}
const base:RecordValue={schema_version:'rootlens-candidate-discriminability.v1',grouping_status:'available',grouping_basis:'reachable_expectation_conditions',equivalence_groups:[{group_id:'g',candidate_ids:['a','b'],candidate_names:['入口温度扰动','阀门粘滞'],condition_signature:[],cost_priors:[{candidate_id:'a',assumption_cost:1,assumption_weight:.25,weighted_cost:.25,applied_to_score:true}]}],evidence_usage:{total_observation_count:263,observed_observation_count:263,condition_grounded_observation_count:14,score_input_status:'available',score_input_observation_count:14,unreferenced_features:[],not_scored_features:[]},candidate_checks:[{predicate_checks:Array.from({length:14},(_,i)=>({fact_id:`f${i}`,value:i<2}))}]}
afterEach(()=>{app?.unmount();app=null;document.body.innerHTML=''})
describe('knowledge diagnostic panel',()=>{
  it('shows old-run absence honestly without a current-graph reconstruction',()=>{expect(render(null).textContent).toContain('本次未生成')})
  it('separates 14 checked facts with 2 true and 12 false from score-input observations',()=>{
    const root=render(base);expect(root.textContent).toContain('14 项，2 满足、12 不满足');expect(root.textContent).toContain('不等于成立或支持的数量');expect(root.textContent).toContain('先验（不是观测区别）')
  })
  it('does not call an unsupported normal/insufficient group a current ranking tie',()=>{
    const root=render({...base,candidate_checks:[{candidate_id:'a',eligible_for_ranking:false},{candidate_id:'b',eligible_for_ranking:false}]})
    expect(root.textContent).toContain('本组本次未获支持');expect(root.textContent).toContain('0 具备 / 2 不具备');expect(root.textContent).not.toContain('并列不是运行错误')
  })
  it('shows all 52 Root inputs and keeps author checks outside the structural scoring contract',()=>{
    const root=render({...base,grouping_basis:'actual_structural_projection',evidence_usage:{...(base.evidence_usage as RecordValue),score_input_observation_count:52}})
    expect(root.querySelector('.diagnostic-counts')?.textContent).toContain('52完整结构比较输入');expect(root.textContent).toContain('不用于 RootKGD');expect(root.textContent).toContain('传播覆盖范围不是评分向量的维数')
  })
})
