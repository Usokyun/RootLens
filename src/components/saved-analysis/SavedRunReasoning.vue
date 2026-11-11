<script setup lang="ts">
import { IconInfoCircle, IconList, IconPushpin, IconRelation } from '@arco-design/web-vue/es/icon'
import { computed, nextTick, ref, watch } from 'vue'
import type { SavedAnalysis, SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { isSavedGradedResult, savedGradedCandidates, savedTentativeCandidates, traceOutcome, traceRecord, traceRows, traceValue, type TraceRecord } from '@/services/unified-reasoning-display'
import { channelLabel, getPathObs, isRootPropagation, nativePath, savedCandidateRanks, savedProofGroups, strings, text, truthColor, truthLabel, valueLabel, type DetailTab, type PathFocus } from './presentation'
import { gradedUnranked } from './graded-presentation'
import SavedRunPanel from './SavedRunPanel.vue'
import SavedRunGraded from './SavedRunGraded.vue'
import SavedRunProofExpr from './SavedRunProofExpr.vue'
import SavedRunTentative from './SavedRunTentative.vue'

const props = defineProps<{ analysis: SavedAnalysis; frame: SavedAnalysisFrame; candidate: TraceRecord | null; factId: string; pathId: string; observationId: string; tentativeCandidateId?: string }>()
const emit = defineEmits<{ tab: [tab: DetailTab]; candidate: [id: string]; graph: [focus: PathFocus]; observation: [id: string, focus?: PathFocus]; 'tentative-observation': [candidateId: string, id: string] }>()
const isRoot = computed(() => props.analysis.run.reasoner_id === 'tep_rootkgd' || isRootPropagation(props.frame.result))
const isGraded = computed(() => isSavedGradedResult(props.frame.result))
const hasGradedTrace = computed(() => savedGradedCandidates(props.frame.result).length > 0 || gradedUnranked(props.frame.result).length > 0)
const isNormal = computed(() => props.frame.result?.reason === 'normal_reference_gate_is_false'
  || (isGraded.value && props.frame.result?.reason === 'anomaly_gate_is_false'))
const candidateId = computed(() => text(props.candidate?.candidate_id))
const ranks = computed(() => savedCandidateRanks(props.frame))
const rank = computed(() => ranks.value.find(item => item.candidate_id === candidateId.value))
const tentative = computed(() => isRoot.value || isGraded.value ? [] : savedTentativeCandidates(props.frame.result))
const unranked = computed(() => isGraded.value ? [] : traceRows(props.frame.result?.candidate_evaluations).filter(item => !ranks.value.some(rank => rank.candidate_id === item.candidate_id)
  && !tentative.value.some(row => row.candidate_id === item.candidate_id)))
const proof = computed(() => props.candidate && !isRoot.value && !isGraded.value ? savedProofGroups(props.analysis.run.working_graph_snapshot, props.frame, props.candidate) : [])
const paths = computed(() => (props.frame.pathsByCandidateId.get(candidateId.value) ?? []).map(path => {
  const native = nativePath(props.frame, path.path_id)
  const obsIds = getPathObs(props.frame, path)
  const obsId = obsIds[0]
  return { path, native, obsIds, focus: { pathId: path.path_id, obsId }, observed: obsId ? props.frame.observationsById.get(obsId)?.value : null }
}))
const scopeJoin: Record<string, string> = { same_subject_same_scope: '同一主体和范围', same_event_same_window: '同一事件和窗口', same_subject_parent_scope: '同一主体的父子范围' }
const scoreDetails = computed(() => traceRecord(props.candidate?.scoring_details ?? rank.value?.scoring_details))
const scores = computed(() => isRoot.value ? [
  ['余弦相似', scoreDetails.value.cosine_similarity], ['覆盖惩罚', scoreDetails.value.coverage_penalty],
  ['熵惩罚', scoreDetails.value.entropy_penalty], ['结构分', scoreDetails.value.structural_score ?? rank.value?.score],
] : [
  ['未解释 U', scoreDetails.value.unexplained_loss], ['冲突 C', scoreDetails.value.conflict_loss],
  ['假设 A', scoreDetails.value.assumption_cost], ['代价 J', scoreDetails.value.total_cost],
])
const scoringCount = computed(() => strings(traceRecord(props.frame.result?.propagation).scoring_input_obs_ids).length)
const evidencePanel = ref<HTMLElement | null>(null)
watch([() => props.factId, () => props.pathId], async ([factId, pathId]) => {
  if (!factId && !pathId) return
  await nextTick()
  const items = evidencePanel.value?.querySelectorAll<HTMLElement>(factId ? '[data-fact-id]' : '[data-saved-path-id]')
  const current = [...items ?? []].find(row => factId ? row.dataset.factId === factId : row.dataset.savedPathId === pathId)
  current?.scrollIntoView?.({ block: 'nearest' })
}, { immediate: true, flush: 'post' })
const selectedScore = computed(() => rank.value?.score ?? props.candidate?.score)
const outcomeNote = computed(() => {
  const result = props.frame.result
  if (!result) return '此 Frame 未保存解释器结果；可以查看同一 Frame 的已有观测。'
  if (isNormal.value) return isGraded.value ? '本次未越过异常门，未启动候选排名。' : '本窗口未越过异常门，未启动候选排名。'
  if (tentative.value.length) return '没有候选获得完整支持。可展开下方待验证分支，查看实测支持与反证。'
  return `${traceOutcome(result.outcome)}。本次没有入排名候选。`
})
</script>

<template>
  <SavedRunGraded v-if="hasGradedTrace" :frame="frame" :candidate="candidate" :path-id="pathId" :observation-id="observationId"
    @candidate="id => emit('candidate', id)" @graph="focus => emit('graph', focus)" @observation="(id, focus) => emit('observation', id, focus)" @tab="tab => emit('tab', tab)" />
  <div v-else class="saved-run-grid saved-run-reasoning-grid">
    <div ref="evidencePanel" class="saved-run-stack">
      <SavedRunPanel :title="isRoot ? '保存的结构传播轨迹' : '选中候选的保存解释'" :icon="IconRelation">
        <template v-if="frame.pathGraph.edge_count" #actions><a-button size="mini" type="text" @click="emit('tab', 'graph')">打开图谱</a-button></template>
        <div v-if="!candidate" class="saved-run-stack">
          <div class="saved-run-notice" :class="{ 'saved-run-notice--normal': isNormal }"><IconInfoCircle />{{ outcomeNote }}</div>
          <div><a-button size="small" type="outline" @click="emit('tab', 'evidence')">查看本次观测</a-button></div>
        </div>
        <div v-else class="saved-run-stack">
          <header class="saved-run-row saved-run-wrap">
            <a-tag v-if="isRoot && scoringCount" size="small" color="blue">{{ scoringCount }} 项结构输入</a-tag>
            <a-tag v-else-if="proof.length" size="small" color="blue">{{ proof.some(group => group.conditions.some(condition => condition.expression)) ? '联合条件' : '保存核验' }}</a-tag>
            <a-tag v-if="rank" size="small">名次 {{ rank.rank }}</a-tag><a-tag v-else size="small" color="orange">未入排名</a-tag>
          </header>
          <div><h3 class="saved-run-proof-title">{{ candidate.candidate_name || candidateId }}</h3>
            <p v-if="isRoot" class="saved-run-note">通道贡献与图传播结构用于评分；下方是实际保存轨迹，不是阈值条件的真假证明。</p>
            <p v-else-if="proof.length" class="saved-run-note">展开本候选的保存机制、联合条件与对应实测。</p>
            <p v-else class="saved-run-note">此候选未保存可展开的联合条件，仅列出实际路径。</p>
          </div>
          <ul v-if="proof.length" class="saved-run-proof-tree">
            <li v-for="group in proof" :key="group.id">
              <template v-if="group.mechanism">
                <div class="saved-run-row saved-run-wrap"><strong>{{ group.label }}</strong><a-tag size="small">机制</a-tag></div>
                <a-button v-if="group.edgeFocus" size="mini" type="text" class="saved-run-compact-action" @click="emit('graph', group.edgeFocus)"><IconRelation /> 高亮机制源边</a-button>
              </template>
              <ul class="saved-run-tree-branch">
                <li v-for="condition in group.conditions" :key="condition.id">
                  <details class="saved-run-proof-condition" :open="condition.truth === true || (!!factId && [...condition.factsByPredicate.values()].some(facts => facts.some(fact => fact.fact_id === factId)))">
                    <summary><strong>{{ condition.label }}</strong><a-tag size="small" :color="truthColor(condition.truth)">{{ truthLabel(condition.truth) }}</a-tag></summary>
                    <p v-if="condition.join || condition.reason" class="saved-run-note">{{ [scopeJoin[condition.join] ?? condition.join, condition.reason].filter(Boolean).join(' · ') }}</p>
                    <a-button v-if="condition.edgeFocus" size="mini" type="text" class="saved-run-compact-action" @click="emit('graph', condition.edgeFocus)"><IconRelation /> 高亮该现象的源边</a-button>
                    <ul v-if="condition.expression || condition.predicates.length" class="saved-run-tree-branch">
                      <SavedRunProofExpr v-if="condition.expression" :expression="condition.expression" :condition="condition" :frame="frame" :candidate-id="candidateId" :fact-id="factId" @graph="focus => emit('graph', focus)" @observation="(id, focus) => emit('observation', id, focus)" />
                      <template v-else>
                        <li class="saved-run-muted">联合表达式未保存；以下只列本次核验事实。</li>
                        <SavedRunProofExpr v-for="predicate in condition.predicates" :key="predicate" :expression="predicate" :condition="condition" :frame="frame" :candidate-id="candidateId" :fact-id="factId" @graph="focus => emit('graph', focus)" @observation="(id, focus) => emit('observation', id, focus)" />
                      </template>
                    </ul>
                    <p v-else class="saved-run-muted">此条件未保存可展开的核验事实。</p>
                  </details>
                </li>
              </ul>
            </li>
          </ul>
          <div v-else-if="paths.length" class="saved-run-stack">
            <article v-for="(item, index) in paths" :key="item.path.path_id" class="saved-run-propagation-path" :class="{ 'is-selected': pathId === item.path.path_id }" :data-saved-path-id="item.path.path_id">
              <div class="saved-run-row saved-run-wrap saved-run-between">
                <strong>{{ channelLabel(item.native?.channel) || `保存路径 ${index + 1}` }}</strong>
                <span v-if="isRoot" class="saved-run-muted">{{ item.observed != null ? `实测贡献 ${valueLabel(item.observed)}` : '' }}<span v-if="item.native?.propagated_signal != null"> · 传播信号 {{ traceValue(item.native.propagated_signal) }}</span></span>
              </div>
              <details class="saved-run-disclosure" :open="pathId === item.path.path_id"><summary>{{ item.path.edges.length }} 条保存源边</summary><p>{{ item.path.nodes.map(node => node.label).join(' → ') }}</p></details>
              <div class="saved-run-row saved-run-wrap saved-run-proof-actions">
                <a-button v-for="(id, obsIndex) in item.obsIds" :key="id" size="mini" type="text" :data-observation-id="id" @click="emit('observation', id, { ...item.focus, obsId: id })"><IconPushpin /> {{ isRoot ? '定位该通道' : item.obsIds.length > 1 ? `定位观测 ${obsIndex + 1}` : '定位观测' }}</a-button>
                <a-button v-if="item.path.edges.length" size="mini" type="text" @click="emit('graph', item.focus)"><IconRelation /> 查看关联路径</a-button>
              </div>
            </article>
          </div>
          <p v-else class="saved-run-muted">该候选没有保存可展示的路径。</p>
        </div>
      </SavedRunPanel>
      <SavedRunTentative v-if="tentative.length" :frame="frame" :open-first="!ranks.length" :active-id="tentativeCandidateId"
        @observation="(candidateId, id) => emit('tentative-observation', candidateId, id)" />
    </div>
    <aside class="saved-run-stack">
      <SavedRunPanel title="候选列表" :icon="IconList">
        <template #heading><a-tag size="small" color="blue">{{ ranks.length }} 项入排名</a-tag></template>
        <div v-if="ranks.length" class="saved-run-candidate-picker">
          <button v-for="item in ranks" :key="text(item.candidate_id)" type="button" :aria-pressed="candidateId === item.candidate_id" :data-candidate-id="item.candidate_id" @click="emit('candidate', text(item.candidate_id))">
            <span><small>#{{ item.rank }}</small> {{ item.candidate_name }}</span><span class="saved-run-number">{{ traceValue(item.score) }}</span>
          </button>
        </div>
        <p v-else class="saved-run-muted">本次没有入排名候选。</p>
        <details v-if="unranked.length" class="saved-run-disclosure"><summary>查看未入排名的评估（{{ unranked.length }}）</summary><div class="saved-run-candidate-picker">
          <button v-for="item in unranked" :key="text(item.candidate_id)" type="button" :aria-pressed="candidateId === item.candidate_id" :data-candidate-id="item.candidate_id" @click="emit('candidate', text(item.candidate_id))"><span>{{ item.candidate_name || item.candidate_id }}</span><small>{{ traceOutcome(item.status) }}</small></button>
        </div></details>
      </SavedRunPanel>
      <SavedRunPanel v-if="candidate" :title="isRoot ? '结构评分' : '解释代价'" :icon="IconInfoCircle">
        <div v-if="scores.some(([, value]) => value != null)" class="saved-run-scores"><div v-for="[label, value] in scores" :key="text(label)"><span>{{ label }}</span><strong>{{ traceValue(value) }}</strong></div></div>
        <p v-else class="saved-run-muted">此候选未保存评分分量。</p>
        <p class="saved-run-note">{{ isRoot ? '结构相容分数，不是概率。' : selectedScore != null ? `${rank ? '排序分' : '评估分'} ${traceValue(selectedScore)} = −J，不是概率。` : '解释代价不是概率。' }}</p>
      </SavedRunPanel>
    </aside>
  </div>
</template>
