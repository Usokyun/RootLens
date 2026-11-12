import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, type App } from 'vue'

import {
  getAppPreferencesEventName,
  updateAppPreferences,
  useAppPreferences,
} from '@/services/app-preferences'
import {
  getWorkbenchStateEventName,
  updateWorkbenchState,
  useWorkbenchState,
} from '@/services/workbench-state'

const preferencesKey = 'rootlens.app-preferences'
const workbenchKey = 'rootlens.workbench-state'
const mounted: Array<{ app: App; host: HTMLElement }> = []

function mountStore<T>(useStore: () => T): T {
  let store!: T
  const host = document.createElement('div')
  const app = createApp({
    setup() {
      store = useStore()
      return () => null
    },
  })
  document.body.append(host)
  app.mount(host)
  mounted.push({ app, host })
  return store
}

function storageEvent(key: string | null, area: Storage = window.localStorage) {
  // The project's localStorage mock is not a native jsdom Storage instance.
  const event = new Event('storage')
  Object.defineProperties(event, {
    key: { value: key },
    storageArea: { value: area },
  })
  window.dispatchEvent(event)
}

afterEach(() => {
  for (const { app, host } of mounted.splice(0)) {
    app.unmount()
    host.remove()
  }
  vi.restoreAllMocks()
})

describe('app preference synchronization', () => {
  it('ignores workbench and sessionStorage events instead of invalidating page preferences', () => {
    const { preferences } = mountStore(useAppPreferences)
    const before = preferences.value
    storageEvent(workbenchKey)
    storageEvent(preferencesKey, window.sessionStorage)
    expect(preferences.value).toBe(before)
  })

  it('keeps the same reactive value for duplicate notifications and no-op updates', () => {
    updateAppPreferences({ dataSourceMode: 'backend' })
    const store = mountStore(useAppPreferences)
    const before = store.preferences.value
    const notify = vi.fn()
    window.addEventListener(getAppPreferencesEventName(), notify)
    try {
      store.updatePreferences({ dataSourceMode: 'backend' })
      expect(notify).not.toHaveBeenCalled()
      window.dispatchEvent(new CustomEvent(getAppPreferencesEventName()))
      storageEvent(preferencesKey)
      expect(store.preferences.value).toBe(before)
    } finally {
      window.removeEventListener(getAppPreferencesEventName(), notify)
    }
  })

  it('synchronizes real changes to every mounted consumer', () => {
    const first = mountStore(useAppPreferences)
    const second = mountStore(useAppPreferences)
    first.updatePreferences({ apiBaseUrl: 'http://127.0.0.1:9001' })
    expect(first.preferences.value.apiBaseUrl).toBe('http://127.0.0.1:9001')
    expect(second.preferences.value.apiBaseUrl).toBe('http://127.0.0.1:9001')
  })

  it('reads cross-tab changes and handles storage.clear without emitting another update', () => {
    updateAppPreferences({ dataSourceMode: 'backend' })
    const store = mountStore(useAppPreferences)
    const notify = vi.fn()
    window.addEventListener(getAppPreferencesEventName(), notify)
    try {
      const payload = JSON.parse(window.localStorage.getItem(preferencesKey)!)
      window.localStorage.setItem(preferencesKey, JSON.stringify({ ...payload, assetLayoutMode: 'list' }))
      storageEvent(preferencesKey)
      expect(store.preferences.value.assetLayoutMode).toBe('list')
      window.localStorage.clear()
      storageEvent(null)
      expect(store.preferences.value.dataSourceMode).toBe('mock')
      expect(store.preferences.value.assetLayoutMode).toBe('grid')
      expect(notify).not.toHaveBeenCalled()
    } finally {
      window.removeEventListener(getAppPreferencesEventName(), notify)
    }
  })

  it('removes synchronization listeners when the consumer unmounts', () => {
    const store = mountStore(useAppPreferences)
    const before = store.preferences.value
    const consumer = mounted.pop()!
    consumer.app.unmount()
    consumer.host.remove()
    updateAppPreferences({ showDebugPanels: true })
    storageEvent(preferencesKey)
    expect(store.preferences.value).toBe(before)
  })
})

describe('workbench state synchronization', () => {
  it('ignores preferences and sessionStorage events instead of invalidating the selection', () => {
    const { state } = mountStore(useWorkbenchState)
    const before = state.value
    storageEvent(preferencesKey)
    storageEvent(workbenchKey, window.sessionStorage)
    expect(state.value).toBe(before)
  })

  it('does not write or broadcast an unchanged selection', () => {
    updateWorkbenchState({ selectedRunId: 'run-1', selectedCaseId: 'case-1' })
    const store = mountStore(useWorkbenchState)
    const before = store.state.value
    const notify = vi.fn()
    const write = vi.spyOn(window.localStorage, 'setItem')
    window.addEventListener(getWorkbenchStateEventName(), notify)
    try {
      store.updateState({ selectedRunId: 'run-1' })
      expect(write).not.toHaveBeenCalled()
      expect(notify).not.toHaveBeenCalled()
      window.dispatchEvent(new CustomEvent(getWorkbenchStateEventName()))
      storageEvent(workbenchKey)
      expect(store.state.value).toBe(before)
    } finally {
      window.removeEventListener(getWorkbenchStateEventName(), notify)
    }
  })

  it('synchronizes actual changes to every consumer without a notification echo', () => {
    const first = mountStore(useWorkbenchState)
    const second = mountStore(useWorkbenchState)
    const notify = vi.fn()
    window.addEventListener(getWorkbenchStateEventName(), notify)
    try {
      first.updateState({ selectedRunId: 'run-2' })
      expect(first.state.value.selectedRunId).toBe('run-2')
      expect(second.state.value.selectedRunId).toBe('run-2')
      expect(notify).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener(getWorkbenchStateEventName(), notify)
    }
  })

  it('applies a cross-tab selection once and resets after storage.clear', () => {
    const store = mountStore(useWorkbenchState)
    window.localStorage.setItem(workbenchKey, JSON.stringify({ selectedRunId: 'run-other-tab' }))
    storageEvent(workbenchKey)
    expect(store.state.value.selectedRunId).toBe('run-other-tab')
    const before = store.state.value
    storageEvent(workbenchKey)
    expect(store.state.value).toBe(before)
    window.localStorage.clear()
    storageEvent(null)
    expect(store.state.value.selectedRunId).toBeNull()
  })
})
