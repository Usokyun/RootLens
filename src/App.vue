<script setup lang="ts">
import {
  IconCloud,
  IconDashboard,
  IconExperiment,
  IconInfoCircle,
  IconMenuFold,
  IconMenuUnfold,
  IconRelation,
} from '@arco-design/web-vue/es/icon'
import type { Component } from 'vue'
import { computed, provide, reactive, ref, shallowRef } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useAppPreferences } from '@/services/app-preferences'
import { workingGraphLeaveGuardKey } from '@/services/working-graph-workspace'

interface NavItem {
  name: 'materials' | 'evidence' | 'graphs'
  label: string
  icon: Component
}

const navItems: NavItem[] = [
  {
    name: 'evidence',
    label: '运行与证据',
    icon: IconDashboard,
  },
  {
    name: 'graphs',
    label: '根因与图谱',
    icon: IconRelation,
  },
  {
    name: 'materials',
    label: '素材与构图',
    icon: IconExperiment,
  },
]

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)
const isSavedAnalysis = computed(() => route.name === 'saved-analysis')
const graphLeaveGuard = shallowRef<(() => Promise<boolean>) | null>(null)
provide(workingGraphLeaveGuardKey, graphLeaveGuard)
const backendConfigModalVisible = ref(false)
const backendConfigForm = reactive({
  host: '127.0.0.1',
  port: '8000',
})
const { preferences, updatePreferences } = useAppPreferences()
const isWorkingGraph = computed(() => route.name === 'graphs')
const siderCollapsed = computed(() => isSavedAnalysis.value || isWorkingGraph.value || collapsed.value)

const activeMenuKey = computed(() => {
  if (isSavedAnalysis.value) return 'evidence'
  const matched = navItems.find((item) => item.name === route.name)
  return matched?.name ?? 'evidence'
})

const currentPageLabel = computed(() => {
  return typeof route.meta.label === 'string' ? route.meta.label : 'RootLens 工作台'
})

const currentContextLabel = computed(() => {
  if (isSavedAnalysis.value) return '保存运行'
  if (isWorkingGraph.value) return '当前工作图'
  return route.name === 'materials' ? '素材库' : '分析记录'
})

const apiBaseLabel = computed(() => preferences.value.apiBaseUrl.replace(/^https?:\/\//, ''))

const backendConfigPreview = computed(() => {
  const host = backendConfigForm.host.trim() || '127.0.0.1'
  const port = backendConfigForm.port.trim() || '8000'
  return `http://${host}:${port}`
})

function parseApiBaseUrl(value: string) {
  try {
    const url = new URL(value)
    return {
      host: url.hostname || '127.0.0.1',
      port: url.port || '8000',
    }
  } catch {
    return {
      host: '127.0.0.1',
      port: '8000',
    }
  }
}

function handleNavigate(key: string | number) {
  const target = String(key) as NavItem['name']
  void router.push({
    name: target,
  })
}

function openBackendConfigModal() {
  const parsed = parseApiBaseUrl(preferences.value.apiBaseUrl)
  backendConfigForm.host = parsed.host
  backendConfigForm.port = parsed.port
  backendConfigModalVisible.value = true
}

function handleBackendConfigReset() {
  backendConfigForm.host = '127.0.0.1'
  backendConfigForm.port = '8000'
}

async function handleBackendConfigSave() {
  const host = backendConfigForm.host.trim() || '127.0.0.1'
  const parsedPort = Number.parseInt(backendConfigForm.port.trim(), 10)
  const port = Number.isFinite(parsedPort) && parsedPort > 0 ? String(parsedPort) : '8000'

  const apiBaseUrl = `http://${host}:${port}`
  if (apiBaseUrl !== preferences.value.apiBaseUrl) {
    if (graphLeaveGuard.value && !await graphLeaveGuard.value()) return false
    updatePreferences({ apiBaseUrl })
  }
  return true
}
</script>

<template>
  <a-config-provider size="small">
    <div class="app-shell">
      <header class="ocean-header">
        <div class="ocean-header__left">
          <div class="ocean-header__logo">
            <span class="ocean-header__logo-mark">RL</span>
            <span class="ocean-header__logo-text">RootLens</span>
          </div>
          <div class="ocean-header__divider" />
          <h1 class="ocean-header__title">
            <icon-dashboard />
            <span>{{ currentPageLabel }}</span>
          </h1>
        </div>
        <div class="ocean-header__right">
          <a-button
            type="text"
            class="ocean-header__api-base-trigger"
            aria-label="修改后端地址"
            @click="openBackendConfigModal"
          >
            <template #icon><icon-cloud /></template>
            {{ apiBaseLabel }}
          </a-button>
        </div>
        <a-tooltip :content="currentContextLabel">
          <div class="ocean-header__profile" aria-label="当前上下文">{{ currentContextLabel }}</div>
        </a-tooltip>
      </header>

      <a-layout class="ads-brain-workbench-layout" has-sider>
        <a-layout-sider
          class="app-sider-menu"
          :width="220"
          :collapsed-width="56"
          :collapsed="siderCollapsed"
          hide-trigger
          breakpoint="xl"
        >
          <a-menu
            class="app-sider-menu__menu"
            :selected-keys="[activeMenuKey]"
            :collapse="siderCollapsed"
            @menu-item-click="handleNavigate"
          >
            <a-menu-item v-for="item in navItems" :key="item.name">
              <template #icon>
                <component :is="item.icon" />
              </template>
              {{ item.label }}
            </a-menu-item>
          </a-menu>

          <a-button
            v-if="!isSavedAnalysis && !isWorkingGraph"
            type="text"
            shape="square"
            class="app-sider-menu__collapse-btn"
            :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="collapsed = !collapsed"
          >
            <IconMenuUnfold v-if="collapsed" />
            <IconMenuFold v-else />
          </a-button>
        </a-layout-sider>

        <a-layout-content class="ads-brain-workbench-layout__content" :class="{ 'workbench-content--saved-analysis': isSavedAnalysis, 'workbench-content--working-graph': isWorkingGraph }">
          <RouterView />
        </a-layout-content>
      </a-layout>

      <a-modal
        v-model:visible="backendConfigModalVisible"
        title="修改后端地址"
        width="420px"
        :on-before-ok="handleBackendConfigSave"
      >
        <a-form
          id="app-form-1"
          :model="backendConfigForm"
          layout="vertical"
          class="ocean-header__modal-stack workspace-form"
        >
          <a-form-item
            field="host"
            label="域名 / IP"
            :label-attrs="{ for: 'backend-backendConfigForm-host-input' }"
            class="workspace-form-item"
          >
            <a-input
              :input-attrs="{
                id: 'backend-backendConfigForm-host-input',
                'aria-label': '域名 / IP',
              }"
              id="backend-backendConfigForm-host"
              aria-label="域名 / IP"
              v-model="backendConfigForm.host"
              placeholder="127.0.0.1"
            />
          </a-form-item>
          <a-form-item
            field="port"
            label="端口"
            :label-attrs="{ for: 'backend-backendConfigForm-port-input' }"
            class="workspace-form-item"
          >
            <a-input
              :input-attrs="{ id: 'backend-backendConfigForm-port-input', 'aria-label': '端口' }"
              id="backend-backendConfigForm-port"
              aria-label="端口"
              v-model="backendConfigForm.port"
              placeholder="8000"
            />
          </a-form-item>
          <div class="workspace-claim-note workspace-claim-note--compact">
            <span class="workspace-summary-label">
              <icon-info-circle />
              <span>预览</span>
            </span>
            <strong>{{ backendConfigPreview }}</strong>
          </div>
          <div class="rl-form-actions rl-form-actions--dual">
            <a-button size="small" @click="handleBackendConfigReset">
              恢复默认 127.0.0.1:8000
            </a-button>
          </div>
        </a-form>
      </a-modal>
    </div>
  </a-config-provider>
</template>

<style scoped>
.workbench-content--saved-analysis,
.workbench-content--working-graph {
  display: flex;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  padding: 0;
}
</style>
