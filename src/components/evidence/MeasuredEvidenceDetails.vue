<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ observation?: Record<string, unknown> | null }>()
const value = computed(() => {
  const v = props.observation?.value
  return v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null
})
const isProcess = computed(() => props.observation?.value_type === 'process-measurements.v1')
const isWafer = computed(() => props.observation?.value_type === 'wafer-measurements.v1')
const channels = computed(() => Array.isArray(value.value?.channels)
  ? (value.value.channels as Array<Record<string, unknown>>).slice().sort((a,b) => Number(b.contribution)-Number(a.contribution)) : [])
const metrics = computed(() => [
  ['有效 / 失效 die', `${value.value?.valid_die_count} / ${value.value?.failed_die_count}`],
  ['失效率（排除背景）', fmt(value.value?.failure_density)],
  ['中心 / 中圈 / 边缘密度', [value.value?.center_density, value.value?.middle_density, value.value?.edge_density].map(fmt).join(' / ')],
  ['最大簇比例 / 线性程度', [value.value?.largest_component_ratio, value.value?.linearity].map(fmt).join(' / ')],
  ['分类观测 / 标注状态', `${value.value?.classifier_pattern ?? '未提供'} / ${value.value?.annotation_state}`],
])
function fmt(v: unknown): string { return typeof v === 'number' ? Number(v.toPrecision(4)).toString() : '—' }
function points(values: unknown) {
  if (!Array.isArray(values)) return ''
  const a = values.map(Number), low = Math.min(...a), range = Math.max(...a)-low || 1
  return a.map((n,i) => `${i/Math.max(a.length-1,1)*180},${34-(n-low)/range*30}`).join(' ')
}
</script>
<template>
  <section v-if="value && (isProcess || isWafer)" class="measured-details">
    <template v-if="isWafer">
      <h4>真实 die 空间测量 · 0 背景 / 1 正常 / 2 失效</h4>
      <dl><template v-for="[label, detail] in metrics" :key="label"><dt>{{ label }}</dt><dd>{{ detail }}</dd></template></dl>
    </template>
    <template v-else>
      <h4>完整窗口 · 样本 {{ value.sample_start }}–{{ value.sample_end }}</h4>
      <p>间隔 {{ value.sampling_interval_seconds }} 秒；正常参考 {{ value.normal_reference_rows }} 行。残差能量 {{ fmt(value.residual_energy) }} / 正常限 {{ fmt(value.normal_energy_limit) }}</p>
      <p class="reference">{{ value.reference_id }}</p>
      <p>趋势为原始值，各通道独立纵轴；完整保留 {{ channels.length }} 通道。图中实际使用的统计见“推理依据”。</p>
      <div class="measurement-scroll"><table>
        <thead><tr><th>通道</th><th>均值 z</th><th>标准差 z</th><th>斜率 z/样本</th><th>PCA 残差贡献</th><th>窗口趋势</th></tr></thead>
        <tbody><tr v-for="channel in channels" :key="String(channel.channel)">
          <td>{{ channel.channel }}</td><td>{{ fmt(channel.mean_z) }}</td><td>{{ fmt(channel.std_z) }}</td><td>{{ fmt(channel.slope_z) }}</td><td>{{ fmt(channel.contribution) }}</td>
          <td><svg viewBox="0 0 180 38" width="180" height="38" role="img" :aria-label="`${channel.channel} 原始窗口趋势`"><polyline :points="points(channel.samples)" fill="none" stroke="currentColor" stroke-width="1.5" /></svg></td>
        </tr></tbody>
      </table></div>
    </template>
  </section>
</template>
<style scoped>
.measured-details { margin: 16px 0; font-size: 13px; line-height: 1.6; }
h4 { margin: 8px 0; font-size: 14px; }
dl { display: grid; grid-template-columns: minmax(125px, 1fr) 1.5fr; gap: 8px 16px; }
dd { margin: 0; overflow-wrap: anywhere; }
dt, .reference { color: var(--color-text-3); overflow-wrap: anywhere; }
.measurement-scroll { max-height: 390px; overflow: auto; }
table { width: 100%; border-collapse: collapse; white-space: nowrap; }
th, td { text-align: left; padding: 7px 12px; border-bottom: 1px solid var(--color-border-2); }
th { position: sticky; top: 0; background: var(--color-bg-2); }
svg { color: rgb(var(--primary-6)); vertical-align: middle; }
</style>
