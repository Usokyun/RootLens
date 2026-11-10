<script setup lang="ts">
import { computed } from 'vue'
import type { RecordValue } from '@/api/workbench'
import { clone, friendly, operatorLabels, record, text, texts } from '@/services/presentation'
import { conditionIssues, featureLabel, operandFor, operatorsFor, type FeatureChoice } from '@/services/feature-authoring'
const props = defineProps<{ condition: RecordValue; features: FeatureChoice[] }>()
const emit = defineEmits<{ update: [condition:RecordValue] }>()
const feature = computed(() => props.features.find((row) => row.feature_id === props.condition.feature_id))
const operand = computed(() => record(props.condition.operand))
const operators = computed(() => feature.value?.allowed_operators ?? operatorsFor(feature.value))
const issues = computed(() => conditionIssues(props.condition,feature.value))
const finite = computed(() => Array.isArray(feature.value?.allowed_values) ? feature.value.allowed_values : null)
function setFeature(id:string) {
  const selected = props.features.find((row) => row.feature_id === id); if (!selected) return
  const op = (selected.allowed_operators ?? operatorsFor(selected))[0] ?? ''
  emit('update',{...clone(props.condition),feature_id:id,op,operand:operandFor(selected,op)})
}
function setOperator(op:string) { if (feature.value) emit('update',{...clone(props.condition),op,operand:operandFor(feature.value,op)}) }
function setValue(value:unknown) {
  const next = clone(props.condition), field = record(next.operand)
  if (field.kind === 'number') field.number = value === '' ? null : Number(value)
  else if (field.kind === 'boolean') field.boolean = value === 'true'
  else if (field.kind === 'candidate_set') field.items = Array.isArray(value) ? value : String(value).split(/[\n,，;；]+/).map(v=>v.trim()).filter(Boolean)
  else field.category = value
  next.operand = field; emit('update',next)
}
function toggle(value:string) { const selected = texts(operand.value.items); setValue(selected.includes(value) ? selected.filter(item=>item!==value) : [...selected,value]) }
</script>
<template>
  <div class="predicate-fields">
    <label class="field">测量特征<select aria-label="测量特征" :value="condition.feature_id" @change="setFeature(($event.target as HTMLSelectElement).value)"><option v-if="!feature" value="" disabled>选择测量特征</option><option v-for="choice in features" :key="choice.feature_id" :value="choice.feature_id">{{ featureLabel(choice) }}{{ !choice.producerDeclared ? '（图谱已有定义）' : '' }}</option></select><small v-if="feature?.requires_reference">需要与本次任务一致的正常参考。</small></label>
    <template v-if="feature"><label class="field">判断方式<select aria-label="判断方式" :value="condition.op" :disabled="!operators.length" @change="setOperator(($event.target as HTMLSelectElement).value)"><option v-if="!operators.includes(text(condition.op))" :value="text(condition.op)" disabled>{{ operatorLabels[text(condition.op)] || condition.op }}（当前类型不支持）</option><option v-for="op in operators" :key="op" :value="op">{{ operatorLabels[op] }}</option></select></label>
    <label v-if="operand.kind === 'boolean'" class="field">条件值<select aria-label="条件值" :value="String(operand.boolean)" @change="setValue(($event.target as HTMLSelectElement).value)"><option value="true">是</option><option value="false">否</option></select></label>
    <label v-else-if="operand.kind === 'number'" class="field">条件值<input aria-label="条件值" :value="operand.number ?? ''" type="number" step="any" required @input="setValue(($event.target as HTMLInputElement).value)" /><small>单位：{{ feature?.unit || '未声明' }}</small></label>
    <fieldset v-else-if="operand.kind === 'candidate_set' && finite" class="finite-values"><legend>条件值（可多选）</legend><label v-for="value in finite" :key="value" class="checkbox-label"><input type="checkbox" :checked="texts(operand.items).includes(value)" @change="toggle(value)" />{{ friendly(value) }}<code v-if="friendly(value) !== value">{{ value }}</code></label></fieldset>
    <label v-else-if="finite" class="field">条件值<select aria-label="条件值" :value="operand.category" required @change="setValue(($event.target as HTMLSelectElement).value)"><option value="" disabled>选择目录中的值</option><option v-if="operand.category && !finite.includes(text(operand.category))" :value="text(operand.category)" disabled>{{ operand.category }}（不在当前目录）</option><option v-for="value in finite" :key="value" :value="value">{{ friendly(value) }}{{ friendly(value) !== value ? ` · ${value}` : '' }}</option></select></label>
    <label v-else class="field">条件值<textarea v-if="operand.kind === 'candidate_set'" aria-label="条件值" :value="texts(operand.items).join('\n')" rows="2" placeholder="每行一个词汇" @input="setValue(($event.target as HTMLTextAreaElement).value)" /><input v-else aria-label="条件值" :value="operand.category" required @input="setValue(($event.target as HTMLInputElement).value)" /><small>{{ feature?.allowed_values === null ? '开放词汇：仅接受实际观测或明确等价映射，不将相近外观自动当作同义。' : '此特征尚无已加载的有限值目录，请先检查后端能力定义。' }}</small></label>
    <p v-for="issue in issues" :key="issue" class="error-text predicate-issue">{{ issue }}</p>
    <details v-if="feature" class="feature-definition"><summary>特征定义与能力边界</summary><p>{{ feature.definition }}</p><dl><dt>值域</dt><dd>{{ finite ? '后端有限目录' : feature.allowed_values === null ? '开放词汇' : '目录未加载' }}</dd><dt>稳定特征 ID</dt><dd><code>{{ feature.feature_id }}</code></dd></dl></details></template>
  </div>
</template>
<style scoped>
.predicate-fields{display:flex;flex-direction:column;gap:16px;}.finite-values{border:1px solid var(--border);border-radius:6px;padding:12px;display:flex;flex-direction:column;gap:9px;margin:0;}.finite-values legend{font-size:12px;color:#6d7d96;padding:0 4px;}.finite-values code{color:#8e9db2;font-size:10px;margin-left:auto;}.predicate-issue{font-size:12px;margin:0;}.feature-definition{font-size:12px;color:#8292aa;}.feature-definition summary{cursor:pointer;}.feature-definition p{font-size:12px;line-height:1.8;margin:10px 0;}.feature-definition dl{display:grid;grid-template-columns:82px 1fr;gap:8px;font-size:11px;}.feature-definition dd{margin:0;overflow-wrap:anywhere;}
</style>
