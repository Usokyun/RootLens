<script setup lang="ts">
import { IconPushpin, IconRelation } from '@arco-design/web-vue/es/icon'
import { computed } from 'vue'
import type { SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { traceRecord } from '@/services/unified-reasoning-display'
import { channelLabel, factReason, number, observationChannel, pathForFact, predicateLabel, savedFacts, strings, text, truthColor, truthLabel, valueLabel, type PathFocus, type SavedCondition } from './presentation'

const props = defineProps<{ expression: unknown; condition: SavedCondition; frame: SavedAnalysisFrame; candidateId: string; factId: string }>()
const emit = defineEmits<{ graph: [focus: PathFocus]; observation: [id: string, focus?: PathFocus] }>()
const op = computed(() => {
  const expression = traceRecord(props.expression)
  if (Array.isArray(expression.all)) return { label: '全部条件', children: expression.all }
  if (Array.isArray(expression.any)) return { label: '任一条件', children: expression.any }
  const threshold = traceRecord(expression.at_least)
  const count = number(threshold.count)
  return count !== null && Array.isArray(threshold.of) ? { label: `至少 ${count} 项`, children: threshold.of } : null
})
const predicateId = computed(() => text(props.expression))
const facts = computed(() => {
  const id = predicateId.value
  if (!id) return []
  const used = props.condition.predicates.includes(id)
  const source = used ? (props.condition.factsByPredicate.get(id) ?? []) : savedFacts(props.frame).filter(fact => fact.predicate_id === id)
  return source.map(fact => {
    const observed = strings(fact.source_obs_ids).filter(id => props.frame.observationsById.has(id))
    const channels = [...new Set(observed.flatMap(id => {
      const obs = props.frame.observationsById.get(id)!
      const subject = props.frame.frame.subjects?.find(subject => subject.subject_id === obs.subject_id)
      const channel = subject?.kind === 'variable' ? observationChannel(props.frame, obs) : ''
      return channel ? [channelLabel(channel)] : []
    }))]
    return { fact, used, observed, channels, focus: used ? pathForFact(props.frame, props.candidateId, fact) : null,
      actual: Array.isArray(fact.actual_values) ? fact.actual_values.map(valueLabel).join('、') : '' }
  })
})
function locate(id: string, focus: PathFocus | null) { emit('observation', id, focus?.obsId === id ? focus : undefined) }
</script>

<template>
  <li v-if="op" class="saved-run-expression">
    <span class="saved-run-expression-label">{{ op.label }}</span>
    <ul class="saved-run-tree-branch">
      <SavedRunProofExpr v-for="(child, index) in op.children" :key="index" :expression="child" :condition="condition" :frame="frame" :candidate-id="candidateId" :fact-id="factId"
        @graph="focus => emit('graph', focus)" @observation="(id, link) => emit('observation', id, link)" />
    </ul>
  </li>
  <template v-else-if="facts.length">
    <li v-for="{ fact, focus, observed, channels, actual, used } in facts" :key="text(fact.fact_id)" class="saved-run-proof-fact" :class="{ 'is-selected': used && factId && factId === fact.fact_id }" :data-fact-id="used ? fact.fact_id : undefined">
      <div class="saved-run-row saved-run-wrap">
        <strong><template v-if="channels.length">{{ channels.join('、') }} · </template>{{ predicateLabel(fact.predicate_check, text(fact.display_name) || predicateId) }}</strong>
        <a-tag size="small" :color="truthColor(fact.value)">{{ truthLabel(fact.value) }}</a-tag>
        <a-tag v-if="!used" size="small" color="gray">未用于此证明</a-tag>
      </div>
      <p class="saved-run-note">{{ actual ? `实际 ${actual}` : '无适用的保存实测值' }}<span v-if="factReason(fact.reason)"> · {{ factReason(fact.reason) }}</span><span v-if="facts.length > 1"> · {{ [fact.subject_id, fact.scope_id].filter(Boolean).join(' / ') }}</span></p>
      <div v-if="used && (observed.length || focus)" class="saved-run-row saved-run-wrap saved-run-proof-actions">
        <a-button v-for="(id, index) in observed" :key="id" size="mini" type="text" :data-observation-id="id" @click="locate(id, focus)"><IconPushpin /> {{ observed.length > 1 ? `定位观测 ${index + 1}` : '定位观测' }}</a-button>
        <a-button v-if="focus" size="mini" type="text" :data-source-edge-id="focus.edgeId" :data-path-id="focus.pathId" @click="emit('graph', focus)"><IconRelation /> {{ focus.edgeId ? '在图中高亮' : '查看关联路径' }}</a-button>
      </div>
    </li>
  </template>
  <li v-else-if="predicateId" class="saved-run-muted">{{ predicateId }} · 未保存此候选分支的核验</li>
  <li v-else class="saved-run-muted">此表达式未保存可读的结构。</li>
</template>
