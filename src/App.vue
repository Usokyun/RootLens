<script setup lang="ts">
import {
  IconBulb,
  IconFile,
  IconFolder,
  IconMenuFold,
  IconMenuUnfold,
  IconRelation,
} from '@arco-design/web-vue/es/icon'
import type { Component } from 'vue'
import { computed, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

interface NavItem {
  name: 'materials' | 'evidence' | 'graphs'
  label: string
  icon: Component
}

const navItems: NavItem[] = [
  {
    name: 'evidence',
    label: '证据管理',
    icon: IconFile,
  },
  {
    name: 'graphs',
    label: '图谱探索',
    icon: IconRelation,
  },
  {
    name: 'materials',
    label: '素材管理',
    icon: IconFolder,
  },
]

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)

const activeMenuKey = computed(() => {
  const matched = navItems.find((item) => item.name === route.name)
  return matched?.name ?? 'evidence'
})

const pageLabel = computed(() => route.meta.label ?? '证据管理')
const pageDescription = computed(
  () => route.meta.description ?? '按重设计文档搭建前端骨架，后续再接入业务逻辑函数。',
)

function handleNavigate(key: string | number) {
  const target = String(key) as NavItem['name']
  void router.push({
    name: target,
  })
}
</script>

<template>
  <div class="app-shell">
    <header class="ocean-header">
      <div class="ocean-header__left">
        <button class="ocean-header__menu" type="button" aria-label="Application menu">
          <icon-bulb />
        </button>
        <div class="ocean-header__logo">
          <span class="ocean-header__logo-mark">RL</span>
          <span class="ocean-header__logo-text">RootLens</span>
        </div>
        <div class="ocean-header__divider" />
        <h1 class="ocean-header__title">RCA Workbench</h1>
      </div>
      <div class="ocean-header__right">
        <a-tag size="small" color="arcoblue">Arco Design</a-tag>
        <a-tag size="small">UI Redesign</a-tag>
      </div>
      <div class="ocean-header__profile">
        <div class="ocean-header__profile-label">Session</div>
        <div class="ocean-header__profile-value">demo</div>
      </div>
    </header>

    <a-layout class="ads-brain-workbench-layout" has-sider>
      <a-layout-sider
        class="app-sider-menu"
        :width="200"
        :collapsed-width="48"
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
        <section class="page-header-card">
          <div class="page-header-card__label">Workspace</div>
          <h2 class="page-header-card__title">{{ pageLabel }}</h2>
          <p class="page-header-card__desc">{{ pageDescription }}</p>
        </section>

        <RouterView />
      </a-layout-content>
    </a-layout>
  </div>
</template>
