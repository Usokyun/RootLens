import fs from 'node:fs'
import path from 'node:path'

import { beforeEach, describe, expect, it, vi } from 'vitest'

const repoRoot = process.cwd()
const curatedCaseIds = [
  'mvtec_fixture_clean_scratch',
  'mvtec_noisy_0001',
  'tep_0001',
  'wafer_0001',
]

function installGeneratedAssetFetchStub() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL | Request) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url
      const relativePath = url.startsWith('/') ? url.slice(1) : url
      const filePath = path.join(repoRoot, relativePath.startsWith('generated/') ? 'public' : '', relativePath)

      if (!fs.existsSync(filePath)) {
        return {
          ok: false,
          status: 404,
          json: async () => ({}),
          text: async () => '',
        }
      }

      const body = fs.readFileSync(filePath, 'utf8')
      return {
        ok: true,
        status: 200,
        json: async () => JSON.parse(body),
        text: async () => body,
      }
    }),
  )
}

describe('mock backend paper demo mode', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetModules()
    vi.unstubAllGlobals()
    installGeneratedAssetFetchStub()
  })

  it('returns exactly one curated demo run with the four paper cases', async () => {
    const { mockBackend } = await import('@/services/mock-backend')

    const runs = await mockBackend.listRuns()
    expect(runs).toHaveLength(1)
    expect(runs[0].run_id).toBe('paper-demo-curated')

    const detail = await mockBackend.getRun(runs[0].run_id)
    expect(detail.cases.map((item) => item.case_id)).toEqual(curatedCaseIds)
  })

  it('rejects uploads in mock mode', async () => {
    const { mockBackend } = await import('@/services/mock-backend')

    await expect(
      mockBackend.uploadRun({
        file: new File(['{}'], 'demo.json', { type: 'application/json' }),
        mode: 'evidence',
        top_k: 5,
      }),
    ).rejects.toThrow('论文演示 mock 模式不支持上传')
  })


  it('uses imported runtime sessions as the active replay run source', async () => {
    const [{ loadBundledRootLensRuntime, saveImportedSession }, { mockBackend }] = await Promise.all([
      import('@/services/rootlens-data'),
      import('@/services/mock-backend'),
    ])

    const bundledRuntime = await loadBundledRootLensRuntime()
    saveImportedSession({
      graphs: null,
      runtime: {
        ...bundledRuntime,
        generator: 'browser-import',
        cases: bundledRuntime.cases.slice(0, 1),
      },
      summary: '导入回放测试',
    })

    const runs = await mockBackend.listRuns()
    expect(runs).toHaveLength(1)
    expect(runs[0].run_id).toBe('imported-runtime-replay')

    const detail = await mockBackend.getRun(runs[0].run_id)
    expect(detail.cases).toHaveLength(1)
    expect(detail.run.label).toContain('导入回放测试')
  })

})
