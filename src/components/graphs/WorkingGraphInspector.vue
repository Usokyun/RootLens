<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import type { KGStudioGraphEdge, KGStudioPayload, WorkingGraphPackage } from '@/api/contracts'
import { editableWorkingGraphNode } from '@/services/working-graph-edit'
import { traceRecord, type TraceRecord } from '@/services/unified-reasoning-display'
import {
  buildWorkingGraphView, graphConditionName, graphExpressionName, graphFeatureName, graphOperandText, graphScopeJoinName, graphScopeName,
  graphSourceLocation, graphSourceOrigin, graphText, knownGraphSources, previewNodeName, readWorkingGraphKnowledge, workingGraphEdgeSources,
  workingGraphGroups, workingGraphKind, workingGraphMode, workingGraphScene, workingRelationshipName, type WorkingGraphSelection,
} from '@/services/working-graph-view'

const props = defineProps<{ studio: KGStudioPayload; graphPackage: WorkingGraphPackage | null; selection: WorkingGraphSelection }>()
const emit = defineEmits<{ select: [selection: WorkingGraphSelection]; 'edit-node': [nodeId: string]; 'open-package': [] }>()
const tab = ref<'details' | 'rules'>('details')
const tabId = useId()
const detailsTab = ref<HTMLButtonElement | null>(null), rulesTab = ref<HTMLButtonElement | null>(null)
const view = computed(() => buildWorkingGraphView(props.studio))
const knowledge = computed(() => readWorkingGraphKnowledge(props.graphPackage, props.studio.graph_id))
const node = computed(() => props.selection?.type === 'node' ? view.value.nodesById.get(props.selection.id) : undefined)
const edge = computed(() => props.selection?.type === 'edge' ? view.value.edgesById.get(props.selection.id) : undefined)
const kind = computed(() => node.value ? workingGraphKind(node.value.node_type, node.value.scenario) : null)
const declaration = computed(() => node.value ? knowledge.value?.indexed.get(node.value.node_id) : undefined)
const editable = computed(() => knowledge.value && node.value ? editableWorkingGraphNode(props.graphPackage, node.value.node_id) : null)
const phenomena = computed(() => [...view.value.nodesById.values()].filter(item => item.node_type === 'Phenomenon'))
const otherEdges = computed(() => node.value ? view.value.adjacency.get(node.value.node_id) ?? [] : [])
const scene = computed(() => props.graphPackage?.dataset ? workingGraphScene(props.graphPackage.dataset) : view.value.scenarios.map(workingGraphScene).join(' / '))
const sources = computed(() => edge.value ? workingGraphEdgeSources(knowledge.value, edge.value)
  : node.value?.node_type === 'SourceAssertion' && declaration.value ? [declaration.value]
    : knownGraphSources(knowledge.value, declaration.value?.source_assertion_ids))
const rules = computed(() => {
  if (!knowledge.value) return []
  return [...knowledge.value.patterns, ...knowledge.value.expectations, ...knowledge.value.effects]
})
const sourceRegistry = computed(() => new Map(props.studio.sources.map(item => [item.source_id, item])))
const knownEndpoint = (id: string) => view.value.nodesById.has(id)

function nodeName(id: unknown) {
  const key = graphText(id)
  return view.value.names.get(key) || graphText(knowledge.value?.indexed.get(key)?.label) || key || '未保存'
}
function conditionSubject(row: TraceRecord) {
  const subject = traceRecord(row.subject_selector)
  return subject.kind === 'focus' ? '任务关注对象' : nodeName(subject.entity_id)
}
function ruleName(row: TraceRecord) {
  if (row.pattern_id && row.from_id) return `${nodeName(row.from_id)} → ${nodeName(row.pattern_id)}`
  if (row.to_id) return `${nodeName(row.from_id)} → ${nodeName(row.to_id)}`
  return graphText(row.label) || nodeName(row.pattern_id)
}
function ruleCondition(row: TraceRecord) {
  if (row.definition_id) return `${graphExpressionName(row.body, id => {
    const atom = knowledge.value?.indexed.get(id)
    return atom ? graphConditionName(atom) : id
  })} · ${graphScopeJoinName(row.scope_join)}`
  if (row.pattern_id && row.from_id) return `${workingGraphMode(row.mode)} · 诊断规则`
  return '作用规则'
}
function endpointLabel(item: KGStudioGraphEdge) {
  return nodeName(item.head === node.value?.node_id ? item.tail : item.head)
}
function sourceName(source: TraceRecord) {
  const id = graphText(source.source_id)
  return sourceRegistry.value.get(id)?.title || id || graphText(source.assertion_id)
}
function sourceLink(source: TraceRecord) {
  const url = sourceRegistry.value.get(graphText(source.source_id))?.path_or_url ?? ''
  try { const address = new URL(url); return /^https?:$/.test(address.protocol) ? address.href : '' } catch { return '' }
}
function selectNode(id: unknown) {
  const key = graphText(id)
  if (knownEndpoint(key)) emit('select', { type: 'node', id: key })
}
function navigateTabs(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const next = event.key === 'Home' ? 'details' : event.key === 'End' ? 'rules' : tab.value === 'details' ? 'rules' : 'details'
  tab.value = next
  ;(next === 'details' ? detailsTab.value : rulesTab.value)?.focus()
}
watch(() => props.selection, (selected) => { if (selected) tab.value = 'details' })
</script>

<template>
  <aside class="working-inspector" aria-label="工作图检查器">
    <div class="inspector-tabs" role="tablist" aria-label="工作图检查内容" @keydown="navigateTabs">
      <button :id="`${tabId}-details-tab`" ref="detailsTab" type="button" role="tab" :aria-selected="tab === 'details'" :tabindex="tab === 'details' ? 0 : -1"
        :aria-controls="`${tabId}-details`" @click="tab = 'details'">详情</button>
      <button :id="`${tabId}-rules-tab`" ref="rulesTab" type="button" role="tab" :aria-selected="tab === 'rules'" :tabindex="tab === 'rules' ? 0 : -1"
        :aria-controls="`${tabId}-rules`" @click="tab = 'rules'">规则与绑定</button>
    </div>
    <div v-if="tab === 'details'" :id="`${tabId}-details`" class="inspector-body" role="tabpanel" :aria-labelledby="`${tabId}-details-tab`">
      <template v-if="node && kind">
        <section>
          <p class="inspector-kind"><i :style="{ background: workingGraphGroups[kind.group].color }" />{{ kind.label }}</p>
          <h2>{{ node.node_type === 'ObservablePredicate' && declaration ? graphConditionName(declaration) : nodeName(node.node_id) }}</h2>
          <p v-if="node.node_type === 'ObservablePredicate' && declaration?.label && declaration.label !== graphConditionName(declaration)" class="inspector-note">{{ declaration.label }}</p>
          <p v-if="node.aliases?.length" class="inspector-note">别名：{{ node.aliases.join('、') }}</p>
          <div class="inspector-actions">
            <a-button v-if="editable" size="small" @click="emit('edit-node', editable.id)">编辑节点</a-button>
            <a-button size="small" type="text" @click="emit('select', null)">清除定位</a-button>
          </div>
          <details class="technical-detail">
            <summary>节点标识</summary>
            <code>{{ node.node_id }}</code><span>类型：{{ node.node_type || '未保存' }}</span>
            <span v-if="node.label && node.label !== node.node_id && nodeName(node.node_id) !== node.label">保存名称：{{ node.label }}</span>
            <span v-if="node.description">{{ node.description }}</span>
          </details>
        </section>
        <section v-if="declaration && node.node_type === 'ObservablePredicate'">
          <h3>观测条件</h3>
          <dl class="inspector-kv">
            <dt>特征</dt><dd>{{ graphFeatureName(declaration.feature_id) }}</dd>
            <dt>主体</dt><dd>{{ conditionSubject(declaration) }}</dd>
            <dt>范围</dt><dd>{{ graphScopeName(declaration.scope_selector) }}</dd>
            <template v-if="declaration.reference_requirement === 'same_as_task'"><dt>参考</dt><dd>与任务使用同一参考</dd></template>
          </dl>
          <details class="technical-detail"><summary>原始条件字段</summary><code>{{ declaration.feature_id }} · {{ declaration.op }} · {{ JSON.stringify(declaration.operand) }}</code></details>
        </section>
        <section v-else-if="declaration?.definition_id">
          <h3>联合条件</h3><p>{{ ruleCondition(declaration) }}</p>
        </section>
        <section v-else-if="declaration?.rule_id">
          <h3>{{ kind.label }}</h3><p>{{ ruleName(declaration) }}</p>
          <p class="inspector-note">{{ ruleCondition(declaration) }}</p>
        </section>
        <section v-else-if="declaration?.binding_id">
          <h3>词汇绑定</h3>
          <p>{{ graphFeatureName(declaration.feature_id) }} · {{ declaration.external_value }} → {{ declaration.canonical_value }}</p>
          <p v-if="declaration.procedure_model_id" class="inspector-note">模型：{{ declaration.procedure_model_id }}</p>
        </section>
        <section v-if="sources.length">
          <h3>来源 <small>{{ sources.length }} 条</small></h3>
          <details v-for="(source, index) in sources" :key="String(source.assertion_id)" class="source-item" :open="index === 0">
            <summary>{{ graphSourceOrigin(source.origin) }}<template v-if="source.locator"> · {{ graphSourceLocation(source.locator) }}</template></summary>
            <p v-if="source.text">{{ source.text }}</p>
            <a v-if="sourceLink(source)" :href="sourceLink(source)" target="_blank" rel="noopener noreferrer">{{ sourceName(source) }}</a>
            <code v-else-if="source.source_id">{{ sourceName(source) }}</code>
            <small v-if="source.source_unit_id">资料片段：{{ source.source_unit_id }}</small>
          </details>
        </section>
        <section>
          <h3>相邻关系 <small>{{ otherEdges.length }} 条（预览）</small></h3>
          <ul v-if="otherEdges.length" class="inspector-list neighbor-list">
            <li v-for="item in otherEdges" :key="item.edge_id">
              <button type="button" class="inspector-link" @click="emit('select', { type: 'edge', id: item.edge_id })">
                <span>{{ endpointLabel(item) }}</span>
                <small>{{ item.head === node.node_id ? '指向' : '来自' }} · {{ workingRelationshipName(item.relation) }}</small>
              </button>
            </li>
          </ul>
          <p v-else class="inspector-note">当前画布未包含该节点的相邻关系。</p>
        </section>
      </template>

      <template v-else-if="edge">
        <section>
          <p class="inspector-kind">有向关系</p>
          <h2>{{ workingRelationshipName(edge.relation) }}</h2>
          <dl class="inspector-kv endpoints">
            <dt>起点</dt><dd><button type="button" class="inspector-link" @click="selectNode(edge.head)">{{ nodeName(edge.head) }}</button></dd>
            <dt>终点</dt><dd><button type="button" class="inspector-link" @click="selectNode(edge.tail)">{{ nodeName(edge.tail) }}</button></dd>
          </dl>
          <a-button size="small" type="text" @click="emit('select', null)">清除定位</a-button>
          <details class="technical-detail"><summary>关系标识</summary>
            <code>{{ edge.edge_id }}</code><span>类型：{{ edge.relation || '未保存' }}</span>
            <span v-if="edge.source">投影记录：{{ edge.source }}</span>
          </details>
        </section>
        <section>
          <h3>来源 <small v-if="sources.length">{{ sources.length }} 条</small></h3>
          <details v-for="(source, index) in sources" :key="String(source.assertion_id)" class="source-item" :open="index === 0">
            <summary>{{ graphSourceOrigin(source.origin) }}<template v-if="source.locator"> · {{ graphSourceLocation(source.locator) }}</template></summary>
            <p v-if="source.text">{{ source.text }}</p>
            <a v-if="sourceLink(source)" :href="sourceLink(source)" target="_blank" rel="noopener noreferrer">{{ sourceName(source) }}</a>
            <code v-else-if="source.source_id">{{ sourceName(source) }}</code>
            <small v-if="source.source_unit_id">资料片段：{{ source.source_unit_id }}</small>
          </details>
          <p v-if="!sources.length && edge.evidence" class="inspector-note">{{ edge.evidence }}</p>
          <p v-else-if="!sources.length" class="inspector-note">这条关系未单独保存资料出处。</p>
        </section>
      </template>

      <template v-else>
        <section>
          <h3>图谱概览</h3>
          <dl class="inspector-kv">
            <template v-if="scene"><dt>场景</dt><dd>{{ scene }}</dd></template>
            <dt>完整图</dt><dd>{{ view.nodeTotal }} 节点 · {{ view.edgeTotal }} 关系</dd>
            <template v-if="knowledge"><dt>知识来源</dt><dd>{{ knowledge.sources.length }} 条来源记录</dd></template>
          </dl>
        </section>
        <section v-if="phenomena.length">
          <h3>从现象开始</h3>
          <ul class="inspector-list">
            <li v-for="item in phenomena.slice(0, 5)" :key="item.node_id">
              <button type="button" class="inspector-link" @click="selectNode(item.node_id)">
                <span>{{ previewNodeName(item) }}</span><small>查看条件与相邻关系</small>
              </button>
            </li>
          </ul>
          <p v-if="phenomena.length > 5" class="inspector-note">更多现象可从画布定位。</p>
        </section>
        <section>
          <h3>分析入口</h3>
          <p class="inspector-note">当前工作图用于新分析。已保存的解释请在运行详情查看。</p>
        </section>
      </template>
    </div>

    <div v-else :id="`${tabId}-rules`" class="inspector-body" role="tabpanel" :aria-labelledby="`${tabId}-rules-tab`">
      <p v-if="!knowledge" class="inspector-note">{{ graphPackage?.schema_version === 'rootlens-working-graph.v1'
        ? '旧版工作图只读，不含当前版本的规范观测条件或 Evidence 绑定。' : '未加载可读取的规范工作图包。' }}</p>
      <template v-else>
        <section>
          <h3>观测条件 <small>{{ knowledge.conditions.length }} 条</small></h3>
          <ul v-if="knowledge.conditions.length" class="inspector-list">
            <li v-for="condition in knowledge.conditions.slice(0, 6)" :key="String(condition.predicate_id)">
              <button v-if="knownEndpoint(graphText(condition.predicate_id))" type="button" class="inspector-link" @click="selectNode(condition.predicate_id)">
                {{ graphConditionName(condition) }}
              </button>
              <details v-else class="technical-detail"><summary>{{ graphConditionName(condition) }}</summary>
                <span>{{ conditionSubject(condition) }} · {{ graphScopeName(condition.scope_selector) }} · 不在画布预览</span>
                <code>{{ condition.predicate_id }}</code>
              </details>
            </li>
          </ul>
          <p v-else class="inspector-note">未配置观测条件。</p>
          <details v-if="knowledge.conditions.length > 6" class="technical-detail">
            <summary>其余 {{ knowledge.conditions.length - 6 }} 条观测条件</summary>
            <ul class="inspector-list">
              <li v-for="condition in knowledge.conditions.slice(6)" :key="String(condition.predicate_id)">
                <button v-if="knownEndpoint(graphText(condition.predicate_id))" type="button" class="inspector-link" @click="selectNode(condition.predicate_id)">{{ graphConditionName(condition) }}</button>
                <span v-else>{{ graphConditionName(condition) }} <small>（不在预览）</small></span>
              </li>
            </ul>
          </details>
        </section>
        <section>
          <h3>Evidence 绑定</h3>
          <dl class="inspector-kv">
            <dt>主体映射</dt><dd>{{ knowledge.subjectBindings.length }} 条</dd>
            <dt>词汇映射</dt><dd>{{ knowledge.valueBindings.length }} 条</dd>
          </dl>
          <div v-for="binding in knowledge.subjectBindings.slice(0, 2)" :key="`${binding.namespace}/${binding.external_id}`" class="binding-row">
            <span>{{ binding.external_id }} → {{ nodeName(binding.target_id) }}</span><small>{{ binding.namespace }}</small>
          </div>
          <details v-if="knowledge.subjectBindings.length > 2" class="technical-detail">
            <summary>其余 {{ knowledge.subjectBindings.length - 2 }} 条主体映射</summary>
            <div v-for="binding in knowledge.subjectBindings.slice(2)" :key="`${binding.namespace}/${binding.external_id}`" class="binding-row">
              <span>{{ binding.external_id }} → {{ nodeName(binding.target_id) }}</span><small>{{ binding.namespace }}</small>
            </div>
          </details>
          <details v-if="knowledge.valueBindings.length" class="technical-detail">
            <summary>查看 {{ knowledge.valueBindings.length }} 条词汇映射</summary>
            <div v-for="binding in knowledge.valueBindings" :key="String(binding.binding_id)" class="binding-row">
              <span>{{ graphOperandText({ kind: 'category', category: binding.external_value }) }} → {{ graphOperandText({ kind: 'category', category: binding.canonical_value }) }}</span>
              <small>{{ graphFeatureName(binding.feature_id) }}<template v-if="binding.procedure_model_id"> · {{ binding.procedure_model_id }}</template></small>
              <button v-if="knownEndpoint(graphText(binding.binding_id))" type="button" class="inspector-link" @click="selectNode(binding.binding_id)">在画布定位</button>
              <small v-for="source in knownGraphSources(knowledge, binding.source_assertion_ids)" :key="String(source.assertion_id)">
                {{ graphSourceOrigin(source.origin) }}<template v-if="source.locator"> · {{ graphSourceLocation(source.locator) }}</template> · {{ sourceName(source) }}
              </small>
            </div>
          </details>
        </section>
        <section>
          <h3>完整可执行知识</h3>
          <p class="inspector-note">画布是关系预览。联合条件、诊断规则和绑定以工作图包为准。</p>
          <a-button size="small" @click="emit('open-package')">查看工作图包</a-button>
          <details v-if="rules.length" class="technical-detail">
            <summary>查看 {{ rules.length }} 条定义与规则</summary>
            <ul class="inspector-list">
              <li v-for="rule in rules" :key="String(rule.rule_id || rule.definition_id)">
                <strong>{{ ruleName(rule) }}</strong><small>{{ ruleCondition(rule) }}</small>
                <button v-if="knownEndpoint(graphText(rule.rule_id || rule.definition_id))" type="button" class="inspector-link" @click="selectNode(rule.rule_id || rule.definition_id)">在画布定位</button>
              </li>
            </ul>
          </details>
        </section>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.working-inspector {
  display: flex; flex-direction: column; min-height: 0; min-width: 0; height: 100%;
  border: 1px solid var(--color-border-2); border-radius: 5px; background: var(--color-bg-2);
  color: var(--color-text-1); font-size: 13px; overflow: hidden; overflow-wrap: anywhere;
}
.inspector-tabs { display: flex; align-items: stretch; flex: none; padding: 0 10px; border-bottom: 1px solid var(--color-border-2); }
.inspector-tabs button {
  min-height: 39px; padding: 0 9px; border: 0; border-bottom: 2px solid transparent; cursor: pointer;
  font: inherit; color: var(--color-text-2); background: transparent; white-space: nowrap;
}
.inspector-tabs button[aria-selected='true'] { border-bottom-color: rgb(var(--primary-6)); color: rgb(var(--primary-6)); font-weight: 600; }
.inspector-tabs button:focus-visible, .inspector-link:focus-visible { outline: 2px solid rgb(var(--primary-6)); outline-offset: -2px; }
.inspector-body { flex: 1; min-height: 0; overflow-y: auto; padding: 0 13px 10px; }
.inspector-body section { padding: 13px 0; }
.inspector-body section + section { border-top: 1px solid var(--color-border-2); }
.inspector-body h2 { margin: 5px 0 8px; font-size: 15px; font-weight: 650; line-height: 1.45; }
.inspector-body h3 { margin: 0 0 8px; font-size: 13px; font-weight: 650; }
.inspector-body p { margin: 5px 0 8px; line-height: 1.55; }
.inspector-body > p { margin-top: 14px; }
.inspector-kind { display: flex; align-items: center; gap: 6px; color: var(--color-text-3); font-size: 12px; }
.inspector-kind i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.inspector-kv { margin: 0 0 3px; display: grid; grid-template-columns: auto 1fr; align-items: baseline; gap: 5px 10px; }
.inspector-kv dd { margin: 0; min-width: 0; }
.inspector-kv dt, .inspector-note, .inspector-body small { color: var(--color-text-3); font-size: 12px; font-weight: 400; }
.inspector-actions { display: flex; flex-wrap: wrap; gap: 4px 6px; margin: 7px 0; }
.inspector-actions :deep(.arco-btn-secondary), .inspector-body section > :deep(.arco-btn-secondary) { background: transparent; border: 1px solid var(--color-border-2); }
.inspector-link {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px; min-width: 0; max-width: 100%; padding: 0;
  color: rgb(var(--primary-6)); border: 0; background: transparent; font: inherit; line-height: 1.45; text-align: left; cursor: pointer;
  overflow-wrap: anywhere;
}
.inspector-link:hover { text-decoration: underline; text-underline-offset: 2px; }
.inspector-list { padding: 0; margin: 0; list-style: none; }
.inspector-list li { padding: 7px 0; min-width: 0; line-height: 1.45; }
.inspector-list li:first-child { padding-top: 0; }
.inspector-list li + li { border-top: 1px solid var(--color-border-2); }
.inspector-list li small { display: block; }
.technical-detail { padding: 4px 0; color: var(--color-text-2); font-size: 12px; line-height: 1.5; }
.technical-detail[open] summary { margin-bottom: 4px; }
.technical-detail summary, .source-item summary { color: var(--color-text-2); cursor: pointer; }
.technical-detail > code, .technical-detail > span, .source-item > code, .source-item > small { display: block; }
.source-item { padding: 5px 0; line-height: 1.5; }
.source-item > a { color: rgb(var(--primary-6)); }
.source-item + .source-item { border-top: 1px solid var(--color-border-2); }
.source-item p { margin: 4px 0; }
.binding-row { display: grid; min-width: 0; gap: 2px; padding: 4px 0; }
@media (max-width: 840px) { .working-inspector { height: auto; } }
</style>
