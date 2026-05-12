<script setup lang="ts">
import {
  IconCodeBlock,
  IconFile,
  IconMenuFold,
  IconMenuUnfold,
  IconRelation,
  IconUpload,
} from '@arco-design/web-vue/es/icon'
import { useWindowSize } from '@vueuse/core'
import type { Component } from 'vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import SystemFlowNav from '@/components/workflow/SystemFlowNav.vue'
import { workspaceContext } from '@/data/workspace-context'
import {
  getImportedSessionSummary,
  getLocalSessionEventName,
  getLocalSessionMeta,
} from '@/services/rootlens-data'
import { buildWorkflowSnapshot } from '@/services/workflow'

interface NavItem {
  name: string
  label: string
  icon: Component
}

const navItems: NavItem[] = [
  {
    name: 'import',
    label: '系统入口',
    icon: IconUpload,
  },
  {
    name: 'graphs',
    label: '图谱可视化',
    icon: IconRelation,
  },
  {
    name: 'evidence',
    label: 'Evidence 审查',
    icon: IconFile,
  },
  {
    name: 'reasoning',
    label: 'RCA 分析',
    icon: IconCodeBlock,
  },
]

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const sessionMeta = ref(getLocalSessionMeta())
const importSummary = ref(getImportedSessionSummary())
const { width } = useWindowSize()

watch(
  width,
  (value) => {
    collapsed.value = value < 1180
  },
  { immediate: true },
)

const selectedKeys = computed(() =>
  route.name ? [String(route.name)] : ['import'],
)

const currentTitle = computed(() => route.meta.label ?? '系统入口')
const currentDescription = computed(
  () => route.meta.description ?? workspaceContext.scope,
)
const workflow = computed(() => buildWorkflowSnapshot(sessionMeta.value, importSummary.value))
const sessionLabel = computed(() => workflow.value.sessionLabel)
const sourceModeLabel = computed(() => workflow.value.modeLabel)
const datasetCountLabel = computed(() =>
  workflow.value.datasetCount === null ? 'demo' : String(workflow.value.datasetCount),
)
const caseCountLabel = computed(() =>
  workflow.value.caseCount === null ? 'demo' : String(workflow.value.caseCount),
)

function refreshSessionMeta() {
  sessionMeta.value = getLocalSessionMeta()
  importSummary.value = getImportedSessionSummary()
}

function handleSessionChange() {
  refreshSessionMeta()
}

function handleNavigate(key: string) {
  void router.push({
    name: key,
  })
}

onMounted(() => {
  refreshSessionMeta()
  window.addEventListener(getLocalSessionEventName(), handleSessionChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLocalSessionEventName(), handleSessionChange)
})
</script>

<template>
  <a-layout class="workspace-shell">
    <a-layout-sider
      class="workspace-sider"
      :collapsed="collapsed"
      :collapsed-width="88"
      :width="280"
      hide-trigger
      breakpoint="xl"
    >
      <div class="workspace-sider__inner">
        <div class="brand-block">
          <div class="brand-block__eyebrow">Visualization System</div>
          <h1 class="brand-block__title">RootLens</h1>
          <p v-if="!collapsed" class="brand-block__subtitle">
            聚焦导入数据、统一图谱、Evidence 审查与 RCA 分析四段主链路。
          </p>
        </div>

        <a-menu
          class="nav-menu"
          :selected-keys="selectedKeys"
          @menu-item-click="handleNavigate"
        >
          <a-menu-item v-for="item in navItems" :key="item.name">
            <template #icon>
              <component :is="item.icon" />
            </template>
            {{ item.label }}
          </a-menu-item>
        </a-menu>

        <div v-if="!collapsed" class="workspace-sider__footer">
          <div class="footer-note">
            <div class="footer-note__label">Current Scope</div>
            <div class="footer-note__value">
              {{ workspaceContext.scope }}
            </div>
          </div>
        </div>
      </div>
    </a-layout-sider>

    <a-layout class="workspace-main">
      <a-layout-header class="workspace-header">
        <div class="workspace-header__main">
          <a-button shape="circle" @click="collapsed = !collapsed">
            <template #icon>
              <icon-menu-unfold v-if="collapsed" />
              <icon-menu-fold v-else />
            </template>
          </a-button>

          <div class="workspace-header__text">
            <div class="workspace-header__eyebrow">
              {{ workspaceContext.currentPhase }}
            </div>
            <h2 class="workspace-header__title">{{ currentTitle }}</h2>
            <p class="workspace-header__description">{{ currentDescription }}</p>
          </div>
        </div>

        <div class="workspace-header__meta">
          <div class="header-chip">
            <div class="header-chip__label">Session</div>
            <div class="header-chip__value">{{ sessionLabel }}</div>
          </div>
          <div class="header-chip">
            <div class="header-chip__label">Mode</div>
            <div class="header-chip__value">{{ sourceModeLabel }}</div>
          </div>
          <div class="header-chip">
            <div class="header-chip__label">Datasets</div>
            <div class="header-chip__value">{{ datasetCountLabel }}</div>
          </div>
          <div class="header-chip">
            <div class="header-chip__label">Cases</div>
            <div class="header-chip__value">{{ caseCountLabel }}</div>
          </div>
        </div>
      </a-layout-header>

      <a-layout-content class="workspace-content">
        <SystemFlowNav :active-name="route.name ? String(route.name) : 'import'" />
        <RouterView />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>
