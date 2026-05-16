<script setup lang="ts">
import {
  IconApps,
  IconCloud,
  IconBulb,
  IconDashboard,
  IconExperiment,
  IconMenuFold,
  IconMenuUnfold,
  IconRelation,
  IconStorage,
} from '@arco-design/web-vue/es/icon'
import type { Component } from 'vue'
import { computed, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useAppPreferences } from '@/services/app-preferences'
import { useWorkbenchState } from '@/services/workbench-state'

interface NavItem {
  name: 'materials' | 'evidence' | 'graphs'
  label: string
  icon: Component
}

const navItems: NavItem[] = [
  {
    name: 'evidence',
    label: '证据与审阅',
    icon: IconDashboard,
  },
  {
    name: 'graphs',
    label: '图谱探索',
    icon: IconRelation,
  },
  {
    name: 'materials',
    label: '图谱工坊',
    icon: IconExperiment,
  },
]

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)
const { preferences, updatePreferences } = useAppPreferences()
const { state: workbenchState } = useWorkbenchState()

const sourceModeOptions = [
  { value: 'mock', label: 'Mock', icon: IconStorage },
  { value: 'backend', label: 'Backend', icon: IconCloud },
] as const

const activeMenuKey = computed(() => {
  const matched = navItems.find((item) => item.name === route.name)
  return matched?.name ?? 'evidence'
})

const currentPageLabel = computed(() => {
  return typeof route.meta.label === 'string' ? route.meta.label : 'RootLens 工作台'
})

const currentContextLabel = computed(() => {
  return [workbenchState.value.selectedRunId, workbenchState.value.selectedCaseId].filter(Boolean).join(' / ') || '未选择上下文'
})

const apiBaseLabel = computed(() => {
  if (preferences.value.dataSourceMode === 'mock') {
    return '内置资产'
  }

  return preferences.value.apiBaseUrl.replace(/^https?:\/\//, '')
})

function handleNavigate(key: string | number) {
  const target = String(key) as NavItem['name']
  void router.push({
    name: target,
  })
}

function handleSourceModeChange(mode: 'mock' | 'backend') {
  updatePreferences({
    dataSourceMode: mode,
  })
}
</script>

<template>
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
        <div class="ocean-header__mode-toggle" role="tablist" aria-label="切换数据源模式">
          <button
            v-for="item in sourceModeOptions"
            :key="item.value"
            type="button"
            class="ocean-header__mode-toggle-button"
            :class="{
              'ocean-header__mode-toggle-button--active': preferences.dataSourceMode === item.value,
            }"
            @click="handleSourceModeChange(item.value)"
          >
            <component :is="item.icon" />
            <span>{{ item.label }}</span>
          </button>
        </div>
        <a-tag size="small" color="arcoblue">
          <icon-apps />
          <span>{{ preferences.dataSourceMode === 'backend' ? '后端模式' : '模拟模式' }}</span>
        </a-tag>
        <a-tag size="small" color="green">
          <icon-bulb />
          <span>{{ apiBaseLabel }}</span>
        </a-tag>
      </div>
      <div class="ocean-header__profile">
        <div class="ocean-header__profile-label">当前上下文</div>
        <div class="ocean-header__profile-value">
          {{ currentContextLabel }}
        </div>
      </div>
    </header>

    <a-layout class="ads-brain-workbench-layout" has-sider>
      <a-layout-sider
        class="app-sider-menu"
        :width="220"
        :collapsed-width="56"
        :collapsed="collapsed"
        hide-trigger
        breakpoint="xl"
      >
        <a-menu
          class="app-sider-menu__menu"
          :selected-keys="[activeMenuKey]"
          :collapse="collapsed"
          @menu-item-click="handleNavigate"
        >
          <a-menu-item v-for="item in navItems" :key="item.name">
            <template #icon>
              <component :is="item.icon" />
            </template>
            {{ item.label }}
          </a-menu-item>
        </a-menu>

        <button
          type="button"
          class="app-sider-menu__collapse-btn"
          :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="collapsed = !collapsed"
        >
          <icon-menu-unfold v-if="collapsed" />
          <icon-menu-fold v-else />
        </button>
      </a-layout-sider>

      <a-layout-content class="ads-brain-workbench-layout__content">
        <RouterView />
      </a-layout-content>
    </a-layout>
  </div>
</template>
