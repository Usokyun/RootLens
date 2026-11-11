<script setup lang="ts">
import { computed } from 'vue'
import type { SavedProcessTrend } from '@/services/saved-analysis-reader'
import { traceRecord, traceValue } from '@/services/unified-reasoning-display'
import { channelLabel, number, scopeLabel } from './presentation'

const props = defineProps<{ trend: SavedProcessTrend; scope: unknown; inherited?: boolean; compact?: boolean }>()
const bounds = computed(() => ({ width: props.compact ? 262 : 620, height: props.compact ? 126 : 162, x: props.compact ? 39 : 46, y: 14 }))
const plotted = computed(() => {
  const { width, height, x, y } = bounds.value
  const values = props.trend.samples
  if (!values.length || !values.every(Number.isFinite)) return null
  let low = Infinity, high = -Infinity
  for (const value of values) { low = Math.min(low, value); high = Math.max(high, value) }
  const right = width - 16, bottom = height - 24
  const points = values.map((value, index) => {
    const px = x + index * (right - x) / Math.max(1, values.length - 1)
    const py = low === high ? (y + bottom) / 2 : bottom - (value - low) * (bottom - y) / (high - low)
    return `${px.toFixed(2)},${py.toFixed(2)}`
  }).join(' ')
  return { low, high, points, right, bottom }
})
const scope = computed(() => traceRecord(props.scope))
const channel = computed(() => channelLabel(props.trend.channel))
</script>

<template>
  <div class="saved-run-trend" :data-channel="trend.channel">
    <header class="saved-run-row saved-run-between"><strong>{{ channel }}</strong><span class="saved-run-muted">{{ scopeLabel(scope) }}</span></header>
    <svg v-if="plotted" :viewBox="`0 0 ${bounds.width} ${bounds.height}`" role="img" :aria-label="`${channel} 保存曲线`" :data-sample-count="trend.samples.length">
      <line v-for="y in [bounds.y, (bounds.y + plotted.bottom) / 2, plotted.bottom]" :key="y" :x1="bounds.x" :x2="plotted.right" :y1="y" :y2="y" class="saved-run-chart-grid" />
      <line :x1="bounds.x" :x2="bounds.x" :y1="bounds.y" :y2="plotted.bottom" class="saved-run-chart-grid" />
      <polyline :points="plotted.points" fill="none" class="saved-run-chart-line" vector-effect="non-scaling-stroke" />
      <text :x="bounds.x - 4" :y="bounds.y + 3" text-anchor="end">{{ traceValue(plotted.high) }}</text>
      <text :x="bounds.x - 4" :y="plotted.bottom + 3" text-anchor="end">{{ traceValue(plotted.low) }}</text>
      <text v-if="number(scope.sample_start) !== null" :x="bounds.x" :y="bounds.height - 8">{{ scope.sample_start }}</text>
      <text v-if="number(scope.sample_end) !== null" :x="plotted.right" :y="bounds.height - 8" text-anchor="end">{{ scope.sample_end }}</text>
    </svg>
    <p v-else class="saved-run-muted">此通道没有可绘制的保存曲线。</p>
    <div class="saved-run-row saved-run-between saved-run-muted"><span>{{ inherited ? '关联既有曲线 · 本次未提取' : '本次保存曲线' }}</span><span>{{ trend.samples.length }} 点<span v-if="number(scope.sampling_seconds) !== null"> · {{ scope.sampling_seconds }} 秒 / 样本</span></span></div>
  </div>
</template>
