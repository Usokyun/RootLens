<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { IconPlus, IconSearch, IconFile, IconBook, IconArrowRight, IconUpload, IconLink, IconRefresh, IconCheck, IconRelation, IconImage, IconBarChart, IconApps, IconDownload } from '@arco-design/web-vue/es/icon'
import type { KGMaterialRecord, KGMaterialChunkRecord } from '@/api/contracts'
import type { Dataset, DemoGroup, WorkTask } from '@/api/workbench'
import { apiUrl } from '@/api/workbench'
import { api, workspace, refreshGraphs, refreshTasks, selectGraph } from '@/services/workspace'
import { capabilityIds, datasetNames, datasetShort, dateTime, fileSize, text, materialLocator } from '@/services/presentation'
import { useTaskObserver } from '@/services/task-observer'
import { revealTask } from '@/services/reveal-task'
import TaskProgress from '@/components/ui/TaskProgress.vue'

const router = useRouter()
const materials = ref<KGMaterialRecord[]>([])
const selectedIds = ref<string[]>([])
const inspectedId = ref('')
const chunks = ref<KGMaterialChunkRecord[]>([])
const chunkIndex = ref(0)
const loading = ref(false)
const chunksLoading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const search = ref('')
const scenarioFilter = ref('all')
const addOpen = ref(false)
const addTab = ref<'file' | 'url'>('file')
const addFiles = ref<File[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const addForm = reactive({ title: '', scenario: 'shared', url: '', notes: '' })
const buildOpen = ref(false)
const buildForm = reactive({ title: '', dataset: 'mvtec' as Dataset, maxRepairs: 1 })
const demoOpen = ref(false)
const selectedDemo = ref<DemoGroup | null>(null)

const filtered = computed(() => materials.value.filter((m) =>
  (scenarioFilter.value === 'all' || m.scenario === scenarioFilter.value) &&
  [m.title, m.filename, m.original_filename, m.notes].join(' ').toLowerCase().includes(search.value.toLowerCase()),
))
const inspected = computed(() => materials.value.find((m) => m.material_id === inspectedId.value) ?? null)
const selected = computed(() => materials.value.filter((m) => selectedIds.value.includes(m.material_id)))
const currentChunk = computed(() => chunks.value[chunkIndex.value])
const buildResultId = computed(() => text(observer.task.value?.result?.graph_id))
const taskHistory = computed(() => workspace.tasks.filter((t) => /material|build|parse/.test(t.kind)).slice(0, 4))
const observer = useTaskObserver(async (task) => {
  await loadMaterials()
  await Promise.all([refreshGraphs(), refreshTasks()])
  if (inspectedId.value) await inspect(inspectedId.value)
  if (task.result?.graph_id) notice.value = '知识图谱已制作完成。查看语义内容后，可修改并投入使用。'
  else notice.value = '资料解析完成，可以检查正文片段或开始制作图谱。'
})
const { task, connectionError, retrying } = observer
function trackTask(next: WorkTask) { observer.observe(next); void revealTask(next.task_id) }
async function retryCurrentTask() { await observer.retry(); if (task.value) void revealTask(task.value.task_id) }

async function loadMaterials() {
  loading.value = true; error.value = ''
  try {
    materials.value = (await api().materials()).materials
    if (!inspectedId.value || !materials.value.some((m) => m.material_id === inspectedId.value)) inspectedId.value = materials.value[0]?.material_id ?? ''
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { loading.value = false }
}
async function inspect(id: string) {
  inspectedId.value = id; chunkIndex.value = 0; chunks.value = []; chunksLoading.value = true
  try { const result = await api().chunks(id); if (inspectedId.value === id) chunks.value = result.chunks }
  catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { chunksLoading.value = false }
}
function toggle(id: string) {
  selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter((x) => x !== id) : [...selectedIds.value, id]
}
function status(m: KGMaterialRecord) {
  if (m.extraction_status === 'extracted' || (m.chunk_count ?? 0) > 0) return '已解析'
  if (m.extraction_status === 'failed' || m.processing_status === 'failed') return '解析失败'
  return '待解析'
}
async function parse(ids = selectedIds.value, force = false) {
  if (!ids.length) return
  error.value = ''; notice.value = ''; busy.value = true
  try { trackTask(await api().parseMaterials(ids, force)) }
  catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { busy.value = false }
}
function chooseFiles(files: File[]) { addFiles.value = files; if (files.length === 1 && !addForm.title) addForm.title = files[0]!.name.replace(/\.[^.]+$/, '') }
function dropFiles(event: DragEvent) { event.preventDefault(); dragging.value = false; chooseFiles(Array.from(event.dataTransfer?.files ?? [])) }
async function addMaterials() {
  error.value = ''; busy.value = true
  try {
    const added: KGMaterialRecord[] = []
    if (addTab.value === 'url') {
      added.push((await api().registerUrl({ url: addForm.url, title: addForm.title || undefined, scenario: addForm.scenario, notes: addForm.notes, source_type: 'webpage' })).material)
    } else {
      if (!addFiles.value.length) throw new Error('请选择需要导入的知识资料。')
      for (const file of addFiles.value) added.push((await api().uploadMaterial(file, { title: addFiles.value.length === 1 ? addForm.title || file.name : file.name, scenario: addForm.scenario, notes: addForm.notes })).material)
    }
    selectedIds.value = added.map((m) => m.material_id); inspectedId.value = added[0]!.material_id
    addOpen.value = false; addFiles.value = []; addForm.title = ''; addForm.url = ''; addForm.notes = ''
    await loadMaterials(); await inspect(inspectedId.value)
    trackTask(await api().parseMaterials(selectedIds.value))
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { busy.value = false }
}
function prepareBuild() {
  const inferred = selected.value.find((m) => ['mvtec', 'tep', 'wafer'].includes(m.scenario))?.scenario as Dataset | undefined
  buildForm.dataset = inferred ?? 'mvtec'; buildForm.title = `${datasetShort[buildForm.dataset]}知识图谱`; buildOpen.value = true
}
async function build() {
  error.value = ''; notice.value = ''; busy.value = true
  try {
    trackTask(await api().buildGraph({ material_ids: selectedIds.value, dataset: buildForm.dataset, title: buildForm.title, capability_id: capabilityIds[buildForm.dataset], enable_when_ready: false, max_repairs: buildForm.maxRepairs }))
    buildOpen.value = false
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { busy.value = false }
}
function openGraph(id: string) { selectGraph(id); void router.push({ name: 'graphs', query: { graph: id } }) }
function openDemo(demo: DemoGroup) { selectedDemo.value = demo; demoOpen.value = true }
async function importDemo() {
  if (!selectedDemo.value) return
  error.value = ''; busy.value = true
  try {
    const response = await api().importDemoMaterials(selectedDemo.value.id)
    selectedIds.value = response.materials.map((m) => m.material_id); inspectedId.value = selectedIds.value[0] ?? ''
    buildForm.dataset = selectedDemo.value.dataset; demoOpen.value = false
    await loadMaterials(); if (inspectedId.value) await inspect(inspectedId.value)
    trackTask(await api().parseMaterials(selectedIds.value))
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { busy.value = false }
}
function taskLabel(item: WorkTask) { return ({ queued: '排队中', running: '处理中', completed: '完成', failed: '失败', interrupted: '中断' })[item.status] }
watch(() => workspace.connected, async (connected, previous) => {
  if (connected && !previous && !materials.value.length && !loading.value) { await loadMaterials(); if (inspectedId.value) await inspect(inspectedId.value) }
})
onMounted(async () => {
  await loadMaterials(); if (inspectedId.value) await inspect(inspectedId.value)
  const running = workspace.tasks.find((t) => /material|build|parse/.test(t.kind) && ['running', 'queued'].includes(t.status))
  if (running) observer.observe(running)
})
</script>

<template>
  <div class="materials-page">
    <div class="page-heading"><div><span class="eyebrow">01 / KNOWLEDGE SOURCES</span><h1>让资料成为可用的知识</h1><p>导入手册、论文或过程说明。后端解析原文、制作图谱，再由你检查并投入分析。</p></div><div class="page-heading__actions"><button class="button button--primary" @click="addOpen = true"><IconPlus /> 导入知识资料</button></div></div>
    <div v-if="error" class="alert alert--error" role="alert"><span class="grow">{{ error }}</span><button class="text-button" @click="error = ''">关闭</button></div>
    <div v-if="notice" class="alert alert--success"><IconCheck /><span class="grow">{{ notice }}</span><button v-if="buildResultId" class="text-button" @click="openGraph(buildResultId)">查看并修改图谱 <IconArrowRight /></button></div>
    <TaskProgress v-if="task" :task="task" :connection-error="connectionError" :retrying="retrying" @retry="retryCurrentTask" @refresh="observer.refresh" />
    <section v-if="workspace.demos.demos.length" class="demo-starter"><div class="demo-starter__intro"><strong>先用公开资料试一遍</strong><small>导入的是资料，不是预制答案</small></div><div class="demo-starter__options"><button v-for="demo in workspace.demos.demos" :key="demo.id" class="demo-choice" @click="openDemo(demo)"><IconImage v-if="demo.dataset === 'mvtec'" /><IconBarChart v-else-if="demo.dataset === 'tep'" /><IconApps v-else /><span><strong>{{ datasetShort[demo.dataset] }}</strong><small>{{ demo.materials.length }} 份知识资料</small></span><IconArrowRight /></button></div></section>
    <div class="materials-workspace">
      <section class="panel material-library"><header class="panel-header"><div><h2>知识资料库 <span class="count-label">{{ materials.length }}</span></h2><p>选择用于制作同一图谱的资料</p></div><button class="text-button" :disabled="loading" aria-label="刷新资料库" @click="loadMaterials"><IconRefresh /></button></header>
        <div class="library-tools"><div class="search-wrap"><IconSearch /><input v-model="search" class="search-input" placeholder="搜索标题或文件名" aria-label="搜索知识资料" /></div><select v-model="scenarioFilter" aria-label="资料场景"><option value="all">全部场景</option><option value="mvtec">视觉缺陷</option><option value="tep">过程监测</option><option value="wafer">晶圆图案</option><option value="shared">通用资料</option></select></div>
        <div v-if="loading && !materials.length" class="loading-inline"><IconRefresh class="is-spinning" /> 读取资料库…</div>
        <div v-else-if="!filtered.length" class="empty-state empty-state--compact"><div class="empty-state__icon"><IconBook /></div><h3>{{ materials.length ? '没有找到匹配资料' : '从第一份知识资料开始' }}</h3><p>知识资料用于制作图谱。待分析的图片、时序或网格请到“推理分析”上传。</p><button class="button button--secondary" @click="addOpen = true">导入知识资料</button></div>
        <div v-else class="material-list"><article v-for="material in filtered" :key="material.material_id" class="material-row" :class="{ active: inspectedId === material.material_id }"><label class="material-check" :aria-label="`选择${material.title}`"><input type="checkbox" :checked="selectedIds.includes(material.material_id)" @change="toggle(material.material_id)" /></label><button class="material-row__open" @click="inspect(material.material_id)"><span class="material-file-icon"><IconFile /></span><span class="grow"><strong>{{ material.title }}</strong><span class="material-row__meta">{{ datasetShort[material.scenario] || material.scenario }} <span>·</span> {{ (material.original_filename?.split('.').at(-1) || material.filename?.split('.').at(-1) || material.content_type?.split('/').at(-1) || material.source_format || '资料').toUpperCase() }}</span><span class="status-dot" :class="status(material) === '已解析' ? 'status-dot--green' : 'status-dot--amber'">{{ status(material) }}<span v-if="material.chunk_count"> · {{ material.chunk_count }} 个片段</span></span></span></button></article></div>
        <footer class="library-selection"><span>已选 <strong>{{ selectedIds.length }}</strong> 份资料</span><button v-if="selectedIds.length" class="text-button" @click="selectedIds = []">清空选择</button></footer>
      </section>
      <div class="material-main">
        <section class="panel material-preview"><header class="panel-header"><div><span class="eyebrow">SOURCE PREVIEW</span><h2>{{ inspected?.title || '资料正文预览' }}</h2><p v-if="inspected">{{ inspected.notes || '检查解析后的正文与定位，图谱来源将引用这些片段。' }}</p></div><button v-if="inspected" class="button button--secondary button--small" :disabled="busy" @click="parse([inspected.material_id], true)"><IconRefresh /> {{ chunks.length ? '重新解析' : '解析此资料' }}</button></header>
          <div v-if="chunksLoading" class="loading-inline"><IconRefresh class="is-spinning" /> 读取正文片段…</div>
          <template v-else-if="currentChunk"><div class="chunk-strip"><span>正文片段</span><button v-for="(chunk, index) in chunks" :key="chunk.chunk_id" :class="{ active: chunkIndex === index }" @click="chunkIndex = index">{{ index + 1 }}</button></div><article class="source-document"><div class="source-locator"><IconBook /> {{ materialLocator(currentChunk.source_locator) }} <span>{{ currentChunk.text_content.length.toLocaleString() }} 字符</span></div><div class="source-document__text">{{ currentChunk.text_content }}</div></article></template>
          <div v-else class="empty-state"><div class="empty-state__icon"><IconFile /></div><h3>{{ inspected ? '正文尚未解析' : '选择一份资料查看原文' }}</h3><p>{{ inspected ? '解析后可按片段检查原文与来源位置。制作图谱时也会自动解析尚未处理的资料。' : '左侧资料库保留原文件与解析结果。' }}</p><button v-if="inspected" class="button button--secondary" :disabled="busy" @click="parse([inspected.material_id])">开始解析</button></div>
          <details v-if="inspected" class="technical material-technical"><summary>文件与来源信息</summary><dl><dt>原始文件</dt><dd>{{ inspected.original_filename || inspected.filename || 'URL 资料' }}</dd><dt>来源地址</dt><dd>{{ inspected.url || inspected.path || inspected.uri || '本地上传' }}</dd><dt>导入时间</dt><dd>{{ dateTime(inspected.created_at || inspected.registered_at) }}</dd><dt>稳定 ID</dt><dd><code>{{ inspected.material_id }}</code></dd></dl></details>
        </section>
        <section class="make-graph"><div class="make-graph__icon"><IconRelation /></div><div class="grow"><h3>把选中的资料制作成图谱</h3><p>{{ selectedIds.length ? `已选择 ${selectedIds.length} 份资料。选择场景后，由 LLM 提取知识并编译为可执行图谱。` : '先勾选左侧资料。图谱制作完成后，前往知识图谱检查、修改并投入使用。' }}</p></div><button class="button button--primary" :disabled="!selectedIds.length || busy" @click="prepareBuild">制作知识图谱 <IconArrowRight /></button></section>
        <section v-if="taskHistory.length" class="recent-tasks"><h3>最近制作记录</h3><button v-for="item in taskHistory" :key="item.task_id" class="recent-task-row" @click="trackTask(item)"><span class="status-dot" :class="item.status === 'completed' ? 'status-dot--green' : 'status-dot--amber'">{{ taskLabel(item) }}</span><strong>{{ item.title }}</strong><time>{{ dateTime(item.created_at) }}</time><IconArrowRight /></button></section>
      </div>
    </div>

    <a-modal v-model:visible="addOpen" title="导入知识资料" :footer="false" width="640px">
      <form class="form-stack" @submit.prevent="addMaterials"><div class="segmented"><button type="button" :class="{ active: addTab === 'file' }" @click="addTab = 'file'"><IconUpload /> 上传文件</button><button type="button" :class="{ active: addTab === 'url' }" @click="addTab = 'url'"><IconLink /> 来源网址</button></div><div v-if="addTab === 'file'" class="file-drop" :class="{ 'is-dragging': dragging }" tabindex="0" role="button" @click="fileInput?.click()" @keydown.enter.prevent="fileInput?.click()" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop="dropFiles"><IconUpload /><strong>{{ addFiles.length ? `已选择 ${addFiles.length} 个文件` : '选择文件，或拖放到这里' }}</strong><p>{{ addFiles.length ? addFiles.map((f) => f.name).join('、') : 'PDF（文本层）、TXT、Markdown、HTML、CSV、JSON / JSONL' }}</p><input ref="fileInput" class="native-file" type="file" multiple accept=".pdf,.txt,.md,.markdown,.html,.htm,.csv,.json,.jsonl" @change="chooseFiles(Array.from(($event.target as HTMLInputElement).files ?? []))" /></div><label v-else class="field">来源网址<input v-model="addForm.url" required type="url" placeholder="https://…" /><small>后端会获取并解析网页正文；失败会保留原因，可重新尝试。</small></label><div class="form-grid"><label class="field">资料标题<input v-model="addForm.title" placeholder="例如：玻璃瓶缺陷手册" /></label><label class="field">所属场景<select v-model="addForm.scenario"><option value="shared">通用资料</option><option v-for="(name, key) in datasetNames" :key="key" :value="key">{{ name }}</option></select></label></div><label class="field">资料说明（可选）<textarea v-model="addForm.notes" rows="2" placeholder="说明资料的主题和用途，方便后续识别" /></label><div v-if="error" class="error-text">{{ error }}</div><div class="button-row justify-end"><button type="button" class="button button--ghost" @click="addOpen = false">取消</button><button class="button button--primary" :disabled="busy || (addTab === 'file' && !addFiles.length)">{{ busy ? '正在导入…' : '导入并解析' }} <IconArrowRight /></button></div></form>
    </a-modal>
    <a-modal v-model:visible="buildOpen" title="制作知识图谱" :footer="false" width="600px"><form class="form-stack" @submit.prevent="build"><p class="muted">使用选中的 {{ selectedIds.length }} 份资料。后端会执行解析、LLM 知识提取、自动校验与编译。</p><label class="field">图谱名称<input v-model="buildForm.title" required placeholder="给图谱起一个容易辨认的名字" /></label><label class="field">测量场景<select v-model="buildForm.dataset"><option v-for="(name, key) in datasetNames" :key="key" :value="key">{{ name }}</option></select><small>{{ buildForm.dataset === 'mvtec' ? '图像异常区域、几何与外观语义' : buildForm.dataset === 'tep' ? '完整过程窗口、正常参考与 52 通道统计' : '0/1/2 原生网格、区域统计与独立图案分类' }}</small></label><div class="selected-source-summary"><span class="section-kicker">本次来源</span><p v-for="material in selected" :key="material.material_id"><IconFile /> {{ material.title }}</p></div><p class="muted">自动校验并修复一次，最多 2 次模型调用。制作完成后先检查，再投入使用。</p><details class="technical"><summary>高级制作设置</summary><label class="checkbox-label" style="margin-top:12px"><input type="checkbox" :checked="buildForm.maxRepairs === 1" @change="buildForm.maxRepairs = ($event.target as HTMLInputElement).checked ? 1 : 0" />允许一次自动修复（关闭后只调用一次模型）</label></details><p v-if="error" class="error-text">{{ error }}</p><div class="button-row justify-end"><button type="button" class="button button--ghost" @click="buildOpen = false">取消</button><button class="button button--primary" :disabled="busy">{{ busy ? '正在提交…' : '开始制作' }} <IconArrowRight /></button></div></form></a-modal>
    <a-modal v-model:visible="demoOpen" :title="selectedDemo?.title || '公开演示资料'" :footer="false" width="650px"><div v-if="selectedDemo" class="form-stack"><p>{{ selectedDemo.purpose }}</p><div class="selected-source-summary"><span class="section-kicker">将导入以下知识资料</span><div v-for="(asset, index) in selectedDemo.materials" :key="text(asset.asset_id, String(index))" class="demo-material-asset"><IconFile /><div class="grow"><strong>{{ asset.title || asset.path?.split('/').at(-1) || `来源资料 ${index + 1}` }}</strong><small>{{ fileSize(asset.size_bytes) }} {{ asset.media_type }}</small></div><a v-if="asset.download_url" :href="apiUrl(workspace.baseUrl, asset.download_url)" target="_blank" rel="noreferrer" class="text-button"><IconDownload /> 原文件</a></div></div><p class="muted">这一步只登记并解析公开知识资料。后续仍会真实调用制作任务，不会用已有结果冒充现场制作。</p><p v-if="error" class="error-text">{{ error }}</p><div class="button-row justify-end"><button class="button button--ghost" @click="demoOpen = false">取消</button><button class="button button--primary" :disabled="busy" @click="importDemo">{{ busy ? '正在导入…' : '导入这些知识资料' }} <IconArrowRight /></button></div></div></a-modal>
  </div>
</template>
<style scoped>
.materials-workspace{display:grid;grid-template-columns:340px minmax(0,1fr);gap:24px;align-items:start;}.material-library{overflow:hidden;}.material-library .panel-header{padding:20px;}.library-tools{padding:16px 18px;display:flex;gap:9px;flex-wrap:wrap;border-bottom:1px solid var(--border);}.library-tools .search-wrap{flex:1;min-width:160px;}.library-tools>select{border:0;background:#f5f7fb;color:#778398;font-size:13px;padding:8px;border-radius:5px;width:100%;}.material-list{max-height:600px;overflow:auto;}.material-row{display:flex;border-bottom:1px solid #edf0f5;padding:15px 16px;gap:10px;transition:background .15s;}.material-row.active{background:#f3f6ff;box-shadow:inset 3px 0 var(--blue);}.material-row:hover{background:#f7f9fd;}.material-check{padding-top:4px;}.material-check input{accent-color:var(--blue);width:14px;height:14px;cursor:pointer;}.material-row__open{border:0;background:none;padding:0;display:flex;align-items:flex-start;gap:10px;flex:1;min-width:0;text-align:left;color:var(--ink);}.material-file-icon{font-size:22px;color:#8a9ab7;}.material-row.active .material-file-icon{color:var(--blue);}.material-row__open strong{display:block;font-size:12px;line-height:1.7;word-break:break-word;font-weight:550;}.material-row__meta{display:flex;align-items:center;gap:7px;margin:6px 0;font-size:12px;color:#8d98a9;}.material-row__meta>span{color:#d3d9e3;}.material-row .status-dot{font-size:12px;}.library-selection{padding:15px 20px;background:#fbfcff;display:flex;justify-content:space-between;font-size:12px;color:var(--muted);}.library-selection strong{color:var(--blue);}.library-selection .text-button{font-size:13px;}.material-main{min-width:0;}.material-preview .eyebrow{font-size:11px;margin-bottom:7px;}.material-preview h2{font-size:17px;}.material-preview .panel-header{align-items:flex-start;}.material-preview .panel-header>div{min-width:0;}.material-preview .panel-header .button{flex-shrink:0;}.chunk-strip{display:flex;gap:7px;align-items:center;padding:13px 24px;border-bottom:1px solid #edf0f5;overflow-x:auto;}.chunk-strip>span{font-size:12px;color:var(--muted);white-space:nowrap;margin-right:8px;}.chunk-strip>button{border:0;background:#f1f3f7;color:#8491a5;font-size:12px;border-radius:4px;width:24px;min-width:24px;height:24px;}.chunk-strip>button.active{color:var(--blue);background:var(--blue-soft);font-weight:600;}.source-document{padding:24px 28px 28px;}.source-locator{display:flex;align-items:center;gap:8px;color:#8793a6;font-size:12px;margin-bottom:18px;}.source-locator>span{margin-left:auto;color:#7f8ca1;}.source-document__text{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.95;color:#4c5970;max-height:470px;overflow:auto;padding-right:12px;}.material-technical{margin:0 24px 19px;}.make-graph{display:flex;align-items:center;gap:16px;padding:23px 0;}.make-graph__icon{display:flex;align-items:center;justify-content:center;width:44px;height:44px;flex-shrink:0;border-radius:10px;background:#eaf0ff;color:var(--blue);font-size:23px;}.make-graph h3{font-size:14px;margin-bottom:5px;}.make-graph p{font-size:13px;line-height:1.7;color:var(--muted);margin:0;}.make-graph>.button{flex-shrink:0;}.recent-tasks{margin-top:10px;border-top:1px solid var(--border);padding-top:22px;}.recent-tasks h3{font-size:12px;color:#68758b;margin-bottom:13px;}.recent-task-row{display:flex;align-items:center;gap:12px;width:100%;padding:11px 0;border:0;border-bottom:1px solid #e9edf4;background:transparent;text-align:left;}.recent-task-row strong{font-size:13px;flex:1;font-weight:500;}.recent-task-row time{font-size:12px;color:var(--muted);}.recent-task-row>svg{color:#8a9ab5;}.selected-source-summary{background:#f7f9fd;border:1px solid var(--border);border-radius:7px;padding:16px;}.selected-source-summary p{font-size:12px;color:#5f6c82;margin:7px 0;}.selected-source-summary p svg{color:#7f8ca1;margin-right:7px;}.demo-material-asset{display:flex;align-items:center;gap:10px;padding:12px 0;border-bottom:1px solid var(--border);}.demo-material-asset:last-child{border:0;}.demo-material-asset>svg{font-size:24px;color:var(--blue);}.demo-material-asset strong{display:block;font-size:12px;line-height:1.6;}.demo-material-asset small{display:block;color:var(--muted);font-size:12px;margin-top:3px;}
@media(max-width:1250px){.materials-workspace{grid-template-columns:300px minmax(0,1fr);gap:18px;}.make-graph{flex-wrap:wrap;}.make-graph>.button{margin-left:60px;}}@media(max-width:1000px){.materials-workspace{grid-template-columns:270px minmax(0,1fr);gap:16px;}.material-preview .panel-header{flex-wrap:wrap;}.source-document{padding:20px;}}@media(max-width:760px){.materials-workspace{grid-template-columns:1fr;}.material-list{max-height:330px;}.material-preview{min-height:300px;}.make-graph>.button{margin-left:0;}.make-graph .grow{min-width:180px;}.recent-task-row time{display:none;}}
</style>
