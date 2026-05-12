<script setup lang="ts">
interface BlockerAction {
  key: string
  label: string
  type?: 'primary' | 'outline' | 'secondary' | 'dashed' | 'text'
}

defineProps<{
  badge: string
  sessionLabel: string
  title: string
  description: string
  reason?: string
  hints?: string[]
  actions?: BlockerAction[]
}>()

const emit = defineEmits<{
  action: [key: string]
}>()
</script>

<template>
  <a-card class="glass-card blocker-card" :bordered="false">
    <a-space wrap>
      <a-tag color="orangered">{{ badge }}</a-tag>
      <a-tag color="grayblue">{{ sessionLabel }}</a-tag>
    </a-space>

    <h3 class="blocker-card__title">{{ title }}</h3>
    <p class="blocker-card__description">{{ description }}</p>

    <a-alert v-if="reason" type="warning" show-icon :content="reason" />

    <div v-if="hints?.length" class="blocker-card__hints">
      <div
        v-for="hint in hints"
        :key="hint"
        class="blocker-card__hint"
      >
        {{ hint }}
      </div>
    </div>

    <a-space v-if="actions?.length" wrap>
      <a-button
        v-for="action in actions"
        :key="action.key"
        :type="action.type ?? 'outline'"
        @click="emit('action', action.key)"
      >
        {{ action.label }}
      </a-button>
    </a-space>
  </a-card>
</template>

<style scoped>
.blocker-card {
  display: grid;
  gap: 16px;
}

.blocker-card__title {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
}

.blocker-card__description {
  margin: 0;
  color: var(--kg-muted);
  line-height: 1.7;
}

.blocker-card__hints {
  display: grid;
  gap: 10px;
}

.blocker-card__hint {
  padding: 12px 14px;
  border: 1px solid rgba(18, 35, 47, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.68);
  color: var(--kg-ink);
  line-height: 1.6;
}
</style>
