import { describe, expect, it } from 'vitest'
import { analysisRunSummary, analysisSnapshotView } from './analysis-snapshot-view'
const frame=(id:string,start:number)=>({case_id:id,task:{scope_id:`scope-${id}`},subjects:[{subject_id:'var',external_id:'xmv_10'}],scopes:[{scope_id:`scope-${id}`,kind:'time_window',sample_start:start,sample_end:start+99,sampling_seconds:180}],observations:[{obs_id:`obs-${id}`,subject_id:'var',feature_id:'statistics.mean_z',value:{kind:'number',number:-2.6,unit:'1'},status:'observed'}]})
const result=(id:string,score=-.25)=>({case_id:id,schema_version:'rootlens-reasoning-result.v2',outcome:'ambiguous',scoring_method:'unified_constraint_abduction_v0',display_labels:{cause:'冷却扰动'},ranked_root_causes:[{candidate_id:'cause',candidate_name:'冷却扰动',rank:1,score,confidence:null,scoring_details:{total_cost:.25},support_obs_ids:[`obs-${id}`]}],top_k_paths:[{path_id:`path-${id}`,nodes:['predicate','cause'],node_names:['均值偏移','冷却扰动'],source_edge_views:[{edge_id:'edge-original',reverse:true}],support_obs_ids:[`obs-${id}`]}]})
const saved=()=>({run_id:'analysis-one',title:'实际分析',created_at:'2026-11-11',status:'completed',dataset:'tep',input_mode:'evidence',source_filename:'source.json',reasoner_id:'unified_abduction',graph_id:'graph',case_count:1,input_snapshot:{top_k:8},working_graph_snapshot:{knowledge:{semantic_role:'preserve-me',value_bindings:[{binding_id:'original'}]}},cases:[{case_id:'original-case',display_name:'过程样本',evidence_frames:[frame('q-a',1),frame('q-b',161)],results:[result('q-b'),result('q-a')],visual_evidence:[]}]})
describe('saved analysis shape bridge',()=>{
  it('pairs every result by Frame identity, not first-frame or positional fallback',()=>{
    const view=analysisSnapshotView(saved());expect(view.cases.map(item=>item.case_id)).toEqual(['q-b','q-a']);expect(view.cases.map(item=>item.label)).toEqual(['样本 161–260','样本 1–100']);expect(view.cases[0]!.source_case_id).toBe('original-case');expect(view.cases[0]!.reasoning_metadata?.evidence_frames?.[0]).toEqual(frame('q-b',161))
  })
  it('preserves scores, costs, tie ranks and missing confidence without normalization',()=>{
    const source=saved();source.cases[0]!.results[0]!.ranked_root_causes.push({...source.cases[0]!.results[0]!.ranked_root_causes[0]!,candidate_id:'other'})
    const view=analysisSnapshotView(source);expect(view.cases[0]!.ranked_root_causes?.map(item=>[item.rank,item.score,item.confidence,item.scoring_details?.total_cost])).toEqual([[1,-.25,null,.25],[1,-.25,null,.25]])
  })
  it('preserves canonical source-edge identity and orientation from saved views',()=>{
    const path=analysisSnapshotView(saved()).cases[0]!.path_graph!.paths[0]!;expect(path.edges[0]).toMatchObject({edge_id:'edge-original',source_node_id:'cause',target_node_id:'predicate'});expect(path.edges[0]!.relation).toContain('类型未保存')
  })
  it('uses actual Root edge records and keeps structural score as-is',()=>{
    const source=saved();const r=source.cases[0]!.results[0]! as Record<string,unknown>;r.scoring_method='tep_rootkgd_propagation_v2';r.ranked_root_causes=[{candidate_id:'cause',rank:1,score:.5854474293642782,confidence:null}];r.top_k_paths=[{path_id:'root-path',nodes:['cause','var'],node_names:['冷却扰动','阀'],source_edge_views:[{edge_id:'real-edge',reverse:false}],source_edges:[{edge_id:'real-edge',head:'cause',tail:'var',relation:'OBSERVES'}]}]
    const item=analysisSnapshotView(source).cases[0]!;expect(item.ranked_root_causes?.[0]?.score).toBe(.5854474293642782);expect(item.path_graph?.paths[0]).toMatchObject({source_entity_id:'var',target_entity_id:'cause',edges:[{edge_id:'real-edge',relation:'OBSERVES',source_node_id:'cause',target_node_id:'var'}]})
  })
  it('rejects an unmatched Frame rather than using another window or a Demo result',()=>{
    const source=saved();source.cases[0]!.evidence_frames=[frame('q-a',1)];expect(()=>analysisSnapshotView(source)).toThrow('缺少对应 EvidenceFrame')
  })
  it('keeps cases that have no result without creating candidates',()=>{
    const source=saved();source.cases[0]!.results=[];const item=analysisSnapshotView(source).cases[0]!;expect(item.case_id).toBe('original-case');expect(item.ranked_root_causes).toEqual([]);expect(item.reasoning_metadata?.evidence_frames).toHaveLength(2)
  })
  it('does not mutate stored input, metadata or the complete knowledge snapshot',()=>{
    const source=saved(),before=JSON.stringify(source),view=analysisSnapshotView(source);expect(JSON.stringify(source)).toBe(before);expect(view.summary?.working_graph_snapshot).toEqual(source.working_graph_snapshot);expect(view.run.top_k).toBe(8);expect(view.run.evidence_count).toBe(2)
  })
  it('marks the actual data contract and leaves unknown summary quantities unknown',()=>{
    const summary=analysisRunSummary({run_id:'new',title:'已完成结果',input_mode:'process'});expect(summary.source_contract).toBe('analysis-v2');expect(summary.label).toContain('已保存分析');expect(summary.mode).toBe('process');expect(summary.top_k).toBeNull();expect(summary.evidence_count).toBeNull();expect(summary.model_backend).toBeNull()
  })
  it('keeps shared media but does not attach a different ROI preview to this Frame',()=>{
    const source=saved() as Record<string,unknown>;const outer=(source.cases as Record<string,unknown>[])[0]!;outer.evidence_frames=[{...frame('q-a',1),observations:[{obs_id:'roi:1:feature'}]},{...frame('q-b',161),observations:[{obs_id:'roi:2:feature'}]}];outer.visual_evidence=[{artifact_id:'shared',source_key:'image_path',metadata:{}},{artifact_id:'one',source_key:'roi_path',metadata:{obs_id:'roi:1'}},{artifact_id:'two',source_key:'roi_path',metadata:{obs_id:'roi:2'}}];const cases=analysisSnapshotView(source).cases;expect(cases[0]!.visual_evidence?.map(item=>item.artifact_id)).toEqual(['shared','two']);expect(cases[1]!.visual_evidence?.map(item=>item.artifact_id)).toEqual(['shared','one'])
  })
  it('uses only the selected Frame observation IDs when attaching saved locations', () => {
    const source = saved()
    const outer = source.cases[0]! as Record<string, unknown>
    const location = { obs_id: 'obs-q-b', scope: frame('q-b', 161).scopes[0], subject_external_id: 'xmv_10' }
    outer.observation_locations = [{ obs_id: 'obs-q-a', scope: frame('q-a', 1).scopes[0] }, location]
    const selected = analysisSnapshotView(source).cases[0]!
    expect(selected.observation_locations).toEqual([location])
    expect(selected.generated_evidence?.observations).toMatchObject([
      { obs_id: 'obs-q-b', subject_external_id: 'xmv_10', observation_location: location, time_window: { sample_start: 161 } },
    ])
    expect(selected.reasoning_metadata?.evidence_frames?.[0]).toEqual(frame('q-b', 161))
  })
  it('rejects a saved edge record whose endpoints contradict its stored direction', () => {
    const source = saved()
    const p = source.cases[0]!.results[0]!.top_k_paths[0]! as Record<string, unknown>
    p.source_edges = [{ edge_id: 'edge-original', head: 'predicate', tail: 'cause', relation: 'SAVED' }]
    expect(() => analysisSnapshotView(source)).toThrow('源边与原方向不一致')
  })
})
