import {
  DEFAULT_APP_PREFERENCES,
  getAppPreferences,
  resetAppPreferences,
  updateAppPreferences,
  useAppPreferences,
} from '@/services/app-preferences'
import { createApp, type App } from 'vue'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

const APP_PREFERENCES_STORAGE_KEY = 'rootlens.app-preferences'

describe('app preferences', () => {
  let app: App | undefined

  function mountPreferences() {
    let consumer!: ReturnType<typeof useAppPreferences>
    app = createApp({
      setup() {
        consumer = useAppPreferences()
        return () => null
      },
    })
    app.mount(document.createElement('div'))
    return consumer.preferences
  }

  function dispatchStorage(key: string | null, storageArea = window.localStorage) {
    // Vitest supplies a mock localStorage, not jsdom's native Storage instance.
    window.dispatchEvent(Object.assign(new Event('storage'), { key, storageArea }))
  }

  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    app?.unmount()
    app = undefined
  })

  it('persists data source mode and api base url updates', () => {
    updateAppPreferences({
      dataSourceMode: 'backend',
      apiBaseUrl: 'http://127.0.0.1:9000',
      showDebugPanels: true,
    })

    expect(getAppPreferences()).toMatchObject({
      dataSourceMode: 'backend',
      apiBaseUrl: 'http://127.0.0.1:9000',
      showDebugPanels: true,
    })
  })

  it('migrates stored legacy local backend ports to 8000', () => {
    window.localStorage.setItem(
      APP_PREFERENCES_STORAGE_KEY,
      JSON.stringify({
        dataSourceMode: 'backend',
        apiBaseUrl: 'http://127.0.0.1:8081',
      }),
    )

    expect(getAppPreferences().apiBaseUrl).toBe('http://127.0.0.1:8000')
  })

  it('preserves an explicit manual override to 8081', () => {
    updateAppPreferences({
      dataSourceMode: 'backend',
      apiBaseUrl: 'http://127.0.0.1:8081',
    })

    expect(getAppPreferences().apiBaseUrl).toBe('http://127.0.0.1:8081')
  })

  it('restores defaults after reset', () => {
    updateAppPreferences({
      dataSourceMode: 'backend',
      showDebugPanels: true,
    })

    expect(resetAppPreferences()).toEqual(DEFAULT_APP_PREFERENCES)
    expect(getAppPreferences()).toEqual(DEFAULT_APP_PREFERENCES)
    expect(getAppPreferences().apiBaseUrl).toBe('http://127.0.0.1:8000')
  })

  it('ignores another tab selecting a run and ignores sessionStorage events', () => {
    updateAppPreferences({ dataSourceMode: 'backend' })
    const preferences = mountPreferences()
    const before = preferences.value

    const selectionKey = 'rootlens.workbench-state'
    window.localStorage.setItem(selectionKey, JSON.stringify({ selectedRunId: 'another-run' }))
    dispatchStorage(selectionKey)
    dispatchStorage(APP_PREFERENCES_STORAGE_KEY, window.sessionStorage)

    expect(preferences.value).toBe(before)
  })

  it('syncs a changed backend address and a storage clear from another tab', () => {
    const preferences = mountPreferences()
    const apiBaseUrl = 'http://127.0.0.1:9000'
    window.localStorage.setItem(APP_PREFERENCES_STORAGE_KEY, JSON.stringify({
      schemaVersion: 2, dataSourceMode: 'backend', apiBaseUrl,
    }))
    dispatchStorage(APP_PREFERENCES_STORAGE_KEY)
    expect(preferences.value).toMatchObject({ dataSourceMode: 'backend', apiBaseUrl })

    window.localStorage.clear()
    dispatchStorage(null)
    expect(preferences.value).toEqual(DEFAULT_APP_PREFERENCES)
  })

  it('keeps preferences in sync between components in the same tab', () => {
    const preferences = mountPreferences()
    updateAppPreferences({ dataSourceMode: 'backend', showDebugPanels: true })
    expect(preferences.value).toMatchObject({ dataSourceMode: 'backend', showDebugPanels: true })
    resetAppPreferences()
    expect(preferences.value).toEqual(DEFAULT_APP_PREFERENCES)
  })
})
