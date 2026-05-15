const CLAIM_BOUNDARY_FALLBACK = '候选/合理解释，仅供研判；并非已验证的根因标签'
const SCORING_METHOD_LABELS: Record<string, string> = {
  relation_weighted_path: '关系加权路径',
  artifact_bridge: '工件桥接',
  heuristic_path_support: '启发式路径支持',
  tep_root_kgd: 'TEP Root-KGD 排序',
  tep_artifact_bridge: 'TEP 工件桥接',
  root_score_fusion: 'RootScore 融合',
}

export function formatClaimBoundaryCopy(value: string | null | undefined) {
  if (!value) {
    return '候选结论边界加载中'
  }

  const normalized = value.trim()
  if (!normalized) {
    return '候选结论边界加载中'
  }

  if (
    normalized === 'candidate/plausible explanation only; not a verified root-cause label' ||
    /candidate\/plausible explanation only/i.test(normalized) ||
    /not a verified root-cause label/i.test(normalized)
  ) {
    return CLAIM_BOUNDARY_FALLBACK
  }

  return normalized
}

export function formatScoringMethodLabel(value: string | null | undefined) {
  if (!value) {
    return '未标注'
  }

  return SCORING_METHOD_LABELS[value] ?? value
}
