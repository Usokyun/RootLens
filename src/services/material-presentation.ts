import type { KGMaterialChunkRecord, KGMaterialRecord } from '@/api/contracts'

export const materialScenarios = [
  { value: 'mvtec', label: 'MVTec', buildLabel: '视觉缺陷 · MVTec' },
  { value: 'tep', label: 'TEP', buildLabel: '过程监测 · TEP' },
  { value: 'wafer', label: 'Wafer', buildLabel: '晶圆图案 · Wafer' },
  { value: 'shared', label: '共享', buildLabel: '共享素材' },
] as const

export const materialTypes = [
  { value: 'pdf', label: 'PDF' },
  { value: 'markdown', label: 'MD' },
  { value: 'text', label: 'TXT' },
  { value: 'webpage', label: '网页' },
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'jsonl', label: 'JSONL' },
  { value: 'other', label: '其他' },
] as const

export const materialStatuses = {
  pending: { label: '待提取', color: 'gold' },
  ready: { label: '已提取', color: 'green' },
  running: { label: '提取中', color: 'arcoblue' },
  failed: { label: '提取失败', color: 'red' },
} as const
export type MaterialStatus = keyof typeof materialStatuses

export function materialStatus(record: KGMaterialRecord): Exclude<MaterialStatus, 'running'> {
  const status = record.extraction_status ?? record.processing_status
  if (status === 'extracted') return 'ready'
  if (status === 'failed') return 'failed'
  return 'pending'
}

export function scenarioLabel(value: string) {
  return materialScenarios.find((scenario) => scenario.value === value)?.label ?? value
}

export function materialTypeLabel(value: string) {
  return materialTypes.find((type) => type.value === value)?.label ?? value
}

export function materialLocation(material: KGMaterialRecord) {
  return material.url ?? material.path ?? material.uri ?? material.source_uri ?? ''
}

export function materialListSource(material: KGMaterialRecord) {
  return material.url ?? material.filename ?? material.original_filename ?? materialLocation(material)
}

export function formatMaterialDate(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

function sourceSpan(chunk: KGMaterialChunkRecord): Record<string, unknown> | null {
  const fromMetadata = chunk.metadata?.source_span
  if (fromMetadata && typeof fromMetadata === 'object' && !Array.isArray(fromMetadata)) {
    return fromMetadata as Record<string, unknown>
  }
  if (!chunk.source_locator) return null
  try {
    const parsed: unknown = JSON.parse(chunk.source_locator)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null
  } catch {
    return null
  }
}

/** Parse source coordinates, not document text: never invent a page or section. */
export function materialChunkLocator(chunk: KGMaterialChunkRecord) {
  const span = sourceSpan(chunk)
  if (typeof span?.page === 'number') return `第 ${span.page} 页`
  if (typeof span?.section === 'string' && span.section.trim()) return span.section
  if (typeof span?.start_line === 'number') {
    const end = typeof span.end_line === 'number' && span.end_line !== span.start_line ? `–${span.end_line}` : ''
    const prefix = span.type === 'extracted_text' ? '提取文本 · ' : ''
    return `${prefix}第 ${span.start_line}${end} 行`
  }
  if (typeof span?.json_path === 'string') return `JSON 路径 ${span.json_path}`
  const start = typeof span?.char_start === 'number' ? span.char_start : chunk.char_start
  const end = typeof span?.char_end === 'number' ? span.char_end : chunk.char_end
  if (typeof start === 'number' && typeof end === 'number') return `字符偏移 ${start}–${end}`
  if (chunk.source_locator && !span) return chunk.source_locator
  return ''
}

export function materialError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
