/** Read-only shape bridge for saved /api/analyses output. No grounding, ranking or graph inference. */
import type { PathGraph, PathGraphPath, RankedRootCause, RunCaseDetail, RunDetail, RunSummary, VisualEvidenceItem } from '@/api/contracts'

type Row = Record<string, unknown>
const row = (value: unknown): Row => value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {}
const rows = (value: unknown): Row[] => Array.isArray(value) ? value.map(row) : []
const strings = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
const text = (value: unknown, fallback = '') => typeof value === 'string' ? value : fallback
const numeric = (value: unknown) => typeof value === 'number' ? value : null

export function analysisRunSummary(value: unknown): RunSummary {
  const source = row(value), input = row(source.input_snapshot)
  return {
    run_id: text(source.run_id), label: `已保存分析 · ${text(source.title, '双闭环结果')}`,
    created_at: text(source.created_at), mode: text(source.input_mode, 'evidence') as RunSummary['mode'],
    status: text(source.status) as RunSummary['status'], source_filename: text(source.source_filename),
    top_k: numeric(input.top_k), run_dir: '', dataset: text(source.dataset) || null,
    case_count: Number(source.case_count ?? 0), evidence_count: Array.isArray(source.cases) ? rows(source.cases).reduce((sum,item) => sum + rows(item.evidence_frames).reduce((total,frame) => total + rows(frame.observations).length,0),0) : null,
    model_preset: text(input.model_preset) || null, model_backend: text(input.model_backend) || null,
    source_contract: 'analysis-v2',
  }
}

function candidateId(path: Row, result: Row) {
  const direct = text(path.candidate_id ?? path.target_entity_id)
  if (direct) return direct
  const ids = strings(path.nodes)
  const matched = rows(result.ranked_root_causes).map(candidate => text(candidate.candidate_id)).filter(id => ids.includes(id))
  return matched.length === 1 ? matched[0]! : ''
}

function savedPath(path: Row, result: Row): PathGraphPath {
  const ids = strings(path.nodes), labels = strings(path.node_names), names = row(result.display_labels)
  const target = candidateId(path,result), views = rows(path.source_edge_views), sourceEdges = rows(path.source_edges)
  // Unified traces persist the exact ordered source IDs plus orientation. Root also persists edge records.
  if (views.length && views.length !== Math.max(0,ids.length-1)) throw new Error(`保存路径 ${text(path.path_id)} 的源边与节点数量不一致。`)
  const sourceId=ids[0]===target?ids.at(-1):ids[0]
  const edges = views.map((view,index) => {
    const edgeId = text(view.edge_id)
    const head = view.reverse === true ? ids[index+1] : ids[index]
    const tail = view.reverse === true ? ids[index] : ids[index+1]
    const edge = sourceEdges.find(item => item.edge_id === view.edge_id)
    if (!edgeId || typeof view.reverse !== 'boolean' || !head || !tail || (edge && (edge.head !== head || edge.tail !== tail))) {
      throw new Error(`保存路径 ${text(path.path_id)} 的源边与原方向不一致。`)
    }
    return {
      edge_id:edgeId, target_key:edgeId, source_node_id:head, target_node_id:tail,
      relation:text(edge?.relation,'源边（类型未保存）'), source:text(edge?.source) || null,
      evidence:text(edge?.evidence) || null, confidence:numeric(edge?.confidence), review_status:text(edge?.review_status) || null,
    }
  })
  return {
    path_id:text(path.path_id), target_key:text(path.path_id), target_entity_id:target,
    source_entity_id:sourceId, score:numeric(path.score), confidence:numeric(path.confidence),
    supporting_evidence:strings(path.support_obs_ids),
    nodes:ids.map((id,index) => ({node_id:id,label:labels[index] ?? text(names[id],id),role:id===target?'target':id===sourceId?'source':'intermediate'})),
    edges,
  }
}
function unionPaths(paths:PathGraphPath[]):PathGraph {
  return {paths,path_count:paths.length,node_count:new Set(paths.flatMap(path=>path.nodes.map(node=>node.node_id))).size,edge_count:new Set(paths.flatMap(path=>path.edges.map(edge=>edge.edge_id))).size}
}
function queryCase(source:Row, outerCase:Row, result:Row, frame:Row, index:number):RunCaseDetail {
  const scope = rows(frame.scopes).find(item => item.scope_id === row(frame.task).scope_id) ?? {}
  const context = scope.kind === 'time_window' ? `样本 ${scope.sample_start}–${scope.sample_end}` : scope.kind === 'image_region' ? `区域 ${index+1}` : text(outerCase.display_name,'完整样本')
  const pathRows:Row[] = rows(result.top_k_paths).map(path => {
    const target = candidateId(path,result)
    return {...path,target_entity_id:target,target_entity_name:text(row(result.display_labels)[target],target)}
  })
  const pathGraph = unionPaths(pathRows.map(path=>savedPath(path,result)))
  const ranked = rows(result.ranked_root_causes).map(candidate => ({
    ...candidate, ranking_id:`ranking:${text(result.case_id)}:${text(candidate.candidate_id)}`,
    candidate_name:text(candidate.candidate_name,text(row(result.display_labels)[text(candidate.candidate_id)],text(candidate.candidate_id))),
    scoring_method:text(result.scoring_method), supporting_evidence:strings(candidate.support_obs_ids),
  })) as unknown as RankedRootCause[]
  const frameObservations = rows(frame.observations)
  const observationIds = new Set(frameObservations.map(item => item.obs_id))
  const locations = rows(outerCase.observation_locations).filter(item => observationIds.has(item.obs_id))
  const locationsById = new Map(locations.map(item => [item.obs_id, item]))
  const media = rows(outerCase.visual_evidence).filter(item => {
    const metadata=row(item.metadata)
    // Scope-specific previews require an explicit association; shared original media remain available.
    if (metadata.scope_id && metadata.scope_id !== scope.scope_id) return false
    if (item.source_key==='roi_path' && metadata.obs_id) return frameObservations.some(observation=>observation.obs_id===metadata.obs_id || text(observation.obs_id).startsWith(`${text(metadata.obs_id)}:`))
    return item.source_key!=='roi_path' || rows(outerCase.results).length<=1 || !!metadata.scope_id
  }) as unknown as VisualEvidenceItem[]
  const observations = frameObservations.map(observation => {
    const subject = rows(frame.subjects).find(item => item.subject_id === observation.subject_id)
    const location = locationsById.get(observation.obs_id)
    const obsScope = location?.scope ?? rows(frame.scopes).find(item => item.scope_id === observation.scope_id)
    const externalId = text(location?.subject_external_id, text(subject?.external_id))
    return {...observation,
      display_name:[externalId,text(observation.feature_id)].filter(Boolean).join(' · '),
      subject_external_id:externalId || null,
      facet:source.dataset==='tep'?'variable':source.dataset==='wafer'?'wafer_measurements':'visual_region',
      observation_location:location ?? (obsScope ? { obs_id:observation.obs_id, scope:obsScope, subject_external_id:externalId || null } : null),
      time_window:row(obsScope).kind==='time_window'?obsScope:undefined, linked_entity_hints:[],
      raw_evidence_refs:strings(observation.raw_refs).map(id=>{const asset=rows(frame.assets).find(item=>item.asset_id===id);return{ref_id:id,label:id,role:text(asset?.kind),file_path:text(asset?.uri),line:null}}),
    }
  })
  return {
    ...outerCase, case_id:text(result.case_id,text(outerCase.case_id)), source_case_id:outerCase.case_id,
    dataset:text(source.dataset), label:context, case_label:context, source:'已保存分析快照',
    generated_evidence:{case_id:result.case_id,dataset:source.dataset,graph_dataset_id:source.graph_id,source:'已保存分析快照',observations},
    linked_entities:[], correction_candidates:[], ranked_root_causes:ranked, top_k_paths:pathRows,
    path_graph:pathGraph, source_edge_provenance:pathRows.flatMap(path=>rows(path.source_edges)), review_targets:[], visual_evidence:media, observation_locations:locations,
    reasoning_metadata:{graph_id:text(source.graph_id),reasoner_adapter:text(source.reasoner_id),reasoning_profile_id:text(source.reasoner_id),selection_mode:'explicit',fallback_applied:false,
      outcome:text(result.outcome),query_results:[result],evidence_frames:[frame]},
  }
}
export function analysisSnapshotView(value:unknown):RunDetail {
  const source=row(value), cases=rows(source.cases).flatMap(outer => {
    const frames=rows(outer.evidence_frames), results=rows(outer.results)
    if (!results.length) return [{...outer,case_id:text(outer.case_id),dataset:text(source.dataset),label:text(outer.display_name),ranked_root_causes:[],top_k_paths:[],path_graph:unionPaths([]),review_targets:[],reasoning_metadata:{graph_id:text(source.graph_id),query_results:[],evidence_frames:frames}}] as RunCaseDetail[]
    return results.map((result,index)=>{
      const frame=frames.find(item=>item.case_id===result.case_id)
      if (!frame) throw new Error(`已保存分析 ${text(source.run_id)} 的问题 ${text(result.case_id)} 缺少对应 EvidenceFrame。`)
      return queryCase(source,outer,result,frame,index)
    })
  })
  const reasoning={graph_id:text(source.graph_id),reasoner_adapter:text(source.reasoner_id),reasoning_profile_id:text(source.reasoner_id),selection_mode:'explicit',fallback_applied:false}
  return {
    run:analysisRunSummary(source),cases,
    workflow_steps:[{step_id:'saved-analysis',title:'打开已保存分析',status:'completed',summary:'只读显示后端保存的候选、原始分数与源路径；不重新测量或推理。',details:{source_contract:'analysis-v2',run_id:source.run_id,reasoner_id:source.reasoner_id}}],
    claim_boundary:'已保存分析快照；候选与路径为解释依据，分数不是根因概率。',
    evidence:null,evidence_summary:null,evidence_with_analysis:null,analysis:{reasoning_metadata:reasoning},
    summary:{source_contract:'analysis-v2',graph_title:source.graph_title,working_graph_snapshot:source.working_graph_snapshot,evidence_download_url:source.evidence_download_url,source_case_count:source.case_count},
    reasoning_metadata:reasoning,linked_entities:[],correction_candidates:[],top_k_paths:cases.flatMap(item=>item.top_k_paths??[]),
    ranked_root_causes:cases.flatMap(item=>item.ranked_root_causes??[]),path_graph:unionPaths(cases.flatMap(item=>item.path_graph?.paths??[])),
    source_edge_provenance:cases.flatMap(item=>item.source_edge_provenance??[]),review_targets:[],
    artifacts:Object.fromEntries(Object.entries(row(source.artifacts)).filter((entry):entry is [string,string]=>typeof entry[1]==='string')),
    visual_evidence:cases.flatMap(item=>item.visual_evidence??[]),
  }
}
