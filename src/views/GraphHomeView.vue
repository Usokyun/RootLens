<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppPreferences } from '@/services/app-preferences'
import { workingGraphLeaveGuardKey } from '@/services/working-graph-workspace'
import WorkingGraphWorkbenchView from './WorkingGraphWorkbenchView.vue'

const { preferences } = useAppPreferences()
const route = useRoute()
const guard = inject(workingGraphLeaveGuardKey, null)
const target = computed(() => preferences.value.apiBaseUrl)
const activeBackend = ref(target.value)
let sourceRevision = 0

async function adoptSource() {
  const revision = ++sourceRevision
  const next = target.value
  if (next === activeBackend.value || route.name !== 'graphs') return
  if (guard?.value && !await guard.value()) return
  if (revision !== sourceRevision || route.name !== 'graphs') return
  activeBackend.value = next
}
watch(target, adoptSource)
</script>

<template>
  <WorkingGraphWorkbenchView :key="activeBackend" :base-url="activeBackend"
    :connection-changed="activeBackend !== target" @switch-source="adoptSource" />
</template>
