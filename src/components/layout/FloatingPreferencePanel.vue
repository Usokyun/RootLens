<script setup lang="ts">
import {
  IconApps,
  IconCloud,
  IconInfoCircle,
  IconList,
  IconRight,
  IconSettings,
  IconStorage,
} from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { useAppPreferences } from '@/services/app-preferences'

const DESKTOP_BREAKPOINT = 960
const PANEL_ID = 'rootlens-floating-preferences'

const { preferences, updatePreferences, resetPreferences } = useAppPreferences()
const desktop = ref(typeof window === 'undefined' || window.innerWidth > DESKTOP_BREAKPOINT)
const open = ref(false)
const panelRef = ref<HTMLElement | null>(null)

const modeOptions = [
  { value: 'mock', label: '模拟', icon: IconStorage },
  { value: 'backend', label: '后端', icon: IconCloud },
] as const

const layoutOptions = [
  { value: 'grid', label: '网格', icon: IconApps },
  { value: 'list', label: '列表', icon: IconList },
] as const

const sourceModeLabel = computed(() =>
  preferences.value.dataSourceMode === 'backend' ? '真实后端接口' : '内置模拟数据链路',
)

function handleApiBaseChange(value: string | number | undefined) {
  updatePreferences({ apiBaseUrl: String(value ?? '') })
}

function handleBooleanPreference(
  key: 'autoSwitchAssetLayoutOnNarrowViewport' | 'enablePageEntranceMotion' | 'showDebugPanels',
  value: string | number | boolean,
) {
  updatePreferences({ [key]: Boolean(value) })
}

function syncViewport() {
  if (typeof window === 'undefined') {
    return
  }

  desktop.value = window.innerWidth > DESKTOP_BREAKPOINT
}

function handlePointerDown(event: PointerEvent) {
  if (!open.value) {
    return
  }

  if (panelRef.value?.contains(event.target as Node)) {
    return
  }

  open.value = false
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    open.value = false
  }
}

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
  window.addEventListener('pointerdown', handlePointerDown)
  window.addEventListener('keydown', handleKeyDown)
})

onBeforeUnmount(() => {
  if (typeof window === 'undefined') {
    return
  }

  window.removeEventListener('resize', syncViewport)
  window.removeEventListener('pointerdown', handlePointerDown)
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div
    ref="panelRef"
    class="floating-preference-panel"
    :class="{
      'floating-preference-panel--open': open,
      'floating-preference-panel--desktop': desktop,
    }"
  >
    <div class="floating-preference-panel__shell">
      <button
        type="button"
        class="floating-preference-panel__handle"
        :aria-expanded="open"
        :aria-controls="PANEL_ID"
        :aria-label="open ? '收起偏好设置' : '打开偏好设置'"
        @click="open = !open"
      >
        <span class="floating-preference-panel__handle-icon">
          <icon-settings />
        </span>
        <span
          class="floating-preference-panel__handle-arrow"
          :class="{ 'floating-preference-panel__handle-arrow--open': open }"
          aria-hidden="true"
        >
          <icon-right />
        </span>
      </button>

      <section :id="PANEL_ID" class="floating-preference-panel__surface" aria-label="偏好设置">
        <header class="floating-preference-panel__header">
          <div>
            <h3 class="floating-preference-panel__title">偏好设置</h3>
            <p class="floating-preference-panel__subtitle">{{ sourceModeLabel }}</p>
          </div>
          <a-button size="mini" @click="resetPreferences">恢复默认</a-button>
        </header>

        <div class="floating-preference-panel__content">
          <section class="floating-preference-panel__section">
            <div class="floating-preference-panel__section-heading">
              <span class="floating-preference-panel__section-label">数据源模式</span>
              <a-tooltip content="模拟模式使用仓库内置运行数据；后端模式直接调用 handoff 文档定义的 API。">
                <span class="floating-preference-panel__info"><icon-info-circle /></span>
              </a-tooltip>
            </div>
            <div class="floating-preference-panel__toggle" role="tablist" aria-label="切换数据源模式">
              <button
                v-for="item in modeOptions"
                :key="item.value"
                type="button"
                class="floating-preference-panel__toggle-option"
                :class="{
                  'floating-preference-panel__toggle-option--active':
                    preferences.dataSourceMode === item.value,
                }"
                @click="updatePreferences({ dataSourceMode: item.value })"
              >
                <span class="floating-preference-panel__toggle-option-icon">
                  <component :is="item.icon" />
                </span>
                <span class="floating-preference-panel__toggle-option-text">{{ item.label }}</span>
              </button>
            </div>
          </section>

          <section class="floating-preference-panel__section">
            <div class="floating-preference-panel__section-heading">
              <span class="floating-preference-panel__section-label">后端地址</span>
              <a-tooltip content="后端模式会使用这里的地址；默认值指向本地 FastAPI 8000 端口。">
                <span class="floating-preference-panel__info"><icon-info-circle /></span>
              </a-tooltip>
            </div>
            <a-input
              :model-value="preferences.apiBaseUrl"
              placeholder="http://127.0.0.1:8000"
              @change="handleApiBaseChange"
            />
          </section>

          <section class="floating-preference-panel__section">
            <div class="floating-preference-panel__section-heading">
              <span class="floating-preference-panel__section-label">素材默认布局</span>
            </div>
            <div class="floating-preference-panel__toggle" role="tablist" aria-label="切换素材布局">
              <button
                v-for="item in layoutOptions"
                :key="item.value"
                type="button"
                class="floating-preference-panel__toggle-option"
                :class="{
                  'floating-preference-panel__toggle-option--active':
                    preferences.assetLayoutMode === item.value,
                }"
                @click="updatePreferences({ assetLayoutMode: item.value })"
              >
                <span class="floating-preference-panel__toggle-option-icon">
                  <component :is="item.icon" />
                </span>
                <span class="floating-preference-panel__toggle-option-text">{{ item.label }}</span>
              </button>
            </div>
          </section>

          <section class="floating-preference-panel__section floating-preference-panel__section--split">
            <div>
              <div class="floating-preference-panel__section-heading">
                <span class="floating-preference-panel__section-label">窄屏自动切列表</span>
              </div>
              <p class="floating-preference-panel__hint">小屏默认转列表，避免工作台被压坏。</p>
            </div>
            <a-switch
              :model-value="Boolean(preferences.autoSwitchAssetLayoutOnNarrowViewport)"
              @change="(value) => handleBooleanPreference('autoSwitchAssetLayoutOnNarrowViewport', value)"
            />
          </section>

          <section class="floating-preference-panel__section floating-preference-panel__section--split">
            <div>
              <div class="floating-preference-panel__section-heading">
                <span class="floating-preference-panel__section-label">页面渐入效果</span>
              </div>
              <p class="floating-preference-panel__hint">关闭后保留静态切换，方便联调和录屏。</p>
            </div>
            <a-switch
              :model-value="Boolean(preferences.enablePageEntranceMotion)"
              @change="(value) => handleBooleanPreference('enablePageEntranceMotion', value)"
            />
          </section>

          <section class="floating-preference-panel__section floating-preference-panel__section--split">
            <div>
              <div class="floating-preference-panel__section-heading">
                <span class="floating-preference-panel__section-label">调试面板</span>
              </div>
              <p class="floating-preference-panel__hint">打开后显示更多运行与构建的原始对象。</p>
            </div>
            <a-switch
              :model-value="Boolean(preferences.showDebugPanels)"
              @change="(value) => handleBooleanPreference('showDebugPanels', value)"
            />
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.floating-preference-panel {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 40;
}

.floating-preference-panel__shell {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
}

.floating-preference-panel__handle {
  width: 54px;
  border: 0;
  border-radius: 18px;
  padding: 14px 0 12px;
  display: grid;
  gap: 10px;
  justify-items: center;
  background: linear-gradient(180deg, #0d1b2a, #1b263b);
  color: #fff;
  box-shadow: 0 20px 42px rgba(15, 23, 42, 0.3);
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.floating-preference-panel__handle:hover {
  transform: translateY(-1px);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.34);
}

.floating-preference-panel__handle-icon {
  display: inline-flex;
  font-size: 20px;
}

.floating-preference-panel__handle-arrow {
  display: inline-flex;
  transition: transform 0.22s ease;
}

.floating-preference-panel__handle-arrow--open {
  transform: rotate(180deg);
}

.floating-preference-panel__surface {
  position: absolute;
  right: 66px;
  bottom: 0;
  width: min(360px, calc(100vw - 32px));
  border: 1px solid rgba(13, 27, 42, 0.12);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 28px 60px rgba(15, 23, 42, 0.18);
  padding: 16px;
  opacity: 0;
  pointer-events: none;
  transform: translateY(12px) scale(0.98);
  transform-origin: bottom right;
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.floating-preference-panel--open .floating-preference-panel__surface {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0) scale(1);
}

.floating-preference-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.floating-preference-panel__title {
  margin: 0;
  font-size: 18px;
  color: #102a43;
}

.floating-preference-panel__subtitle {
  margin: 4px 0 0;
  color: #52606d;
  font-size: 12px;
  line-height: 1.5;
}

.floating-preference-panel__content {
  margin-top: 14px;
  display: grid;
  gap: 12px;
}

.floating-preference-panel__section {
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(247, 250, 255, 0.94), rgba(242, 246, 252, 0.96));
  padding: 12px;
}

.floating-preference-panel__section--split {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.floating-preference-panel__section-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.floating-preference-panel__section-label {
  color: #102a43;
  font-size: 13px;
  font-weight: 700;
}

.floating-preference-panel__hint {
  margin: 0;
  color: #52606d;
  font-size: 12px;
  line-height: 1.5;
}

.floating-preference-panel__info {
  display: inline-flex;
  color: #7b8794;
  cursor: help;
}

.floating-preference-panel__toggle {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.floating-preference-panel__toggle-option {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 14px;
  padding: 10px 12px;
  background: #fff;
  color: #334e68;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    box-shadow 0.22s ease,
    color 0.22s ease,
    background-color 0.22s ease;
}

.floating-preference-panel__toggle-option:hover {
  transform: translateY(-1px);
  border-color: rgba(59, 130, 246, 0.28);
  box-shadow: 0 10px 20px rgba(59, 130, 246, 0.08);
}

.floating-preference-panel__toggle-option--active {
  border-color: rgba(59, 130, 246, 0.42);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.96), rgba(230, 240, 255, 0.94));
  color: #1d4ed8;
  box-shadow: 0 10px 22px rgba(59, 130, 246, 0.12);
}

.floating-preference-panel__toggle-option-icon {
  display: inline-flex;
  font-size: 15px;
}

.floating-preference-panel__toggle-option-text {
  font-weight: 700;
  letter-spacing: 0.02em;
}

@media (max-width: 960px) {
  .floating-preference-panel {
    right: 12px;
    bottom: 12px;
  }

  .floating-preference-panel__surface {
    right: 0;
    bottom: 66px;
  }
}
</style>
