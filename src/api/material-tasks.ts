import { jsonInit, requestJson } from '@/api/client'
import type { KGMaterialRecord } from '@/api/contracts'
import type { WorkTask } from '@/api/two-loop'

export const materialCapabilities = {
  mvtec: 'visual-region-v2',
  tep: 'process-window-v2',
  wafer: 'spatial-grid-v2',
} as const

export type MaterialBuildScenario = keyof typeof materialCapabilities
type MaterialSelection = Pick<KGMaterialRecord, 'material_id' | 'scenario'>

export interface MaterialBuildOptions {
  title: string
  dataset: MaterialBuildScenario
  allowRepair: boolean
}

export function materialBuildBlocker(
  materials: MaterialSelection[],
  options: MaterialBuildOptions,
): string {
  if (!materials.length) return '请先勾选至少一份素材。'
  if (!options.title.trim()) return '请输入输出图谱名。'
  if (materials.some(({ scenario }) => scenario !== 'shared' && scenario !== options.dataset)) {
    return '所选素材包含其他场景，请分开制作工作图。'
  }
  return ''
}

export function submitMaterialBuild(
  baseUrl: string,
  materials: MaterialSelection[],
  options: MaterialBuildOptions,
): Promise<WorkTask> {
  const blocker = materialBuildBlocker(materials, options)
  if (blocker) throw new Error(blocker)
  return requestJson(baseUrl, '/api/tasks/material-build', jsonInit('POST', {
    material_ids: [...new Set(materials.map(({ material_id }) => material_id))],
    dataset: options.dataset,
    title: options.title.trim(),
    capability_id: materialCapabilities[options.dataset],
    enable_when_ready: false,
    max_repairs: options.allowRepair ? 1 : 0,
    candidate_limit: null,
  }))
}

export function submitMaterialParse(
  baseUrl: string,
  materialId: string,
  force: boolean,
): Promise<WorkTask> {
  return requestJson(baseUrl, '/api/tasks/material-parse', jsonInit('POST', {
    material_ids: [materialId],
    force,
  }))
}
