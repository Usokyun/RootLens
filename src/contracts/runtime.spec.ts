import fs from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import { parseRootLensRuntimeFile } from '@/contracts/runtime'

describe('generated runtime contract', () => {
  it('parses the checked-in runtime artifact', () => {
    const runtimePath = path.resolve(process.cwd(), 'public/generated/rootlens-runtime.json')
    const raw = JSON.parse(fs.readFileSync(runtimePath, 'utf8'))

    const parsed = parseRootLensRuntimeFile(raw)

    expect(parsed.cases.length).toBeGreaterThanOrEqual(100)
    expect(parsed.cases.some((item) => item.analysis.route1 !== null)).toBe(true)
    expect(parsed.cases.some((item) => item.analysis.route2 !== null)).toBe(true)
  })
})
