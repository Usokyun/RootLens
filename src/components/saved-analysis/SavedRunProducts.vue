<script setup lang="ts">
import { IconFile, IconImage, IconInfoCircle, IconLink } from '@arco-design/web-vue/es/icon'
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import type { SavedAnalysis, SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { traceRecord, traceValue } from '@/services/unified-reasoning-display'
import { channelLabel, datasetLabel, inputLabel, number, procedureLabel, reasonerLabel, scopeLabel, text, type DetailTab } from './presentation'
import SavedRunPanel from './SavedRunPanel.vue'
import SavedRunMedia from './SavedRunMedia.vue'
import SavedRunTrend from './SavedRunTrend.vue'
import SavedRunWafer from './SavedRunWafer.vue'

const props = defineProps<{ tab: 'input' | 'backbone'; analysis: SavedAnalysis; frame: SavedAnalysisFrame }>()
const emit = defineEmits<{ tab: [tab: DetailTab] }>()
const run = computed(() => props.analysis.run)
const options = computed(() => traceRecord(run.value.input_snapshot))
const scope = computed(() => traceRecord(props.frame.scope))
const filename = computed(() => text(run.value.source_filename ?? options.value.source_filename))
const original = computed(() => props.frame.media.find(item => ['source_path', 'image_path'].includes(item.source_key)))
const products = computed(() => props.frame.media.filter(item => ['mask', 'heatmap'].includes(item.kind) || item.source_key === 'roi_path'))
const skipped = computed(() => props.analysis.backbone.state === 'skipped')
const channel = ref('')
watch(() => props.frame, value => { channel.value = value.processTrends[0]?.channel ?? '' }, { immediate: true })
const trend = computed(() => props.frame.processTrends.find(item => item.channel === channel.value))
const stageText = computed(() => skipped.value
  ? props.analysis.run.input_mode === 'evidence' ? '本次直接读取已有 Frame，跳过新 Backbone 测量。' : '本次读取中间测量记录，未执行新的 Backbone 提取。'
  : props.analysis.backbone.state === 'measured' ? '以下仅显示与此 Frame 关联的实际保存产物。' : '此保存运行未记录 Backbone 执行状态。')
const inputFields = computed(() => [
  ['输入文件', filename.value || '未保存'], ['输入类型', inputLabel(run.value.input_mode)], ['场景', datasetLabel(run.value.dataset)],
  ['当前范围', props.frame.label], ['解释器', reasonerLabel(run.value.reasoner_id)],
  ['保存工作图', text(run.value.graph_title) || text(run.value.graph_id) || '未保存'],
  ...(text(options.value.object_name) ? [['产品对象', text(options.value.object_name)]] : []),
  ...(text(options.value.model_preset) ? [['提交时模型配置', text(options.value.model_preset)]] : []),
  ...(run.value.input_mode === 'image' && text(options.value.semantic_mode) ? [['提交时 ROI 外观语义', options.value.semantic_mode === 'disabled' ? '关闭' : traceValue(options.value.semantic_mode)]] : []),
  ...(number(options.value.top_k) !== null ? [['保留候选数', traceValue(options.value.top_k)]] : []),
  ...(scope.value.kind === 'time_window' ? [
    ['样本索引', scopeLabel(scope.value)], ['索引基准', number(scope.value.index_base) !== null ? String(scope.value.index_base) : '未保存'],
    ['结束索引', typeof scope.value.end_inclusive === 'boolean' ? scope.value.end_inclusive ? '包含' : '不包含' : '未保存'],
    ...(number(scope.value.sampling_seconds) !== null ? [['采样间隔', `${scope.value.sampling_seconds} 秒 / 样本`]] : []),
  ] : []),
])
</script>

<template>
  <div v-if="tab === 'input'" class="saved-run-grid saved-run-overview-grid">
    <SavedRunPanel title="本次输入与配置" :icon="IconFile">
      <dl class="saved-run-kv"><div v-for="[label, value] in inputFields" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div></dl>
      <details class="saved-run-disclosure"><summary>保存的身份</summary><dl class="saved-run-kv saved-run-kv--mono"><div><dt>Run</dt><dd>{{ run.run_id }}</dd></div><div><dt>Frame</dt><dd>{{ frame.id }}</dd></div><div><dt>输入样本</dt><dd>{{ frame.sampleId }}</dd></div><div v-if="run.graph_id"><dt>工作图</dt><dd>{{ run.graph_id }}</dd></div></dl></details>
      <template v-if="run.graph_id" #footer>
        <RouterLink class="saved-run-link" :to="{ name: 'graphs', query: { graph: run.graph_id } }"><IconLink /> 打开当前登记工作图</RouterLink>
        <span class="saved-run-muted"> · 另页编辑，不是本次保存图</span>
      </template>
    </SavedRunPanel>
    <SavedRunPanel :title="skipped ? '关联的输入附件' : '输入预览'" :icon="IconImage">
      <SavedRunMedia v-if="original" :item="original" :scope="frame.scope" :scope-label="frame.label" compact />
      <SavedRunWafer v-else-if="frame.waferGrid" :grid="frame.waferGrid" :inherited="skipped" />
      <p v-else class="saved-run-muted">此输入没有可预览附件；原始引用见 Evidence。</p>
    </SavedRunPanel>
  </div>
  <div v-else class="saved-run-stack">
    <div class="saved-run-notice"><IconInfoCircle /> <span>{{ stageText }}<span v-if="skipped && (frame.media.length || frame.processTrends.length || frame.waferGrid)"> 下列附件沿用既有数据。</span></span></div>
    <SavedRunPanel :title="skipped ? '关联的保存产物' : '本次保存的 Backbone 产物'" :icon="IconImage">
      <template #actions><a-button size="mini" type="text" @click="emit('tab', 'evidence')">查看观测</a-button></template>
      <div v-if="original || products.length" class="saved-run-media-grid saved-run-product-grid">
        <SavedRunMedia v-if="original" :item="original" :scope="frame.scope" :scope-label="frame.label" :caption="skipped ? '关联既有原图' : '本次输入'" compact />
        <SavedRunMedia v-for="product in products" :key="product.artifact_id" :item="product" :caption="skipped ? '关联既有产物' : '模型保存产物'" compact />
      </div>
      <div v-else-if="trend" class="saved-run-stack">
        <div class="saved-run-row saved-run-wrap saved-run-between">
          <label class="saved-run-row"><span>保存通道</span><a-select v-model="channel" v-control-label="'选择 Backbone 保存通道'" size="small" aria-label="选择 Backbone 保存通道" class="saved-run-channel-select"><a-option v-for="item in frame.processTrends" :key="item.channel" :value="item.channel">{{ channelLabel(item.channel) }}</a-option></a-select></label>
          <span class="saved-run-muted">{{ frame.processTrends.length }} 个通道</span>
        </div>
        <SavedRunTrend :trend="trend" :scope="frame.scope" :inherited="skipped" />
      </div>
      <SavedRunWafer v-else-if="frame.waferGrid" :grid="frame.waferGrid" :inherited="skipped" />
      <p v-else class="saved-run-muted">此 Frame 没有关联可预览的模型产物。</p>
      <template v-if="analysis.run.dataset === 'mvtec' && !skipped" #footer>仅列出已保存的图像产物；本次分析接口未提供模型原始检测分。</template>
    </SavedRunPanel>
    <SavedRunPanel v-if="frame.frame.procedures?.length" title="随 Frame 保存的测量程序" :icon="IconFile">
      <ul class="saved-run-detail-list"><li v-for="procedure in frame.frame.procedures" :key="text(procedure.procedure_id)"><strong>{{ procedureLabel(procedure) }}</strong><span v-if="procedure.definition" class="saved-run-muted">{{ procedure.definition }}</span></li></ul>
    </SavedRunPanel>
  </div>
</template>
