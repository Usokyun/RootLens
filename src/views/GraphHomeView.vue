<script setup lang="ts">
import { computed, defineAsyncComponent, inject, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppPreferences } from '@/services/app-preferences'
import { graphRequest, useGraphReplay, workingGraphLeaveGuardKey } from '@/services/working-graph-workspace'

const WorkingGraphWorkbenchView = defineAsyncComponent(() => import('@/views/WorkingGraphWorkbenchView.vue'))
const GraphExploreView = defineAsyncComponent(() => import('@/views/GraphExploreView.vue'))
const { preferences } = useAppPreferences()
const replay = useGraphReplay()
const router = useRouter(), route = useRoute()
const guard = inject(workingGraphLeaveGuardKey, null)
const target = computed(() => preferences.value.dataSourceMode === 'backend' && !replay.value
  ? preferences.value.apiBaseUrl.trim().replace(/\/+$/, '') : null)
const activeBackend = ref(target.value)
let sourceRevision = 0

async function adoptSource() {
  const revision = ++sourceRevision
  const next = target.value
  if (next === activeBackend.value || route.name !== 'graphs') return
  if (guard?.value && !await guard.value()) return
  if (revision !== sourceRevision || route.name !== 'graphs') return
  // A deliberate switch out of Backend leaves the working-graph URL behind.
  if (next === null && graphRequest(route.query).kind !== 'default') await router.replace({ name: 'graphs' })
  else if (next !== null && activeBackend.value === null && graphRequest(route.query).kind === 'default' && route.query.run_id) {
    await router.replace({ name: 'graphs' })
  }
  if (revision === sourceRevision && route.name === 'graphs') activeBackend.value = next
}
watch(target, adoptSource)
</script>

<template>
  <WorkingGraphWorkbenchView v-if="activeBackend" :key="activeBackend" :base-url="activeBackend"
    :connection-changed="activeBackend !== target" @switch-source="adoptSource" />
  <GraphExploreView v-else />
</template>
