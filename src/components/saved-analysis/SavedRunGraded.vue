<script setup lang="ts">
import { IconInfoCircle, IconList, IconPushpin, IconRelation } from '@arco-design/web-vue/es/icon'
import { computed, nextTick, ref, watch } from 'vue'
import type { SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { traceOutcome, traceRecord, traceRows, traceValue, type TraceRecord } from '@/services/unified-reasoning-display'
import { contributionPolarity, gradedCandidateGroups, gradedConditionRows, gradedReason, gradedScore, gradedStatus, gradedUnranked, signedContribution } from './graded-presentation'
import { channelLabel, factReason, number, observationChannel, predicateLabel, sourceLocator, strings, text, valueLabel, type DetailTab, type PathFocus } from './presentation'
import SavedRunPanel from './SavedRunPanel.vue'

const props = defineProps<{ frame: SavedAnalysisFrame; candidate: TraceRecord | null; pathId: string; observationId: string }>()
const emit = defineEmits<{ candidate: [id: string]; graph: [focus: PathFocus]; observation: [id: string, focus?: PathFocus]; tab: [tab: DetailTab] }>()
const activeId = computed(() => text(props.candidate?.candidate_id))
const scores = computed(() => gradedScore(props.candidate))
const groups = computed(() => {
  const { supported, pending } = gradedCandidateGroups(props.frame.result)
  const meta = traceRecord(props.frame.result?.graded_comparison)
  return [
    { status: 'supported', label: '有支持', rows: supported, total: number(meta.supported_count) ?? supported.length },
    { status: 'pending', label: '待核验', rows: pending, total: number(meta.pending_count) ?? pending.length },
  ]
})
const unranked = computed(() => gradedUnranked(props.frame.result))
const conditions = computed(() => gradedConditionRows(props.frame, props.candidate))
const candidateReasons = computed(() => strings(props.candidate?.reasons).map(gradedReason).filter(Boolean))
const sourceById = computed(() => new Map(traceRows(props.frame.result?.source_assertions).map(row => [text(row.assertion_id), row])))
const selectedRow = computed(() => conditions.value.find(row => row.observations.some(item => props.pathId
  ? item.focus?.pathId === props.pathId : !!props.observationId && item.id === props.observationId)))
const list = ref<HTMLElement | null>(null)
watch(selectedRow, async row => {
  if (!row) return
  await nextTick()
  const el = [...list.value?.querySelectorAll<HTMLElement>('[data-graded-condition]') ?? []]
    .find(item => item.dataset.gradedCondition === row.key)
  el?.scrollIntoView?.({ block: 'nearest' })
}, { immediate: true, flush: 'post' })
function exactSources(condition: TraceRecord) {
  return strings(condition.source_assertion_ids).flatMap(id => {
    const source = sourceById.value.get(id)
    return source ? [source] : []
  })
}
function gradeBasis(value: unknown) {
  return ({ source_explicit: '来源参数', normal_reference_estimate: '正常参考估计', declared_demo_heuristic: '演示启发式' } as Record<string, string>)[text(value)] ?? ''
}
</script>

<template>
  <div class="saved-run-grid saved-run-reasoning-grid" aria-label="分级解释溯因">
    <SavedRunPanel title="选中候选的分级贡献" :icon="IconRelation">
      <template v-if="frame.pathGraph.edge_count" #actions><a-button size="mini" type="text" @click="emit('tab', 'graph')">打开图谱</a-button></template>
      <div v-if="candidate" class="saved-run-stack">
        <header class="saved-run-row saved-run-wrap">
          <h3 class="saved-run-proof-title">{{ candidate.candidate_name || activeId }}</h3>
          <a-tag size="small" :color="candidate.status === 'supported' ? 'green' : 'orange'">{{ candidate.status === 'supported' ? '有支持' : candidate.status === 'pending' ? '待核验' : '未入分级榜' }}</a-tag>
        </header>
        <div v-if="scores.score !== null" class="saved-run-scores graded-scores" aria-label="分级分数分解">
          <div><span>相容分 S</span><strong data-graded-score="S">{{ traceValue(scores.score) }}</strong></div>
          <div><span>支持 P</span><strong data-graded-score="P">{{ traceValue(scores.support) }}</strong></div>
          <div><span>反证 C</span><strong data-graded-score="C">{{ traceValue(scores.conflict) }}</strong></div>
          <div><span>已核验覆盖 V</span><strong data-graded-score="V">{{ traceValue(scores.coverage) }}</strong></div>
        </div>
        <p v-if="candidateReasons.length" class="saved-run-note">{{ candidateReasons.join(' ') }}</p>
        <ul v-if="conditions.length" ref="list" class="graded-conditions">
          <li v-for="row in conditions" :key="row.key" :data-graded-condition="row.key" :data-predicate-id="row.condition.predicate_id"
              :class="{ 'is-selected': selectedRow === row }">
            <div class="saved-run-row saved-run-wrap saved-run-between">
              <div class="saved-run-row saved-run-wrap">
                <strong>{{ row.label }}</strong><a-tag size="small" :color="gradedStatus(row.condition).color">{{ gradedStatus(row.condition).label }}</a-tag>
                <a-tag v-if="row.condition.mode === 'possible'" size="small">辅证</a-tag>
              </div>
              <strong v-if="row.condition.slot_id" class="graded-delta" :data-polarity="contributionPolarity(row.condition.score_contribution)"
                :data-graded-contribution="row.condition.score_contribution" title="本条件对 S 的加权贡献">{{ signedContribution(row.condition.score_contribution) }}</strong>
              <span v-else class="saved-run-muted">不计分</span>
            </div>
            <div class="saved-run-row saved-run-wrap graded-reading">
              <span v-if="traceRows(row.condition.actual_values).length"><span class="saved-run-muted">{{ row.condition.status === 'unknown' ? '绑定记录' : '实测' }} </span>{{ traceRows(row.condition.actual_values).map(valueLabel).join(' · ') }}</span>
              <span v-else class="saved-run-muted">无适用实测</span>
              <span v-if="row.condition.slot_id" class="saved-run-muted">p {{ traceValue(row.condition.support) }} · c {{ traceValue(row.condition.conflict) }} · 权重 {{ traceValue(row.condition.weight) }}</span>
              <span v-if="row.condition.reason" class="saved-run-muted">{{ gradedReason(row.condition.reason) || factReason(row.condition.reason) }}</span>
            </div>
            <div v-if="row.observations.length" class="saved-run-row saved-run-wrap saved-run-proof-actions">
              <template v-for="item in row.observations" :key="item.id">
                <a-button size="mini" type="text" :data-observation-id="item.id" @click="emit('observation', item.id, item.focus ?? undefined)"><IconPushpin /> {{ item.obs.status === 'observed' ? '定位实测' : '查看观测记录' }}<template v-if="observationChannel(frame, item.obs) && frame.scope?.kind === 'time_window'"> · {{ channelLabel(observationChannel(frame, item.obs)) }}</template></a-button>
                <a-button v-if="item.focus" size="mini" type="text" :data-graded-path-id="item.focus.pathId" :data-graded-edge-id="item.focus.edgeId" @click="emit('graph', item.focus)"><IconRelation /> {{ item.focus.edgeId ? '定位图谱源边' : '查看贡献路径' }}</a-button>
              </template>
            </div>
            <details v-if="row.condition.grade || exactSources(row.condition).length" class="saved-run-disclosure graded-source">
              <summary>条件与来源</summary>
              <p>{{ predicateLabel(row.condition, row.label) }}</p>
              <p v-if="row.condition.grade" class="saved-run-note">
                {{ gradeBasis(traceRecord(row.condition.grade).basis) }} · 正／反宽度 {{ traceValue(traceRecord(row.condition.grade).support_width) }} / {{ traceValue(traceRecord(row.condition.grade).conflict_width) }}
                <template v-if="Number(traceRecord(row.condition.grade).neutral_support) || Number(traceRecord(row.condition.grade).neutral_conflict)"> · 正／反中性带 {{ traceValue(traceRecord(row.condition.grade).neutral_support) }} / {{ traceValue(traceRecord(row.condition.grade).neutral_conflict) }}</template>
              </p>
              <ul class="saved-run-detail-list"><li v-for="source in exactSources(row.condition)" :key="text(source.assertion_id)"><span>{{ source.text }}<template v-if="source.locator"> · {{ sourceLocator(source.locator) }}</template></span></li></ul>
            </details>
          </li>
        </ul>
        <p v-else class="saved-run-muted">此候选没有保存可核对的条件贡献。</p>
      </div>
      <p v-else class="saved-run-muted">选择一项候选，查看对应实测和贡献。</p>
      <template #footer>图谱定位到本次实际保存的贡献路径；单条路径不构成完整布尔证明。</template>
    </SavedRunPanel>
    <aside class="saved-run-stack">
      <SavedRunPanel title="分级候选" :icon="IconList">
        <div class="saved-run-stack">
          <section v-for="group in groups" :key="group.status" :aria-label="group.label" class="graded-group">
            <header class="saved-run-row saved-run-between"><h3>{{ group.label }}</h3><a-tag size="small" :color="group.status === 'supported' ? 'green' : 'orange'">{{ group.total }} 项</a-tag></header>
            <div v-if="group.rows.length" class="saved-run-candidate-picker">
              <button v-for="item in group.rows" :key="item.candidate_id" type="button" :aria-pressed="activeId === item.candidate_id" :data-candidate-id="item.candidate_id" @click="emit('candidate', item.candidate_id)">
                <span><small v-if="item.rank != null">#{{ item.rank }}</small> {{ item.candidate_name || item.candidate_id }}</span><span class="saved-run-number">S {{ traceValue(gradedScore(item).score) }}</span>
              </button>
            </div>
            <p v-else class="saved-run-muted">本次没有{{ group.label }}候选。</p>
            <small v-if="group.total > group.rows.length" class="saved-run-muted">本次保存了组内前 {{ group.rows.length }} 项的明细。</small>
          </section>
          <details v-if="unranked.length" class="saved-run-disclosure" :open="unranked.some(item => item.candidate_id === activeId)">
            <summary>其他评估（{{ unranked.length }}）</summary>
            <div class="saved-run-candidate-picker">
              <button v-for="item in unranked" :key="text(item.candidate_id)" type="button" :aria-pressed="activeId === item.candidate_id" :data-candidate-id="item.candidate_id" @click="emit('candidate', text(item.candidate_id))"><span>{{ item.candidate_name || item.candidate_id }}</span><small>{{ traceOutcome(item.status) }}</small></button>
            </div>
          </details>
        </div>
      </SavedRunPanel>
      <SavedRunPanel title="如何比较" :icon="IconInfoCircle">
        <p>两组同用 S = P − C，名次各按组内排列。S 是相容分，不是概率。</p>
        <p class="saved-run-note">缺测不扣分，测量权重不因缺项缩小。V 为该分支已核验的声明槽权重比例。</p>
      </SavedRunPanel>
    </aside>
  </div>
</template>

<style scoped>
.graded-group { display: grid; gap: 6px; }
.graded-scores > div:first-child { background: var(--sr-soft-blue); }
.graded-scores strong { font-size: 16px; }
.graded-conditions { list-style: none; padding: 0; margin: 0; }
.graded-conditions > li { border-top: 1px solid var(--sr-line); padding: 9px 5px 7px; }
.graded-conditions > li.is-selected { background: var(--sr-soft-blue); }
.graded-delta { color: var(--sr-muted); font-variant-numeric: tabular-nums; }
.graded-delta[data-polarity='positive'] { color: #1f6c46; }
.graded-delta[data-polarity='negative'] { color: #a73838; }
.graded-reading { margin: 2px 0; font-size: 12px; }
.graded-source { margin-top: 2px; padding-top: 0; border: 0; }
</style>
