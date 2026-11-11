<script setup lang="ts">
import { IconImage, IconInfoCircle, IconPushpin, IconRelation } from '@arco-design/web-vue/es/icon'
import { computed } from 'vue'
import SavedRunPanel from './SavedRunPanel.vue'
import SavedRunMedia from './SavedRunMedia.vue'
import SavedRunTrend from './SavedRunTrend.vue'
import SavedRunWafer from './SavedRunWafer.vue'
import type { SavedAnalysis, SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { savedTentativeCandidates, traceOutcome, traceRows, traceValue, type TraceRecord } from '@/services/unified-reasoning-display'
import { factReason, featureLabel, isRootPropagation, observationChannel, predicateLabel, reasonerLabel, savedCandidateRanks, savedFacts, strings, text, valueLabel, type DetailTab } from './presentation'

const props = defineProps<{ analysis: SavedAnalysis; frame: SavedAnalysisFrame; candidate: TraceRecord | null }>()
const emit = defineEmits<{ tab: [tab: DetailTab]; observation: [id: string] }>()
const result = computed(() => props.frame.result)
const ranks = computed(() => savedCandidateRanks(props.frame))
const isRoot = computed(() => isRootPropagation(result.value))
const tentativeCount = computed(() => isRoot.value ? 0 : savedTentativeCandidates(result.value).length)
const original = computed(() => props.frame.media.find(item => ['source_path', 'image_path'].includes(item.source_key)))
const heatmap = computed(() => props.frame.media.find(item => item.kind === 'heatmap'))
const support = computed(() => strings(props.candidate?.support_obs_ids).flatMap(id => {
  const observation = props.frame.observationsById.get(id)
  return observation ? [observation] : []
}))
const trend = computed(() => {
  const channel = support.value.map(obs => observationChannel(props.frame, obs)).find(id => props.frame.processTrends.some(item => item.channel === id))
  return props.frame.processTrends.find(item => item.channel === channel) ?? props.frame.processTrends[0]
})
const headline = computed(() => {
  const r = result.value
  if (!r) return { title: '未保存该 Frame 的推理结果', tag: '未保存', color: 'gray', copy: '此 Frame 的输入与观测仍可查看。' }
  if (r.reason === 'normal_reference_gate_is_false') return { title: '本窗口未越过异常门', tag: '正常门控', color: 'green', copy: '保存结果未启动候选排名，本窗口没有根因路径。' }
  if (!ranks.value.length && tentativeCount.value) return { title: `${tentativeCount.value} 项待验证`, tag: '证据不足', color: 'orange', copy: '部分实测符合联合分支，仍有反证或缺项；没有候选进入完整排名。' }
  if (r.outcome === 'insufficient_evidence') return { title: '本次证据不足', tag: '证据不足', color: 'orange', copy: '本次保存的观测未满足形成候选支持所需的条件。下方列出当前可见缺口。' }
  if (r.outcome === 'ambiguous' && ranks.value.length) {
    const topRank = ranks.value[0]?.rank
    const count = topRank == null ? 0 : ranks.value.filter(row => row.rank === topRank).length
    return { title: count > 1 ? `${count} 个候选并列首位` : '多个候选尚未区分', tag: '候选并列', color: 'orange',
      copy: isRoot.value ? '本窗口保存的通道贡献与图传播结构无法区分首位候选。' : '已有观测可支持多种候选，当前条件不足以区分这些解释。' }
  }
  return { title: traceOutcome(r.outcome), tag: r.outcome === 'supported' ? '有支持候选' : '保存结论', color: r.outcome === 'supported' ? 'green' : 'blue', copy: '候选及其依据来自本次保存结果。' }
})
const gaps = computed(() => savedFacts(props.frame).filter(fact => fact.value == null).slice(0, 3))
const claim = computed(() => traceRows(result.value?.source_assertions).find(row => row.origin === 'declared_demo_heuristic' && text(row.text)))
</script>

<template>
  <div class="saved-run-stack">
    <section class="saved-run-conclusion" :data-outcome="result?.outcome ?? 'not_recorded'" :data-tone="headline.color">
      <header class="saved-run-row saved-run-wrap"><h2>{{ headline.title }}</h2><a-tag size="small" :color="headline.color">{{ headline.tag }}</a-tag></header>
      <p>{{ headline.copy }}</p>
      <div class="saved-run-meta">{{ frame.observationsById.size }} 条观测<span class="saved-run-separator">·</span>{{ frame.pathGraph.path_count }} 条保存路径<span v-if="tentativeCount && ranks.length" class="saved-run-separator">·</span><template v-if="tentativeCount && ranks.length">{{ tentativeCount }} 项待验证</template><span class="saved-run-separator">·</span>{{ reasonerLabel(analysis.run.reasoner_id) }}</div>
    </section>
    <div class="saved-run-grid saved-run-overview-grid">
      <SavedRunPanel title="样本与测量" :icon="IconImage">
        <template #actions><a-button size="mini" type="text" @click="emit('tab', 'backbone')">查看 Backbone</a-button></template>
        <div v-if="original || heatmap" class="saved-run-media-grid" :class="{ 'saved-run-media-grid--single': !original || !heatmap }">
          <SavedRunMedia v-if="original" :item="original" :scope="frame.scope" :scope-label="frame.label" :caption="analysis.backbone.state === 'skipped' ? '关联既有原图' : '本次输入'" />
          <SavedRunMedia v-if="heatmap" :item="heatmap" :caption="analysis.backbone.state === 'skipped' ? '关联既有产物' : '模型保存产物'" />
        </div>
        <SavedRunTrend v-else-if="trend" :trend="trend" :scope="frame.scope" :inherited="analysis.backbone.state === 'skipped'" />
        <SavedRunWafer v-else-if="frame.waferGrid" :grid="frame.waferGrid" :inherited="analysis.backbone.state === 'skipped'" />
        <p v-else class="saved-run-muted">此 Frame 没有保存可预览的图像、网格或曲线。</p>
        <p v-if="claim" class="saved-run-note">{{ claim.text }}</p>
        <p v-else-if="heatmap" class="saved-run-note">热图是模型保存产物，不表示成因。</p>
      </SavedRunPanel>
      <div class="saved-run-stack">
        <SavedRunPanel :title="tentativeCount && !ranks.length ? '待验证观测' : '本候选用到的观测'" :icon="IconPushpin" flat>
          <template #actions><a-button size="mini" type="text" @click="emit('tab', 'evidence')">全部观测</a-button></template>
          <div v-if="support.length" class="saved-run-observation-preview">
            <button v-for="obs in support.slice(0, 5)" :key="text(obs.obs_id)" type="button" :data-observation-id="text(obs.obs_id)" @click="emit('observation', text(obs.obs_id))">
              <span><strong>{{ featureLabel(obs.feature_id) }}</strong><small>{{ observationChannel(frame, obs) || frame.label }}</small></span><span>{{ valueLabel(obs.value) }}</span>
            </button>
          </div>
          <p v-else class="saved-run-card-body saved-run-muted">{{ ranks.length ? '所选候选未保存支持观测引用。' : tentativeCount ? '待验证观测与反证见推理页。' : '本次没有入排名候选；已保存观测仍可查看。' }}</p>
        </SavedRunPanel>
        <SavedRunPanel title="还缺什么" :icon="IconInfoCircle">
          <ul v-if="gaps.length" class="saved-run-gap-list">
            <li v-for="fact in gaps" :key="text(fact.fact_id)"><strong>{{ predicateLabel(fact.predicate_check, text(fact.display_name) || text(fact.predicate_id)) }}</strong><span>{{ factReason(fact.reason) || '没有可判定的保存观测。' }}</span></li>
          </ul>
          <p v-else-if="result?.reason === 'normal_reference_gate_is_false'" class="saved-run-muted">异常前置条件未成立，本窗口无需展开候选条件。</p>
          <p v-else-if="result?.outcome === 'ambiguous'" class="saved-run-muted">当前结果没有足以区分并列候选的证据。</p>
          <p v-else-if="tentativeCount" class="saved-run-muted">查看待验证分支中与条件不符的实测。</p>
          <p v-else class="saved-run-muted">此结果未记录额外的缺测条件。</p>
        </SavedRunPanel>
      </div>
    </div>
    <SavedRunPanel title="候选摘要" :icon="IconRelation" flat>
      <template #actions><a-button size="mini" type="outline" @click="emit('tab', 'reasoning')">{{ tentativeCount && !ranks.length ? '查看待验证与代价' : '查看保存解释' }}</a-button></template>
      <ul v-if="ranks.length" class="saved-run-summary-candidates">
        <li v-for="rank in ranks.slice(0, 3)" :key="text(rank.candidate_id)"><span><small>#{{ rank.rank }}</small> {{ rank.candidate_name }}</span><span>{{ isRoot ? '结构分' : '排序分' }} {{ traceValue(rank.score) }}</span></li>
      </ul>
      <p v-else class="saved-run-card-body saved-run-muted">{{ result ? '本次没有入排名候选。' : '本次未保存候选结果。' }}</p>
      <template v-if="ranks.length" #footer>{{ isRoot ? '结构相容分数，不是概率。' : '排序分 = −J；假设成本与实测观测分开。' }}</template>
    </SavedRunPanel>
  </div>
</template>
