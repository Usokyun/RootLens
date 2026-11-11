<script setup lang="ts">
import { IconQuestionCircle } from '@arco-design/web-vue/es/icon'
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    title: string
    help?: string | string[] | null
    tooltipPosition?: string
  }>(),
  {
    help: null,
    tooltipPosition: 'top',
  },
)

const helpItems = computed(() => {
  const values = Array.isArray(props.help) ? props.help : props.help ? [props.help] : []
  return values
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length)
})
</script>

<template>
  <span class="workspace-title-with-help">
    <span class="workspace-title-with-icon">
      <slot />
      <span>{{ title }}</span>
    </span>
    <a-tooltip
      v-if="helpItems.length"
      :position="tooltipPosition"
      content-class="workspace-title-tooltip-shell"
      arrow-class="workspace-title-tooltip-arrow"
    >
      <span
        class="workspace-help-trigger"
        tabindex="0"
        role="button"
        :aria-label="`查看${title}说明`"
      >
        <icon-question-circle />
      </span>
      <template #content>
        <div class="workspace-title-tooltip">
          <p v-for="(item, index) in helpItems" :key="`${title}:${index}`">
            {{ item }}
          </p>
        </div>
      </template>
    </a-tooltip>
  </span>
</template>
