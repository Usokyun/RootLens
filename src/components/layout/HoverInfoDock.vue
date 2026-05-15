<script setup lang="ts">
import { ref } from 'vue'

type DockTone = 'blue' | 'teal' | 'amber'

const props = withDefaults(
  defineProps<{
    title: string
    label?: string
    subtitle?: string
    tone?: DockTone
  }>(),
  {
    label: 'INFO',
    subtitle: '',
    tone: 'blue',
  },
)

const expanded = ref(false)

function toggleExpanded() {
  expanded.value = !expanded.value
}
</script>

<template>
  <aside
    class="hover-info-dock"
    :class="[`hover-info-dock--${props.tone}`, { 'hover-info-dock--expanded': expanded }]"
    @mouseenter="expanded = true"
    @mouseleave="expanded = false"
  >
    <button type="button" class="hover-info-dock__tab" @click="toggleExpanded">
      <span class="hover-info-dock__tab-label">{{ props.label }}</span>
    </button>

    <section class="hover-info-dock__panel">
      <header class="hover-info-dock__header">
        <div>
          <h4 class="hover-info-dock__title">{{ props.title }}</h4>
          <p v-if="props.subtitle" class="hover-info-dock__subtitle">{{ props.subtitle }}</p>
        </div>
      </header>
      <div class="hover-info-dock__body">
        <slot />
      </div>
    </section>
  </aside>
</template>
