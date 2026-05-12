<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  getImportedSessionSummary,
  getLocalSessionEventName,
  getLocalSessionMeta,
} from '@/services/rootlens-data'
import {
  buildWorkflowSnapshot,
  type WorkflowStageName,
  type WorkflowStageStatus,
} from '@/services/workflow'

const props = defineProps<{
  activeName?: string
}>()

const router = useRouter()
const sessionMeta = ref(getLocalSessionMeta())
const importSummary = ref(getImportedSessionSummary())

const workflow = computed(() => buildWorkflowSnapshot(sessionMeta.value, importSummary.value))

function refreshSessionState() {
  sessionMeta.value = getLocalSessionMeta()
  importSummary.value = getImportedSessionSummary()
}

function handleSessionChange() {
  refreshSessionState()
}

function statusColor(status: WorkflowStageStatus) {
  switch (status) {
    case 'ready':
      return 'green'
    case 'attention':
      return 'gold'
    case 'waiting':
      return 'grayblue'
  }
}

function statusLabel(name: WorkflowStageName, status: WorkflowStageStatus) {
  if (props.activeName === name) {
    return '当前页面'
  }

  switch (status) {
    case 'ready':
      return '已就绪'
    case 'attention':
      return '待补齐'
    case 'waiting':
      return '等待输入'
  }
}

function datasetLabel() {
  return workflow.value.datasetCount === null ? 'demo graph' : `${workflow.value.datasetCount} dataset`
}

function caseLabel() {
  return workflow.value.caseCount === null ? 'demo case' : `${workflow.value.caseCount} case`
}

function goToStage(name: WorkflowStageName) {
  if (props.activeName === name) {
    return
  }

  void router.push({
    name,
  })
}

onMounted(() => {
  refreshSessionState()
  window.addEventListener(getLocalSessionEventName(), handleSessionChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLocalSessionEventName(), handleSessionChange)
})
</script>

<template>
  <a-card class="workflow-strip" :bordered="false">
    <div class="workflow-strip__head">
      <div>
        <div class="workflow-strip__eyebrow">Main Flow</div>
        <div class="workflow-strip__title">
          导入数据 -> 构建图谱 -> Evidence -> RCA 可视化
        </div>
      </div>

      <a-space wrap>
        <a-tag color="arcoblue">{{ workflow.sessionLabel }}</a-tag>
        <a-tag color="grayblue">{{ workflow.modeLabel }}</a-tag>
        <a-tag color="green">{{ datasetLabel() }}</a-tag>
        <a-tag color="gold">{{ caseLabel() }}</a-tag>
        <a-tag v-if="workflow.warningCount" color="orangered">
          {{ workflow.warningCount }} warning{{ workflow.warningCount > 1 ? 's' : '' }}
        </a-tag>
      </a-space>
    </div>

    <div class="workflow-strip__grid">
      <button
        v-for="(stage, index) in workflow.stages"
        :key="stage.name"
        class="workflow-card"
        :class="{ 'workflow-card--active': activeName === stage.name }"
        type="button"
        @click="goToStage(stage.name)"
      >
        <div class="workflow-card__step">
          {{ String(index + 1).padStart(2, '0') }}
        </div>

        <div class="workflow-card__body">
          <div class="workflow-card__title">{{ stage.label }}</div>
          <p class="workflow-card__description">{{ stage.description }}</p>
          <p class="workflow-card__note">{{ stage.note }}</p>
        </div>

        <div class="workflow-card__meta">
          <a-tag :color="statusColor(stage.status)">
            {{ statusLabel(stage.name, stage.status) }}
          </a-tag>
          <span class="workflow-card__action">
            {{ activeName === stage.name ? '当前工作台' : '进入' }}
          </span>
        </div>
      </button>
    </div>
  </a-card>
</template>

<style scoped>
.workflow-strip {
  border: 1px solid rgba(15, 139, 141, 0.14);
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(15, 139, 141, 0.08), transparent 26%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(247, 251, 252, 0.96));
}

.workflow-strip__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.workflow-strip__eyebrow {
  color: var(--kg-accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.workflow-strip__title {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.35;
}

.workflow-strip__grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 18px;
}

.workflow-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid rgba(18, 35, 47, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.workflow-card:hover,
.workflow-card--active {
  transform: translateY(-1px);
  border-color: rgba(15, 139, 141, 0.32);
  box-shadow: 0 18px 36px rgba(12, 31, 43, 0.08);
}

.workflow-card__step {
  color: var(--kg-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.workflow-card__body {
  display: grid;
  gap: 8px;
}

.workflow-card__title {
  font-size: 18px;
  font-weight: 700;
}

.workflow-card__description,
.workflow-card__note {
  margin: 0;
  color: var(--kg-muted);
  line-height: 1.6;
}

.workflow-card__note {
  color: var(--kg-ink);
  font-size: 13px;
}

.workflow-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.workflow-card__action {
  color: var(--kg-muted);
  font-size: 13px;
  font-weight: 600;
}

@media (max-width: 1280px) {
  .workflow-strip__grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 780px) {
  .workflow-strip__head,
  .workflow-card__meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .workflow-strip__grid {
    grid-template-columns: 1fr;
  }
}
</style>
