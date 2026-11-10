<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IconArrowRight, IconCheck, IconDownload, IconUpload, IconRelation, IconEdit, IconSave, IconSearch, IconInfoCircle, IconFile, IconRefresh, IconPlus } from '@arco-design/web-vue/es/icon'
import type { WorkingGraphPackage } from '@/api/contracts'
import { apiUrl, type AuthoringCapability, type Dataset, type RecordValue } from '@/api/workbench'
import { api, workspace, currentGraph, refreshGraphs, selectGraph } from '@/services/workspace'
import { record, rows, text, texts, clone, friendly, datasetShort, downloadJson } from '@/services/presentation'
import { knowledgeOf, catalog, nameOf, knowledgeSections, sourcesFor, rowId, type KnowledgeSection, type KnowledgeItem } from '@/services/knowledge'
import { newAnalysisRoute } from '@/services/analysis-entry'
import { categoricalFeatures, conditionIssues, featureChoices, newValueBinding, registerFeature, valueBindingIssues } from '@/services/feature-authoring'
import CandidateConditions from '@/components/graphs/CandidateConditions.vue'
import ConditionPredicateEditor from '@/components/graphs/ConditionPredicateEditor.vue'
import ValueBindingEditor from '@/components/graphs/ValueBindingEditor.vue'
import SemanticGraph from '@/components/graphs/SemanticGraph.vue'
import ExpressionEditor from '@/components/graphs/ExpressionEditor.vue'

const route = useRoute(), router = useRouter()
const pkg = ref<WorkingGraphPackage | null>(null)
const loading = ref(false), saving = ref(false), enabling = ref(false), dirty = ref(false)
const error = ref(''), notice = ref('')
const section = ref<KnowledgeSection>('hypotheses'), selectedId = ref(''), search = ref('')
const importOpen = ref(false), importFile = ref<File | null>(null), importing = ref(false)
const importInput = ref<HTMLInputElement | null>(null)
const capabilities = ref<Partial<Record<Dataset,AuthoringCapability>>>({})
const capabilitiesLoading = ref(false), capabilitiesError = ref('')
const editedConditions = new Set<string>(), editedBindings = new Set<string>()
const executableGraphs = computed(() => workspace.graphs.filter((g) => record(g.knowledge).schema_version === 'rootlens-knowledge-package.v2'))
const knowledge = computed(() => knowledgeOf(pkg.value))
const capability = computed(() => capabilities.value[pkg.value?.dataset as Dataset] ?? null)
const features = computed(() => featureChoices(knowledge.value,capability.value))
const mappingFeatures = computed(() => categoricalFeatures(features.value))
const items = computed(() => catalog(knowledge.value, section.value))
const filteredItems = computed(() => items.value.filter((item) => [item.label, item.subtitle].join(' ').toLowerCase().includes(search.value.toLowerCase())))
const selectedItem = computed(() => items.value.find((item) => item.id === selectedId.value) ?? items.value[0] ?? null)
const selectedRow = computed(() => selectedItem.value?.raw ?? {})
const selectedSources = computed(() => sourcesFor(knowledge.value, selectedRow.value))
const activeOptions = computed(() => [...rows(knowledge.value.hypotheses), ...rows(knowledge.value.mechanisms)])
const expressionOptions = computed(() => [...rows(knowledge.value.observable_definitions), ...rows(knowledge.value.pattern_definitions)].filter((r) => rowId(r) !== selectedItem.value?.id).map((r) => ({ id: rowId(r), label: friendly(r.label) })))
const summaryCounts = computed(() => [
  { label: '对象与变量', count: rows(knowledge.value.entities).length },
  { label: '候选解释', count: rows(knowledge.value.hypotheses).length },
  { label: '联合现象', count: rows(knowledge.value.pattern_definitions).length },
  { label: '观测条件', count: rows(knowledge.value.observable_definitions).length },
])
const canEnable = computed(() => currentGraph.value?.status === 'ready' && !dirty.value && !saving.value)

async function loadGraph(id: string) {
  if (!id) { pkg.value = null; return }
  loading.value = true; error.value = ''; notice.value = ''; dirty.value = false
  try {
    const next = await api().graph(id)
    if (workspace.graphId !== id) return
    pkg.value = clone(next); selectedId.value = ''; search.value = ''; editedConditions.clear(); editedBindings.clear()
    const candidate = typeof route.query.candidate === 'string' ? route.query.candidate : ''
    if (rows(knowledge.value.hypotheses).some(row => row.hypothesis_id === candidate)) { section.value = 'hypotheses'; selectedId.value = candidate }
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { loading.value = false }
}
function chooseGraph(id: string) {
  if (dirty.value && !window.confirm('还有未保存的修改。切换图谱会放弃这些修改，是否继续？')) return
  selectGraph(id); void loadGraph(id)
}
function chooseItem(item: KnowledgeItem) { selectedId.value = item.id }
function selectSemantic(id: string) {
  for (const option of knowledgeSections) {
    if (catalog(knowledge.value, option.key).some((item) => item.id === id)) { section.value = option.key; selectedId.value = id; search.value = ''; return }
  }
}
function changed() { dirty.value = true; notice.value = '' }
function setAliases(value: string) { selectedRow.value.aliases = value.split(/[,，;；\n]+/).map((v) => v.trim()).filter(Boolean); changed() }
async function loadCapabilities() {
  capabilitiesLoading.value = true; capabilitiesError.value = ''
  try { capabilities.value = (await api().authoringCapabilities()).capabilities }
  catch (e) { capabilitiesError.value = e instanceof Error ? e.message : String(e) }
  finally { capabilitiesLoading.value = false }
}
function updatePredicate(next: RecordValue) {
  Object.assign(selectedRow.value,next)
  const feature = features.value.find((row) => row.feature_id === next.feature_id)
  if (feature) registerFeature(knowledge.value,feature)
  editedConditions.add(text(next.predicate_id)); changed()
}
function updateBinding(next: RecordValue) {
  Object.assign(selectedRow.value,next)
  const feature = features.value.find((row) => row.feature_id === next.feature_id)
  if (feature) registerFeature(knowledge.value,feature)
  editedBindings.add(text(next.binding_id)); changed()
}
function addBinding() {
  const feature = mappingFeatures.value.find((row) => row.feature_id === 'appearance.semantic_candidates') ?? mappingFeatures.value[0]
  if (!feature) return
  const binding = newValueBinding(feature.feature_id)
  knowledge.value.value_bindings = [...rows(knowledge.value.value_bindings),binding]
  selectedId.value = text(binding.binding_id); editedBindings.add(text(binding.binding_id)); changed()
}
function removeBinding() {
  const id = text(selectedRow.value.binding_id)
  knowledge.value.value_bindings = rows(knowledge.value.value_bindings).filter((row) => row.binding_id !== id)
  editedBindings.delete(id); selectedId.value = ''; changed()
}
function setSubject(kind: string) {
  selectedRow.value.subject_selector = kind === 'bound_entity' ? { kind, entity_id: rows(knowledge.value.entities)[0]?.entity_id } : { kind: 'focus' }; changed()
}
function setScope(kind: string) { selectedRow.value.scope_selector = kind === 'task_scope' ? { kind } : { kind: 'spatial_zone', zone: 'all_valid', parent: 'task_scope' }; changed() }
async function save() {
  if (!pkg.value || !workspace.graphId) return
  const issues = [
    ...rows(knowledge.value.observable_definitions).filter((row) => editedConditions.has(text(row.predicate_id))).flatMap((row) => conditionIssues(row,features.value.find((feature) => feature.feature_id === row.feature_id))),
    ...rows(knowledge.value.value_bindings).filter((row) => editedBindings.has(text(row.binding_id))).flatMap((row) => valueBindingIssues(row,features.value,knowledge.value)),
  ]
  if (issues.length) { error.value = `请先完成条件或等价词汇：${[...new Set(issues)].join(' ')}`; return }
  saving.value = true; error.value = ''
  try {
    await api().saveGraph(workspace.graphId, clone(pkg.value)); dirty.value = false; editedConditions.clear(); editedBindings.clear()
    await refreshGraphs(); notice.value = '修改已保存并生效。后续新分析使用这一版；已有分析保留原图快照。'
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { saving.value = false }
}
async function enable(enabled: boolean) {
  if (!workspace.graphId) return
  enabling.value = true; error.value = ''
  try {
    await api().enableGraph(workspace.graphId, enabled); await refreshGraphs()
    notice.value = enabled ? '图谱已投入使用。可携带当前图谱前往分析。' : '图谱已停用，后续分析不能选择它。'
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { enabling.value = false }
}
async function importPackage(value?: WorkingGraphPackage) {
  importing.value = true; error.value = ''
  try {
    const body = value ?? (importFile.value ? JSON.parse(await importFile.value.text()) as WorkingGraphPackage : null)
    if (!body) throw new Error('请选择完整图谱包。')
    if (body.schema_version !== 'rootlens-working-graph.v2') throw new Error('请选择 rootlens-working-graph.v2 格式的可执行图谱。')
    const graph = await api().importGraph(body); await refreshGraphs(); importOpen.value = false; selectGraph(graph.graph_id); await loadGraph(graph.graph_id)
    notice.value = '图谱已作为新副本导入，尚未投入使用。可以先修改内容。'
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
  finally { importing.value = false }
}
async function importPrepared(url: string) {
  importing.value = true; error.value = ''
  try {
    const response = await fetch(apiUrl(workspace.baseUrl, url)); if (!response.ok) throw new Error('无法读取已准备的图谱包。')
    await importPackage(await response.json() as WorkingGraphPackage)
  } catch (e) { error.value = e instanceof Error ? e.message : String(e); importing.value = false }
}
async function conditionBundleChanged() {
  const id = workspace.graphId, candidate = text(selectedRow.value.hypothesis_id)
  await refreshGraphs(); await loadGraph(id); section.value = 'hypotheses'; selectedId.value = candidate
  notice.value = '候选专属诊断条件已保存。后续新分析使用这一版；已有运行保持原快照。'
}
function setGroupField(field: string, value: unknown) { selectedRow.value[field] = value; changed() }
watch(() => workspace.connected, (connected, previous) => { if (connected && !previous && !pkg.value && !loading.value && workspace.graphId) void loadGraph(workspace.graphId) })
watch(section, () => { search.value = ''; selectedId.value = '' }, { flush:'sync' })
watch(() => route.query.graph, (id) => { if (typeof id === 'string' && id !== workspace.graphId) chooseGraph(id) })
onMounted(async () => {
  void loadCapabilities()
  try {
    await refreshGraphs()
    const requested = typeof route.query.graph === 'string' ? route.query.graph : workspace.graphId
    const chosen = executableGraphs.value.find((g) => g.graph_id === requested) ?? executableGraphs.value.find((g) => g.enabled) ?? executableGraphs.value[0]
    if (chosen) { selectGraph(chosen.graph_id); await loadGraph(chosen.graph_id) }
  } catch (e) { error.value = e instanceof Error ? e.message : String(e) }
})
</script>
<template>
  <div class="graphs-page">
    <div class="page-heading"><div><span class="eyebrow">02 / EXECUTABLE KNOWLEDGE</span><h1>看懂知识，再投入使用</h1><p>从候选解释追到联合现象和观测条件。修改会持久保存，新分析使用当前版本。</p></div><div class="page-heading__actions"><button class="button button--secondary" @click="importOpen = true"><IconUpload /> 导入图谱</button><button v-if="pkg" class="button button--secondary" @click="downloadJson(`${pkg.title || '知识图谱'}.json`, pkg)"><IconDownload /> 导出</button></div></div>
    <div v-if="error" class="alert alert--error" role="alert"><span class="grow">{{ error }}</span><button class="text-button" @click="error = ''">关闭</button></div>
    <div v-if="notice" class="alert alert--success"><IconCheck /><span class="grow">{{ notice }}</span><button v-if="currentGraph?.enabled" class="text-button" @click="router.push(newAnalysisRoute(workspace.graphId))">前往推理分析 <IconArrowRight /></button></div>
    <section v-if="executableGraphs.length" class="graph-toolbar panel"><label class="graph-selector"><span class="section-kicker">当前图谱</span><select :value="workspace.graphId" aria-label="选择知识图谱" @change="chooseGraph(($event.target as HTMLSelectElement).value)"><option v-for="graph in executableGraphs" :key="graph.graph_id" :value="graph.graph_id">{{ friendly(graph.title, '未命名知识图谱') }}{{ graph.enabled ? ' · 已投入使用' : ' · 待启用' }}</option></select></label><div class="graph-toolbar__meta"><span class="tag tag--blue">{{ datasetShort[currentGraph?.dataset || ''] }}</span><span class="status-dot" :class="currentGraph?.enabled ? 'status-dot--green' : 'status-dot--amber'">{{ currentGraph?.enabled ? '已投入使用' : '尚未投入使用' }}</span></div><div class="grow" /><button v-if="dirty" class="button button--secondary" :disabled="saving" @click="save"><IconSave /> {{ saving ? '保存中…' : '保存修改' }}</button><button v-if="currentGraph?.enabled" class="button button--primary" :disabled="dirty" @click="router.push(newAnalysisRoute(workspace.graphId))">使用此图分析 <IconArrowRight /></button><button v-else class="button button--primary" :disabled="!canEnable || enabling" @click="enable(true)"><IconCheck />{{ enabling ? '正在启用…' : '投入使用' }}</button></section>
    <div v-if="loading" class="loading-inline"><IconRefresh class="is-spinning" /> 读取可执行知识…</div>
    <div v-else-if="!pkg" class="panel empty-state"><div class="empty-state__icon"><IconRelation /></div><h3>还没有可查看的知识图谱</h3><p>从素材页制作图谱，或导入一个完整、可执行的图谱包。</p><div class="button-row" style="justify-content:center"><button class="button button--primary" @click="router.push('/materials')">从知识资料开始 <IconArrowRight /></button><button class="button button--secondary" @click="importOpen = true">导入已准备图谱</button></div></div>
    <template v-else-if="pkg.schema_version === 'rootlens-working-graph.v2'">
      <div v-if="dirty" class="alert alert--warning"><IconEdit /><span>当前有未保存的修改。保存后，新分析才能使用它们。</span><button class="text-button" :disabled="saving" @click="save">保存修改</button></div>
      <div class="graph-workspace"><div class="graph-overview"><section class="panel"><header class="panel-header"><div><h2>知识关系概览</h2><p>点击任一内容，在右侧理解或修改</p></div><span class="tag">语义视图</span></header><div class="graph-counters"><div v-for="count in summaryCounts" :key="count.label"><strong>{{ count.count }}</strong><span>{{ count.label }}</span></div></div><div class="graph-canvas-wrap"><SemanticGraph :knowledge="knowledge" :selected-id="selectedItem?.id" @select="selectSemantic" /></div><footer class="graph-map-footer"><IconInfoCircle /><span>连线表达图谱中的规则。候选原因仍需实际观测与联合条件支持，不表示已验证根因。</span></footer></section><section class="objects-band"><span class="section-kicker">观测对象与变量</span><div class="tag-row"><button v-for="entity in rows(knowledge.entities)" :key="text(entity.entity_id)" class="object-chip" @click="selectSemantic(text(entity.entity_id))">{{ friendly(entity.label) }}<small v-if="texts(entity.aliases).length">{{ texts(entity.aliases).length }} 个别名</small></button></div></section><details class="technical"><summary>完整可执行图谱与高级操作</summary><div class="button-row" style="margin-top:14px"><button class="button button--secondary button--small" @click="downloadJson(`${pkg.title}.json`, pkg)">下载完整图谱</button><button v-if="currentGraph?.enabled" class="button button--danger button--small" :disabled="enabling || dirty" @click="enable(false)">停止用于新分析</button></div><dl><dt>稳定图谱 ID</dt><dd><code>{{ workspace.graphId }}</code></dd><dt>包格式</dt><dd>{{ pkg.schema_version }}</dd></dl><pre>{{ JSON.stringify(pkg, null, 2) }}</pre></details></div>
      <aside class="panel knowledge-inspector"><header class="panel-header"><div><h2>查看与修改</h2><p>{{ knowledgeSections.find((s) => s.key === section)?.hint }}</p></div><IconEdit class="subtle" /></header><div class="inspector-picker"><select v-model="section" aria-label="图谱内容类别"><option v-for="item in knowledgeSections" :key="item.key" :value="item.key">{{ item.label }}（{{ catalog(knowledge, item.key).length }}）</option></select><div class="search-wrap"><IconSearch /><input v-model="search" class="search-input" placeholder="查找内容" aria-label="搜索图谱内容" /></div><button v-if="section === 'bindings'" type="button" class="button button--secondary button--small" :disabled="!mappingFeatures.length" @click="addBinding"><IconPlus />添加等价词汇</button><div v-if="section === 'bindings' || section === 'observable_definitions'" class="capability-status"><span>{{ capabilitiesLoading ? '正在读取后端能力目录…' : capability ? '使用后端共用能力目录' : '目录尚未加载' }}</span><button type="button" class="text-button" :disabled="capabilitiesLoading" @click="loadCapabilities"><IconRefresh />重读</button><p v-if="capabilitiesError" class="error-text">{{ capabilitiesError }}</p></div></div><div class="knowledge-item-list"><button v-for="item in filteredItems" :key="item.id" :class="{ active: selectedItem?.id === item.id }" @click="chooseItem(item)"><span class="knowledge-item-dot" :class="section" /><span><strong>{{ item.label }}</strong><small>{{ item.subtitle }}</small></span><IconArrowRight /></button><p v-if="!filteredItems.length" class="muted" style="padding:10px 18px">这里暂无内容。</p></div>
        <form v-if="selectedItem" class="knowledge-editor" @submit.prevent="save" @input="changed">
          <template v-if="['entities', 'hypotheses', 'mechanisms', 'pattern_definitions', 'observable_definitions'].includes(selectedItem.group)"><label class="field">名称<input v-model="selectedRow.label" required /></label></template>
          <template v-if="selectedItem.group === 'entities'"><label class="field">别名<textarea aria-label="别名" :value="texts(selectedRow.aliases).join('\n')" rows="2" placeholder="每行一个别名；用于识别同一观测对象" @input="setAliases(($event.target as HTMLTextAreaElement).value)" /><small>新增别名保留同一主体身份，不创建新的测量值。</small></label><p class="muted">对象类型：{{ friendly(selectedRow.kind) }}</p></template>
          <template v-else-if="selectedItem.group === 'hypotheses'"><label class="field">假设成本<input v-model.number="selectedRow.assumption_cost" type="number" min="0" step="0.1" required /><small>统一推理中单根假设的显式代价，不是置信率。</small></label><p class="muted">目标：{{ selectedRow.target_role === 'pattern_family' ? '图案类别' : '候选原因机制' }}<br />适用对象：{{ nameOf(knowledge, selectedRow.applies_to_class_id) }}</p><CandidateConditions :key="text(selectedRow.hypothesis_id)" :graph-id="workspace.graphId" :candidate-id="text(selectedRow.hypothesis_id)" :candidate-name="friendly(selectedRow.label)" :knowledge="knowledge" :disabled="dirty || saving" @changed="conditionBundleChanged" /></template>
          <template v-else-if="selectedItem.group === 'pattern_definitions'"><div class="field">联合条件<ExpressionEditor :model-value="selectedRow.body" :options="expressionOptions" @update:model-value="setGroupField('body', $event)" /><small>同一联合现象需要符合这里的逻辑与范围要求。</small></div><label class="field">联合范围<select v-model="selectedRow.scope_join" @change="changed"><option value="same_subject_same_scope">同一主体、同一区域</option><option value="same_event_same_window">同一事件、同一时间窗</option><option value="same_wafer_parent_scope">同一晶圆的不同区域</option><option value="same_subject_parent_scope">同一主体的父级范围</option></select></label></template>
          <template v-else-if="selectedItem.group === 'observable_definitions'"><ConditionPredicateEditor :condition="selectedRow" :features="features" @update="updatePredicate" /><label class="field">观测主体<select aria-label="观测主体" :value="record(selectedRow.subject_selector).kind" @change="setSubject(($event.target as HTMLSelectElement).value)"><option value="focus">本次关注的区域 / 对象</option><option value="bound_entity">指定图谱对象或变量</option></select><select v-if="record(selectedRow.subject_selector).kind === 'bound_entity'" v-model="record(selectedRow.subject_selector).entity_id" aria-label="指定观测变量" @change="changed"><option v-for="entity in rows(knowledge.entities)" :key="text(entity.entity_id)" :value="text(entity.entity_id)">{{ friendly(entity.label) }}</option></select></label><label class="field">作用范围<select aria-label="作用范围" :value="record(selectedRow.scope_selector).kind" @change="setScope(($event.target as HTMLSelectElement).value)"><option value="task_scope">当前分析范围</option><option value="spatial_zone">晶圆 / 空间指定区域</option></select><select v-if="record(selectedRow.scope_selector).kind !== 'task_scope'" v-model="record(selectedRow.scope_selector).zone" aria-label="空间区域" @change="changed"><option value="all_valid">全片有效区</option><option value="center">中心区</option><option value="middle">中圈</option><option value="edge">边缘区</option></select></label></template>
          <template v-else-if="['effect_rules', 'expectation_rules'].includes(selectedItem.group)"><label class="field">起点<select v-model="selectedRow.from_id" @change="changed"><option v-for="node in activeOptions" :key="rowId(node)" :value="rowId(node)">{{ friendly(node.label) }}</option></select></label><label v-if="selectedItem.group === 'effect_rules'" class="field">影响到的机制 / 假设<select v-model="selectedRow.to_id" @change="changed"><option v-for="node in activeOptions" :key="rowId(node)" :value="rowId(node)">{{ friendly(node.label) }}</option></select></label><template v-else><label class="field">预期的联合现象<select v-model="selectedRow.pattern_id" @change="changed"><option v-for="pattern in rows(knowledge.pattern_definitions)" :key="text(pattern.pattern_id)" :value="text(pattern.pattern_id)">{{ friendly(pattern.label) }}</option></select></label><label class="field">关系强度<select v-model="selectedRow.mode" @change="changed"><option value="expected">预期表现</option><option value="necessary">必要条件</option><option value="possible">可能表现</option></select><small>必要条件冲突或缺失会阻止候选进入支持排名。</small></label></template></template>
          <template v-else-if="selectedItem.group === 'relations'"><label class="field">起点<select v-model="selectedRow.head" @change="changed"><option v-for="entity in rows(knowledge.entities)" :key="text(entity.entity_id)" :value="text(entity.entity_id)">{{ friendly(entity.label) }}</option></select></label><label class="field">关系<input v-model="selectedRow.relation" required /></label><label class="field">终点<select v-model="selectedRow.tail" @change="changed"><option v-for="entity in rows(knowledge.entities)" :key="text(entity.entity_id)" :value="text(entity.entity_id)">{{ friendly(entity.label) }}</option></select></label></template>
          <template v-else-if="selectedItem.group === 'subject_bindings'"><label class="field">外部命名空间<input v-model="selectedRow.namespace" required /></label><label class="field">外部主体名称<input v-model="selectedRow.external_id" required /></label><label class="field">对应图谱对象<select v-model="selectedRow.target_id" @change="changed"><option v-for="entity in rows(knowledge.entities)" :key="text(entity.entity_id)" :value="text(entity.entity_id)">{{ friendly(entity.label) }}</option></select></label></template>
          <template v-else-if="selectedItem.group === 'value_bindings'"><ValueBindingEditor :binding="selectedRow" :features="features" :knowledge="knowledge" @update="updateBinding" @remove="removeBinding" /></template>
          <template v-else-if="selectedItem.group === 'source_assertions'"><span class="tag">{{ friendly(selectedRow.origin) }}</span><p class="source-text">{{ selectedRow.text }}</p><p v-if="selectedRow.locator" class="muted">原文位置：{{ selectedRow.locator }}</p><p class="muted">参数来源：{{ friendly(selectedRow.parameter_origin) }}</p></template>
          <div v-if="selectedSources.length && selectedItem.group !== 'value_bindings'" class="editor-source"><span class="section-kicker">这项知识的依据</span><details v-for="(source, index) in selectedSources" :key="text(source.assertion_id)"><summary><IconFile /> {{ friendly(source.origin) }}<span v-if="source.locator"> · {{ source.locator }}</span><span v-else> · 来源 {{ index + 1 }}</span></summary><p>{{ source.text }}</p><small>参数：{{ friendly(source.parameter_origin) }}</small></details></div>
          <details class="technical"><summary>稳定引用与原始字段</summary><p style="margin-top:12px"><code>{{ selectedItem.id }}</code></p><pre>{{ JSON.stringify(selectedRow, null, 2) }}</pre></details>
          <footer v-if="section !== 'sources'" class="editor-save"><button class="button button--primary button--full" :disabled="!dirty || saving" type="submit"><IconSave />{{ saving ? '保存中…' : dirty ? '保存修改并生效' : '所有修改已保存' }}</button></footer>
        </form>
      </aside></div>
    </template>
    <div v-else class="panel empty-state"><h3>这份图谱不是当前可执行格式</h3><p>请从素材重新制作，或导入 v2 图谱包。</p><button class="button button--primary" @click="router.push('/materials')">前往素材管理</button></div>
    <a-modal v-model:visible="importOpen" title="导入可执行知识图谱" :footer="false" width="650px"><div class="form-stack"><p class="muted">导入会创建未启用的新副本。要完整展示资料制作流程，请从素材管理开始。</p><div class="file-drop" role="button" tabindex="0" @click="importInput?.click()" @keydown.enter.prevent="importInput?.click()"><IconUpload /><strong>{{ importFile?.name || '选择图谱 JSON 文件' }}</strong><p>rootlens-working-graph.v2 · 完整知识、条件与来源</p><input ref="importInput" class="native-file" type="file" accept=".json" @change="importFile = ($event.target as HTMLInputElement).files?.[0] ?? null" /></div><button class="button button--primary" :disabled="!importFile || importing" @click="importPackage()">{{ importing ? '正在导入…' : '导入为新图谱' }}</button><div v-if="workspace.demos.demos.length" class="subsection"><span class="section-kicker">或载入已准备的演示图谱（跳过制作）</span><button v-for="demo in workspace.demos.demos" :key="demo.id" class="prepared-graph" :disabled="!demo.working_graph?.available || importing" @click="importPrepared(demo.working_graph.download_url!)"><IconRelation /><div class="grow"><strong>{{ demo.title }}</strong><small>经过演示适配 · 导入后可修改与启用</small></div><IconArrowRight /></button></div><p v-if="error" class="error-text">{{ error }}</p></div></a-modal>
  </div>
</template>
<style scoped>
.graph-toolbar{padding:17px 20px;display:flex;align-items:center;gap:16px;margin-bottom:22px;}.graph-selector{min-width:230px;max-width:450px;flex:1;}.graph-selector .section-kicker{display:block;font-size:11px;margin-bottom:6px;}.graph-selector select{border:0;background:none;color:#2c3d58;font-size:14px;max-width:100%;width:100%;padding:0 24px 0 0;outline-color:#7f8ca1;}.graph-toolbar__meta{display:flex;gap:12px;align-items:center;}.graph-workspace{display:grid;grid-template-columns:minmax(0,1fr) 345px;gap:22px;align-items:start;}.graph-overview{min-width:0;}.graph-counters{display:flex;gap:30px;padding:21px 24px;border-bottom:1px solid #edf0f5;}.graph-counters>div{display:flex;gap:9px;align-items:baseline;}.graph-counters strong{font-size:20px;font-weight:500;color:#405674;}.graph-counters span{font-size:12px;color:var(--muted);}.graph-canvas-wrap{padding:8px 12px 0;}.graph-map-footer{padding:15px 24px 19px;display:flex;gap:8px;align-items:flex-start;border-top:1px solid #f0f2f6;color:#8d98aa;font-size:12px;line-height:1.7;}.graph-map-footer svg{font-size:12px;margin-top:2px;flex-shrink:0;}.objects-band{padding:24px 0;}.objects-band>.section-kicker{display:block;}.object-chip{display:inline-flex;align-items:center;gap:7px;border:1px solid #e0e6f0;background:#fff;border-radius:5px;padding:6px 10px;font-size:13px;color:#5f718e;}.object-chip:hover{border-color:#7f8ca1;}.object-chip small{font-size:11px;color:#7f8ca1;}.knowledge-inspector{overflow:hidden;}.capability-status{display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:11px;color:#8a9ab2;}.capability-status>.text-button{font-size:11px;margin-left:auto;}.capability-status>.error-text{font-size:11px;margin:3px 0 0;width:100%;}.knowledge-inspector .panel-header{padding:19px;}.knowledge-inspector .panel-header p{font-size:12px;}.inspector-picker{padding:15px 18px;display:flex;flex-direction:column;gap:11px;border-bottom:1px solid var(--border);}.inspector-picker>select{width:100%;padding:8px 10px;font-size:12px;border:1px solid #e0e6f0;border-radius:5px;color:#526a8e;background:#fff;}.inspector-picker .search-input{min-height:32px;font-size:13px;padding-top:6px;padding-bottom:6px;}.inspector-picker .search-wrap svg{top:9px;font-size:12px;}.knowledge-item-list{max-height:205px;overflow:auto;background:#fcfdff;border-bottom:1px solid var(--border);}.knowledge-item-list>button{display:flex;align-items:flex-start;gap:8px;text-align:left;border:0;background:none;width:100%;padding:11px 18px;border-bottom:1px solid #f0f3f8;color:#687a96;}.knowledge-item-list>button.active{background:#edf3ff;color:var(--blue);box-shadow:inset 3px 0 var(--blue);}.knowledge-item-list>button>span:nth-child(2){flex:1;min-width:0;}.knowledge-item-list strong{display:block;font-size:13px;font-weight:500;line-height:1.7;}.knowledge-item-list small{display:block;font-size:11px;color:#7f8ca1;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;margin-top:4px;}.knowledge-item-list>button>svg{font-size:12px;margin-top:4px;opacity:0;}.knowledge-item-list>button.active>svg{opacity:1;}.knowledge-item-dot{width:5px;height:5px;background:#7597d7;border-radius:50%;margin-top:6px;flex-shrink:0;}.knowledge-item-dot.mechanisms{background:#aa8bcc;}.knowledge-item-dot.pattern_definitions{background:#dfad6f;}.knowledge-editor{padding:19px;display:flex;flex-direction:column;gap:18px;}.knowledge-editor .field{font-size:13px;gap:6px;}.knowledge-editor .field>input,.knowledge-editor .field>select,.knowledge-editor .field>textarea{font-size:12px;min-height:34px;padding:7px 9px;}.knowledge-editor .field small{font-size:12px;}.knowledge-editor .form-grid{gap:12px;}.knowledge-editor .technical{margin-top:0;}.editor-source{border-top:1px solid var(--border);padding-top:16px;}.editor-source .section-kicker{font-size:11px;display:block;}.editor-source details{font-size:12px;color:#7e8ba0;padding:8px 0;line-height:1.7;}.editor-source summary{cursor:pointer;}.editor-source details p{font-size:13px;color:#68768d;margin:9px 0;line-height:1.9;}.editor-source details small{font-size:11px;color:#7f8ca1;}.editor-save{margin:0 -19px -19px;padding:15px 19px;border-top:1px solid var(--border);background:#fafbfe;}.source-text{font-size:12px;line-height:1.9;color:#5e6c82;}.prepared-graph{display:flex;align-items:center;gap:12px;padding:15px 0;background:none;border:0;border-bottom:1px solid var(--border);width:100%;text-align:left;}.prepared-graph>svg{font-size:22px;color:var(--blue);}.prepared-graph strong{display:block;font-size:12px;color:#4b6183;}.prepared-graph small{display:block;color:#7f8ca1;font-size:12px;margin-top:5px;}.prepared-graph>svg:last-child{font-size:13px;color:#7f8ca1;}
@media(max-width:1350px){.graph-workspace{grid-template-columns:minmax(0,1fr) 310px;gap:16px;}.graph-counters{gap:18px;padding:17px 20px;}.graph-counters>div{display:block;}.graph-counters strong{display:block;font-size:18px;margin-bottom:3px;}.graph-toolbar__meta{display:none;}}@media(max-width:1100px){.graph-workspace{grid-template-columns:1fr;}.knowledge-inspector{display:grid;grid-template-columns:280px minmax(0,1fr);}.knowledge-inspector .panel-header{grid-column:1/-1;}.inspector-picker{grid-column:1;}.knowledge-item-list{grid-column:1;max-height:420px;grid-row:3/5;}.knowledge-editor{grid-column:2;grid-row:2/5;border-left:1px solid var(--border);}.graph-counters>div{display:flex;gap:8px;align-items:baseline;}.graph-counters strong{display:inline-block;}.graph-toolbar{flex-wrap:wrap;}.graph-selector{max-width:none;}}@media(max-width:650px){.knowledge-inspector{display:block;}.knowledge-item-list{max-height:180px;}.knowledge-editor{border-left:0;}.graph-toolbar .grow{display:none;}.graph-toolbar{gap:12px;}.graph-selector{width:100%;min-width:0;flex:auto;}.graph-counters{justify-content:space-between;gap:8px;}.graph-counters>div{display:block;}.graph-counters span{font-size:11px;}}
</style>
