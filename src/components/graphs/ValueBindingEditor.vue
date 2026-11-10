<script setup lang="ts">
import { computed } from 'vue'
import { IconDelete, IconFile } from '@arco-design/web-vue/es/icon'
import type { RecordValue } from '@/api/workbench'
import { friendly, materialLocator, text, texts } from '@/services/presentation'
import { canonicalSuggestions, categoricalFeatures, featureLabel, updateBindingField, valueBindingIssues, type FeatureChoice } from '@/services/feature-authoring'
const props = defineProps<{ binding:RecordValue; features:FeatureChoice[]; knowledge:RecordValue }>()
const emit = defineEmits<{ update:[binding:RecordValue]; remove:[] }>()
const choices = computed(() => categoricalFeatures(props.features))
const feature = computed(() => choices.value.find((row) => row.feature_id === props.binding.feature_id))
const finite = computed(() => Array.isArray(feature.value?.allowed_values) ? feature.value.allowed_values : null)
const suggestions = computed(() => canonicalSuggestions(props.knowledge,props.binding.feature_id))
const issues = computed(() => valueBindingIssues(props.binding,props.features,props.knowledge))
const sources = computed(() => Array.isArray(props.knowledge.source_assertions) ? props.knowledge.source_assertions as RecordValue[] : [])
function set(field:string,value:unknown) { emit('update',updateBindingField(props.binding,field,value)) }
function toggleSource(id:string) { const selected=texts(props.binding.source_assertion_ids);set('source_assertion_ids',selected.includes(id)?selected.filter(value=>value!==id):[...selected,id]) }
</script>
<template>
  <div class="value-binding-editor">
    <div class="binding-purpose"><strong>等价词汇</strong><p>把不同表达绑定为同一观测语义，不补充新的观测事实。通用玻璃缺损不能映射成“已确认瓶口”部位。</p></div>
    <label class="field">对应测量特征<select aria-label="对应测量特征" :value="binding.feature_id" @change="set('feature_id',($event.target as HTMLSelectElement).value)"><option v-for="choice in choices" :key="choice.feature_id" :value="choice.feature_id">{{ featureLabel(choice) }}</option></select></label>
    <label class="field">外部词汇<input aria-label="外部词汇" :value="binding.external_value" required placeholder="例如：来自既有测量的另一种同义表达" @input="set('external_value',($event.target as HTMLInputElement).value)" /></label>
    <label class="field">等价的标准词汇<select v-if="finite" aria-label="等价的标准词汇" :value="binding.canonical_value" required @change="set('canonical_value',($event.target as HTMLSelectElement).value)"><option value="" disabled>选择目录中的标准值</option><option v-if="binding.canonical_value && !finite.includes(text(binding.canonical_value))" :value="text(binding.canonical_value)" disabled>{{ binding.canonical_value }}（不在目录）</option><option v-for="value in finite" :key="value" :value="value">{{ friendly(value) }}{{ friendly(value) !== value ? ` · ${value}` : '' }}</option></select><input v-else aria-label="等价的标准词汇" :value="binding.canonical_value" :list="`canonical-${binding.binding_id}`" required placeholder="选择图谱已有词汇，或填写明确的等价词汇" @input="set('canonical_value',($event.target as HTMLInputElement).value)" /><datalist v-if="!finite" :id="`canonical-${binding.binding_id}`"><option v-for="value in suggestions" :key="value" :value="value">{{ friendly(value) }}</option></datalist><small>{{ finite ? '标准值必须来自后端能力目录。' : '开放词汇不会自动匹配；请依据下方来源明确说明等价关系。' }}</small></label>
    <fieldset class="binding-sources"><legend>等价关系的依据（至少一项）</legend><div class="binding-source-options"><article v-for="(source,index) in sources" :key="text(source.assertion_id)"><label class="checkbox-label"><input type="checkbox" :checked="texts(binding.source_assertion_ids).includes(text(source.assertion_id))" @change="toggleSource(text(source.assertion_id))" /><span>{{ friendly(source.origin,'来源依据') }} · {{ source.locator ? materialLocator(source.locator) : `来源 ${index + 1}` }}</span></label><details><summary><IconFile /> 查看原断言与定位</summary><p>{{ source.text }}</p><small v-if="source.source_id">来源：{{ source.source_id }}<br />单元：{{ source.source_unit_id || '未记录' }}</small></details></article><p v-if="!sources.length" class="muted">当前图谱没有可选择的来源依据，不能保存无来源的映射。</p></div></fieldset>
    <details class="binding-model"><summary>限定来源模型（高级）</summary><label class="field">模型 ID（可选）<input :value="binding.procedure_model_id || ''" aria-label="限定来源模型" @input="set('procedure_model_id',($event.target as HTMLInputElement).value || null)" /><small>留空时适用于同一特征的全部模型；填写后只作用于该实际模型。</small></label></details>
    <p v-for="issue in issues" :key="issue" class="error-text binding-issue">{{ issue }}</p>
    <button type="button" class="button button--danger button--small" @click="emit('remove')"><IconDelete />移除这条等价词汇</button><small class="muted">新增、修改或移除均在“保存修改”后生效。</small>
  </div>
</template>
<style scoped>
.value-binding-editor{display:flex;flex-direction:column;gap:17px;}.binding-purpose{padding:13px;border:1px solid #dae5f7;background:#f5f8ff;border-radius:6px;}.binding-purpose strong{font-size:13px;color:#5f7fae;}.binding-purpose p{font-size:12px;line-height:1.8;color:#8192ac;margin:7px 0 0;}.binding-sources{margin:0;padding:12px;border:1px solid var(--border);border-radius:6px;}.binding-sources legend{font-size:12px;color:#6f819d;padding:0 5px;}.binding-source-options{max-height:245px;overflow:auto;}.binding-source-options article{padding:11px 0;border-bottom:1px solid #edf0f5;}.binding-source-options article:last-child{border:0;}.binding-source-options .checkbox-label{align-items:flex-start;font-size:11px;}.binding-source-options .checkbox-label input{flex-shrink:0;margin-top:2px;}.binding-source-options details{font-size:10px;color:#8c9bb1;padding:7px 0 0 24px;}.binding-source-options summary{cursor:pointer;line-height:1.7;}.binding-source-options p{font-size:11px;line-height:1.9;color:#6e809b;margin:10px 0;}.binding-source-options small{font-size:10px;color:#93a0b4;overflow-wrap:anywhere;display:block;}.binding-model{font-size:12px;color:#8191aa;}.binding-model summary{cursor:pointer;}.binding-model .field{margin-top:12px;}.binding-issue{font-size:12px;line-height:1.7;margin:0;}
</style>
