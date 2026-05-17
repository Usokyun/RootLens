import { readFileSync } from 'node:fs'

import { parseRootLensRuntimeFile, parseUnifiedGraphsFile } from '@/contracts/runtime'
import { buildLocalImportResult } from '@/services/browser-runtime'
import { describe, expect, it } from 'vitest'

function readJsonFixture<T>(relativePath: string): T {
  return JSON.parse(readFileSync(new URL(relativePath, import.meta.url), 'utf8')) as T
}

function clone<T>(value: T): T {
  return structuredClone(value)
}

const demoGraphs = parseUnifiedGraphsFile(
  readJsonFixture('../../public/generated/unified-graphs.json'),
)
const demoRuntime = parseRootLensRuntimeFile(
  readJsonFixture('../../public/generated/rootlens-runtime.json'),
)

function createJsonFile(name: string, payload: unknown): File {
  const content = JSON.stringify(payload, null, 2)

  return {
    name,
    size: content.length,
    type: 'application/json',
    webkitRelativePath: '',
    text: async () => content,
  } as File
}

describe('buildLocalImportResult', () => {
  it('imports runtime and graphs as a finished replay bundle', async () => {
    const result = await buildLocalImportResult([
      createJsonFile('rootlens-runtime.json', clone(demoRuntime)),
      createJsonFile('unified-graphs.json', clone(demoGraphs)),
    ])

    expect(result.summary.sourceMode).toBe('runtime')
    expect(result.summary.cases).toHaveLength(demoRuntime.cases.length)
    expect(result.summary.datasets).toHaveLength(demoGraphs.datasets.length)
    expect(result.runtime?.cases[0]?.case_id).toBe(demoRuntime.cases[0]?.case_id)
  })

  it('rejects incomplete replay assets', async () => {
    await expect(
      buildLocalImportResult([createJsonFile('unified-graphs.json', clone(demoGraphs))]),
    ).rejects.toThrow(
      '当前版本仅支持完整回放导入：请同时选择 rootlens-runtime.json 与 unified-graphs.json。',
    )
  })

  it('rejects legacy raw graph/evidence imports', async () => {
    const legacyEvidence = createJsonFile('evidence-demo.json', {
      case_id: 'legacy-case',
      case_label: 'Legacy Case',
    })

    await expect(buildLocalImportResult([legacyEvidence])).rejects.toThrow(
      '当前版本仅支持导入成品回放资产（rootlens-runtime.json + unified-graphs.json）或 session bundle；不再支持从 nodes/edges/evidence 在浏览器端临时组装 runtime。',
    )
  })
})
