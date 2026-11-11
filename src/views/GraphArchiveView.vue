<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRouter } from 'vue-router'
import { useAppPreferences } from '@/services/app-preferences'
import { useGraphReplay } from '@/services/working-graph-workspace'

const GraphExploreView = defineAsyncComponent(() => import('@/views/GraphExploreView.vue'))
const { preferences, updatePreferences } = useAppPreferences()
const replay = useGraphReplay()
const router = useRouter()
const available = computed(() => preferences.value.dataSourceMode === 'backend' && !replay.value)
</script>

<template>
  <section class="rl-page rl-screen" aria-label="旧运行档案">
    <div class="rl-form-actions" style="margin-bottom: 10px">
      <a-button type="text" @click="router.push({ name: 'graphs' })">返回工作图</a-button>
      <span class="workspace-subtle">旧运行档案 · 只读</span>
    </div>
    <GraphExploreView v-if="available" archive-only />
    <a-alert v-else type="info">
      {{ replay ? '请先在运行与证据退出回放，再查看后端旧运行。' : '旧运行保存在后端。请切换到 Backend。' }}
      <a-button v-if="!replay" size="mini" type="text" @click="updatePreferences({ dataSourceMode: 'backend' })">切换 Backend</a-button>
    </a-alert>
  </section>
</template>
