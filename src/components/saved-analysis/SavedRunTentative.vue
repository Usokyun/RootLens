<script setup lang="ts">
import { IconInfoCircle, IconPushpin } from '@arco-design/web-vue/es/icon'
import { computed } from 'vue'
import type { SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { savedTentativeCandidates, traceRecord, traceRows, traceValue, type TraceRecord } from '@/services/unified-reasoning-display'
import { factReason, observationChannel, observationScope, predicateLabel, scopeLabel, strings, text, valueLabel } from './presentation'
import SavedRunPanel from './SavedRunPanel.vue'

const props = defineProps<{ frame: SavedAnalysisFrame; openFirst: boolean; activeId?: string }>()
const emit = defineEmits<{ observation: [candidateId: string, obsId: string] }>()
const candidates = computed(() => savedTentativeCandidates(props.frame.result))
const initialOpenId = computed(() => props.activeId || (props.openFirst ? candidates.value[0]?.candidate_id : ''))
const joinedScope: Record<string, string> = {
  same_subject_same_scope: '同一主体和范围',
  same_event_same_window: '同一事件和窗口',
  same_subject_parent_scope: '同一主体和父范围',
  same_wafer_parent_scope: '同一晶圆父范围',
}
const stateLabels: Record<string, { label: string; color: string }> = {
  supported: { label: '符合', color: 'green' },
  refuted: { label: '分支反证', color: 'red' },
  conflicting: { label: '观测相互矛盾', color: 'red' },
  unknown: { label: '缺项 / 未核验', color: 'orange' },
}
const scoreFields = [
  ['未覆盖 U', 'unexplained_loss'], ['分支冲突 C', 'conflict_loss'],
  ['假设 A', 'assumption_cost'], ['待验证代价 J', 'total_cost'],
] as const
const unknownReasons: Record<string, string> = {
  observation_not_available: '未保存可用实测。', feature_type_or_unit_mismatch: '实测类型或单位不匹配。',
  incompatible_normal_reference: '没有与本次任务一致的参考。',
}
function linkedObservations(check: TraceRecord) {
  return ['support_obs_ids', 'counter_obs_ids', 'unknown_obs_ids'].flatMap(field => strings(check[field]).flatMap(id => {
    const observation = props.frame.observationsById.get(id)
    return observation ? [{ id, value: valueLabel(observation.value), channel: observationChannel(props.frame, observation),
      scope: scopeLabel(observationScope(props.frame, observation), props.frame.label) }] : []
  }))
}
function state(check: TraceRecord) {
  return stateLabels[text(check.status)] ?? { label: '未保存真值', color: 'gray' }
}
</script>

<template>
  <SavedRunPanel v-if="candidates.length" title="待验证" :icon="IconInfoCircle">
    <template #heading><a-tag size="small" color="orange">{{ candidates.length }} 项</a-tag></template>
    <div class="saved-run-stack">
      <p class="saved-run-note tentative-boundary">同一保存分支有部分实测支持，但未形成完整证明。分支反证不等于推翻该原因；待验证代价不与完整榜混排。</p>
      <details v-for="row in candidates" :key="row.candidate_id" class="tentative-candidate"
        :open="initialOpenId === row.candidate_id" :data-tentative-candidate-id="row.candidate_id">
        <summary>
          <strong>{{ row.candidate_name || row.candidate_id }}</strong>
          <small>{{ row.support_measurement_count }} 项实测支持 · J = {{ traceValue(traceRecord(row.scoring_details).total_cost) }}</small>
        </summary>
        <div class="tentative-candidate__body">
          <p class="saved-run-note">{{ row.pattern_label || row.pattern_id }}<template v-if="row.scope_join"> · {{ joinedScope[text(row.scope_join)] || row.scope_join }}</template></p>
          <ul class="tentative-checks" aria-label="待验证分支条件">
            <li v-for="check in traceRows(row.condition_checks)" :key="text(check.predicate_id)" :data-tentative-predicate-id="check.predicate_id">
              <div class="saved-run-row saved-run-wrap">
                <strong>{{ predicateLabel(check.predicate_check, text(check.label) || text(check.predicate_id)) }}</strong>
                <a-tag size="small" :color="state(check).color">{{ state(check).label }}</a-tag>
              </div>
              <div v-if="check.role === 'presence_gate' || check.role === 'context'" class="saved-run-note">{{ check.role === 'presence_gate' ? '前置门控' : '上下文' }} · 不计入诊断量</div>
              <div v-else-if="check.status === 'supported' && check.counts_toward_support === false" class="saved-run-note">同一诊断量有反证，不计入支持数。</div>
              <div v-if="check.status === 'unknown'" class="saved-run-note">{{ strings(check.unknown_reasons).map(reason => unknownReasons[reason] ?? factReason(reason)).join(' · ') || '没有可核验的实测。' }}</div>
              <div v-if="linkedObservations(check).length" class="saved-run-row saved-run-wrap">
                <a-button v-for="obs in linkedObservations(check)" :key="obs.id" type="text" size="mini"
                  :data-tentative-obs-id="obs.id" :title="[obs.channel, obs.scope].filter(Boolean).join(' · ')" @click="emit('observation', row.candidate_id, obs.id)">
                  <IconPushpin /> {{ check.status === 'unknown' ? '查看记录' : '定位观测' }} · {{ obs.value }}
                </a-button>
              </div>
            </li>
          </ul>
          <div class="saved-run-scores tentative-scores">
            <div v-for="[label, key] in scoreFields" :key="key"><span>{{ label }}</span><strong>{{ traceValue(traceRecord(row.scoring_details)[key]) }}</strong></div>
          </div>
          <p class="saved-run-note">J = U + {{ traceValue(traceRecord(row.scoring_details).conflict_weight) }} × C + {{ traceValue(traceRecord(row.scoring_details).assumption_weight) }} × A。U 和 C 分别取各依赖组的未覆盖占比、实测反证占比的平均；同一诊断量只计一次，缺项不计为反证。</p>
          <div class="saved-run-table-wrap">
            <table class="saved-run-table tentative-groups" aria-label="待验证代价分母与分子">
              <thead><tr><th scope="col">依赖组</th><th scope="col">可判实测</th><th scope="col">支持</th><th scope="col">未覆盖</th><th scope="col">反证</th></tr></thead>
              <tbody><tr v-for="group in traceRows(traceRecord(row.scoring_details).groups)" :key="text(group.group_id)">
                <td>{{ strings(group.dependency_group_ids).join(' · ') || group.group_id }}</td>
                <td>{{ group.observed_quantity_count }}</td><td>{{ group.supported_quantity_count }}</td>
                <td>{{ group.uncovered_quantity_count }}</td><td>{{ group.conflicting_quantity_count }}</td>
              </tr></tbody>
            </table>
          </div>
          <details class="saved-run-disclosure"><summary>规则与定义标识</summary>
            <dl class="saved-run-kv saved-run-kv--mono"><div><dt>期待规则</dt><dd>{{ row.rule_id }}</dd></div><div><dt>现象定义</dt><dd>{{ row.definition_id }}</dd></div></dl>
          </details>
        </div>
      </details>
    </div>
  </SavedRunPanel>
</template>

<style scoped>
.tentative-boundary { margin: 0; }
.tentative-candidate { min-width: 0; border: 1px solid var(--sr-line); border-radius: 4px; }
.tentative-candidate > summary { padding: 8px 10px; cursor: pointer; line-height: 1.6; }
.tentative-candidate > summary strong { color: #1c3c59; }
.tentative-candidate > summary small { display: inline-block; margin-left: 9px; color: var(--sr-muted); font-variant-numeric: tabular-nums; }
.tentative-candidate[open] > summary { background: #f7f9fc; border-bottom: 1px solid var(--sr-line); }
.tentative-candidate__body { min-width: 0; padding: 0 10px 9px; }
.tentative-checks { list-style: none; padding: 0; margin: 6px 0 9px; }
.tentative-checks li { padding: 6px 0; border-bottom: 1px solid var(--sr-line); }
.tentative-checks li:last-child { border-bottom: 0; }
.tentative-checks li > .saved-run-note { margin-top: 3px; }
.tentative-scores { margin-top: 3px; }
.tentative-groups td, .tentative-groups th { font-variant-numeric: tabular-nums; }
</style>
