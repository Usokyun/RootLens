<script setup lang="ts">
import { computed } from 'vue'
import type { WorkTask } from '@/api/workbench'
import { IconCheck, IconClockCircle, IconExclamationCircle, IconRefresh } from '@arco-design/web-vue/es/icon'
const props = defineProps<{ task: WorkTask; connectionError?: string; retrying?: boolean }>()
defineEmits<{ retry: []; refresh: [] }>()
const active = computed(() => ['queued', 'running'].includes(props.task.status))
const failed = computed(() => ['failed', 'interrupted'].includes(props.task.status))
const statusLabel = computed(() => props.connectionError ? '状态待确认' : ({ queued: '排队中', running: '处理中', completed: '已完成', failed: '处理失败', interrupted: '已中断' })[props.task.status])
const percent = computed(() => {
  const p = props.task.progress
  return !p?.indeterminate && p?.total && typeof p.completed === 'number' ? Math.min(100, p.completed / p.total * 100) : null
})
</script>
<template>
  <section class="task-progress" :data-task-id="task.task_id" :class="{ 'task-progress--failed': failed, 'task-progress--complete': task.status === 'completed' }" aria-live="polite" aria-label="后端处理进度">
    <div class="task-progress__head">
      <span class="task-progress__symbol" :class="{ 'is-spinning': active && !connectionError }"><IconRefresh v-if="active" /><IconExclamationCircle v-else-if="failed" /><IconCheck v-else /></span>
      <div class="grow"><span class="eyebrow">{{ statusLabel }} · 后端真实任务</span><h3>{{ task.stage_label || task.title }}</h3></div>
      <span v-if="task.progress?.total && !task.progress.indeterminate" class="muted">{{ task.progress.completed ?? 0 }} / {{ task.progress.total }} {{ task.progress.unit }}</span>
      <span v-else-if="active" class="muted"><IconClockCircle /> 等待当前阶段完成</span>
    </div>
    <div v-if="active && !connectionError" class="task-progress__track" :class="{ 'is-indeterminate': percent === null }"><span :style="percent === null ? {} : { width: percent + '%' }" /></div>
    <p v-if="failed" class="error-text">{{ task.error?.message || '服务重启中断了任务，原输入已保留。' }}</p>
    <div v-if="connectionError" class="alert alert--warning">无法取得最新进度（显示上次状态）：{{ connectionError }} <button class="text-button" @click="$emit('refresh')">重新连接</button></div>
    <details v-if="task.events?.length" class="task-events"><summary>查看处理记录（{{ task.events.length }}）</summary><ol><li v-for="event in task.events" :key="event.sequence"><time>{{ new Date(event.at).toLocaleTimeString('zh-CN', { hour12: false }) }}</time><span>{{ event.label }}</span></li></ol></details>
    <div v-if="failed" class="button-row"><button class="button button--secondary" :disabled="retrying" @click="$emit('retry')"><IconRefresh />{{ retrying ? '正在重新提交…' : '保留输入，重试任务' }}</button><span class="muted">重试会创建新任务；需要模型的阶段将重新执行。</span></div>
  </section>
</template>
