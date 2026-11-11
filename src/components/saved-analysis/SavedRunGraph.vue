<script setup lang="ts">
import { IconInfoCircle, IconPushpin, IconRefresh, IconRelation } from '@arco-design/web-vue/es/icon'
import { computed, ref } from 'vue'
import KnowledgeForceGraph from '@/components/graphs/KnowledgeForceGraph.vue'
import { buildPathSubgraphDataset } from '@/services/saved-path-graph'
import type { SavedAnalysis, SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { isSavedGradedResult, traceRows, type TraceRecord } from '@/services/unified-reasoning-display'
import { channelLabel, factOnPath, featureLabel, getPathObs, isRootPropagation, nativePath, pathForFact, sourceLocator, text, type PathFocus } from './presentation'
import { gradedPathFocus, signedContribution } from './graded-presentation'
import SavedRunPanel from './SavedRunPanel.vue'

const props = defineProps<{ analysis: SavedAnalysis; frame: SavedAnalysisFrame; candidate: TraceRecord | null; pathId: string; edgeId: string; nodeId: string; observationId: string }>()
const emit = defineEmits<{ select: [item: { type: 'node' | 'edge'; id: string } | null]; path: [focus: PathFocus]; observation: [id: string]; reasoning: [] }>()
const renderRevision = ref(0)
const dataset = computed(() => {
  if (!props.frame.pathGraph.edge_count) return null
  const graph = buildPathSubgraphDataset(props.frame.pathGraph)
  return { ...graph, id: `saved-${props.analysis.run.run_id}-${props.frame.id}`.replace(/[^a-zA-Z0-9_-]/g, '-') }
})
const path = computed(() => props.frame.pathsById.get(props.pathId))
const activeNative = computed(() => path.value ? nativePath(props.frame, path.value.path_id) : null)
const node = computed(() => dataset.value?.nodes.find(item => item.id === props.nodeId))
const edge = computed(() => dataset.value?.edges.find(item => item.id === props.edgeId))
const labels = computed(() => new Map(dataset.value?.nodes.map(item => [item.id, item.name]) ?? []))
const focusPaths = computed(() => path.value ? [path.value] : props.frame.pathsByCandidateId.get(text(props.candidate?.candidate_id)) ?? [])
const focusEdges = computed(() => [...new Set(focusPaths.value.flatMap(item => item.edges.map(edge => edge.edge_id)))])
const focusNodes = computed(() => [...new Set(focusPaths.value.flatMap(item => item.nodes.map(node => node.node_id)))])
const alternatives = computed(() => edge.value ? props.frame.pathsByEdgeId.get(edge.value.id) ?? [] : node.value ? props.frame.pathGraph.paths.filter(path => path.nodes.some(item => item.node_id === node.value?.id)) : [])
const obsIds = computed(() => path.value ? getPathObs(props.frame, path.value) : [])
const activeObs = computed(() => obsIds.value.includes(props.observationId) ? props.observationId : obsIds.value[0])
const exactObservation = computed(() => {
  if (!path.value || !edge.value || !activeObs.value) return false
  const grade = gradedPathFocus(props.frame, path.value, activeObs.value)
  if (grade) return grade.edgeId === edge.value.id
  const fact = factOnPath(props.frame, path.value, activeObs.value, edge.value.id)
  const linked = fact ? pathForFact(props.frame, text(path.value.target_entity_id), fact) : null
  return linked?.edgeId === edge.value.id && linked.obsId === activeObs.value
})
const assertions = computed(() => traceRows(activeNative.value?.source_assertions))
const isRoot = computed(() => props.analysis.run.reasoner_id === 'tep_rootkgd' || isRootPropagation(props.frame.result))
const isGraded = computed(() => isSavedGradedResult(props.frame.result))
const normalGate = computed(() => props.frame.result?.reason === 'normal_reference_gate_is_false'
  || (isGraded.value && props.frame.result?.reason === 'anomaly_gate_is_false'))
const kindLabels: Record<string, string> = { support: '正证贡献', conflict: '反证贡献', prerequisite: '前置路径 · 不计分' }
function pathLabel(pathId: string, index: number) {
  const native = nativePath(props.frame, pathId)
  const selected = props.frame.pathsById.get(pathId)
  const candidate = props.frame.candidatesById.get(text(selected?.target_entity_id))
  if (native?.path_kind === 'graded_contribution') return [
    labels.value.get(text(selected?.target_entity_id)), labels.value.get(text(native.predicate_id)), kindLabels[text(native.contribution_kind)],
  ].filter(Boolean).join(' · ') || `贡献路径 ${index + 1}`
  return [text(candidate?.candidate_name) || labels.value.get(text(selected?.target_entity_id)), channelLabel(native?.channel) || `路径 ${index + 1}`].filter(Boolean).join(' · ')
}
function changePath(value: unknown) {
  if (typeof value === 'string' && alternatives.value.some(item => item.path_id === value)) emit('path', { pathId: value, edgeId: edge.value?.id, nodeId: node.value?.id })
}
</script>

<template>
  <SavedRunPanel v-if="!dataset" title="本次保存的源图子图" :icon="IconRelation">
    <div class="saved-run-stack">
      <div class="saved-run-notice" :class="{ 'saved-run-notice--normal': normalGate }"><IconInfoCircle /> <span>{{ normalGate
        ? isGraded ? '本次未越过异常门，没有保存候选或路径。' : '本窗口未越过异常门，没有保存候选或路径。'
        : frame.result ? '此 Frame 没有保存可绘制的源边。' : '此 Frame 未保存推理结果。' }}</span></div>
      <div><a-button size="small" type="outline" @click="emit('reasoning')">查看保存结论</a-button></div>
    </div>
  </SavedRunPanel>
  <div v-else class="saved-run-grid saved-run-graph-grid">
    <SavedRunPanel title="本次保存的源图子图" :icon="IconRelation" flat>
      <template #actions>
        <a-tag size="small" color="green">{{ dataset.nodes.length }} 节点</a-tag><a-tag size="small">{{ dataset.edges.length }} 边</a-tag>
        <a-button size="mini" title="复位图谱视图" @click="renderRevision += 1"><IconRefresh /> 复位</a-button>
      </template>
      <div class="saved-run-graph-stage" aria-label="本次保存的有向知识图谱">
        <KnowledgeForceGraph :dataset="dataset" :render-key="`${dataset.id}:${renderRevision}`" :show-labels="false" search-term="" :focused-node-ids="focusNodes" :focused-edge-ids="focusEdges"
          :selected-node-id="nodeId || null" :selected-edge-id="edgeId || null" @select="item => emit('select', item ? { type: item.type, id: item.item.id } : null)" />
        <span class="saved-run-graph-tip">滚轮缩放 · 拖动节点 · 点选源边</span>
      </div>
      <template #footer>{{ isGraded ? '本次分级贡献与前置路径中的实际方向边。' : '保存路径中的实际方向边；同一 ID 的节点和边只显示一次。' }}</template>
    </SavedRunPanel>
    <aside class="saved-run-stack">
      <SavedRunPanel title="当前定位" :icon="IconPushpin">
        <div class="saved-run-stack" :data-selected-source-edge-id="edge?.id" :data-selected-source-node-id="node?.id" :data-selected-saved-path-id="path?.path_id">
          <div><a-tag v-if="edge" size="small" color="blue">选中的保存源边</a-tag><a-tag v-else-if="node" size="small" color="blue">选中的保存节点</a-tag><a-tag v-else size="small">当前候选</a-tag></div>
          <p v-if="activeNative?.path_kind === 'graded_contribution'" class="saved-run-note">{{ kindLabels[text(activeNative.contribution_kind)] }}<template v-if="activeNative.contribution_kind !== 'prerequisite'"> · ΔS {{ signedContribution(activeNative.score_contribution) }}</template></p>
          <dl v-if="edge" class="saved-run-kv saved-run-kv--compact">
            <div><dt>起点</dt><dd>{{ labels.get(edge.source) ?? edge.source }}</dd></div>
            <div><dt>终点</dt><dd>{{ labels.get(edge.target) ?? edge.target }}</dd></div>
            <div><dt>关系</dt><dd>{{ edge.relation }}</dd></div>
          </dl>
          <div v-else-if="node"><strong>{{ node.name }}</strong><p class="saved-run-note">此节点出现在 {{ alternatives.length }} 条保存路径上。</p></div>
          <div v-else><strong>{{ candidate?.candidate_name || '未选择候选' }}</strong><p class="saved-run-note">点击图中的节点或边，查看保存路径及对应观测。</p></div>
          <div v-if="alternatives.length > 1" class="saved-run-stack saved-run-graph-path-select">
            <span class="saved-run-muted">此处对应多条路径，当前定位</span>
            <a-select :model-value="pathId || undefined" v-control-label="'选择此源边的保存路径'" size="small" aria-label="选择此源边的保存路径" @change="changePath"><a-option v-for="(item, index) in alternatives" :key="item.path_id" :value="item.path_id">{{ pathLabel(item.path_id, index) }}</a-option></a-select>
          </div>
          <div v-if="assertions.length" class="saved-run-graph-sources">
            <strong>保存路径附带来源</strong>
            <details class="saved-run-disclosure"><summary>查看路径级记录（{{ assertions.length }}）</summary>
              <ul class="saved-run-detail-list"><li v-for="(source, index) in assertions" :key="text(source.assertion_id) || index"><strong>{{ [text(source.source_id), sourceLocator(source.locator)].filter(Boolean).join(' · ') || text(source.origin) }}</strong><span>{{ source.text }}</span></li></ul>
            </details>
          </div>
          <details v-if="edge || node || path" class="saved-run-disclosure">
            <summary>保存 ID</summary><ul class="saved-run-detail-list"><li v-if="edge"><code>{{ edge.id }}</code></li><li v-if="node"><code>{{ node.id }}</code></li><li v-if="path"><code>{{ path.path_id }}</code></li></ul>
          </details>
          <div v-if="activeObs" class="saved-run-stack">
            <a-button size="mini" type="text" class="saved-run-compact-action" :data-observation-id="activeObs" @click="emit('observation', activeObs)"><IconPushpin /> {{ exactObservation ? '定位同一观测' : '查看路径关联观测' }}</a-button>
            <a-button v-for="id in obsIds.filter(id => id !== activeObs)" :key="id" size="mini" type="text" class="saved-run-compact-action" :data-observation-id="id" @click="emit('observation', id)">定位 {{ featureLabel(frame.observationsById.get(id)?.feature_id) }}</a-button>
          </div>
        </div>
      </SavedRunPanel>
      <SavedRunPanel :title="isRoot ? '与传播轨迹的关系' : isGraded ? '与分级贡献的关系' : '与推理树的关系'" :icon="IconInfoCircle">
        <p>{{ isRoot ? '所选路径由实际通道和源边组成；图谱不执行阈值条件。' : isGraded
          ? '每条路径连接本次实测、候选和实际源边；正反贡献路径不是完整布尔证明。'
          : '图是本次保存路径的并集，树只展开当前候选。选中的源边与树中引用的是同一 ID。' }}</p>
        <a-button size="mini" type="text" class="saved-run-compact-action" @click="emit('reasoning')">返回保存解释</a-button>
      </SavedRunPanel>
    </aside>
  </div>
</template>
