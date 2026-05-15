<script setup lang="ts">
type HeroTone = 'blue' | 'teal' | 'amber'

interface WorkbenchHeroMetric {
  label: string
  value: string | number
  hint?: string
  tone?: HeroTone
}

withDefaults(
  defineProps<{
    eyebrow: string
    title: string
    description?: string
    metrics?: WorkbenchHeroMetric[]
    tone?: HeroTone
  }>(),
  {
    description: '',
    metrics: () => [],
    tone: 'blue',
  },
)
</script>

<template>
  <section class="workbench-hero" :class="`workbench-hero--${tone}`">
    <div class="workbench-hero__backdrop" aria-hidden="true" />

    <div class="workbench-hero__main">
      <span class="workbench-hero__eyebrow">{{ eyebrow }}</span>

      <div class="workbench-hero__title-row">
        <h2 class="workbench-hero__title">{{ title }}</h2>
        <div v-if="$slots.badges" class="workbench-hero__badges">
          <slot name="badges" />
        </div>
      </div>

      <p v-if="description" class="workbench-hero__description">{{ description }}</p>

      <div v-if="$slots.summary" class="workbench-hero__summary">
        <slot name="summary" />
      </div>

      <div v-if="$slots.actions" class="workbench-hero__actions">
        <slot name="actions" />
      </div>
    </div>

    <div v-if="metrics.length" class="workbench-hero__metrics">
      <article
        v-for="metric in metrics"
        :key="metric.label"
        class="workbench-hero__metric"
        :class="`workbench-hero__metric--${metric.tone ?? tone}`"
      >
        <span class="workbench-hero__metric-label">{{ metric.label }}</span>
        <strong class="workbench-hero__metric-value">{{ metric.value }}</strong>
        <small v-if="metric.hint" class="workbench-hero__metric-hint">{{ metric.hint }}</small>
      </article>
    </div>
  </section>
</template>

<style scoped>
.workbench-hero {
  position: relative;
  border: 1px solid rgba(63, 124, 255, 0.14);
  border-radius: 18px;
  padding: 16px 18px;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(260px, 0.9fr);
  gap: 14px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 255, 0.94)),
    radial-gradient(circle at top left, rgba(63, 124, 255, 0.14), transparent 30%);
  box-shadow: 0 20px 42px rgba(17, 25, 39, 0.08);
  overflow: hidden;
  isolation: isolate;
}

.workbench-hero__backdrop {
  position: absolute;
  inset: auto -8% -45% auto;
  width: 240px;
  height: 240px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(63, 124, 255, 0.16), transparent 66%);
  pointer-events: none;
}

.workbench-hero--teal {
  border-color: rgba(15, 118, 110, 0.16);
}

.workbench-hero--teal .workbench-hero__backdrop {
  background: radial-gradient(circle, rgba(15, 118, 110, 0.18), transparent 66%);
}

.workbench-hero--amber {
  border-color: rgba(217, 119, 6, 0.18);
}

.workbench-hero--amber .workbench-hero__backdrop {
  background: radial-gradient(circle, rgba(245, 158, 11, 0.18), transparent 66%);
}

.workbench-hero__main,
.workbench-hero__metrics {
  position: relative;
  z-index: 1;
}

.workbench-hero__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.workbench-hero__eyebrow {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border-radius: 999px;
  padding: 4px 10px;
  background: rgba(63, 124, 255, 0.1);
  color: #2959b3;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.workbench-hero--teal .workbench-hero__eyebrow {
  background: rgba(15, 118, 110, 0.1);
  color: #0f766e;
}

.workbench-hero--amber .workbench-hero__eyebrow {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.workbench-hero__title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.workbench-hero__title {
  margin: 0;
  color: #102a43;
  font-size: clamp(1.5rem, 2vw, 2rem);
  line-height: 1.05;
}

.workbench-hero__badges {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.workbench-hero__description {
  max-width: 760px;
  margin: 0;
  color: #466079;
  font-size: 14px;
  line-height: 1.75;
}

.workbench-hero__summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.workbench-hero__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.workbench-hero__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  gap: 8px;
  align-self: start;
}

.workbench-hero__metric {
  min-width: 0;
  border: 1px solid rgba(63, 124, 255, 0.16);
  border-radius: 14px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
}

.workbench-hero__metric--teal {
  border-color: rgba(15, 118, 110, 0.18);
}

.workbench-hero__metric--amber {
  border-color: rgba(245, 158, 11, 0.18);
}

.workbench-hero__metric-label {
  color: #73869a;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.workbench-hero__metric-value {
  color: #102a43;
  font-size: 20px;
  line-height: 1;
}

.workbench-hero__metric-hint {
  color: #4e5969;
  font-size: 11px;
  line-height: 1.45;
}

@media (max-width: 1100px) {
  .workbench-hero {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .workbench-hero {
    padding: 18px 16px 16px;
    border-radius: 18px;
  }

  .workbench-hero__title {
    font-size: 1.48rem;
  }

  .workbench-hero__metrics {
    grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  }
}
</style>
