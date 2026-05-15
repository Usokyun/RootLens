import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  getAppPreferences,
  getAppPreferencesEventName,
  updateAppPreferences,
  type AssetLayoutMode,
} from '@/services/app-preferences'

export type { AssetLayoutMode } from '@/services/app-preferences'

export const ASSET_LAYOUT_AUTO_SWITCH_BREAKPOINT = 1360

export function useResponsiveAssetLayoutMode() {
  const assetLayoutMode = ref<AssetLayoutMode>(getAppPreferences().assetLayoutMode)
  const autoSwitchEnabled = ref(getAppPreferences().autoSwitchAssetLayoutOnNarrowViewport)
  const narrowViewport = ref(
    typeof window !== 'undefined' && window.innerWidth <= ASSET_LAYOUT_AUTO_SWITCH_BREAKPOINT,
  )
  const narrowViewportLayoutOverride = ref<AssetLayoutMode | null>(null)

  const syncViewport = () => {
    if (typeof window === 'undefined') {
      return
    }

    narrowViewport.value = window.innerWidth <= ASSET_LAYOUT_AUTO_SWITCH_BREAKPOINT
  }

  const syncPreferences = () => {
    const preferences = getAppPreferences()
    assetLayoutMode.value = preferences.assetLayoutMode
    autoSwitchEnabled.value = preferences.autoSwitchAssetLayoutOnNarrowViewport
  }

  onMounted(() => {
    syncViewport()
    syncPreferences()
    window.addEventListener('resize', syncViewport)
    window.addEventListener(getAppPreferencesEventName(), syncPreferences as EventListener)
    window.addEventListener('storage', syncPreferences)
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.removeEventListener('resize', syncViewport)
    window.removeEventListener(getAppPreferencesEventName(), syncPreferences as EventListener)
    window.removeEventListener('storage', syncPreferences)
  })

  watch(narrowViewport, (value) => {
    if (!value) {
      narrowViewportLayoutOverride.value = null
    }
  })

  const effectiveAssetLayoutMode = computed<AssetLayoutMode>(() => {
    if (!autoSwitchEnabled.value || !narrowViewport.value) {
      return assetLayoutMode.value
    }

    return narrowViewportLayoutOverride.value ?? 'list'
  })

  function setAssetLayoutMode(nextMode: AssetLayoutMode) {
    assetLayoutMode.value = nextMode
    updateAppPreferences({ assetLayoutMode: nextMode })

    if (autoSwitchEnabled.value && narrowViewport.value) {
      narrowViewportLayoutOverride.value = nextMode
      return
    }

    narrowViewportLayoutOverride.value = null
  }

  return {
    assetLayoutMode,
    effectiveAssetLayoutMode,
    narrowViewport,
    autoSwitchEnabled,
    setAssetLayoutMode,
  }
}
