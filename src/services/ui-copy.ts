const CLAIM_BOUNDARY_FALLBACK = '候选/合理解释，仅供研判；并非已验证的根因标签'

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
