<script setup lang="ts">
interface WorkspaceHeaderTag {
  label: string
  color?: 'arcoblue' | 'green' | 'gold' | 'orangered' | 'purple' | 'gray'
}

withDefaults(
  defineProps<{
    title: string
    description: string
    eyebrow?: string
    tags?: WorkspaceHeaderTag[]
  }>(),
  {
    eyebrow: '当前工作区',
    tags: () => [],
  },
)
</script>

<template>
  <section class="workspace-header-strip">
    <div class="workspace-header-strip__copy">
      <span class="workspace-header-strip__label">{{ eyebrow }}</span>
      <strong class="workspace-header-strip__title">{{ title }}</strong>
      <p class="workspace-header-strip__desc">{{ description }}</p>
    </div>

    <div class="workspace-header-strip__side">
      <div v-if="tags.length || $slots.tags" class="workspace-header-strip__tags">
        <slot name="tags">
          <a-tag v-for="tag in tags" :key="tag.label" size="small" :color="tag.color">
            {{ tag.label }}
          </a-tag>
        </slot>
      </div>

      <div v-if="$slots.actions" class="workspace-header-strip__actions">
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.workspace-header-strip {
  margin-bottom: 10px;
  border: 1px solid var(--rl-border);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--rl-shadow);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.workspace-header-strip__copy,
.workspace-header-strip__side {
  min-width: 0;
}

.workspace-header-strip__copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.workspace-header-strip__label {
  font-size: 12px;
  color: var(--rl-muted);
  letter-spacing: 0.08em;
}

.workspace-header-strip__title {
  color: #102a43;
  font-size: 16px;
  line-height: 1.2;
}

.workspace-header-strip__desc {
  margin: 0;
  color: #4e5969;
  font-size: 13px;
  line-height: 1.45;
}

.workspace-header-strip__side {
  min-width: 240px;
  display: grid;
  justify-items: end;
  gap: 4px;
}

.workspace-header-strip__tags {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px;
}

.workspace-header-strip__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 720px) {
  .workspace-header-strip {
    align-items: flex-start;
    flex-direction: column;
  }

  .workspace-header-strip__side {
    min-width: 0;
    width: 100%;
    justify-items: start;
  }

  .workspace-header-strip__tags,
  .workspace-header-strip__actions {
    justify-content: flex-start;
  }
}
</style>
