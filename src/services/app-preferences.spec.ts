import {
  DEFAULT_APP_PREFERENCES,
  getAppPreferences,
  resetAppPreferences,
  updateAppPreferences,
} from '@/services/app-preferences'
import { beforeEach, describe, expect, it } from 'vitest'

const APP_PREFERENCES_STORAGE_KEY = 'rootlens.app-preferences'

describe('app preferences', () => {
  beforeEach(() => {
    window.localStorage.clear()
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
})
