import {
  DEFAULT_APP_PREFERENCES,
  getAppPreferences,
  resetAppPreferences,
  updateAppPreferences,
} from '@/services/app-preferences'
import { beforeEach, describe, expect, it } from 'vitest'

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

  it('migrates legacy local backend ports to 8081', () => {
    updateAppPreferences({
      dataSourceMode: 'backend',
      apiBaseUrl: 'http://127.0.0.1:8001',
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
    expect(getAppPreferences().apiBaseUrl).toBe('http://127.0.0.1:8081')
  })
})
