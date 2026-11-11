<script setup lang="ts">
import { computed } from 'vue'
import type { WorkTask } from '@/api/two-loop'
import { taskCanRetry, taskIsActive, taskStatusLabels } from '@/services/task-observer'

const props = defineProps<{ task: WorkTask; connectionError?: string; retrying?: boolean }>()
defineEmits<{ refresh: []; retry: [] }>()
const active = computed(() => taskIsActive(props.task))
const count = computed(() => {
  const progress = props.task.progress
  if (!progress || progress.indeterminate || typeof progress.completed !== 'number'
    || typeof progress.total !== 'number' || progress.total <= 0) return null
  return `${progress.completed} / ${progress.total}${progress.unit ? ` ${progress.unit}` : ''}`
})
const color = computed(() => props.task.status === 'completed' ? 'green' : taskCanRetry(props.task) ? 'red' : 'arcoblue')
</script>

<template>
  <section class="workspace-stack workspace-stack--tight" aria-label="任务进度">
    <a-space wrap>
      <strong>{{ task.title }}</strong>
      <a-tag :color="color">{{ taskStatusLabels[task.status] }}</a-tag>
    </a-space>
    <div aria-live="polite">
      <a-spin v-if="active && !count && !connectionError" :size="12" />
      {{ task.stage_label || taskStatusLabels[task.status] }}<template v-if="count"> · {{ count }}</template>
    </div>
    <a-alert v-if="task.error" type="error">{{ task.error.message }}</a-alert>
    <a-alert v-if="connectionError" type="warning">
      {{ connectionError }}
      <a-button type="text" size="mini" @click="$emit('refresh')">重新读取状态</a-button>
    </a-alert>
    <details v-if="task.events.length" class="task-events">
      <summary>阶段记录（{{ task.events.length }}）</summary>
      <ol>
        <li v-for="event in task.events" :key="event.sequence">{{ event.label }}</li>
      </ol>
    </details>
    <a-space wrap>
      <a-button v-if="taskCanRetry(task)" size="small" :loading="retrying" @click="$emit('retry')">按原输入重试</a-button>
      <slot name="actions" />
    </a-space>
  </section>
</template>

<style scoped>
.task-events summary { cursor: pointer; }
.task-events ol { margin: 6px 0 0; padding-inline-start: 20px; max-height: 144px; overflow-y: auto; }
</style>
