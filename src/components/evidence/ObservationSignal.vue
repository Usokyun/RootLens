<script setup lang="ts">
import { computed } from "vue";
import type { ObservationBrowseItem } from "@/services/evidence-observation";
import { readable, scoreText } from "@/services/presentation";

const props = defineProps<{ observation: ObservationBrowseItem }>();
const labels: Record<string, string> = {
  contribution: "变量贡献",
  normalized_contribution: "归一化贡献",
  value: "观测值",
  severity: "异常强度",
  confidence: "观察置信度",
};
const measures = computed(
  () =>
    Object.entries(props.observation.rawObservation).filter(
      ([k, v]) => k in labels && typeof v === "number" && Number.isFinite(v),
    ) as [string, number][],
);
const series = computed(() => {
  const data =
    props.observation.rawObservation.series ??
    props.observation.rawObservation.values;
  return Array.isArray(data) &&
    data.length > 1 &&
    data.every((v) => typeof v === "number" && Number.isFinite(v))
    ? (data as number[])
    : [];
});
const points = computed(() => {
  const min = Math.min(...series.value),
    max = Math.max(...series.value);
  return series.value
    .map(
      (v, i) =>
        `${20 + (i / (series.value.length - 1)) * 720},${180 - ((v - min) / (max - min || 1)) * 140}`,
    )
    .join(" ");
});
const snippet = computed(() =>
  String(
    props.observation.rawObservation.message ??
      props.observation.rawObservation.text ??
      props.observation.rawObservation.value ??
      props.observation.rawObservation.display_name ??
      props.observation.rawObservation.name ??
      readable(props.observation.title, "未提供文本片段"),
  ),
);
</script>
<template>
  <div class="signal-panel">
    <template v-if="observation.modality === 'time_series'">
      <div class="signal-panel__heading">
        <span class="eyebrow">过程变量</span>
        <h3>
          {{
            readable(
              String(
                observation.rawObservation.variable_name ?? observation.title,
              ),
            )
          }}
        </h3>
        <p class="subtle">{{ observation.timeLabel }}</p>
      </div>
      <svg
        v-if="series.length"
        viewBox="0 0 760 210"
        role="img"
        :aria-label="`${observation.title} 时序曲线`"
      >
        <path d="M20 20V180H740" fill="none" stroke="var(--color-border-2)" />
        <polyline
          :points="points"
          fill="none"
          stroke="rgb(var(--primary-6))"
          stroke-width="3"
        />
      </svg>
      <div class="measure-list">
        <div v-for="[key, value] in measures" :key="key" class="measure-row">
          <span>{{ labels[key] }}</span
          ><a-progress
            v-if="value >= 0 && value <= 1"
            :percent="value"
            :show-text="false"
          /><strong>{{ scoreText(value) }}</strong>
        </div>
      </div>
      <p v-if="!series.length" class="subtle">
        此回放保留变量贡献与时间窗口，未提供原始时序曲线。
      </p>
    </template>
    <template v-else
      ><span class="eyebrow">{{
        observation.source === "time_series"
          ? "过程描述"
          : readable(observation.modality) + "观察"
      }}</span>
      <blockquote>{{ snippet }}</blockquote>
      <p class="subtle">{{ observation.timeLabel }}</p></template
    >
  </div>
</template>
