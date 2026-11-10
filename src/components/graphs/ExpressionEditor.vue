<script setup lang="ts">
import { computed } from 'vue'
import { record } from '@/services/presentation'
import { IconPlus, IconClose } from '@arco-design/web-vue/es/icon'
const props = defineProps<{ modelValue: unknown; options: Array<{ id: string; label: string }>; depth?: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: unknown] }>()
const expression = computed(() => record(props.modelValue))
const mode = computed(() => expression.value.all ? 'all' : expression.value.any ? 'any' : 'at_least')
const children = computed<unknown[]>(() => Array.isArray(expression.value.all) ? expression.value.all : Array.isArray(expression.value.any) ? expression.value.any : record(expression.value.at_least).of as unknown[] ?? [])
function replace(children: unknown[], newMode = mode.value) {
  emit('update:modelValue', newMode === 'at_least' ? { at_least: { count: Math.min(Number(record(expression.value.at_least).count) || 1, Math.max(1, children.length)), of: children } } : { [newMode]: children })
}
function setChild(index: number, value: unknown) { const next = [...children.value]; next[index] = value; replace(next) }
function remove(index: number) { if (children.value.length > 1) replace(children.value.filter((_, i) => i !== index)) }
function add(group = false) {
  const next = props.options.find((o) => !children.value.includes(o.id))?.id ?? props.options[0]?.id
  if (next) replace([...children.value, group ? { all: [next] } : next])
}
</script>
<template>
  <div v-if="typeof modelValue === 'string'" class="expression-leaf"><select :value="modelValue" aria-label="条件引用" @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"><option v-for="option in options" :key="option.id" :value="option.id">{{ option.label }}</option></select></div>
  <div v-else class="expression-group" :class="{ nested: (depth ?? 0) > 0 }"><div class="expression-group__head"><select :value="mode" aria-label="联合方式" @change="replace(children, ($event.target as HTMLSelectElement).value)"><option value="all">全部满足（且）</option><option value="any">任一满足（或）</option><option value="at_least">至少满足指定项数</option></select><input v-if="mode === 'at_least'" :value="record(expression.at_least).count" type="number" min="1" :max="children.length" aria-label="至少满足数量" @input="emit('update:modelValue', { at_least: { count: Number(($event.target as HTMLInputElement).value), of: children } })" /></div><div v-for="(child, index) in children" :key="index" class="expression-row"><span class="expression-branch" /> <ExpressionEditor :model-value="child" :options="options" :depth="(depth ?? 0) + 1" @update:model-value="setChild(index, $event)" /><button type="button" class="expression-remove" :disabled="children.length <= 1" :aria-label="`移除条件 ${index + 1}`" @click="remove(index)"><IconClose /></button></div><div class="expression-actions"><button type="button" class="text-button" @click="add()"><IconPlus /> 条件</button><button v-if="(depth ?? 0) < 2" type="button" class="text-button" @click="add(true)"><IconPlus /> 条件组</button></div></div>
</template>
<style scoped>
.expression-group{padding:11px;border:1px solid var(--border);background:#fbfcfe;border-radius:7px;min-width:0;}.expression-group.nested{padding:8px;background:white;}.expression-group__head{display:flex;gap:7px;margin-bottom:12px;}.expression-group select,.expression-leaf select{font-size:13px;padding:6px 7px;border:1px solid #e0e6f0;border-radius:5px;max-width:100%;width:100%;color:#5f7090;background:white;}.expression-group__head>select{width:auto;max-width:100%;}.expression-group__head>input{width:48px;font-size:13px;border:1px solid var(--border);border-radius:5px;padding:5px;}.expression-row{display:flex;gap:5px;align-items:flex-start;margin:8px 0;min-width:0;}.expression-row>.expression-leaf,.expression-row>.expression-group{flex:1;min-width:0;}.expression-branch{height:14px;width:8px;min-width:8px;border-left:1px solid #ccd7e7;border-bottom:1px solid #ccd7e7;margin-top:2px;}.expression-remove{border:0;background:none;color:#7f8ca1;font-size:11px;padding:8px 0 0;}.expression-actions{display:flex;gap:16px;margin-top:12px;padding-left:12px;}.expression-actions .text-button{font-size:12px;}
</style>
