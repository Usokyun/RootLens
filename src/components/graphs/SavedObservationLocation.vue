<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { RunCaseDetail } from '@/api/contracts'
import type { ObservationBrowseItem } from '@/services/evidence-observation'
import { savedObservationLocation } from '@/services/saved-analysis-graph'
import { traceValue } from '@/services/unified-reasoning-display'

const props = defineProps<{ caseDetail: RunCaseDetail; observation: ObservationBrowseItem; apiBase: string }>()
const location = computed(() => savedObservationLocation(props.caseDetail, props.observation, props.apiBase))
const image = computed(() => location.value?.kind === 'image_region' ? location.value : null)
const windowLocation = computed(() => location.value?.kind === 'time_window' ? location.value : null)
const mediaId = ref<string | null>(null)
watch(image, (value) => {
  mediaId.value = value?.media.find(item => item.source_key === 'source_path')?.artifact_id
    ?? value?.media[0]?.artifact_id ?? null
}, { immediate: true })
const activeMedia = computed(() => image.value?.media.find(item => item.artifact_id === mediaId.value))
const bboxOverlay = computed(() => activeMedia.value?.source_key === 'source_path'
  && image.value?.coordinateSpace === 'original_image_pixels' && image.value.imageShape && image.value.bbox
  ? { width: image.value.imageShape[1]!, height: image.value.imageShape[0]!, bbox: image.value.bbox } : null)
const trendPoints = computed(() => {
  const values = windowLocation.value?.samples
  if (!values) return ''
  let low = Infinity, high = -Infinity
  for (const value of values) { low = Math.min(low, value); high = Math.max(high, value) }
  return values.map((value, index) => `${index / Math.max(1, values.length - 1) * 240},${high === low ? 24 : 44 - (value - low) / (high - low) * 40}`).join(' ')
})

const mediaLabels: Record<string, string> = { source_path: '原图', mask_path: '掩码', heatmap_path: '热图', roi_path: 'ROI' }
</script>

<template>
  <details v-if="location" class="saved-observation-location">
    <summary>
      证据定位 · <template v-if="image">{{ image.scopeId ?? '图像区域' }}</template>
      <template v-else-if="windowLocation">{{ windowLocation.channel ?? '过程窗口' }} · 样本 {{ windowLocation.start }}–{{ windowLocation.end }}</template>
    </summary>
    <p>{{ location.feature }} · <strong>{{ traceValue(location.value) }}</strong></p>
    <template v-if="image">
      <p v-if="image.bbox" :title="JSON.stringify(image.bbox)">
        {{ image.coordinateSpace === 'original_image_pixels' ? '原图像素' : image.coordinateSpace }} ROI
        [{{ image.bbox.map(item => Number(item.toFixed(2))).join(', ') }}]
      </p>
      <a-radio-group v-if="image.media.length > 1" v-model="mediaId" size="mini" type="button" aria-label="观测媒体">
        <a-radio v-for="item in image.media" :key="item.artifact_id" :value="item.artifact_id">{{ mediaLabels[item.source_key] ?? item.title }}</a-radio>
      </a-radio-group>
      <figure v-if="activeMedia">
        <img :src="activeMedia.url" :alt="activeMedia.title" />
        <svg v-if="bboxOverlay" :viewBox="`0 0 ${bboxOverlay.width} ${bboxOverlay.height}`" aria-hidden="true">
          <rect :x="bboxOverlay.bbox[0]" :y="bboxOverlay.bbox[1]"
            :width="bboxOverlay.bbox[2]! - bboxOverlay.bbox[0]!" :height="bboxOverlay.bbox[3]! - bboxOverlay.bbox[1]!"
            fill="none" stroke="#f68038" stroke-width="2" vector-effect="non-scaling-stroke" />
        </svg>
      </figure>
      <p v-else>{{ caseDetail.media_note || '此保存结果没有可读取的图像附件。' }}</p>
    </template>
    <template v-else-if="windowLocation">
      <p v-if="windowLocation.samplingSeconds !== null">采样间隔 {{ windowLocation.samplingSeconds }} 秒</p>
      <template v-if="trendPoints">
        <svg class="saved-observation-location__trend" viewBox="0 0 240 48" role="img" :aria-label="`${windowLocation.channel} 原始窗口趋势`">
          <polyline :points="trendPoints" fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke" />
        </svg>
        <p>{{ windowLocation.samples?.length }} 个保存样本 · 首值 {{ traceValue(windowLocation.samples?.[0]) }} / 末值 {{ traceValue(windowLocation.samples?.at(-1)) }}</p>
      </template>
      <p v-else>当前观测没有单通道原始曲线。</p>
    </template>
  </details>
</template>

<style scoped>
.saved-observation-location { margin: 8px 0; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
summary { cursor: pointer; color: rgb(var(--primary-6)); }
p { margin: 4px 0; }
figure { position: relative; max-width: 260px; margin: 6px 0 0; }
figure img { display: block; width: 100%; height: auto; }
figure svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.saved-observation-location__trend { display: block; width: min(100%, 260px); height: auto; color: rgb(var(--primary-6)); }
</style>
