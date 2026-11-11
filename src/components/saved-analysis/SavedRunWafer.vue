<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ grid: number[][]; inherited?: boolean }>()
const width = computed(() => props.grid[0]?.length ?? 0)
// Only a display projection of the persisted cells; no inference or new region detection.
const paths = computed(() => {
  const segments: string[][] = [[], [], []]
  for (const [y, row] of props.grid.entries()) {
    for (let x = 0; x < row.length;) {
      const cell = row[x]!, start = x
      while (x < row.length && row[x] === cell) x += 1
      segments[cell]?.push(`M${start} ${y}h${x - start}v1h-${x - start}Z`)
    }
  }
  return segments.map(segment => segment.join(''))
})
</script>
<template>
  <figure v-if="width" class="saved-run-wafer">
    <svg :viewBox="`0 0 ${width} ${grid.length}`" role="img" :aria-label="`${grid.length} × ${width} 保存晶圆网格`" shape-rendering="crispEdges">
      <path :d="paths[0]" fill="#e8edf4" /><path :d="paths[1]" fill="#6aa3de" /><path :d="paths[2]" fill="#e87845" />
    </svg>
    <figcaption>{{ grid.length }} 行 × {{ width }} 列 · 0 背景 / 1 正常 / 2 失效<span v-if="inherited"> · 关联既有网格</span></figcaption>
  </figure>
</template>
