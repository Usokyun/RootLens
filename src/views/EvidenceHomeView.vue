<script setup lang="ts">
import { useAppPreferences } from '@/services/app-preferences'
import AnalysisRunsView from './AnalysisRunsView.vue'

const { preferences } = useAppPreferences()
</script>

<template>
  <AnalysisRunsView :key="preferences.apiBaseUrl" :base-url="preferences.apiBaseUrl" />
</template>
