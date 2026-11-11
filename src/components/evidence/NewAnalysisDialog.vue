<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { ApiError, createApiClient } from '@/api/client'
import { backendResourceUrl, createTwoLoopClient, type Dataset, type InputVariant, type ReasonerId, type WorkTask } from '@/api/two-loop'
import TaskStatusPanel from '@/components/tasks/TaskStatusPanel.vue'
import {
  analysisSubmission, createAnalysisDraft, currentDemoSample, datasetNames, demoGraphReference, demoGraphUnavailableNote,
  demoInputAvailable, enabledAnalysisGraphs, isAnalysisDataset, modeForDraft, readyDemoGraph, reconcileAnalysisSelection,
  sampleIdentity, type AnalysisCatalog, type AnalysisDraftSeed,
} from '@/services/analysis-draft'
import { taskIsActive, useTaskObserver } from '@/services/task-observer'

const props = defineProps<{ visible: boolean; baseUrl: string; seed: AnalysisDraftSeed | null }>()
const emit = defineEmits<{ 'update:visible': [visible: boolean]; 'task-change': [task: WorkTask | null]; 'open-result': [runId: string] }>()
const draft = ref(createAnalysisDraft())
const catalog = shallowRef<AnalysisCatalog | null>(null)
const preparing = ref(false)
const catalogError = ref('')
const sampleError = ref('')
const submitError = ref('')
const submitting = ref(false)
const showTask = ref(false)
const fileKey = ref(0)
const fileInput = ref<HTMLInputElement | null>(null)
const referenceInput = ref<HTMLInputElement | null>(null)
let catalogRevision = 0
let draftRevision = 0
let disposed = false

const observer = useTaskObserver(() => createTwoLoopClient(props.baseUrl), (finished) => {
  const id = finished.result?.run_id
  if (typeof id !== 'string' || !id) throw new Error('任务已完成，但服务未返回保存分析编号。')
  if (props.visible && showTask.value) emit('open-result', id)
})
const { task, connectionError, retrying } = observer
watch(task, (next) => emit('task-change', next))
const activeTask = computed(() => taskIsActive(task.value))
const completedRunId = computed(() => task.value?.status === 'completed' && typeof task.value.result?.run_id === 'string'
  ? task.value.result.run_id : null)

const sample = computed(() => catalog.value ? currentDemoSample(draft.value, catalog.value) : null)
const availableGraphs = computed(() => enabledAnalysisGraphs(catalog.value?.graphs ?? [], draft.value.dataset))
const graphUsable = computed(() => availableGraphs.value.some((graph) => graph.graph_id === draft.value.graphId))
const chosenGraph = computed(() => catalog.value?.graphs.find((graph) => graph.graph_id === draft.value.graphId))
const compatibleReasoners = computed(() => catalog.value?.reasoners.filter((reasoner) => reasoner.datasets.includes(draft.value.dataset)) ?? [])
const chosenReasoner = computed(() => compatibleReasoners.value.find((reasoner) => reasoner.reasoner_id === draft.value.reasonerId))
const pairedReference = computed(() => demoGraphReference(sample.value, catalog.value?.demos ?? null))
const pairedGraph = computed(() => readyDemoGraph(pairedReference.value, catalog.value?.graphs ?? [], draft.value.dataset))
const pairDiffers = computed(() => draft.value.graphOrigin === 'explicit' && pairedGraph.value && pairedGraph.value.graph_id !== draft.value.graphId)
const pairDownload = computed(() => backendResourceUrl(props.baseUrl, pairedReference.value?.download_url))
const sampleAsset = computed(() => draft.value.variant === 'evidence' ? sample.value?.evidence : sample.value?.raw_input)
const sampleDownload = computed(() => backendResourceUrl(props.baseUrl, sampleAsset.value?.download_url))
const inputMode = computed(() => modeForDraft(draft.value))
const inputAccept = computed(() => ({ image: '.png,.jpg,.jpeg,.bmp,.webp', process: '.dat,.csv,.txt', wafer: '.json,.jsonl', evidence: '.json', records: '.json,.jsonl' })[inputMode.value])
const inputHint = computed(() => ({
  image: 'PNG / JPG 等原始图像。后端定位 ROI 并测量几何。',
  process: 'DAT / CSV / TXT，完整 52 通道，另选配套正常参考。',
  wafer: 'JSON / JSONL，可包含 waferMap；0 背景、1 正常、2 失效。',
  evidence: '上传原生 EvidenceFrame、Frame 数组或 {frames:[…]}，不重复模型测量。',
  records: 'JSON / JSONL 测量记录。',
})[inputMode.value])
const canSubmit = computed(() => !!catalog.value && !preparing.value && !catalogError.value && !activeTask.value && !submitting.value
  && graphUsable.value && !!chosenReasoner.value && (draft.value.sampleId ? !!sample.value && demoInputAvailable(sample.value, draft.value.variant)
    : !!draft.value.file && (inputMode.value !== 'process' || !!draft.value.referenceFile)))
const sampleGroups = computed(() => (Object.keys(datasetNames) as Dataset[]).map((dataset) => ({
  dataset,
  samples: (catalog.value?.demos?.samples ?? []).filter((item) => item.dataset === dataset)
    .sort((left, right) => Number(right.recommended === true) - Number(left.recommended === true)),
})).filter((group) => group.samples.length))

function reconcileSelection() {
  if (catalog.value) Object.assign(draft.value, reconcileAnalysisSelection(draft.value, catalog.value))
}
async function readCatalog(resolveSeedGraph = false) {
  const revision = ++catalogRevision
  const base = props.baseUrl
  const service = createTwoLoopClient(base)
  preparing.value = true
  catalogError.value = ''
  sampleError.value = ''
  const [graphs, reasoners, demos] = await Promise.allSettled([
    createApiClient(base).listWorkingGraphs(), service.reasoners(), service.demos(),
  ])
  if (disposed || revision !== catalogRevision || props.baseUrl !== base) return
  preparing.value = false
  if (graphs.status === 'rejected' || reasoners.status === 'rejected') {
    catalogError.value = String(graphs.status === 'rejected' ? graphs.reason : reasoners.status === 'rejected' ? reasoners.reason : '')
    return
  }
  if (demos.status === 'rejected') sampleError.value = String(demos.reason)
  catalog.value = { graphs: graphs.value.graphs, reasoners: reasoners.value.reasoners, demos: demos.status === 'fulfilled' ? demos.value : null }
  if (resolveSeedGraph && draft.value.graphOrigin === 'explicit') {
    const intended = catalog.value.graphs.find((graph) => graph.graph_id === draft.value.graphId)
    if (intended) draft.value.dataset = intended.dataset
  }
  reconcileSelection()
}
function clearLocalInput() {
  draft.value.file = null
  draft.value.referenceFile = null
  draft.value.title = ''
  fileKey.value += 1
  submitError.value = ''
}
function changeDataset(value: unknown) {
  if (!isAnalysisDataset(value) || value === draft.value.dataset) return
  draft.value.dataset = value
  clearLocalInput()
  reconcileSelection()
}
function chooseGraph(value: unknown) {
  if (typeof value !== 'string' || !availableGraphs.value.some((graph) => graph.graph_id === value)) return
  draft.value.graphId = value
  draft.value.graphOrigin = 'explicit'
  submitError.value = ''
}
function chooseReasoner(value: unknown) {
  if (compatibleReasoners.value.some((item) => item.reasoner_id === value)) draft.value.reasonerId = value as ReasonerId
}
function chooseSample(value: unknown) {
  if (typeof value !== 'string' || !value) {
    draft.value.sampleId = ''
    reconcileSelection()
    return
  }
  const next = catalog.value?.demos?.samples.find((item) => sampleIdentity(item) === value)
  if (!next) return
  draft.value.sampleId = value
  draft.value.dataset = next.dataset
  draft.value.variant = demoInputAvailable(next, 'evidence') ? 'evidence' : 'raw'
  clearLocalInput()
  reconcileSelection()
}
function changeVariant(value: unknown) {
  if ((value !== 'raw' && value !== 'evidence') || value === draft.value.variant) return
  draft.value.variant = value as InputVariant
  clearLocalInput()
}
function fileFrom(event: Event) { return (event.target as HTMLInputElement).files?.[0] ?? null }
async function submit() {
  if (!canSubmit.value || !catalog.value) return
  submitError.value = ''
  submitting.value = true
  const base = props.baseUrl
  const revision = draftRevision
  try {
    const submission = analysisSubmission(draft.value, catalog.value)
    const service = createTwoLoopClient(base)
    const next = await (submission.kind === 'demo' ? service.inferDemo(submission.input) : service.infer(submission.input))
    if (disposed || props.baseUrl !== base) return
    if (revision === draftRevision) showTask.value = true
    observer.observe(next)
  } catch (error) {
    if (disposed || props.baseUrl !== base) return
    if (revision !== draftRevision) return
    submitError.value = error instanceof Error ? error.message : String(error)
    if (error instanceof ApiError && error.status === 0) submitError.value += ' 提交结果尚未确认，不会自动再次提交。'
  } finally {
    if (!disposed && props.baseUrl === base) submitting.value = false
  }
}

watch(() => [props.visible, props.seed] as const, ([visible, seed], previous) => {
  if (!visible) return
  if (!seed) {
    showTask.value = true
    return
  }
  if (previous?.[1] === seed) return
  draftRevision += 1
  draft.value = createAnalysisDraft(seed)
  catalog.value = null
  fileKey.value += 1
  submitError.value = ''
  showTask.value = false
  void readCatalog(true)
}, { immediate: true })
onBeforeUnmount(() => { disposed = true; catalogRevision += 1 })
</script>

<template>
  <a-modal
    :visible="visible" :title="showTask ? '分析任务' : '新建分析'" :footer="false"
    width="min(640px, calc(100vw - 32px))" :mask-closable="false" :closable="!submitting" :esc-to-close="!submitting"
    @update:visible="emit('update:visible', $event)"
  >
    <TaskStatusPanel v-if="showTask && task" :task="task" :connection-error="connectionError" :retrying="retrying" @refresh="observer.refresh" @retry="observer.retry">
      <template #actions>
        <a-button v-if="completedRunId" type="primary" size="small" @click="emit('open-result', completedRunId)">打开本次分析</a-button>
      </template>
    </TaskStatusPanel>
    <template v-else>
      <a-alert v-if="catalogError" type="error">
        {{ catalogError }}
        <a-button size="mini" type="text" :loading="preparing" @click="readCatalog(!catalog)">重新读取图谱与推理器</a-button>
      </a-alert>
      <div v-else-if="!catalog" role="status"><a-spin :size="14" /> 正在读取工作图与推理器…</div>
      <a-form v-else :model="draft" layout="vertical" class="new-analysis-form">
        <a-form-item v-if="sampleGroups.length || sampleError" label="公开演示样本（可选）">
          <div class="workspace-stack workspace-stack--tight new-analysis-fill">
            <a-select v-if="sampleGroups.length" :model-value="draft.sampleId || undefined" placeholder="选择样本以填入，不会自动运行" allow-clear allow-search aria-label="公开演示样本" @change="chooseSample">
              <a-optgroup v-for="group in sampleGroups" :key="group.dataset" :label="datasetNames[group.dataset]">
                <a-option v-for="item in group.samples" :key="sampleIdentity(item)" :value="sampleIdentity(item)" :label="item.title">
                  {{ item.title }}<a-tag v-if="item.recommended" color="arcoblue" size="small" class="new-analysis-recommended">推荐</a-tag>
                </a-option>
              </a-optgroup>
            </a-select>
            <a-alert v-if="sampleError" type="warning">公开样例暂不可读；可继续上传本地文件。</a-alert>
          </div>
        </a-form-item>

        <div class="new-analysis-pair">
          <a-form-item label="输入类型">
            <a-radio-group :model-value="draft.variant" type="button" aria-label="输入类型" @change="changeVariant">
              <a-radio value="raw" :disabled="!!sample && !demoInputAvailable(sample, 'raw')">原始样本</a-radio>
              <a-radio value="evidence" :disabled="!!sample && !demoInputAvailable(sample, 'evidence')">中间 Evidence</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item label="数据场景">
            <a-select :model-value="draft.dataset" :disabled="!!draft.sampleId" aria-label="数据场景" @change="changeDataset">
              <a-option v-for="(label, dataset) in datasetNames" :key="dataset" :value="dataset">{{ label }}</a-option>
            </a-select>
          </a-form-item>
        </div>

        <a-alert v-if="draft.sampleId" type="info" class="new-analysis-note">
          {{ sample?.title ?? '样例已选，当前目录不可读' }} · {{ draft.variant === 'evidence' ? '使用保存的真实观测，不重跑测量' : '将按样例设置重新测量' }}
          <span v-if="draft.variant === 'raw' && sample?.raw_options?.semantic_mode === 'vlm'">（包含外部 ROI 视觉模型）</span>
          <a v-if="sampleDownload" :href="sampleDownload" download>下载当前输入</a>
        </a-alert>
        <template v-else>
          <a-form-item label="待分析文件" :extra="inputHint">
            <div class="new-analysis-file">
              <a-button @click="fileInput?.click()">选择样本文件</a-button>
              <span class="workspace-subtle" aria-live="polite">{{ draft.file?.name ?? '未选择文件' }}</span>
              <input :key="fileKey" ref="fileInput" hidden type="file" :accept="inputAccept" aria-label="待分析文件" @change="draft.file = fileFrom($event)">
            </div>
          </a-form-item>
          <template v-if="inputMode === 'process'">
            <a-form-item label="正常参考文件" extra="参考与样本必须使用相同的 52 通道顺序。">
              <div class="new-analysis-file">
                <a-button @click="referenceInput?.click()">选择正常参考</a-button>
                <span class="workspace-subtle" aria-live="polite">{{ draft.referenceFile?.name ?? '未选择文件' }}</span>
                <input :key="`ref-${fileKey}`" ref="referenceInput" hidden type="file" accept=".dat,.csv,.txt" aria-label="正常参考文件" @change="draft.referenceFile = fileFrom($event)">
              </div>
            </a-form-item>
            <div class="new-analysis-pair">
              <a-form-item label="分析窗口（一基闭区间）">
                <a-input v-model="draft.windows" placeholder="1–100，161–260" aria-label="分析窗口" />
              </a-form-item>
              <a-form-item label="采样间隔（秒）">
                <a-input-number v-model="draft.samplingSeconds" :min="0.001" aria-label="采样间隔（秒）" />
              </a-form-item>
            </div>
          </template>
          <template v-if="inputMode === 'image'">
            <div class="new-analysis-pair">
              <a-form-item label="产品对象" extra="须与后端已配置的对象模型一致。"><a-input v-model="draft.objectName" aria-label="产品对象" /></a-form-item>
              <a-form-item label="异常定位模型">
                <a-select v-model="draft.modelPreset" aria-label="异常定位模型">
                  <a-option value="">自动选择</a-option><a-option value="patchcore">PatchCore</a-option>
                  <a-option value="stfpm">STFPM</a-option><a-option value="efficientad">EfficientAD</a-option>
                </a-select>
              </a-form-item>
            </div>
            <a-form-item extra="默认关闭：仅使用本地测量，不调用外部视觉模型。">
              <a-checkbox v-model="draft.roiSemantics">提取 ROI 外观语义（调用视觉模型）</a-checkbox>
            </a-form-item>
          </template>
        </template>

        <div class="new-analysis-pair">
          <a-form-item label="工作图（已启用）">
            <a-select :model-value="graphUsable ? draft.graphId : undefined" placeholder="选择当前场景工作图" aria-label="工作图（已启用）" @change="chooseGraph">
              <a-option v-for="graph in availableGraphs" :key="graph.graph_id" :value="graph.graph_id">{{ graph.title }}</a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="推理器">
            <a-select :model-value="draft.reasonerId || undefined" placeholder="当前场景无兼容推理器" aria-label="推理器" @change="chooseReasoner">
              <a-option v-for="reasoner in compatibleReasoners" :key="reasoner.reasoner_id" :value="reasoner.reasoner_id">{{ reasoner.title }}</a-option>
            </a-select>
          </a-form-item>
        </div>
        <p v-if="chosenReasoner" class="workspace-subtle new-analysis-reasoner">{{ chosenReasoner.description }}</p>
        <a-alert v-if="pairDiffers" type="warning" class="new-analysis-note">
          保留已明确选择的“{{ chosenGraph?.title ?? '工作图' }}”。它与样例配套图不同，可能得到证据不足。
          <a-button size="mini" type="text" @click="pairedGraph && chooseGraph(pairedGraph.graph_id)">切换到样例配套图</a-button>
        </a-alert>
        <a-alert v-else-if="draft.sampleId && !pairedGraph" type="warning" class="new-analysis-note">
          {{ demoGraphUnavailableNote(pairedReference) }}
          {{ graphUsable ? '按您明确选择的工作图运行。' : '请在图谱页导入并启用配套图，或明确选择其他工作图。' }}
          <a v-if="pairDownload" :href="pairDownload" download>下载配套图包</a>
        </a-alert>
        <a-alert v-else-if="!graphUsable" type="warning" class="new-analysis-note">
          {{ draft.graphOrigin === 'explicit' ? '指定图未启用、不可用或与场景不符，请核对后明确选图。' : '当前场景没有已启用的 v2 工作图，请先在图谱页启用。' }}
        </a-alert>
        <details class="new-analysis-options">
          <summary>结果设置</summary>
          <div class="new-analysis-pair">
            <a-form-item v-if="!draft.sampleId" label="分析名称（可选）"><a-input v-model="draft.title" aria-label="分析名称" /></a-form-item>
            <a-form-item label="保留候选数"><a-input-number v-model="draft.topK" :min="1" :max="100" :step="1" aria-label="保留候选数" /></a-form-item>
          </div>
        </details>
        <a-alert v-if="submitError" type="error" class="new-analysis-note">{{ submitError }}</a-alert>
        <div class="rl-form-actions new-analysis-actions">
          <a-button :loading="preparing" :disabled="submitting" @click="readCatalog()">重读目录</a-button>
          <a-button v-if="activeTask" @click="showTask = true">查看进行中的分析</a-button>
          <a-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">开始分析</a-button>
        </div>
      </a-form>
    </template>
  </a-modal>
</template>

<style scoped>
.new-analysis-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.new-analysis-fill { width: 100%; }
.new-analysis-form :deep(.arco-form-item) { margin-bottom: 12px; }
.new-analysis-file { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; overflow-wrap: anywhere; }
.new-analysis-note { margin-bottom: 12px; }
.new-analysis-note a { margin-inline-start: 8px; }
.new-analysis-recommended { margin-inline-start: 6px; }
.new-analysis-reasoner { margin: -3px 0 12px; }
.new-analysis-options summary { cursor: pointer; }
.new-analysis-options .new-analysis-pair { margin-top: 8px; }
.new-analysis-actions { justify-content: flex-end; margin-top: 12px; }
@media (max-width: 540px) { .new-analysis-pair { grid-template-columns: minmax(0, 1fr); gap: 0; } }
</style>
