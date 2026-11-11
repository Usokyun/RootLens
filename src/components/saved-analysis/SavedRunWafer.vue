<script setup lang="ts">
import { computed } from 'vue'
import { waferZoneOverlay, type SavedWaferZone } from './wafer-zone'
const props = defineProps<{ grid: number[][]; inherited?: boolean; zone?: SavedWaferZone | null }>()
const width = computed(() => props.grid[0]?.length ?? 0)
// Only a display projection of the persisted cells; no inference or new region detection.
function cellPaths(mask?: boolean[][]) {
  const segments: string[][] = [[], [], []]
  for (const [y, row] of props.grid.entries()) {
    for (let x = 0; x < row.length;) {
      const cell = row[x]!, start = x
      if (mask && !mask[y]?.[x]) { x += 1; continue }
      while (x < row.length && row[x] === cell && (!mask || mask[y]?.[x])) x += 1
      segments[cell]?.push(`M${start} ${y}h${x - start}v1h-${x - start}Z`)
    }
  }
  return segments.map(segment => segment.join(''))
}
const paths = computed(() => cellPaths())
const overlay = computed(() => props.zone ? waferZoneOverlay(props.grid, props.zone) : null)
const highlights = computed(() => overlay.value ? cellPaths(overlay.value.cells) : null)
</script>
<template>
  <figure v-if="width" class="saved-run-wafer" :data-wafer-zone="zone?.name" :data-zone-valid="overlay?.validCount" :data-zone-failed="overlay?.failedCount">
    <svg :viewBox="`0 0 ${width} ${grid.length}`" role="img" :aria-label="`${grid.length} × ${width} 保存晶圆网格${zone ? `，高亮${zone.label}` : ''}`" shape-rendering="crispEdges">
      <path :d="paths[0]" fill="#e8edf4" />
      <g :opacity="highlights ? 0.24 : 1"><path :d="paths[1]" fill="#6aa3de" /><path :d="paths[2]" fill="#e87845" /></g>
      <g v-if="highlights"><path :d="highlights[1]" fill="#6aa3de" /><path :d="highlights[2]" fill="#e87845" /></g>
    </svg>
    <figcaption>{{ grid.length }} 行 × {{ width }} 列 · 0 背景 / 1 正常 / 2 失效<span v-if="inherited"> · 关联既有网格</span><br v-if="zone && overlay"><span v-if="zone && overlay">{{ zone.label }}高亮 · {{ overlay.failedCount }} 失效 / {{ overlay.validCount }} 有效 die</span></figcaption>
  </figure>
</template>
