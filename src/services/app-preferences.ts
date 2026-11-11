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
const APP_PREFERENCES_STORAGE_VERSION = 2
const APP_PREFERENCES_UPDATED_EVENT = 'rootlens:app-preferences-updated'

interface StoredAppPreferences extends Partial<AppPreferences> {
  schemaVersion?: number
}
const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const LEGACY_LOCAL_API_BASE_URLS = new Set([
  'http://127.0.0.1:8081',
  'http://localhost:8081',
  'http://127.0.0.1:8001',
  'http://localhost:8001',
])

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

function normalizeApiBaseUrl(
  value: unknown,
  options?: { migrateLegacyLocalUrls?: boolean },
): string {
  if (typeof value !== 'string') {
    return DEFAULT_API_BASE_URL
  }

  const normalized = value.trim()
  if (!normalized.length) {
    return DEFAULT_API_BASE_URL
  }

  if (options?.migrateLegacyLocalUrls && LEGACY_LOCAL_API_BASE_URLS.has(normalized)) {
    return DEFAULT_API_BASE_URL
  }

  return normalized
}

function normalizeAppPreferences(
  candidate?: Partial<AppPreferences> | null,
  options?: { migrateLegacyLocalUrls?: boolean },
): AppPreferences {
  return {
    dataSourceMode: candidate?.dataSourceMode === 'backend' ? 'backend' : 'mock',
    apiBaseUrl: normalizeApiBaseUrl(candidate?.apiBaseUrl, options),
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

    const parsed = JSON.parse(rawValue) as StoredAppPreferences
    const nextPreferences = normalizeAppPreferences(parsed, {
      migrateLegacyLocalUrls: (parsed.schemaVersion ?? 0) < APP_PREFERENCES_STORAGE_VERSION,
    })

    if ((parsed.schemaVersion ?? 0) < APP_PREFERENCES_STORAGE_VERSION) {
      writeStoredAppPreferences(nextPreferences)
    }

    return nextPreferences
  } catch {
    return { ...DEFAULT_APP_PREFERENCES }
  }
}

function writeStoredAppPreferences(preferences: AppPreferences) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.setItem(
    APP_PREFERENCES_STORAGE_KEY,
    JSON.stringify({
      ...preferences,
      schemaVersion: APP_PREFERENCES_STORAGE_VERSION,
    } satisfies StoredAppPreferences),
  )
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
