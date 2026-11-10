import type { Dataset, DemoGraphReference, DemoGroup, DemoSample, GraphSummary } from '@/api/workbench'
import { record } from '@/services/presentation'
export function demoGraphReference(sample:Pick<DemoSample,'graph_ref'>|null,group:Pick<DemoGroup,'graph_ref'>|null):DemoGraphReference|null {
  return sample?.graph_ref ?? group?.graph_ref ?? null
}
/** A scene/title/latest graph is never evidence that it is this sample's paired knowledge. */
export function readyDemoGraph(reference:DemoGraphReference|null,graphs:GraphSummary[],dataset:Dataset):GraphSummary|null {
  if (!reference || reference.state!=='ready' || !reference.available || !reference.graph_id) return null
  return graphs.find(graph=>graph.graph_id===reference.graph_id && graph.dataset===dataset && graph.enabled && graph.status==='ready' && record(graph.knowledge).schema_version==='rootlens-knowledge-package.v2') ?? null
}
export function demoGraphUnavailableNote(reference:DemoGraphReference|null) {
  if (!reference) return '尚未取得样例配套图信息，请刷新资料库后重试。'
  return reference.note || ({disabled:'样例配套图尚未投入使用。',missing:'尚未导入样例配套图。',ambiguous:'存在多个相同内容的配套图，请明确选择。',unavailable:'无法读取样例配套图资产。',ready:'配套图状态与当前图列表不一致，请重读图列表。'})[reference.state]
}
