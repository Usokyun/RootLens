<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IconArrowRight, IconUpload, IconFile, IconImage, IconApps, IconBarChart, IconHistory, IconPlus, IconCheck, IconDownload, IconRefresh, IconExperiment, IconRelation, IconInfoCircle, IconClose, IconFolder } from '@arco-design/web-vue/es/icon'
import type { Dataset, InputMode, ReasonerId, DemoSample, DemoGroup, AnalysisRun, WorkTask } from '@/api/workbench'
import { apiUrl } from '@/api/workbench'
import { api, workspace, currentGraph, refreshWorkspace, refreshGraphs, refreshAnalyses, selectGraph, selectAnalysis } from '@/services/workspace'
import { datasetShort, text, record, friendly, fileSize, dateTime, parseWindows } from '@/services/presentation'
import { useTaskObserver } from '@/services/task-observer'
import { demoGraphReference, readyDemoGraph, demoGraphUnavailableNote } from '@/services/demo-graph-selection'
import { newAnalysisIntent } from '@/services/analysis-entry'
import { revealTask } from '@/services/reveal-task'
import TaskProgress from '@/components/ui/TaskProgress.vue'
import RunResults from '@/components/analysis/RunResults.vue'

const router = useRouter(), route = useRoute()
let contextVersion = 0
const inputKind = ref<'raw' | 'evidence'>('raw'), rawFormat = ref<'native' | 'records'>('native')
const dataset = ref<Dataset>(currentGraph.value?.dataset ?? 'mvtec')
const file = ref<File | null>(null), reference = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null), referenceInput = ref<HTMLInputElement | null>(null)
const previewUrl = ref(''), dragging = ref(false)
const graphId = ref(workspace.graphId), reasonerId = ref<ReasonerId>('unified_abduction')
const inputTitle = ref('')
const form = reactive({ objectName: 'bottle', modelPreset: 'auto', semantics: true, windows: '1–100，161–260', topK: 8 })
const busy = ref(false), error = ref(''), loadingRun = ref(false), initializing = ref(true)
const run = ref<AnalysisRun | null>(null), setupOpen = ref(true), historyOpen = ref(false)
const demoOpen = ref(false), demoGroup = ref<DemoGroup | null>(null), selectedSampleId = ref('')
const loadedSample = ref<DemoSample | null>(null), loadedGroup = ref<DemoGroup | null>(null)
const loadedVariant = ref<'raw' | 'evidence'>('raw')
const enabledGraphs = computed(() => workspace.graphs.filter((g) => g.enabled && g.status === 'ready' && g.dataset === dataset.value && record(g.knowledge).schema_version === 'rootlens-knowledge-package.v2'))
const pairedReference = computed(() => {
  const group = workspace.demos.demos.find(item=>item.id===loadedGroup.value?.id) ?? loadedGroup.value
  const sampleId = loadedSample.value?.sample_id ?? loadedSample.value?.id
  const sample = group?.samples.find(item=>(item.sample_id ?? item.id)===sampleId) ?? loadedSample.value
  return demoGraphReference(sample,group)
})
const pairedGraph = computed(() => readyDemoGraph(pairedReference.value,workspace.graphs,dataset.value))
const selectedGraphApplicable = computed(() => enabledGraphs.value.some(graph => graph.graph_id===graphId.value))
const selectedGraphTitle = computed(() => friendly(workspace.graphs.find(graph => graph.graph_id===graphId.value)?.title,'当前指定图谱'))
const compatibleReasoners = computed(() => workspace.reasoners.filter((r) => r.datasets.includes(dataset.value)))
const inputMode = computed<InputMode>(() => inputKind.value === 'evidence' ? 'evidence' : rawFormat.value === 'records' ? 'records' : dataset.value === 'mvtec' ? 'image' : dataset.value === 'tep' ? 'process' : 'wafer')
const inputAccept = computed(() => inputMode.value === 'image' ? '.png,.jpg,.jpeg,.bmp,.webp' : inputMode.value === 'process' ? '.dat,.csv,.txt' : ['records','wafer'].includes(inputMode.value) ? '.json,.jsonl' : '.json')
const inputHint = computed(() => ({ image: 'PNG / JPG · 后端定位 ROI、测量几何并识别外观', process: 'DAT / CSV · 完整 52 通道过程文件，并提供配套正常参考', wafer: 'JSON / JSONL · 原生二维网格或晶圆记录，0 背景 / 1 正常 / 2 失效', evidence: 'JSON · EvidenceFrame、frames 数组或结构化 Evidence', records: 'JSON / JSONL · 已有测量 adapter records' })[inputMode.value])
const selectedSample = computed(() => demoGroup.value?.samples.find((s) => (s.sample_id ?? s.id) === selectedSampleId.value) ?? demoGroup.value?.samples[0])
const mainSample = computed(() => demoGroup.value?.samples.find((s) => s.recommended === true || s.demo_role === 'recommended' || s.role === 'primary') ?? demoGroup.value?.samples.find((s) => /主演示|推荐/.test(s.title)) ?? demoGroup.value?.samples[0])
const otherSamples = computed(() => demoGroup.value?.samples.filter((s) => s !== mainSample.value) ?? [])
const running = computed(() => task.value && ['queued','running'].includes(task.value.status))
const canRun = computed(() => (file.value || loadedSample.value) && selectedGraphApplicable.value && compatibleReasoners.value.some((r) => r.reasoner_id === reasonerId.value) && !busy.value && !running.value && !initializing.value)
const taskObserver = useTaskObserver(async (next) => {
  if (next.result?.run_id) { await loadRun(text(next.result.run_id)); await refreshAnalyses() }
})
const { task, connectionError, retrying } = taskObserver
function trackTask(next: WorkTask) { taskObserver.observe(next); void revealTask(next.task_id) }
async function retryCurrentTask() { await taskObserver.retry(); if (task.value) void revealTask(task.value.task_id) }

function syncGraph() {
  let chosenId = graphId.value
  if (workspace.graphSelection === 'explicit') chosenId = workspace.graphId || graphId.value
  else if (loadedSample.value) chosenId = pairedGraph.value?.graph_id ?? ''
  else chosenId = enabledGraphs.value.find(graph=>graph.graph_id===graphId.value)?.graph_id ?? enabledGraphs.value.find(graph=>graph.graph_id===workspace.graphId)?.graph_id ?? enabledGraphs.value[0]?.graph_id ?? ''
  graphId.value = chosenId
  if (workspace.graphSelection !== 'explicit' || chosenId !== workspace.graphId) selectGraph(chosenId,workspace.graphSelection)
  if (!compatibleReasoners.value.some((r) => r.reasoner_id === reasonerId.value)) reasonerId.value = compatibleReasoners.value[0]?.reasoner_id ?? 'unified_abduction'
}
function chooseAnalysisGraph(id:string) { graphId.value=id; selectGraph(id,'explicit') }
function chooseDataset(value: Dataset) {
  if (value === dataset.value) return
  dataset.value = value; file.value = null; reference.value = null; loadedSample.value = null; loadedGroup.value = null; inputTitle.value = ''; setPreview(null)
  graphId.value=''; selectGraph('','implicit'); syncGraph()
}
function clearDemo() { loadedSample.value = null; loadedGroup.value = null; syncGraph() }
function setInputKind(value: 'raw' | 'evidence') {
  inputKind.value = value
  if (loadedSample.value) loadedVariant.value = value
  else { file.value = null; setPreview(null) }
}
function setPreview(value: File | null) {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = value?.type.startsWith('image/') ? URL.createObjectURL(value) : ''
}
function chooseFile(value: File | null) {
  file.value = value; loadedSample.value = null; loadedGroup.value = null; setPreview(value)
  if (value) inputTitle.value = value.name.replace(/\.[^.]+$/, '')
}
function drop(event: DragEvent) { event.preventDefault(); dragging.value = false; chooseFile(event.dataTransfer?.files[0] ?? null) }
function openDemo(demo: DemoGroup) { demoGroup.value = demo; const recommended = demo.samples.find((s) => s.recommended === true || s.demo_role === 'recommended' || s.role === 'primary') ?? demo.samples[0]; selectedSampleId.value = text(recommended?.sample_id ?? recommended?.id); demoOpen.value = true }
function loadDemo(variant: 'raw' | 'evidence') {
  if (!selectedSample.value || !demoGroup.value) return
  loadedSample.value = selectedSample.value; loadedGroup.value = demoGroup.value; loadedVariant.value = variant; dataset.value = demoGroup.value.dataset
  inputKind.value = variant; inputTitle.value = selectedSample.value.title; file.value = null; reference.value = null; setPreview(null)
  rawFormat.value = 'native'; syncGraph(); demoOpen.value = false; setupOpen.value = true
}
async function start() {
  error.value = ''; busy.value = true
  try {
    if (!selectedGraphApplicable.value) throw new Error('先选择当前场景已投入使用的知识图谱。')
    selectGraph(graphId.value,workspace.graphSelection)
    if (loadedSample.value) {
      trackTask(await api().inferDemo({ sample_id: text(loadedSample.value.sample_id ?? loadedSample.value.id), graph_id: graphId.value, reasoner_id: reasonerId.value, input_variant: loadedVariant.value, top_k: form.topK }))
    } else {
      if (!file.value) throw new Error('请先选择待分析样本。')
      if (inputMode.value === 'process' && !reference.value) throw new Error('请提供配套的正常参考文件，用于拟合过程测量基准。')
      trackTask(await api().infer({ file: file.value, reference_file: inputMode.value === 'process' ? reference.value! : undefined, graph_id: graphId.value, reasoner_id: reasonerId.value, input_mode: inputMode.value, dataset: dataset.value, object_name: inputMode.value === 'image' ? form.objectName : undefined, model_preset: inputMode.value === 'image' ? form.modelPreset : undefined, semantic_mode: inputMode.value === 'image' ? form.semantics ? 'vlm' : 'disabled' : undefined, windows: inputMode.value === 'process' ? parseWindows(form.windows) : undefined, title: inputTitle.value || undefined, top_k: form.topK }))
    }
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { busy.value = false }
}
async function loadRun(id: string) {
  const version = ++contextVersion
  loadingRun.value = true; error.value = ''
  try {
    const saved = await api().analysis(id)
    if (version !== contextVersion) return
    run.value = saved; selectAnalysis(id); setupOpen.value = false; historyOpen.value = false
  } catch (e) { if (version === contextVersion) error.value = e instanceof Error ? e.message : String(e) }
  finally { if (version === contextVersion) loadingRun.value = false }
}
function enterNewAnalysis(selectedGraphId: string, origin:'implicit'|'explicit' = workspace.graphSelection) {
  contextVersion += 1; taskObserver.clear(); run.value = null; loadingRun.value = false
  setupOpen.value = true; historyOpen.value = false; demoOpen.value = false; error.value = ''
  selectAnalysis(''); file.value = null; reference.value = null; loadedSample.value = null; loadedGroup.value = null
  inputTitle.value = ''; inputKind.value = 'raw'; rawFormat.value = 'native'; setPreview(null)
  if (fileInput.value) fileInput.value.value = ''
  if (referenceInput.value) referenceInput.value.value = ''
  const chosen = workspace.graphs.find((graph) => graph.graph_id === selectedGraphId)
  if (!chosen || !chosen.enabled || chosen.status !== 'ready') {
    graphId.value = ''; error.value = '选定的图谱尚未投入使用或已不可用，请重新选择工作图谱。'; return
  }
  dataset.value = chosen.dataset; graphId.value = chosen.graph_id; selectGraph(chosen.graph_id,origin); syncGraph()
}
async function consumeNewAnalysisIntent() {
  const intent = newAnalysisIntent(route.query)
  if (!intent) return false
  enterNewAnalysis(intent.graphId,'explicit')
  await router.replace({ name: 'evidence' })
  return true
}
function newAnalysis() {
  enterNewAnalysis(workspace.graphId || run.value?.graph_id || '')
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
watch(() => workspace.connected, (connected) => { if (connected && error.value.startsWith('无法连接后端服务')) error.value = '' })
watch([() => workspace.graphs, () => workspace.reasoners, dataset, pairedReference], syncGraph)
watch(() => [route.query.intent, route.query.graph], () => {
  if (!newAnalysisIntent(route.query)) return
  selectAnalysis('')
  if (!initializing.value) void consumeNewAnalysisIntent()
})
onMounted(async () => {
  if (newAnalysisIntent(route.query)) selectAnalysis('')
  const entryVersion = contextVersion
  try {
    if (!workspace.connected) await refreshWorkspace()
    else await Promise.all([refreshGraphs(), refreshAnalyses()])
    if (entryVersion !== contextVersion || await consumeNewAnalysisIntent()) return
    syncGraph(); initializing.value = false
    const activeTask = workspace.tasks.find((t) => t.kind === 'inference' && ['running','queued'].includes(t.status))
    if (activeTask) taskObserver.observe(activeTask)
    if (workspace.analysisId && !activeTask) { setupOpen.value = false; await loadRun(workspace.analysisId) }
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { initializing.value = false }
})
onBeforeUnmount(() => { contextVersion += 1; if (previewUrl.value) URL.revokeObjectURL(previewUrl.value) })
</script>
<template>
  <div class="analysis-page"><div class="page-heading"><div><span class="eyebrow">03 / TRACEABLE REASONING</span><h1>从样本走到解释</h1><p>原始样本先测量，Evidence 直接进入推理。把观测、知识条件与候选逐一对应起来。</p></div><div class="page-heading__actions"><button class="button button--secondary" :disabled="initializing" @click="historyOpen = true; refreshAnalyses()"><IconHistory /> 已保存分析</button><button v-if="run && !setupOpen" class="button button--primary" @click="newAnalysis"><IconPlus /> 新建分析</button></div></div>
    <div v-if="error" class="alert alert--error" role="alert"><span class="grow">{{ error }}</span><button class="text-button" @click="error = ''">关闭</button></div>
    <TaskProgress v-if="task && (setupOpen || running || task.result?.run_id === run?.run_id)" :task="task" :connection-error="connectionError" :retrying="retrying" @retry="retryCurrentTask" @refresh="taskObserver.refresh" />
    <div v-if="initializing" class="loading-inline analysis-initializing" role="status"><IconRefresh class="is-spinning" />正在准备本次图谱与分析入口…</div>
    <template v-else-if="setupOpen"><section v-if="workspace.demos.demos.length" class="demo-starter"><div class="demo-starter__intro"><strong>加载公开演示样本</strong><small>选择输入，再真实运行</small></div><div class="demo-starter__options"><button v-for="demo in workspace.demos.demos" :key="demo.id" class="demo-choice" @click="openDemo(demo)"><IconImage v-if="demo.dataset === 'mvtec'" /><IconBarChart v-else-if="demo.dataset === 'tep'" /><IconApps v-else /><span><strong>{{ datasetShort[demo.dataset] }}</strong><small>原始样本 / 中间 Evidence</small></span><IconArrowRight /></button></div></section>
      <div class="analysis-setup"><section class="panel input-panel"><header class="panel-header"><div class="step-title"><span class="step-number">1</span><div><h2>待分析样本</h2><p>这里上传样本，不是用于构图的知识资料</p></div></div><button v-if="run" class="text-button" @click="setupOpen = false">返回结果</button></header><div class="panel-body"><div class="input-kind-options"><button :class="{ active: inputKind === 'raw' }" @click="setInputKind('raw')"><IconFolder /><span><strong>从原始样本开始</strong><small>模型测量 → Evidence → 推理</small></span><i /></button><button :class="{ active: inputKind === 'evidence' }" @click="setInputKind('evidence')"><IconFile /><span><strong>从 Evidence 开始</strong><small>保留已有观测，直接复算</small></span><i /></button></div><label class="field input-scene-label">数据场景</label><div class="scene-options"><button v-for="(name,key) in datasetShort" v-show="key !== 'shared'" :key="key" :class="{ active: dataset === key }" @click="chooseDataset(key as Dataset)"><IconImage v-if="key === 'mvtec'" /><IconBarChart v-else-if="key === 'tep'" /><IconApps v-else />{{ name }}</button></div>
          <section v-if="loadedSample" class="loaded-demo-input"><div class="loaded-demo-heading"><span class="tag tag--blue">公开演示输入</span><span class="tag">{{ loadedVariant === 'raw' ? '原始样本' : '冻结测量 Evidence' }}</span><button aria-label="清除演示输入" class="text-button" @click="clearDemo"><IconClose /></button></div><img v-if="dataset === 'mvtec' && loadedSample.raw_input?.download_url" :src="apiUrl(workspace.baseUrl, loadedSample.raw_input.download_url)" alt="待运行的公开原始图像" /><div class="loaded-demo-input__body"><strong>{{ loadedSample.title }}</strong><p>{{ loadedVariant === 'raw' ? '将真实执行测量与推理。' : '将使用已冻结的实际观测，按当前图谱重新推理。' }}</p><span class="status-dot status-dot--amber">输入已载入，等待开始分析</span></div></section>
          <template v-else><div class="file-drop inference-drop" :class="{ 'is-dragging': dragging }" role="button" tabindex="0" @click="fileInput?.click()" @keydown.enter.prevent="fileInput?.click()" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop="drop"><template v-if="previewUrl"><img :src="previewUrl" alt="待分析的原始图片" /></template><IconUpload v-else /><strong>{{ file?.name || '选择样本，或拖放到这里' }}</strong><p>{{ file ? `${fileSize(file.size)} · 点击更换文件` : inputHint }}</p><input ref="fileInput" class="native-file" type="file" :accept="inputAccept" @change="chooseFile(($event.target as HTMLInputElement).files?.[0] ?? null)" /></div><div v-if="inputMode === 'process'" class="reference-upload"><span><strong>配套正常参考</strong><small>与样本相同的 52 通道顺序</small></span><button class="button button--secondary button--small" @click="referenceInput?.click()"><IconUpload />{{ reference?.name || '选择正常参考' }}</button><input ref="referenceInput" class="native-file" type="file" accept=".dat,.csv,.txt" @change="reference = ($event.target as HTMLInputElement).files?.[0] ?? null" /></div></template>
          <div class="input-bottom-fields"><label class="field">分析名称<input v-model="inputTitle" placeholder="例如：玻璃边缘样本检查 / 冷却回路窗口" /></label><template v-if="!loadedSample"><label v-if="inputMode === 'process'" class="field">分析窗口<input v-model="form.windows" placeholder="1–100，161–260" /><small>样本编号从 1 开始，首尾均包含；多个窗口用逗号分隔。</small></label><label v-if="inputMode === 'image'" class="checkbox-label"><input v-model="form.semantics" type="checkbox" />提取 ROI 外观语义（调用视觉模型）</label><details v-if="inputKind === 'raw'" class="input-advanced"><summary>输入与模型设置</summary><div class="form-stack"><label class="field">原始输入格式<select v-model="rawFormat"><option value="native">场景原生样本</option><option value="records">已有模型中间记录（records）</option></select></label><div v-if="inputMode === 'image'" class="form-grid"><label class="field">产品对象<input v-model="form.objectName" placeholder="bottle" /><small>必须对应后端已配置的对象模型。</small></label><label class="field">异常定位模型<select v-model="form.modelPreset"><option value="auto">自动选择可用模型</option><option value="patchcore">PatchCore</option><option value="stfpm">STFPM</option><option value="efficientad">EfficientAD</option></select></label></div></div></details></template></div>
          <div class="input-contract-note"><IconInfoCircle /><span>{{ inputKind === 'raw' ? '测量和推理在后端完成。没有可用模型或必要参考时，会明确失败，不用示例结果替代。' : '上传的测量值与范围将原样保留。缺测不是阴性；无图像或序列附件时仍可检查标量依据。' }}</span></div>
        </div></section>
        <section class="panel inference-config"><header class="panel-header"><div class="step-title"><span class="step-number">2</span><div><h2>选择知识与推理器</h2><p>明确本次解释依据</p></div></div></header><div class="panel-body"><label class="field">工作图谱<select aria-label="工作图谱" :value="graphId" :disabled="!enabledGraphs.length" @change="chooseAnalysisGraph(($event.target as HTMLSelectElement).value)"><option v-if="graphId && !selectedGraphApplicable" :value="graphId" disabled>{{ selectedGraphTitle }} · 不适用当前场景 / 尚不可用</option><option v-else-if="!graphId && enabledGraphs.length" value="" disabled>{{ loadedSample ? '请明确选择配套图或其他工作图' : '请选择工作图谱' }}</option><option v-if="!enabledGraphs.length" value="">{{ workspace.loading ? '正在读取工作图谱…' : '当前场景没有已启用的图谱' }}</option><option v-for="graph in enabledGraphs" :key="graph.graph_id" :value="graph.graph_id">{{ friendly(graph.title, '知识图谱') }}</option></select><small v-if="enabledGraphs.length">只列出当前场景已投入使用的图谱。</small><small v-else>前往知识图谱检查并“投入使用”，再回来分析。</small></label><div v-if="loadedSample" class="demo-graph-context" :class="{ 'demo-graph-context--warning':!pairedGraph || graphId!==pairedGraph.graph_id }" role="status"><template v-if="pairedGraph && graphId===pairedGraph.graph_id"><strong>已选择样例配套图</strong><p>{{ friendly(pairedGraph.title) }}</p></template><template v-else-if="pairedGraph"><strong>保留你明确选择的工作图</strong><p>{{ selectedGraphTitle }} 与此样例配套图不同，结果可能无匹配或证据不足。</p><button type="button" class="text-button" @click="chooseAnalysisGraph(pairedGraph.graph_id)">切换到样例配套图：{{ friendly(pairedGraph.title) }}</button></template><template v-else><strong>样例配套图尚不可用</strong><p>{{ demoGraphUnavailableNote(pairedReference) }}</p><p v-if="workspace.graphSelection==='explicit'">当前仍保留你的指定图谱；结果取决于它实际支持的条件。</p><div class="tag-row"><a v-if="pairedReference?.download_url" class="text-button" :href="apiUrl(workspace.baseUrl,pairedReference.download_url)" download>下载配套图谱</a><router-link class="text-button" :to="{name:'graphs',query:pairedReference?.graph_id?{graph:pairedReference.graph_id}:{}}">前往导入 / 启用</router-link><button type="button" class="text-button" @click="refreshWorkspace()">重读配套图状态</button></div></template></div><button v-if="!enabledGraphs.length" class="button button--secondary button--full" @click="router.push('/graphs')"><IconRelation /> 前往启用图谱 <IconArrowRight /></button><div class="reasoner-selection"><label class="field">推理器</label><p v-if="workspace.loading" class="muted">正在读取可用推理器…</p><button v-for="reasoner in workspace.reasoners" :key="reasoner.reasoner_id" class="reasoner-option" :class="{ active: reasonerId === reasoner.reasoner_id, unavailable: !reasoner.datasets.includes(dataset) }" :disabled="!reasoner.datasets.includes(dataset)" @click="reasonerId = reasoner.reasoner_id"><span class="reasoner-radio"><IconCheck v-if="reasonerId === reasoner.reasoner_id" /></span><span><strong>{{ reasoner.reasoner_id === 'tep_rootkgd' ? 'TEP RootKGD' : '统一约束推理' }}</strong><small>{{ reasoner.reasoner_id === 'tep_rootkgd' ? '图传播与全通道贡献结构比较' : '联合条件、冲突与缺测的统一溯因' }}</small><em v-if="!reasoner.datasets.includes(dataset)">仅支持 TEP 过程数据</em><em v-else>{{ reasoner.reasoner_id === 'tep_rootkgd' ? '结构分数，不是置信率' : '解释代价，不是置信率' }}</em></span></button></div><label class="field">保留候选数<input v-model.number="form.topK" type="number" min="1" max="20" /><small>同分候选不会因截断丢失。复算时保持与原运行一致。</small></label><div class="run-config-summary"><span class="section-kicker">本次将执行</span><ol><li><span>输入</span>{{ inputKind === 'raw' ? '原始样本' : 'Evidence JSON' }}</li><li><span>场景</span>{{ datasetShort[dataset] }}</li><li><span>处理</span>{{ inputKind === 'raw' ? '实际测量 → 绑定 → 推理' : '类型与绑定检查 → 推理' }}</li><li v-if="dataset === 'tep' && loadedSample"><span>窗口</span>{{ JSON.stringify(record(loadedSample.raw_options).windows ?? '示例配套窗口') }}</li></ol></div></div><footer class="panel-footer"><button class="button button--primary button--full" :disabled="!canRun" @click="start"><IconExperiment />{{ busy ? '正在提交…' : running ? '正在处理本次样本…' : '开始分析' }}<IconArrowRight /></button><p>{{ loadedSample ? '运行已载入输入，不是打开已有结果' : '任务可追踪，输入与完整结果会持久保存' }}</p></footer></section>
      </div>
    </template>
    <div v-if="loadingRun" class="loading-inline"><IconRefresh class="is-spinning" /> 读取保存的分析与图谱快照…</div>
    <RunResults v-if="run && !loadingRun" :run="run" @new-analysis="newAnalysis" />
    <section v-else-if="!setupOpen && !loadingRun" class="panel empty-state"><h3>选择输入，开始一次真实分析</h3><button class="button button--primary" @click="setupOpen = true">新建分析</button></section>
    <a-drawer v-model:visible="historyOpen" title="已保存分析" :width="550" :footer="false"><p class="muted">打开已有结果不会重新测量或推理。图谱与 Evidence 使用该次运行的快照。</p><div v-if="!workspace.analyses.length" class="empty-state"><IconHistory class="empty-state__icon" /><h3>还没有保存的分析</h3><p>完成第一次任务后，可在这里重新打开。</p></div><button v-for="saved in workspace.analyses" :key="saved.run_id" class="history-analysis" :data-run-id="saved.run_id" @click="loadRun(saved.run_id)"><span class="history-analysis__icon"><IconImage v-if="saved.dataset === 'mvtec'" /><IconBarChart v-else-if="saved.dataset === 'tep'" /><IconApps v-else /></span><span class="grow"><strong>{{ friendly(saved.title, '样本分析') }}</strong><small>{{ datasetShort[saved.dataset] }} · {{ saved.reasoner_id === 'tep_rootkgd' ? 'RootKGD' : '统一约束推理' }} · {{ saved.case_count }} 个样本范围</small><em>{{ dateTime(saved.created_at) }}</em></span><IconArrowRight /></button></a-drawer>
    <a-modal v-model:visible="demoOpen" :title="demoGroup?.title || '选择演示样本'" :footer="false" width="760px"><div v-if="demoGroup" class="demo-sample-picker"><p class="muted">{{ demoGroup.purpose }}</p><span class="section-kicker">推荐演示</span><button v-if="mainSample" class="demo-sample-option recommended" :class="{ active: (selectedSample?.sample_id ?? selectedSample?.id) === (mainSample.sample_id ?? mainSample.id) }" @click="selectedSampleId = text(mainSample.sample_id ?? mainSample.id)"><span class="demo-sample-radio" /><span class="grow"><strong>{{ mainSample.title }}</strong><small>{{ mainSample.expectation }}</small></span><span class="tag tag--blue">推荐</span></button><details v-if="otherSamples.length" class="sample-controls"><summary>正常、缺测与失败对照（{{ otherSamples.length }}）</summary><button v-for="sample in otherSamples" :key="text(sample.sample_id ?? sample.id)" class="demo-sample-option" :class="{ active: (selectedSample?.sample_id ?? selectedSample?.id) === (sample.sample_id ?? sample.id) }" @click="selectedSampleId = text(sample.sample_id ?? sample.id)"><span class="demo-sample-radio" /><span class="grow"><strong>{{ sample.title }}</strong><small>{{ sample.expectation }}</small></span></button></details><div v-if="selectedSample" class="demo-sample-actions"><div class="demo-sample-selected"><strong>已选：{{ selectedSample.title }}</strong><div class="tag-row"><a v-if="selectedSample.raw_input?.download_url" class="text-button" :href="apiUrl(workspace.baseUrl,selectedSample.raw_input.download_url)" target="_blank" rel="noreferrer"><IconDownload /> 原始样本</a><a v-if="selectedSample.evidence?.download_url" class="text-button" :href="apiUrl(workspace.baseUrl,selectedSample.evidence.download_url)" target="_blank" rel="noreferrer"><IconDownload /> 实际 Evidence</a></div></div><div class="sample-entry-buttons"><button class="sample-entry-button" :disabled="!selectedSample.raw_input?.available" @click="loadDemo('raw')"><IconFolder /><span><strong>从原始样本开始</strong><small>重新测量与推理{{ demoGroup.dataset === 'mvtec' ? '，包含视觉模型调用' : '' }}</small></span><IconArrowRight /></button><button class="sample-entry-button" :disabled="!selectedSample.evidence?.available" @click="loadDemo('evidence')"><IconFile /><span><strong>从 Evidence 开始</strong><small>不重跑测量，按当前知识复算</small></span><IconArrowRight /></button></div></div></div></a-modal>
  </div>
</template>
<style scoped>
.demo-graph-context{padding:12px 13px;border-radius:6px;background:#f3f7ff;border:1px solid #e2e9f6;margin:0 0 18px;font-size:12px;color:#6b83a7;}.demo-graph-context strong{font-size:12px;font-weight:550;}.demo-graph-context p{font-size:12px;line-height:1.8;margin:6px 0;}.demo-graph-context .text-button{font-size:12px;text-align:left;line-height:1.7;}.demo-graph-context--warning{background:#faf7ef;border-color:#ede4d2;color:#927b55;}.analysis-setup{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:24px;margin-bottom:30px;align-items:start;}.step-title{display:flex;align-items:center;gap:12px;}.step-number{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:var(--blue-soft);color:#6589d4;font-size:12px;font-weight:500;}.step-title h2{font-size:15px;}.step-title p{font-size:12px;color:#7f8ca1;margin-top:4px;}.input-panel .panel-body{padding:23px;}.input-kind-options{display:flex;gap:12px;margin-bottom:24px;}.input-kind-options>button{flex:1;display:flex;gap:11px;align-items:center;border:1px solid #e1e7f0;border-radius:7px;background:#fff;padding:16px 14px;text-align:left;color:#8d9cb2;}.input-kind-options>button>svg{font-size:22px;color:#7f8ca1;}.input-kind-options strong{display:block;font-size:12px;font-weight:500;color:#6d7d97;}.input-kind-options small{font-size:11px;color:#7f8ca1;display:block;margin-top:6px;}.input-kind-options i{margin-left:auto;width:11px;height:11px;border:1px solid #d3ddeb;border-radius:50%;flex-shrink:0;}.input-kind-options>button.active{background:#f6f9ff;border-color:#7f8ca1;box-shadow:0 0 0 1px #3166df05;}.input-kind-options>button.active>svg{color:#7196dd;}.input-kind-options>button.active strong{color:#567bb8;}.input-kind-options>button.active i{border:3px solid #7298dd;}.input-scene-label{font-size:13px;}.scene-options{display:flex;gap:9px;margin:10px 0 22px;}.scene-options button{display:flex;align-items:center;justify-content:center;gap:8px;flex:1;border:1px solid #e3e9f2;background:#fff;border-radius:5px;padding:10px 8px;color:#8c9bb2;font-size:13px;}.scene-options button svg{font-size:14px;}.scene-options button.active{border-color:#7f8ca1;background:#f4f8ff;color:#6389c7;}.inference-drop{min-height:204px;padding:31px 25px;background:#f9fbff;}.inference-drop>img{max-height:230px;max-width:100%;display:block;margin:0 auto 20px;border-radius:5px;}.inference-drop strong{font-size:13px;color:#758cab;}.inference-drop p{font-size:12px;color:#7f8ca1;max-width:400px;line-height:1.9;margin:auto;}.reference-upload{display:flex;align-items:center;gap:15px;justify-content:space-between;padding:16px 0;border-bottom:1px solid var(--border);}.reference-upload strong{display:block;font-size:13px;color:#7b8da9;font-weight:500;}.reference-upload small{font-size:11px;color:#7f8ca1;display:block;margin-top:4px;}.reference-upload>.button{max-width:55%;white-space:normal;font-size:12px;}.input-bottom-fields{display:flex;flex-direction:column;gap:20px;margin-top:22px;}.input-bottom-fields .field{font-size:13px;}.input-bottom-fields .field>input{font-size:12px;}.input-bottom-fields .checkbox-label{font-size:13px;color:#8c9ab0;}.input-advanced{font-size:12px;color:#7f8ca1;}.input-advanced>summary{cursor:pointer;}.input-advanced>.form-stack{padding-top:18px;}.input-contract-note{display:flex;gap:8px;border-top:1px solid #edf0f5;padding-top:18px;margin-top:23px;font-size:11px;line-height:1.9;color:#7f8ca1;}.input-contract-note>svg{font-size:12px;margin-top:2px;flex-shrink:0;}.inference-config .panel-header{padding:22px;}.inference-config .panel-body{display:flex;flex-direction:column;gap:20px;padding:22px;}.inference-config .field{font-size:13px;}.inference-config .field>select{font-size:13px;}.inference-config .field>small{font-size:11px;color:#7f8ca1;}.reasoner-selection>.field{margin-bottom:10px;}.reasoner-option{display:flex;align-items:flex-start;gap:10px;width:100%;background:#fff;border:1px solid #e1e8f1;border-radius:6px;padding:14px 12px;text-align:left;margin-bottom:9px;}.reasoner-radio{width:13px;height:13px;border:1px solid #cfd9e9;border-radius:50%;margin-top:2px;flex-shrink:0;}.reasoner-radio>svg{font-size:11px;color:white;vertical-align:0;display:block;margin:1px;}.reasoner-option.active{border-color:#7f8ca1;background:#f6f9ff;}.reasoner-option.active .reasoner-radio{border-color:#88a7dc;background:#88a7dc;}.reasoner-option strong{display:block;font-size:12px;font-weight:550;color:#7287a8;}.reasoner-option small{display:block;font-size:11px;color:#7f8ca1;line-height:1.8;margin-top:5px;}.reasoner-option em{display:block;font-size:10px;color:#7f8ca1;line-height:1.8;font-style:normal;margin-top:4px;}.reasoner-option.unavailable{background:#fafbfc;opacity:.55;}.run-config-summary{border-top:1px solid var(--border);padding-top:19px;}.run-config-summary>.section-kicker{font-size:11px;display:block;}.run-config-summary ol{list-style:none;margin:0;padding:0;}.run-config-summary li{display:flex;gap:16px;padding:8px 0;font-size:12px;color:#7e92b1;line-height:1.7;}.run-config-summary li>span{color:#7f8ca1;min-width:28px;}.inference-config .panel-footer{padding:17px 22px;}.inference-config .panel-footer>.button{min-height:41px;}.inference-config .panel-footer>p{font-size:10px;text-align:center;color:#7f8ca1;margin:10px 0 0;}.loaded-demo-input{display:flex;flex-wrap:wrap;gap:16px;padding:18px;border:1px solid #dce6f6;background:#f8faff;border-radius:7px;}.loaded-demo-heading{display:flex;gap:7px;align-items:center;width:100%;}.loaded-demo-heading>.text-button{margin-left:auto;color:#7f8ca1;}.loaded-demo-input>img{max-height:150px;width:150px;object-fit:contain;border-radius:4px;background:#f0f3fa;}.loaded-demo-input__body{flex:1;min-width:170px;padding:6px 0;}.loaded-demo-input__body strong{display:block;font-size:13px;line-height:1.7;color:#6684b4;}.loaded-demo-input__body p{font-size:12px;line-height:1.8;color:#7f8ca1;margin:8px 0 12px;}.loaded-demo-input__body .status-dot{font-size:11px;}.history-analysis{display:flex;align-items:center;gap:14px;padding:20px 0;width:100%;border:0;border-bottom:1px solid var(--border);background:none;text-align:left;}.history-analysis__icon{width:38px;height:38px;display:flex;align-items:center;justify-content:center;background:#f0f5ff;color:#7f8ca1;border-radius:7px;font-size:20px;}.history-analysis strong{display:block;font-size:13px;font-weight:500;color:#6d84a6;line-height:1.7;}.history-analysis small{display:block;font-size:12px;color:#7f8ca1;margin-top:6px;}.history-analysis em{display:block;font-size:11px;color:#7f8ca1;margin-top:6px;font-style:normal;}.history-analysis>svg{color:#7f8ca1;font-size:13px;}.demo-sample-picker>.muted{margin-bottom:22px;}.demo-sample-picker>.section-kicker{display:block;font-size:12px;}.demo-sample-option{display:flex;gap:12px;align-items:center;border:1px solid #e7ecf4;border-radius:7px;background:#fff;padding:15px;text-align:left;width:100%;margin:10px 0;color:#7c91b2;}.demo-sample-option.active{background:#f5f9ff;border-color:#7f8ca1;}.demo-sample-radio{display:block;width:12px;height:12px;border:1px solid #c4d1e5;border-radius:50%;flex-shrink:0;}.demo-sample-option.active .demo-sample-radio{border:3px solid #7fa2dc;}.demo-sample-option strong{display:block;font-size:12px;font-weight:550;color:#6d86ab;}.demo-sample-option small{display:block;font-size:12px;line-height:1.8;color:#7f8ca1;margin-top:6px;}.sample-controls{margin:20px 0;font-size:13px;color:#7f8ca1;}.sample-controls>summary{cursor:pointer;padding:0 0 7px;}.sample-controls .demo-sample-option{padding:13px;}.sample-controls .demo-sample-option strong{font-size:13px;}.sample-controls .demo-sample-option small{font-size:11px;}.demo-sample-actions{border-top:1px solid var(--border);padding-top:23px;margin-top:23px;}.demo-sample-selected{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:18px;}.demo-sample-selected>strong{font-size:12px;font-weight:500;color:#788ead;}.demo-sample-selected .text-button{font-size:12px;}.sample-entry-buttons{display:grid;grid-template-columns:1fr 1fr;gap:12px;}.sample-entry-button{display:flex;gap:10px;align-items:center;background:#f7faff;border:1px solid #dce7f7;border-radius:7px;padding:15px 13px;text-align:left;}.sample-entry-button>svg{font-size:21px;color:#8da9d7;}.sample-entry-button strong{display:block;font-size:12px;font-weight:550;color:#6b88b4;}.sample-entry-button small{display:block;font-size:11px;line-height:1.8;color:#7f8ca1;margin-top:5px;}.sample-entry-button>svg:last-child{font-size:12px;margin-left:auto;color:#7f8ca1;}
@media(max-width:1200px){.analysis-setup{grid-template-columns:minmax(0,1fr) 300px;gap:17px;}.input-kind-options{gap:8px;}.input-kind-options>button{padding:14px 10px;gap:7px;}.input-kind-options small{font-size:10px;}.input-kind-options i{display:none;}.inference-config .panel-header,.inference-config .panel-body,.input-panel .panel-body{padding:20px;}}@media(max-width:1000px){.analysis-setup{grid-template-columns:1fr;}.inference-config .panel-body{display:grid;grid-template-columns:1fr 1fr;}.reasoner-selection{grid-column:2;grid-row:1/4;}.run-config-summary{grid-column:1;}.inference-config .panel-footer>.button{max-width:360px;display:flex;margin-left:auto;}.inference-config .panel-footer>p{text-align:right;}.input-kind-options small{font-size:12px;}}@media(max-width:650px){.input-kind-options{flex-direction:column;}.input-kind-options>button{padding:15px;}.scene-options button{font-size:12px;gap:5px;}.inference-config .panel-body{display:flex;}.inference-config .panel-footer>.button{max-width:none;}.inference-config .panel-footer>p{text-align:center;}.sample-entry-buttons{grid-template-columns:1fr;}.demo-sample-selected{display:block;}.demo-sample-selected .tag-row{margin-top:13px;}.loaded-demo-input>img{max-width:110px;}.loaded-demo-input__body{min-width:130px;}}
</style>
