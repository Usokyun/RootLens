import { afterEach, describe, expect, it, vi } from 'vitest'

import { changeMaterialArchive, listArchivedMaterials } from '@/api/material-archive'

const base = 'https://material-fixture.test'
afterEach(() => vi.unstubAllGlobals())

describe('material archive transport', () => {
  it('keeps the archived collection separate from active materials', async () => {
    const response = { materials: [{ material_id: 'm', archived_at: '2026-11-11T00:00:00Z' }] }
    const fetcher = vi.fn(async () => new Response(JSON.stringify(response)))
    vi.stubGlobal('fetch', fetcher)
    expect(await listArchivedMaterials(base)).toEqual(response)
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(base + '/api/kg/materials?archived=true', undefined)
  })

  it.each(['archive', 'restore'] as const)('posts %s only for the exact material identity', async (action) => {
    const response = { material: { material_id: 'm', archived_at: action === 'archive' ? '2026-11-11T00:00:00Z' : null } }
    const fetcher = vi.fn(async () => new Response(JSON.stringify(response)))
    vi.stubGlobal('fetch', fetcher)
    expect(await changeMaterialArchive(base, 'm', action)).toEqual(response)
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(base + '/api/kg/materials/m/' + action, { method: 'POST' })
  })

  it('preserves the server conflict and does not replay the archive request', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ detail: '该素材正被构图任务使用。' }), { status: 409 }))
    vi.stubGlobal('fetch', fetcher)
    await expect(changeMaterialArchive(base, 'm', 'archive')).rejects.toMatchObject({
      status: 409, message: '该素材正被构图任务使用。',
    })
    expect(fetcher).toHaveBeenCalledOnce()
  })
})
