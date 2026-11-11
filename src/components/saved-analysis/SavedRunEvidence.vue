<script setup lang="ts">
import { IconInfoCircle, IconList, IconPushpin, IconRelation, IconSearch } from '@arco-design/web-vue/es/icon'
import { computed, nextTick, ref, watch } from 'vue'
import type { SavedAnalysis, SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { traceRecord, traceRows, traceValue, type TraceRecord } from '@/services/unified-reasoning-display'
import { channelLabel, featureLabel, isRootPropagation, observationChannel, observationScope, observationStatus, observationUsage, predicateLabel, procedureLabel, savedFacts, scopeLabel, strings, text, truthColor, truthLabel, valueKind, valueLabel } from './presentation'
import SavedRunPanel from './SavedRunPanel.vue'
import SavedRunMedia from './SavedRunMedia.vue'
import SavedRunTrend from './SavedRunTrend.vue'
import SavedRunWafer from './SavedRunWafer.vue'
import { savedWaferZone } from './wafer-zone'

const props = defineProps<{ analysis: SavedAnalysis; frame: SavedAnalysisFrame; candidate: TraceRecord | null; observationId: string }>()
const emit = defineEmits<{ observation: [id: string]; graph: [id: string]; reasoning: [] }>()
const initialObservation = props.frame.observationsById.get(props.observationId)
const query = ref(initialObservation && props.frame.observationsById.size > 60 ? observationChannel(props.frame, initialObservation) : '')
const usedFilter = ref('all')
const table = ref<HTMLElement | null>(null)
const obs = computed(() => props.frame.observationsById.get(props.observationId))
const scope = computed(() => obs.value ? observationScope(props.frame, obs.value) : null)
const waferZone = computed(() => {
  const zone = savedWaferZone(scope.value)
  return zone && traceRows(props.frame.frame.scopes).some(parent => parent.kind === 'spatial_grid'
    && parent.scope_id === zone.parentId && parent.scope_id === props.frame.scope?.scope_id
    && parent.subject_id === obs.value?.subject_id) ? zone : null
})
const subject = computed(() => props.frame.frame.subjects?.find(item => item.subject_id === obs.value?.subject_id))
const selectedChannel = computed(() => obs.value ? observationChannel(props.frame, obs.value) : '')
const chosenTrend = computed(() => props.frame.processTrends.find(item => item.channel === selectedChannel.value))
const procedure = computed(() => props.frame.frame.procedures?.find(item => item.procedure_id === obs.value?.procedure_id))
const reference = computed(() => props.frame.frame.references?.find(item => item.reference_id === obs.value?.reference_id))
const rawRefs = computed(() => strings(obs.value?.raw_refs).map(id => ({ id, asset: props.frame.frame.assets?.find(item => item.asset_id === id) })))
const appliedFacts = computed(() => savedFacts(props.frame).filter(fact => strings(fact.source_obs_ids).includes(props.observationId)))
const usage = computed(() => observationUsage(props.frame, props.candidate))
const observedCount = computed(() => new Set([...usage.value.condition, ...usage.value.structural, ...usage.value.support].filter(id => props.frame.observationsById.has(id))).size)
const unused = computed(() => new Set(traceRows(props.frame.result?.unused_observations).map(row => text(row.obs_id))))
const isRoot = computed(() => isRootPropagation(props.frame.result))
const media = computed(() => props.frame.media.filter(item => {
  if (scope.value?.kind !== 'image_region') return false
  const meta = traceRecord(item.metadata)
  if (meta.scope_id && meta.scope_id !== scope.value?.scope_id) return false
  if (item.source_key !== 'roi_path') return true
  const linked = text(meta.obs_id)
  return linked ? props.observationId === linked || props.observationId.startsWith(`${linked}:`) : meta.scope_id === scope.value?.scope_id
}))
const mediaId = ref('')
watch(media, value => { mediaId.value = value.find(item => ['image_path','source_path'].includes(item.source_key))?.artifact_id ?? value[0]?.artifact_id ?? '' }, { immediate: true })
const selectedMedia = computed(() => media.value.find(item => item.artifact_id === mediaId.value))
const locatable = computed(() => props.frame.pathsByObsId.get(props.observationId)?.some(path => !props.candidate || path.target_entity_id === props.candidate.candidate_id) ?? false)
const mediaName: Record<string, string> = { image_path: '原图', source_path: '原图', roi_path: 'ROI', heatmap_path: '热图', mask_path: '掩码' }

function useLabel(id: string) {
  if (usage.value.structural.has(id)) return { label: '结构评分', color: 'blue', used: true }
  if (usage.value.support.has(id)) return { label: '候选支持', color: 'blue', used: true }
  if (usage.value.condition.has(id)) return { label: '条件核验', color: 'gray', used: true }
  return { label: unused.value.has(id) ? '未使用' : '未标为使用', color: 'gray', used: false }
}
function subjectLabel(observation: TraceRecord) {
  const external = observationChannel(props.frame, observation)
  if (external === 'wafer' && props.analysis.run.dataset === 'wafer') return '晶圆'
  return external ? channelLabel(external) : observation.scope_id === props.frame.scope?.scope_id && props.frame.scope?.kind === 'image_region'
    ? props.frame.label : text(observation.subject_id) || '主体未保存'
}
const observations = computed(() => [...props.frame.observationsById].map(([id, observation]) => ({ id, observation,
  label: featureLabel(observation.feature_id), usage: useLabel(id), channel: observationChannel(props.frame, observation), subject: subjectLabel(observation),
  zone: props.analysis.run.dataset === 'wafer' ? savedWaferZone(observationScope(props.frame, observation))?.label : undefined,
})))
const shown = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return observations.value.filter(row => (usedFilter.value === 'all' || row.usage.used === (usedFilter.value === 'used'))
    && (!needle || [row.id, row.label, row.channel, row.subject, row.observation.feature_id].join(' ').toLowerCase().includes(needle)))
})
watch(() => props.observationId, async (id) => {
  if (!id) return
  if (!shown.value.some(row => row.id === id)) { query.value = ''; usedFilter.value = 'all' }
  await nextTick()
  const selected = [...table.value?.querySelectorAll<HTMLElement>('[data-observation-id]') ?? []].find(row => row.dataset.observationId === id)
  selected?.scrollIntoView?.({ block: 'nearest' })
}, { immediate: true, flush: 'post' })
</script>

<template>
  <div class="saved-run-stack">
    <div class="saved-run-notice"><IconInfoCircle /><span>{{ analysis.run.input_mode === 'evidence' ? '沿用导入 Frame；本次校验并绑定已有观测。' : '以下为此 Frame 保存的类型化观测。' }} 原始引用可查，未保存逐字段变换。</span></div>
    <div class="saved-run-grid saved-run-evidence-grid">
      <SavedRunPanel title="类型化观测" :icon="IconList" flat>
        <template #heading><a-tag color="blue" size="small">{{ observations.length }} 条</a-tag></template>
        <template #actions><span class="saved-run-muted">{{ isRoot ? `条件核验 ${usage.condition.size} · 结构评分 ${usage.structural.size}` : `${observedCount} 条用于条件核验或候选支持` }}</span></template>
        <div class="saved-run-filters">
          <a-input v-model="query" size="small" placeholder="特征或通道" :input-attrs="{ 'aria-label': '搜索观测' }" allow-clear><template #prefix><IconSearch /></template></a-input>
          <a-select v-model="usedFilter" v-control-label="'观测使用筛选'" size="small" aria-label="观测使用筛选"><a-option value="all">全部观测</a-option><a-option value="used">已使用</a-option><a-option value="unused">未标为使用</a-option></a-select>
        </div>
        <div v-if="shown.length" ref="table" class="saved-run-table-wrap">
          <table class="saved-run-table" aria-label="本次保存观测">
            <thead><tr><th scope="col">观测</th><th scope="col">实测值</th><th scope="col">主体 / 范围</th><th scope="col">本次使用</th></tr></thead>
            <tbody><tr v-for="row in shown" :key="row.id" :data-observation-id="row.id" :class="{ 'is-selected': row.id === observationId }" @click="emit('observation', row.id)">
              <td><button class="saved-run-table-button" type="button" :aria-pressed="row.id === observationId" @click.stop="emit('observation', row.id)">{{ row.label }}</button><small>{{ observationStatus(row.observation.status) }}</small></td>
              <td>{{ valueLabel(row.observation.value) }}</td><td>{{ row.subject }}<small v-if="row.observation.scope_id && row.observation.scope_id !== frame.scope?.scope_id">{{ row.zone ?? row.observation.scope_id }}</small></td>
              <td><a-tag size="small" :color="row.usage.color">{{ row.usage.label }}</a-tag></td>
            </tr></tbody>
          </table>
        </div>
        <p v-else class="saved-run-card-body saved-run-muted">{{ observations.length ? '没有符合当前筛选的观测。' : '此 Frame 没有保存观测。' }}</p>
      </SavedRunPanel>
      <aside class="saved-run-inspector">
        <SavedRunPanel title="观测定位" :icon="IconPushpin">
          <div v-if="obs" class="saved-run-stack" :data-located-observation-id="observationId">
            <div><div class="saved-run-row saved-run-wrap"><h3>{{ featureLabel(obs.feature_id) }}</h3><a-tag size="small" :color="useLabel(observationId).color">{{ useLabel(observationId).label }}</a-tag></div>
              <p class="saved-run-note">{{ subjectLabel(obs) }}<template v-if="scope?.kind === 'time_window'"> · {{ scopeLabel(scope) }}</template></p></div>
            <dl class="saved-run-kv saved-run-kv--compact">
              <div><dt>实测值</dt><dd><strong :title="JSON.stringify(obs.value)">{{ valueLabel(obs.value) }}</strong></dd></div>
              <div><dt>值类型</dt><dd>{{ valueKind(obs.value) }}</dd></div>
              <div><dt>单位</dt><dd>{{ text(traceRecord(obs.value).unit) || '未保存 / 不适用' }}</dd></div>
              <div><dt>主体</dt><dd>{{ text(subject?.external_id ?? obs.subject_id) || '未保存' }}</dd></div>
              <div><dt>范围</dt><dd>{{ scopeLabel(scope, text(obs.scope_id) || '未保存') }}</dd></div>
              <div><dt>测量程序</dt><dd :title="text(procedure?.definition)">{{ procedure ? procedureLabel(procedure) : text(obs.procedure_id) || '未保存' }}</dd></div>
              <div v-if="obs.reference_id"><dt>参考</dt><dd :title="text(obs.reference_id)">{{ reference?.kind === 'normal_standardization' ? '正常标准化参考' : text(reference?.kind) || '保存参考' }}</dd></div>
            </dl>
            <div v-if="selectedMedia" class="saved-run-observation-media">
              <a-radio-group v-if="media.length > 1" v-model="mediaId" type="button" size="mini" aria-label="观测媒体"><a-radio v-for="item in media" :key="item.artifact_id" :value="item.artifact_id">{{ mediaName[item.source_key] ?? item.title }}</a-radio></a-radio-group>
              <SavedRunMedia :item="selectedMedia" :scope="scope" :scope-label="frame.label" compact />
              <p v-if="Array.isArray(scope?.bbox_xyxy)" class="saved-run-note">{{ scope?.coordinate_space === 'original_image_pixels' ? '原图像素' : scope?.coordinate_space }} ROI [{{ scope?.bbox_xyxy.map(traceValue).join(', ') }}]</p>
            </div>
            <SavedRunTrend v-else-if="chosenTrend" :trend="chosenTrend" :scope="scope" :inherited="analysis.backbone.state === 'skipped'" compact />
            <SavedRunWafer v-else-if="(scope?.kind === 'spatial_grid' || waferZone) && frame.waferGrid" :grid="frame.waferGrid" :zone="waferZone" :inherited="analysis.backbone.state === 'skipped'" />
            <p v-else-if="scope?.kind === 'image_region' || selectedChannel && scope?.kind === 'time_window' || scope?.kind === 'spatial_grid' || waferZone" class="saved-run-muted">此观测没有关联可预览的附件。</p>
            <details v-if="appliedFacts.length" class="saved-run-disclosure">
              <summary>{{ isRoot ? '作者条件（非结构评分输入）' : '关联的保存条件' }}（{{ appliedFacts.length }}）</summary>
              <ul class="saved-run-detail-list"><li v-for="fact in appliedFacts" :key="text(fact.fact_id)"><strong>{{ predicateLabel(fact.predicate_check, text(fact.display_name)) }}</strong><a-tag size="small" :color="truthColor(fact.value)">{{ truthLabel(fact.value) }}</a-tag></li></ul>
            </details>
            <details class="saved-run-disclosure">
              <summary>已保存原始引用（{{ rawRefs.length }}）</summary>
              <ul v-if="rawRefs.length" class="saved-run-detail-list"><li v-for="ref in rawRefs" :key="ref.id"><strong>{{ ref.id }}<span v-if="ref.asset?.kind"> · {{ ref.asset.kind }}</span></strong><code>{{ ref.asset?.uri || '此引用没有保存资产记录' }}</code></li></ul>
              <p v-if="obs.reference_id" class="saved-run-note">参考 ID：<code>{{ obs.reference_id }}</code></p>
              <p class="saved-run-note">观测 ID：<code>{{ observationId }}</code></p>
            </details>
            <div class="saved-run-row saved-run-wrap">
              <a-button v-if="locatable" size="mini" type="text" @click="emit('graph', observationId)"><IconRelation /> 查看关联路径</a-button>
              <a-button v-if="frame.result" size="mini" type="text" @click="emit('reasoning')">返回保存解释</a-button>
            </div>
          </div>
          <p v-else class="saved-run-muted">选择一条观测，查看它的值、引用和关联范围。</p>
        </SavedRunPanel>
      </aside>
    </div>
  </div>
</template>
