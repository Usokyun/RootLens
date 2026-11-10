<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { queryLabel, selectTraceCandidate, traceOutcome, traceQueryIndex, traceRecord, traceRows, traceTruth, traceValue, unifiedQueries } from '@/services/unified-reasoning-display'

const props = defineProps<{ metadata?: unknown; candidateId?: string | null; queryId?: unknown }>()
const visible = ref(false)
const queryIndex = ref(0)
const chosenId = ref<string | null>(null)
const activeTab = ref('comparison')
const factFilter = ref('all')
const queries = computed(() => unifiedQueries(props.metadata))
const query = computed(() => queries.value[queryIndex.value] ?? queries.value[0])
const result = computed(() => query.value?.result ?? {})
const candidates = computed(() => traceRows(result.value.candidate_evaluations))
const candidate = computed(() => selectTraceCandidate(result.value, chosenId.value ?? props.candidateId))
const costs = computed(() => traceRecord(candidate.value?.scoring_details))
const policy = computed(() => traceRecord(result.value.execution_policy))
const facts = computed(() => traceRows(result.value.grounded_facts).filter((f) =>
  factFilter.value === 'all' || (factFilter.value === 'true' ? f.value === true : factFilter.value === 'false' ? f.value === false : f.value === null)))
const checks = computed(() => traceRows(candidate.value?.expectation_checks))
const paths = computed(() => traceRows(result.value.top_k_paths).filter((p) => p.candidate_id === candidate.value?.candidate_id || p.target_entity_id === candidate.value?.candidate_id || (Array.isArray(p.nodes) && p.nodes.includes(candidate.value?.candidate_id))))
const frameTask = computed(() => traceRecord(query.value?.frame.task))
const observations = computed(() => traceRows(query.value?.frame.observations))
const proof = computed(() => traceRecord(result.value.proof_graph))
watch([() => props.metadata, () => props.queryId], () => {
  queryIndex.value = traceQueryIndex(queries.value, props.queryId)
  chosenId.value = null
}, { immediate: true })
watch(() => props.candidateId, () => { chosenId.value = null })
watch(queryIndex, () => { chosenId.value = null })
function json(value: unknown) { return JSON.stringify(value, null, 2) }
function pathLabel(path: Record<string, unknown>) {
  const nodes = Array.isArray(path.nodes) ? path.nodes : []
  const fact = traceRows(result.value.grounded_facts).find((f) => f.predicate_id === nodes[0])
  return `${traceRecord(fact?.predicate_check).feature_id ?? nodes[0] ?? '观测'} → 联合条件 → ${candidate.value?.candidate_name ?? '候选'}`
}
</script>

<template>
  <template v-if="queries.length">
    <a-button size="small" type="outline" @click="visible = true">推理依据</a-button>
    <a-drawer v-model:visible="visible" :width="940" :footer="false" title="观测 → 条件 → 候选" class="unified-reasoning-drawer">
      <div class="unified-trace">
        <div class="trace-topline">
          <a-select v-model="queryIndex" aria-label="聚焦推理问题" :style="{ width: '320px' }">
            <a-option v-for="(q, i) in queries" :key="q.id" :value="i">{{ queryLabel(q.frame, i) }}</a-option>
          </a-select>
          <a-tag :color="result.outcome === 'ambiguous' ? 'orange' : result.outcome === 'supported' ? 'green' : 'gray'">{{ traceOutcome(result.outcome) }}</a-tag>
        </div>
        <p class="trace-context">{{ frameTask.target_role === 'pattern_family' ? '图案家族比较' : '候选机制比较' }} · {{ traceValue(frameTask.focus_subject_ids) }} · {{ observations.length }} 条原始观测</p>
        <p class="trace-formula">J = U + {{ traceValue(policy.conflict_weight) }} × C + {{ traceValue(policy.assumption_weight) }} × A；score = −J。U、C 使用当前问题固定的观测分母，同源事实不重复投票。</p>
        <a-tabs v-model:active-key="activeTab">
          <a-tab-pane key="comparison" title="候选与代价">
            <div class="trace-scroll">
              <table class="trace-table candidate-table">
                <thead><tr><th>候选</th><th>U 未解释</th><th>C 冲突</th><th>A 假设</th><th>J / score</th><th>状态</th></tr></thead>
                <tbody><tr v-for="row in candidates" :key="String(row.candidate_id)" :class="{ selected: row.candidate_id === candidate?.candidate_id }">
                  <td><button class="candidate-select" @click="chosenId = String(row.candidate_id)">{{ row.candidate_name }}</button></td>
                  <td>{{ traceValue(traceRecord(row.scoring_details).unexplained_loss) }}</td><td>{{ traceValue(traceRecord(row.scoring_details).conflict_loss) }}</td>
                  <td>{{ traceValue(traceRecord(row.scoring_details).assumption_cost) }}</td><td>{{ traceValue(traceRecord(row.scoring_details).total_cost) }} / {{ traceValue(row.score) }}</td>
                  <td>{{ row.eligible_for_ranking ? '有完整支持' : row.status === 'ruled_out' ? '必要条件冲突' : row.status === 'insufficient_evidence' ? '证据不足' : '未匹配' }}</td>
                </tr></tbody>
              </table>
            </div>
            <a-empty v-if="!candidates.length">无可评价候选；请查看缺失观测和未评估项。</a-empty>
            <template v-if="candidate">
              <h3>{{ candidate.candidate_name }}</h3>
              <p>总解释代价 {{ traceValue(costs.total_cost) }}；支持观测 {{ traceValue(candidate.support_obs_ids) }}；反证观测 {{ traceValue(candidate.counter_obs_ids) }}</p>
              <h4>实际执行的联合条件</h4>
              <details v-for="check in checks" :key="String(check.rule_id)" class="trace-check">
                <summary><a-tag :color="check.observed_value === true ? 'green' : check.observed_value === false ? 'red' : 'gray'">{{ traceTruth(check.observed_value) }}</a-tag> {{ check.mode }} · {{ check.pattern_id }}</summary>
                <dl><dt>期待规则</dt><dd>{{ check.rule_id }}</dd><dt>选中分支 / scope</dt><dd>{{ traceTruth(check.selected_signature_value) }} / {{ check.scope_valid ? '可联合' : '不可联合' }}</dd><dt>联合谓词</dt><dd>{{ traceValue(check.predicate_ids) }}</dd><dt>覆盖事实</dt><dd>{{ traceValue(check.covered_fact_ids) }}</dd><dt>冲突事实</dt><dd>{{ traceValue(check.conflicting_fact_ids) }}</dd><dt>缺失谓词</dt><dd>{{ traceValue(check.missing_predicate_ids) }}</dd></dl>
              </details>
              <details class="trace-check"><summary>代价分母与未解释事实</summary><pre>{{ json({ groups: costs.groups, unexplained_fact_ids: candidate.unexplained_fact_ids }) }}</pre></details>
            </template>
          </a-tab-pane>
          <a-tab-pane key="facts" :title="`观测与匹配（${traceRows(result.grounded_facts).length}）`">
            <a-radio-group v-model="factFilter" type="button"><a-radio value="all">全部</a-radio><a-radio value="true">满足</a-radio><a-radio value="false">不满足</a-radio><a-radio value="unknown">未知 / 缺测</a-radio></a-radio-group>
            <article v-for="fact in facts" :key="String(fact.fact_id)" class="trace-fact">
              <header><strong>{{ traceRecord(fact.predicate_check).feature_id }}</strong><a-tag :color="fact.value === true ? 'green' : fact.value === false ? 'red' : 'gray'">{{ traceTruth(fact.value) }}</a-tag></header>
              <p><b>实测</b> {{ traceValue(fact.actual_values) }} <span class="trace-muted">→</span> <b>{{ traceRecord(fact.predicate_check).op }}</b> {{ traceValue(traceRecord(fact.predicate_check).operand) }}</p>
              <p class="trace-muted">主体 {{ fact.subject_id ?? '未绑定' }} · scope {{ fact.scope_id ?? '未绑定' }} · {{ fact.status }}</p>
              <details><summary>观测来源与绑定</summary><dl><dt>事实 ID</dt><dd>{{ fact.fact_id }}</dd><dt>原始观测</dt><dd>{{ traceValue(fact.source_obs_ids) }}</dd><dt>使用的值绑定</dt><dd>{{ traceValue(fact.applied_value_binding_ids) }}</dd><dt>说明</dt><dd>{{ fact.reason || '按注册类型、单位和作用域执行比较' }}</dd></dl></details>
            </article>
            <details class="trace-check"><summary>未参与推理的观测（{{ traceRows(result.unused_observations).length }}）与未评估候选</summary><pre>{{ json({ unused_observations: result.unused_observations, unassessed_candidates: result.unassessed_candidates }) }}</pre></details>
          </a-tab-pane>
          <a-tab-pane key="proof" title="路径与联合证明">
            <p>每条展示路径是联合证明的一部分；须同时满足其 required_joint_fact_ids，而非任意一条边即可成立。</p>
            <details v-for="(path, index) in paths" :key="String(path.path_id ?? index)" class="trace-check">
              <summary>路径 {{ index + 1 }} · {{ pathLabel(path) }}</summary>
              <pre>{{ json({ nodes: path.nodes, joint_proof_id: path.joint_proof_id, required_joint_fact_ids: path.required_joint_fact_ids, source_edge_views: path.source_edge_views }) }}</pre>
            </details>
            <details class="trace-check"><summary>完整证明 DAG（{{ traceRows(proof.nodes).length }} 节点 / {{ traceRows(proof.edges).length }} 边）</summary><pre>{{ json(proof) }}</pre></details>
            <details class="trace-check"><summary>原始强类型 Evidence JSON</summary><pre>{{ json(query?.frame) }}</pre></details>
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-drawer>
  </template>
</template>

<style scoped>
.unified-trace { font-size: 14px; line-height: 1.65; }
.trace-topline, .trace-fact header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.trace-context, .trace-muted { color: var(--color-text-3); }
.trace-formula { background: var(--color-fill-1); border-radius: 6px; padding: 12px 16px; }
.trace-scroll { overflow-x: auto; }
.trace-table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
.trace-table th, .trace-table td { padding: 10px 8px; text-align: left; border-bottom: 1px solid var(--color-border-2); }
.trace-table th:not(:first-child), .trace-table td:not(:first-child) { white-space: nowrap; }
.trace-table .selected { background: var(--color-primary-light-1); }
.candidate-select { border: 0; background: none; color: rgb(var(--primary-6)); text-align: left; cursor: pointer; font: inherit; }
.trace-fact { border-bottom: 1px solid var(--color-border-2); padding: 16px 0; }
.trace-fact p { margin: 8px 0; }
.trace-check { margin: 12px 0; padding: 12px; background: var(--color-fill-1); border-radius: 6px; }
summary { cursor: pointer; overflow-wrap: anywhere; }
dl { display: grid; grid-template-columns: 135px minmax(0, 1fr); gap: 8px 16px; }
dt { color: var(--color-text-3); }
dd { margin: 0; overflow-wrap: anywhere; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; max-height: 500px; overflow: auto; }
</style>
