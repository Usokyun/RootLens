import { describe, expect, it } from 'vitest'

import type { KGMaterialChunkRecord } from '@/api/contracts'
import { materialChunkLocator } from '@/services/material-presentation'

const chunk: KGMaterialChunkRecord = {
  chunk_id: 'chunk-1', material_id: 'source-1', chunk_index: 0, text_content: 'Original text.',
  source_locator: null, char_start: null, char_end: null, metadata: {}, created_at: null,
}

describe('material fragment coordinates', () => {
  it.each([
    [{ type: 'page', page: 13, char_start: 0, char_end: 55 }, '第 13 页'],
    [{ type: 'row', start_line: 5, end_line: 7 }, '第 5–7 行'],
    [{ type: 'extracted_text', start_line: 2, end_line: 2 }, '提取文本 · 第 2 行'],
    [{ type: 'json', json_path: '$[0]' }, 'JSON 路径 $[0]'],
  ])('displays the location saved by the real parser', (span, expected) => {
    expect(materialChunkLocator({ ...chunk, source_locator: JSON.stringify(span) })).toBe(expected)
    expect(materialChunkLocator({ ...chunk, metadata: { source_span: span } })).toBe(expected)
  })

  it('falls back to real character offsets but does not invent a location', () => {
    expect(materialChunkLocator({ ...chunk, char_start: 0, char_end: 37 })).toBe('字符偏移 0–37')
    expect(materialChunkLocator(chunk)).toBe('')
  })
})
