<script setup lang="ts">
import {
  IconApps,
  IconDesktop,
  IconInfoCircle,
  IconShrink,
  IconUnorderedList,
} from '@arco-design/web-vue/es/icon'

import type { AssetLayoutMode } from '@/composables/useResponsiveAssetLayoutMode'

defineProps<{
  value: AssetLayoutMode
  narrowViewport: boolean
}>()

const emit = defineEmits<{
  change: [value: AssetLayoutMode]
}>()
</script>

<template>
  <div class="collection-layout-toolbar">
    <div
      class="collection-layout-switch"
      :data-active-index="value === 'list' ? 1 : 0"
      role="tablist"
      aria-label="切换列表布局"
    >
      <span class="collection-layout-switch__thumb" aria-hidden="true" />

      <a-tooltip content="网格模式">
        <button
          type="button"
          class="collection-layout-switch__option"
          :class="{ 'collection-layout-switch__option--active': value === 'grid' }"
          role="tab"
          :aria-selected="value === 'grid'"
          aria-label="网格模式"
          @click="emit('change', 'grid')"
        >
          <icon-apps />
        </button>
      </a-tooltip>

      <a-tooltip content="列表模式">
        <button
          type="button"
          class="collection-layout-switch__option"
          :class="{ 'collection-layout-switch__option--active': value === 'list' }"
          role="tab"
          :aria-selected="value === 'list'"
          aria-label="列表模式"
          @click="emit('change', 'list')"
        >
          <icon-unordered-list />
        </button>
      </a-tooltip>
    </div>

    <a-tooltip
      :content="
        narrowViewport
          ? '当前窗口较窄，默认切到列表模式；你仍可以用切换按钮临时改回网格。'
          : '当前窗口足够宽，默认按你选择的布局展示。'
      "
    >
      <span
        class="collection-layout-toolbar__status"
        :class="{ 'collection-layout-toolbar__status--narrow': narrowViewport }"
      >
        <icon-shrink v-if="narrowViewport" />
        <icon-desktop v-else />
      </span>
    </a-tooltip>

    <a-tooltip content="窄屏自动切列表说明">
      <span class="collection-layout-toolbar__info">
        <icon-info-circle />
      </span>
    </a-tooltip>
  </div>
</template>

<style scoped>
.collection-layout-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.collection-layout-switch {
  position: relative;
  width: fit-content;
  border-radius: 12px;
  padding: 2px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px;
  background: rgba(16, 42, 67, 0.08);
  box-shadow: inset 0 0 0 1px rgba(16, 42, 67, 0.04);
  overflow: hidden;
}

.collection-layout-switch__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: calc(50% - 3px);
  height: calc(100% - 4px);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), #f5f9ff);
  box-shadow: 0 8px 18px rgba(22, 93, 255, 0.16);
  transition: transform 0.26s cubic-bezier(0.22, 1, 0.36, 1);
}

.collection-layout-switch[data-active-index='1'] .collection-layout-switch__thumb {
  transform: translateX(calc(100% + 2px));
}

.collection-layout-switch__option {
  position: relative;
  z-index: 1;
  width: 38px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
  background: transparent;
  color: #4e5969;
  cursor: pointer;
  transition: color 0.22s ease, transform 0.22s ease, background-color 0.22s ease;
}

.collection-layout-switch__option > svg {
  display: block;
  font-size: 15px;
  transition: transform 0.22s ease;
}

.collection-layout-switch__option:hover {
  transform: translateY(-1px);
}

.collection-layout-switch__option--active {
  color: #165dff;
}

.collection-layout-switch__option--active > svg {
  transform: scale(1.02);
}

.collection-layout-toolbar__status,
.collection-layout-toolbar__info {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #4e5969;
  background: rgba(16, 42, 67, 0.06);
  box-shadow: inset 0 0 0 1px rgba(16, 42, 67, 0.04);
  transition: transform 0.18s ease, color 0.18s ease, background-color 0.18s ease;
}

.collection-layout-toolbar__status--narrow {
  color: #b45309;
  background: rgba(245, 158, 11, 0.12);
}

.collection-layout-toolbar__status:hover,
.collection-layout-toolbar__info:hover {
  transform: translateY(-1px);
}
</style>
