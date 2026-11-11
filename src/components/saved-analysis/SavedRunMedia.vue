<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { VisualEvidenceItem } from '@/api/contracts'
import { traceRecord } from '@/services/unified-reasoning-display'
import { number } from './presentation'

const props = defineProps<{ item: VisualEvidenceItem; scope?: unknown; scopeLabel?: string; caption?: string; compact?: boolean }>()
const broken = ref(false)
watch(() => props.item.url, () => { broken.value = false })
const labels: Record<string, string> = { source_path: '原图', image_path: '原图', roi_path: 'ROI', heatmap_path: '异常热图', mask_path: '掩码', wafer_map_path: '晶圆网格' }
const label = computed(() => labels[props.item.source_key] ?? props.item.title)
const overlay = computed(() => {
  const scope = traceRecord(props.scope)
  if (!['source_path', 'image_path'].includes(props.item.source_key) || scope.kind !== 'image_region' || scope.coordinate_space !== 'original_image_pixels') return null
  if (!Array.isArray(scope.image_shape_hw) || scope.image_shape_hw.length !== 2 || !scope.image_shape_hw.every(Number.isFinite)
    || !Array.isArray(scope.bbox_xyxy) || scope.bbox_xyxy.length !== 4 || !scope.bbox_xyxy.every(Number.isFinite)) return null
  const [h, w] = scope.image_shape_hw as [number, number]
  const [x1, y1, x2, y2] = scope.bbox_xyxy as [number, number, number, number]
  if (h <= 0 || w <= 0 || x2 <= x1 || y2 <= y1) return null
  return { w, h, bbox: [x1, y1, x2, y2] as const, width: x2 - x1, height: y2 - y1 }
})
const imgWidth = computed(() => overlay.value?.w ?? number(props.item.metadata?.preview_width))
const imgHeight = computed(() => overlay.value?.h ?? number(props.item.metadata?.preview_height))
</script>

<template>
  <figure class="saved-run-media" :class="{ 'saved-run-media--compact': compact }" :data-asset-id="item.artifact_id">
    <div class="saved-run-media-surface">
      <div v-if="broken || !item.url" class="saved-run-muted saved-run-media-error">无法读取这份保存附件</div>
      <div v-else class="saved-run-image-fit" :style="imgWidth && imgHeight ? { '--sr-image-ratio': imgWidth / imgHeight } : undefined">
        <img :src="item.url" :alt="`${label} · 本次保存附件`" @error="broken = true" />
        <svg v-if="overlay" class="saved-run-roi" :viewBox="`0 0 ${overlay.w} ${overlay.h}`" aria-hidden="true" :data-bbox="overlay.bbox.join(',')">
          <rect :x="overlay.bbox[0]" :y="overlay.bbox[1]" :width="overlay.width" :height="overlay.height" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke" />
        </svg>
        <span v-if="overlay && scopeLabel" class="saved-run-roi-label" :style="{ left: `${overlay.bbox[0] / overlay.w * 100}%`, top: `${overlay.bbox[1] / overlay.h * 100}%` }">{{ scopeLabel }}</span>
      </div>
    </div>
    <figcaption><span>{{ label }}</span><span v-if="caption">{{ caption }}</span></figcaption>
  </figure>
</template>
