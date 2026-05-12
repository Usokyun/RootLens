import { readFileSync } from 'node:fs'

import { parseRootLensRuntimeFile, parseUnifiedGraphsFile } from '@/contracts/runtime'
import { buildLocalImportResult } from '@/services/browser-runtime'
import { saveImportedSession } from '@/services/rootlens-data'
import type { RootLensRuntimeCase } from '@/types/rootlens'
import { beforeEach, describe, expect, it } from 'vitest'

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

function createRuntimeWithCases(cases: RootLensRuntimeCase[]) {
  return parseRootLensRuntimeFile({
    schema_version: 'rootlens-runtime.v1',
    generated_at: new Date().toISOString(),
    generator: 'browser-import',
    cases,
  })
}

describe('buildLocalImportResult', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('marks unified-graphs replay as graphs-only when runtime is absent', async () => {
    const result = await buildLocalImportResult([
      createJsonFile('unified-graphs.json', clone(demoGraphs)),
    ])

    expect(result.graphs?.datasets).toHaveLength(demoGraphs.datasets.length)
    expect(result.runtime).toBeNull()
    expect(result.summary.sourceMode).toBe('graphs-only')
    expect(result.summary.warnings).toContain(
      '检测到 unified-graphs.json，但缺少 rootlens-runtime.json；Evidence 与 RCA 工作台将不可用。',
    )
  })

  it('reuses current session graphs and merges evidence-only imports by case_id', async () => {
    const existingCase = clone(demoRuntime.cases[0])
    const nextCase = clone(demoRuntime.cases[1])
    const updatedEvidence = {
      ...clone(existingCase.evidence),
      case_label: 'Updated TEP Fault 06',
      summary: 'Updated evidence summary from appended import.',
    }

    saveImportedSession({
      graphs: clone(demoGraphs),
      runtime: createRuntimeWithCases([existingCase]),
      summary: 'existing imported session',
    })

    const result = await buildLocalImportResult([
      createJsonFile('evidence-updated.json', updatedEvidence),
      createJsonFile('case-appended.json', clone(nextCase.evidence)),
    ])

    expect(result.summary.sourceMode).toBe('graphs+evidence')
    expect(result.summary.warnings).toContain(
      '当前未选择图谱文件，已复用当前会话图谱生成 runtime case。',
    )
    expect(result.summary.warnings).toContain('已基于当前会话合并 case：覆盖 1 个，新增 1 个。')
    expect(result.runtime?.cases).toHaveLength(2)
    expect(
      result.runtime?.cases.find((caseItem) => caseItem.case_id === existingCase.case_id)?.case_label,
    ).toBe('Updated TEP Fault 06')
    expect(
      result.runtime?.cases.find((caseItem) => caseItem.case_id === existingCase.case_id)?.summary,
    ).toBe('Updated evidence summary from appended import.')
    expect(
      result.runtime?.cases.find((caseItem) => caseItem.case_id === nextCase.case_id)?.case_label,
    ).toBe(nextCase.case_label)
  })
})
