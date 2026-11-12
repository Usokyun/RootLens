<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { VisualEvidenceItem } from "@/api/contracts";
import { resolveVisualEvidenceUrl } from "@/services/ui-copy";

const props = defineProps<{ items: VisualEvidenceItem[]; label?: string }>();
const selectedKind = ref("image");
const overlay = ref(false);
const opacity = ref(55);
const failed = ref<string[]>([]);
const zoomVisible = ref(false);
const valid = computed(() =>
  props.items.filter((i) => i.available && resolveVisualEvidenceUrl(i)),
);
const base = computed(() =>
  valid.value.find((i) => ["image", "wafer_map"].includes(i.kind)),
);
const selected = computed(
  () =>
    valid.value.find((i) => i.kind === selectedKind.value) ?? valid.value[0],
);
const response = computed(() => valid.value.find((i) => i.kind === "heatmap"));
const kindLabels: Record<string, string> = {
  image: "原图",
  mask: "异常区域",
  heatmap: "响应图",
  wafer_map: "晶圆图",
};
watch(
  () => props.items,
  () => {
    selectedKind.value = valid.value[0]?.kind ?? "image";
    failed.value = [];
    overlay.value = false;
  },
);
const selectedUrl = computed(() =>
  selected.value ? resolveVisualEvidenceUrl(selected.value) : null,
);
const canOverlay = computed(
  () =>
    !!base.value &&
    !!response.value &&
    base.value.metadata.registered === true &&
    response.value.metadata.registered === true,
);
</script>

<template>
  <section class="evidence-visual" aria-label="可视证据">
    <div v-if="valid.length" class="evidence-visual__toolbar">
      <a-radio-group
        v-model="selectedKind"
        type="button"
        aria-label="证据图层"
        @change="overlay = false"
      >
        <a-radio
          v-for="item in valid"
          :key="item.artifact_id"
          :value="item.kind"
          >{{ kindLabels[item.kind] ?? item.title }}</a-radio
        >
      </a-radio-group>
      <a-space>
        <a-button
          v-if="canOverlay"
          :type="overlay ? 'primary' : 'secondary'"
          @click="overlay = !overlay"
          >叠加</a-button
        >
        <a-button @click="zoomVisible = true">放大</a-button>
      </a-space>
    </div>
    <div
      v-if="
        valid.length &&
        selected &&
        selectedUrl &&
        !failed.includes(selected.artifact_id)
      "
      class="evidence-visual__stage"
    >
      <img
        :src="
          overlay && base ? (resolveVisualEvidenceUrl(base) ?? '') : selectedUrl
        "
        :alt="label ?? selected.title"
        @error="failed.push(selected.artifact_id)"
      />
      <img
        v-if="overlay && response"
        class="evidence-visual__overlay"
        :src="resolveVisualEvidenceUrl(response) ?? ''"
        :style="{ opacity: opacity / 100 }"
        alt="响应图叠加"
        @error="
          failed.push(response.artifact_id);
          overlay = false;
        "
      />
    </div>
    <a-empty
      v-else
      :description="
        valid.length ? '图像加载失败，请核对后端资源地址' : '未提供可视资源'
      "
    />
    <div v-if="overlay" class="evidence-visual__opacity">
      <span>叠加强度</span
      ><a-slider v-model="opacity" :min="0" :max="100" aria-label="叠加强度" />
    </div>
    <p v-if="selected?.metadata.scope === 'case'" class="subtle">
      案例级资源 · 未提供逐观察绑定
    </p>
    <p v-if="selected?.note" class="subtle evidence-visual__note">
      {{ selected.note }}
    </p>
    <a-modal
      v-model:visible="zoomVisible"
      :title="selected?.title ?? '可视证据'"
      :footer="false"
      width="min(1000px, 94vw)"
    >
      <img
        v-if="selectedUrl"
        :src="selectedUrl"
        :alt="selected?.title"
        class="evidence-visual__zoom"
      />
    </a-modal>
  </section>
</template>
