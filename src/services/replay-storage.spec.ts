import { beforeEach, describe, expect, it, vi } from 'vitest'

const stored = vi.hoisted(() => new Map<string, unknown>())
vi.mock('@/services/replay-asset-store', () => ({
  storeReplayRuntime: vi.fn(async (key: string, value: unknown) => { stored.set(key, value) }),
  readReplayRuntime: vi.fn(async (key: string) => stored.get(key)),
}))

const runtime = (large = false) => ({ schema_version: 'rootlens-runtime.v1',
  generated_at: '2026-11-10T00:00:00Z', generator: large ? 'x'.repeat(1_600_000) : 'small', cases: [] })

describe('durable replay storage', () => {
  beforeEach(() => { localStorage.clear(); stored.clear(); vi.resetModules(); vi.clearAllMocks() })

  it('stores large payloads in IndexedDB and hydrates after a page/module restart', async () => {
    let data = await import('@/services/rootlens-data')
    const payload = runtime(true)
    await data.saveImportedSession({ graphs: null, runtime: payload })
    expect(localStorage.getItem('rootlens.local.runtime')).toBeNull()
    expect(data.getLocalSessionMeta()?.runtimeAssetKey).toBeTruthy()
    vi.resetModules()
    data = await import('@/services/rootlens-data')
    expect(data.getStoredImportedRuntime()).toBeNull()
    expect(await data.loadStoredImportedRuntime()).toEqual(payload)
  })

  it('keeps the old session when large asset persistence fails', async () => {
    const data = await import('@/services/rootlens-data')
    const assets = await import('@/services/replay-asset-store')
    await data.saveImportedSession({ graphs: null, runtime: runtime(), summary: 'old session' })
    vi.mocked(assets.storeReplayRuntime).mockRejectedValueOnce(new Error('quota'))
    await expect(data.saveImportedSession({ graphs: null, runtime: runtime(true) })).rejects.toThrow('quota')
    expect(data.getLocalSessionMeta()?.summary).toBe('old session')
    expect(data.getStoredImportedRuntime()?.generator).toBe('small')
  })
})
