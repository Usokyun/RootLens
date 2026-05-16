import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

export type DataSourceMode = 'mock' | 'backend'
export type AssetLayoutMode = 'grid' | 'list'

export interface AppPreferences {
  dataSourceMode: DataSourceMode
  apiBaseUrl: string
  assetLayoutMode: AssetLayoutMode
  autoSwitchAssetLayoutOnNarrowViewport: boolean
  enablePageEntranceMotion: boolean
  showDebugPanels: boolean
}

interface AppPreferencesApi {
  preferences: Ref<AppPreferences>
  updatePreferences: (patch: Partial<AppPreferences>) => void
  resetPreferences: () => void
}

const APP_PREFERENCES_STORAGE_KEY = 'rootlens.app-preferences'
const APP_PREFERENCES_UPDATED_EVENT = 'rootlens:app-preferences-updated'
const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001'

export const DEFAULT_APP_PREFERENCES: AppPreferences = {
  dataSourceMode: 'mock',
  apiBaseUrl: DEFAULT_API_BASE_URL,
  assetLayoutMode: 'grid',
  autoSwitchAssetLayoutOnNarrowViewport: true,
  enablePageEntranceMotion: true,
  showDebugPanels: false,
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function normalizeApiBaseUrl(value: unknown): string {
  if (typeof value !== 'string') {
    return DEFAULT_API_BASE_URL
  }

  const normalized = value.trim()
  return normalized.length ? normalized : DEFAULT_API_BASE_URL
}

function normalizeAppPreferences(candidate?: Partial<AppPreferences> | null): AppPreferences {
  return {
    dataSourceMode: candidate?.dataSourceMode === 'backend' ? 'backend' : 'mock',
    apiBaseUrl: normalizeApiBaseUrl(candidate?.apiBaseUrl),
    assetLayoutMode: candidate?.assetLayoutMode === 'list' ? 'list' : 'grid',
    autoSwitchAssetLayoutOnNarrowViewport: candidate?.autoSwitchAssetLayoutOnNarrowViewport !== false,
    enablePageEntranceMotion: candidate?.enablePageEntranceMotion !== false,
    showDebugPanels: candidate?.showDebugPanels === true,
  }
}

function readStoredAppPreferences(): AppPreferences {
  if (!canUseStorage()) {
    return { ...DEFAULT_APP_PREFERENCES }
  }

  try {
    const rawValue = window.localStorage.getItem(APP_PREFERENCES_STORAGE_KEY)
    if (!rawValue) {
      return { ...DEFAULT_APP_PREFERENCES }
    }

    return normalizeAppPreferences(JSON.parse(rawValue) as Partial<AppPreferences>)
  } catch {
    return { ...DEFAULT_APP_PREFERENCES }
  }
}

function writeStoredAppPreferences(preferences: AppPreferences) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(APP_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences))
  window.dispatchEvent(new CustomEvent(APP_PREFERENCES_UPDATED_EVENT))
}

export function getAppPreferencesEventName() {
  return APP_PREFERENCES_UPDATED_EVENT
}

export function getAppPreferences() {
  return readStoredAppPreferences()
}

export function updateAppPreferences(patch: Partial<AppPreferences>) {
  const nextPreferences = normalizeAppPreferences({
    ...readStoredAppPreferences(),
    ...patch,
  })

  writeStoredAppPreferences(nextPreferences)
  return nextPreferences
}

export function resetAppPreferences() {
  const nextPreferences = { ...DEFAULT_APP_PREFERENCES }
  writeStoredAppPreferences(nextPreferences)
  return nextPreferences
}

export function useAppPreferences(): AppPreferencesApi {
  const preferences = ref<AppPreferences>(readStoredAppPreferences())

  const syncPreferences = () => {
    preferences.value = readStoredAppPreferences()
  }

  onMounted(() => {
    window.addEventListener('storage', syncPreferences)
    window.addEventListener(APP_PREFERENCES_UPDATED_EVENT, syncPreferences as EventListener)
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.removeEventListener('storage', syncPreferences)
    window.removeEventListener(APP_PREFERENCES_UPDATED_EVENT, syncPreferences as EventListener)
  })

  return {
    preferences,
    updatePreferences(patch) {
      preferences.value = updateAppPreferences(patch)
    },
    resetPreferences() {
      preferences.value = resetAppPreferences()
    },
  }
}
