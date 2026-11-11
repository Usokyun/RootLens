<script setup lang="ts">
import { Message } from '@arco-design/web-vue'
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAppPreferences } from '@/services/app-preferences'
import { getLocalSessionEventName, getLocalSessionMeta } from '@/services/rootlens-data'

const AnalysisRunsView = defineAsyncComponent(() => import('@/views/AnalysisRunsView.vue'))
const EvidenceManageView = defineAsyncComponent(() => import('@/views/EvidenceManageView.vue'))
const ReplayImportDialog = defineAsyncComponent(() => import('@/components/evidence/ReplayImportDialog.vue'))
const { preferences } = useAppPreferences()
const replay = ref(getLocalSessionMeta()?.source === 'import')
const replayDialog = ref(false)
const updateReplay = () => { replay.value = getLocalSessionMeta()?.source === 'import' }
const live = computed(() => preferences.value.dataSourceMode === 'backend' && !replay.value)
onMounted(() => window.addEventListener(getLocalSessionEventName(), updateReplay))
onBeforeUnmount(() => window.removeEventListener(getLocalSessionEventName(), updateReplay))
</script>

<template>
  <AnalysisRunsView v-if="live" :key="preferences.apiBaseUrl" :base-url="preferences.apiBaseUrl" @import-replay="replayDialog = true" />
  <EvidenceManageView v-else @import-replay="replayDialog = true" />
  <ReplayImportDialog v-if="replayDialog" v-model:visible="replayDialog" @imported="Message.success($event)" />
</template>
