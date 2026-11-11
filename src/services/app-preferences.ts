import { onBeforeUnmount, onMounted, ref } from 'vue'

export interface AppPreferences {
  apiBaseUrl: string
  enablePageEntranceMotion: boolean
}

const APP_PREFERENCES_STORAGE_KEY = 'rootlens.app-preferences'
const APP_PREFERENCES_UPDATED_EVENT = 'rootlens:app-preferences-updated'

export const DEFAULT_APP_PREFERENCES: AppPreferences = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  enablePageEntranceMotion: true,
}

function normalize(candidate?: Partial<AppPreferences> | null): AppPreferences {
  return {
    apiBaseUrl: typeof candidate?.apiBaseUrl === 'string' && candidate.apiBaseUrl.trim()
      ? candidate.apiBaseUrl.trim().replace(/\/+$/, '') : DEFAULT_APP_PREFERENCES.apiBaseUrl,
    enablePageEntranceMotion: candidate?.enablePageEntranceMotion !== false,
  }
}

export function getAppPreferences(): AppPreferences {
  try {
    return normalize(JSON.parse(window.localStorage.getItem(APP_PREFERENCES_STORAGE_KEY) ?? 'null'))
  } catch {
    return { ...DEFAULT_APP_PREFERENCES }
  }
}

export function updateAppPreferences(patch: Partial<AppPreferences>) {
  const preferences = normalize({ ...getAppPreferences(), ...patch })
  window.localStorage.setItem(APP_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences))
  window.dispatchEvent(new CustomEvent(APP_PREFERENCES_UPDATED_EVENT))
  return preferences
}

export function useAppPreferences() {
  const preferences = ref<AppPreferences>(getAppPreferences())

  const syncPreferences = () => { preferences.value = getAppPreferences() }
  function syncStoragePreferences(event: StorageEvent) {
    if ((event.key === APP_PREFERENCES_STORAGE_KEY || event.key === null) && event.storageArea === window.localStorage) {
      syncPreferences()
    }
  }

  onMounted(() => {
    window.addEventListener('storage', syncStoragePreferences)
    window.addEventListener(APP_PREFERENCES_UPDATED_EVENT, syncPreferences)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('storage', syncStoragePreferences)
    window.removeEventListener(APP_PREFERENCES_UPDATED_EVENT, syncPreferences)
  })

  return {
    preferences,
    updatePreferences(patch: Partial<AppPreferences>) { preferences.value = updateAppPreferences(patch) },
  }
}
