import type { LocalImportSummary } from '@/services/browser-runtime'
import type { LocalSessionMeta } from '@/services/rootlens-data'

export type WorkflowStageName = 'import' | 'graphs' | 'evidence' | 'reasoning'
export type WorkflowStageStatus = 'ready' | 'attention' | 'waiting'

export interface WorkflowStage {
  name: WorkflowStageName
  label: string
  description: string
  status: WorkflowStageStatus
  note: string
}

export interface WorkflowSnapshot {
  sessionLabel: string
  modeLabel: string
  datasetCount: number | null
  caseCount: number | null
  warningCount: number
  hasGraphs: boolean
  hasCases: boolean
  stages: WorkflowStage[]
}

function buildModeLabel(
  sessionMeta: LocalSessionMeta | null,
  importSummary: LocalImportSummary | null,
): string {
  if (sessionMeta?.source !== 'import') {
    return 'demo replay'
  }

  switch (importSummary?.sourceMode) {
    case 'runtime':
      return 'runtime replay'
    case 'graphs+evidence':
      return 'graphs + evidence'
    case 'graphs-only':
      return 'graphs only'
    default:
      return 'import session'
  }
}

export function buildWorkflowSnapshot(
  sessionMeta: LocalSessionMeta | null,
  importSummary: LocalImportSummary | null,
): WorkflowSnapshot {
  const isDemo = sessionMeta?.source !== 'import'
  const datasetCount = importSummary?.datasets.length ?? null
  const caseCount = importSummary?.cases.length ?? null
  const hasGraphs = isDemo || Boolean(datasetCount)
  const hasCases = isDemo || Boolean(caseCount)
  const warningCount = importSummary?.warnings.length ?? 0

  return {
    sessionLabel: isDemo ? '内置示例' : '本地导入',
    modeLabel: buildModeLabel(sessionMeta, importSummary),
    datasetCount,
    caseCount,
    warningCount,
    hasGraphs,
    hasCases,
    stages: [
      {
        name: 'import',
        label: '导入数据',
        description: '上传 runtime、nodes/edges 或 evidence 文件。',
        status: warningCount ? 'attention' : 'ready',
        note: isDemo
          ? '当前使用内置示例，可直接体验完整链路。'
          : '导入结果已写入浏览器 localStorage，可刷新恢复。',
      },
      {
        name: 'graphs',
        label: '构建图谱',
        description: '统一节点/边格式并进入图谱可视化。',
        status: hasGraphs ? 'ready' : 'waiting',
        note: hasGraphs
          ? datasetCount === null
            ? '内置统一图谱已就绪。'
            : `${datasetCount} 个 dataset 已就绪，可直接检查图谱结构。`
          : '导入 nodes/edges 或 unified-graphs.json 后可用。',
      },
      {
        name: 'evidence',
        label: '导入 Evidence',
        description: '将 observation 组装成可回放的 runtime case。',
        status: hasCases ? 'ready' : hasGraphs ? 'attention' : 'waiting',
        note: hasCases
          ? caseCount === null
            ? '内置 Evidence 已就绪。'
            : `${caseCount} 个 case 已生成，可直接做证据审查。`
          : hasGraphs
            ? '继续导入 evidence*.json 或 case*.json 生成 runtime。'
            : '先导入图谱，再导入 Evidence。',
      },
      {
        name: 'reasoning',
        label: 'RCA 分析',
        description: '浏览 route1 / route2，并执行本地 what-if。',
        status: hasCases ? 'ready' : hasGraphs ? 'attention' : 'waiting',
        note: hasCases
          ? '路线 1 / 路线 2 已可用，可直接进入 RCA 工作台。'
          : hasGraphs
            ? '当前只有图谱，缺少 runtime case，无法执行 RCA。'
            : '等待完整 case 后才能执行推理。',
      },
    ],
  }
}
