import { tepChannelLabels } from '@/data/tep-channel-labels'
import type { RecordValue, Dataset } from '@/api/workbench'

export function record(value: unknown): RecordValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {}
}
export function rows(value: unknown): RecordValue[] { return Array.isArray(value) ? value.filter((r) => r && typeof r === 'object' && !Array.isArray(r)) as RecordValue[] : [] }
export function texts(value: unknown): string[] { return Array.isArray(value) ? value.map(String) : [] }
export function text(value: unknown, fallback = '') { return value === null || value === undefined ? fallback : String(value) }
export function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T }
export function number(value: unknown, digits = 4): string {
  return typeof value === 'number' && Number.isFinite(value) ? Number(value.toPrecision(digits)).toString() : '—'
}
export const datasetNames: Record<Dataset, string> = { mvtec: '视觉缺陷 · MVTec', tep: '过程监测 · TEP', wafer: '晶圆图案 · Wafer' }
export const datasetShort: Record<string, string> = { mvtec: '视觉缺陷', tep: '过程监测', wafer: '晶圆图案', shared: '通用资料' }
export const capabilityIds: Record<Dataset, string> = { mvtec: 'visual-region-v2', tep: 'process-window-v2', wafer: 'spatial-grid-v2' }
export const featureNames: Record<string, string> = {
  'detection.anomaly_present': '检测到异常', 'geometry.area_ratio': '区域面积占比', 'geometry.aspect_ratio': '区域长宽比',
  'geometry.eccentricity': '区域离心率', 'geometry.component_count': '连通区域数', 'geometry.morphology': '区域形态',
  'geometry.location': '区域位置', 'appearance.semantic_candidates': '外观语义候选', 'appearance.defect_present': '外观判断为缺陷',
  'statistics.mean_z': '均值偏移（标准化）', 'statistics.std_z': '标准差（标准化）', 'statistics.slope_z': '趋势斜率',
  'residual.contribution': 'PCA 残差贡献', 'residual.energy': '残差能量', 'residual.normal_limit': '正常残差上限',
  'classifier.pattern': '独立分类图案', 'spatial.valid_die_count': '有效芯粒数', 'spatial.failed_die_count': '失效芯粒数',
  'spatial.failure_density': '区域失效率', 'spatial.component_count': '失效簇数量',
  'spatial.largest_component_ratio': '最大失效簇占比', 'spatial.linearity': '失效排列线性度',
}
const labels: Record<string, string> = {
  'bottle': '玻璃瓶', 'wafer': '晶圆', 'Tennessee Eastman Process': '田纳西伊士曼过程',
  'Glass too cold from feeder': '供料玻璃温度过低',
  'Machine setup/operation maladjustment (plunger, mold timing, tongs, neck ring, blowhead)': '成型设备调整或操作不当',
  'Bad match between blank and ring (mold equipment)': '初型与口模不匹配',
  'Careless handling of cold ware (stacking equipment)': '冷端搬运或堆垛不当',
  'Faulty or incorrectly set gauging heads (inspection equipment)': '检验测量头故障或设置不当',
  'Thermal glass condition': '玻璃热状态', 'Mechanical setup and handling': '机械调整与搬运',
  'Mold equipment condition': '模具设备状态', 'Inspection equipment condition': '检验设备状态',
  'Finish with cracks or glass pieces broken out': '瓶口裂纹或玻璃破损',
  'Small section broken on top or side of finish': '瓶口顶部或侧边局部崩缺',
  'Explicit anomaly prerequisite': '必须检测到异常',
  'VLM appearance candidate indicates broken/chipped glass': '外观候选包含玻璃破损',
  'VLM assesses the ROI as defective': '区域外观明确判断为缺陷',
  'VLM appearance candidate indicates chipped/broken glass': '外观候选包含玻璃崩缺',
  'Feed composition / A-C ratio step disturbance': '进料组成或 A/C 比例阶跃扰动',
  'Feed temperature step disturbance': '进料温度阶跃扰动',
  'Cooling water inlet temperature disturbance': '冷却水入口温度扰动',
  'Slow reaction-kinetics drift': '反应动力学缓慢漂移', 'Cooling water valve sticking': '冷却水阀卡滞',
  'Feed boundary condition change': '进料边界条件变化', 'Heat-removal boundary condition change': '散热边界条件变化',
  'Reaction kinetics change': '反应动力学变化', 'Actuator fault': '执行器故障',
  'Persistent standardized level shift in one or more process channels': '过程变量持续偏离正常水平',
  'Increased window variability without a dominant mean shift': '窗口波动增强而非均值主导偏移',
  'Manipulated-variable movement with maintained controlled temperature': '操纵变量补偿且温度维持受控',
  'Concentrated PCA residual contribution in feed/purge analysis channels': '进料或排放分析通道的残差贡献集中',
  'Window mean of a channel is displaced from normal reference': '变量窗口均值偏离正常参考',
  'Residual energy exceeds matched normal limit': '残差能量超过配套正常上限',
  'Window standard deviation of standardized channel is elevated': '标准化变量的窗口波动升高',
  'Reactor cooling water flow manipulated variable shows a shift': '反应器冷却水操纵变量偏移',
  'Residual contribution concentrated in a sampled analysis channel': '采样分析通道的残差贡献集中',
  'Center': '中心型', 'Donut': '环状型', 'Edge-Loc': '边缘局部型', 'Edge-Ring': '边缘环型',
  'Loc': '局部型', 'Random': '随机型', 'Scratch': '划痕型', 'Near-full': '近全失效型',
  'Central failure cluster': '中心失效簇', 'Annular failure ring': '环状失效带', 'Localized edge cluster': '边缘局部失效簇',
  'Peripheral ring of failures': '周边环状失效', 'Single localized region': '单个局部失效区',
  'Scattered failures': '散布失效', 'Linear streak of failures': '线性失效条带', 'Global wafer-wide failure': '全片广泛失效',
  'Elevated failure density in the center zone': '中心区失效率升高', 'Elevated failure density in the middle zone': '中圈失效率升高',
  'Elevated failure density in the edge zone': '边缘区失效率升高', 'Failures form a compact localized cluster': '失效形成紧凑局部簇',
  'Failures spread over many components rather than one cluster': '失效分布在多个连通簇', 'Failures dominated by a single salient region': '失效由单个显著区域主导',
  'Low overall failure density': '整体失效率较低', 'Failures fragmented into many components': '失效分散成多个簇',
  'No dominant component': '没有主导失效簇', 'Failures are highly collinear': '失效芯粒高度共线',
  'Very high overall failure density': '整体失效率很高',
  'chipped_edge': '玻璃边缘崩缺', 'cracked_or_missing_glass': '裂纹或玻璃缺失', 'broken_glass': '玻璃破损', 'chipped_glass': '玻璃崩缺', 'normal': '正常', 'good': '正常', 'unknown': '未知',
  'center': '中心', 'middle': '中圈', 'edge': '边缘', 'all_valid': '全片有效区', 'upper': '上部', 'lower': '下部',
  'left': '左侧', 'right': '右侧', 'linear': '线状', 'spot': '斑点状', 'scattered': '散布状', 'dense': '密集状', 'surface': '表面', 'irregular': '不规则', 'compact': '紧凑',
  'center_pattern': '中心型', 'donut': '环状型', 'edge_loc': '边缘局部型', 'edge_ring': '边缘环型',
  'loc': '局部型', 'random': '随机型', 'scratch': '划痕型', 'near_full': '近全失效型', 'nearfull': '近全失效型',
  'expected': '预期表现', 'necessary': '必要条件', 'possible': '可能表现', 'source_explicit': '资料明确记载',
  'llm_proposed': '模型提出', 'normal_reference_estimate': '正常参考估计', 'declared_demo_heuristic': '演示启发式',
  'synthetic_design_assertion': '合成设计', 'measured': '实测', 'model_estimate': '模型估计', 'measurement': '数值测量',
}
export function channelCode(value: unknown): string {
  const match = String(value ?? '').toLowerCase().match(/(?:xmeas|xmv)[_ (]?(\d+)/)
  return match ? `${match[0].startsWith('xmv') ? 'xmv' : 'xmeas'}_${match[1]}` : ''
}
export function channelLabel(value: unknown) {
  const code = channelCode(value)
  if (!code) return text(value)
  const [family, index] = code.split('_')
  return `${tepChannelLabels[code] || (family === 'xmv' ? '操纵变量' : '过程测量')} · ${family!.toUpperCase()}(${index})`
}
export function friendly(value: unknown, fallback = '未命名'): string {
  const name = text(value).trim()
  if (!name) return fallback
  if (labels[name]) return labels[name]
  if (featureNames[name]) return featureNames[name]
  if (/^(?:variable:|entity:tep_braatz.channel:)?(?:xmeas|xmv)[_ (]?\d+\)?$/i.test(name)) return channelLabel(name)
  if (name.startsWith('Classifier label is ')) return `分类图案为${friendly(name.slice(20))}`
  if (name.endsWith(' pattern family')) return `${friendly(name.slice(0, -15))}图案`
  if (/^(?:graph|task)_[a-f\d]{12,}$/.test(name) || /^[a-f\d]{8}-[a-f\d-]{27,}$/.test(name)) return fallback
  if (/^(hypothesis|mechanism|signature|entity|fact|obs|source|rule):/.test(name)) {
    return name.split(':').at(-1)!.replace(/[_-]+/g, ' ')
  }
  return name
}
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '未提供'
  if (typeof value === 'number') return number(value)
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.map(formatValue).join('、') || '无'
  if (typeof value === 'object') {
    const v = record(value)
    if (v.kind === 'number') return `${number(v.number)}${v.unit && v.unit !== '1' ? ` ${v.unit}` : ''}`
    if (v.kind === 'boolean') return v.boolean === true ? '是' : '否'
    if (v.kind === 'category') return friendly(v.category)
    if (v.kind === 'candidate_set') return `${formatValue(v.items)}${v.exhaustive === false ? '（开放候选集）' : ''}`
    if (v.kind === 'array_ref') return '完整数组（见原始数据）'
    if (v.kind === 'interval') return `${formatValue(v.lower)}–${formatValue(v.upper)}`
    return JSON.stringify(value)
  }
  return friendly(value)
}
export const operatorLabels: Record<string, string> = { gte: '≥', lte: '≤', abs_gte: '绝对值 ≥', eq: '等于', in: '属于', intersects: '与集合相交', candidate_contains: '候选包含', bool_eq: '等于' }
export function conditionText(row: RecordValue) { return `${featureNames[text(row.feature_id)] ?? friendly(row.feature_id)} ${operatorLabels[text(row.op)] ?? text(row.op)} ${formatValue(row.operand)}` }
export function outcomeLabel(value: unknown) {
  return ({ supported: '存在支持候选', ambiguous: '多个候选并列', no_match: '未形成完整支持', insufficient_evidence: '证据不足', not_applicable: '图谱不适用', search_incomplete: '搜索未完成', partial: '部分匹配', unsupported: '缺乏支持', unassessed: '未评估' } as Record<string, string>)[text(value)] ?? friendly(value, '尚无结果')
}
export function truthLabel(value: unknown) { return value === true ? '满足' : value === false ? '冲突' : '缺测 / 未知' }
export function dateTime(value: unknown) {
  const date = new Date(text(value))
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}
export function fileSize(value: unknown) { return typeof value !== 'number' ? '' : value >= 1024 * 1024 ? `${(value / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB` }
export function downloadJson(filename: string, payload: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function parseWindows(value: string): number[][] {
  const parts = value.split(/[,，;；\n]+/).map((x) => x.trim()).filter(Boolean)
  if (!parts.length) throw new Error('请至少填写一个样本窗口，例如 1–100。')
  return parts.map((part) => {
    const match = part.match(/^(\d+)\s*[-–—:]\s*(\d+)$/)
    if (!match || Number(match[1]) < 1 || Number(match[2]) < Number(match[1])) throw new Error(`窗口“${part}”无效。使用一基闭区间，例如 1–100。`)
    return [Number(match[1]), Number(match[2])]
  })
}

export function materialLocator(value: unknown): string {
  if (!value) return '正文片段'
  let locator = record(value)
  if (typeof value === 'string') {
    try { locator = record(JSON.parse(value)) } catch { return value }
  }
  if (locator.page_number ?? locator.page) return `第 ${locator.page_number ?? locator.page} 页`
  if (locator.start_line) return `第 ${locator.start_line}–${locator.end_line ?? locator.start_line} 行`
  if (locator.char_start !== undefined) return `字符 ${locator.char_start}–${locator.char_end ?? ''}`
  return typeof value === 'string' ? value : '正文片段'
}

export function mediaOptions(value: unknown): Array<RecordValue & { display: string; mediaKey: string }> {
  return rows(value).filter((v) => v.available !== false && (v.url || v.preview_path)).map((v,index) => ({
    ...v, mediaKey: text(v.artifact_id, `${text(v.kind)}-${index}`),
    display: v.source_key === 'roi_path' || v.kind === 'roi' ? '区域裁切' : ({ image: '原图', mask: '分割掩码', heatmap: '异常热力图', wafer_map: '晶圆网格' } as Record<string,string>)[text(v.kind)] ?? friendly(v.title,'预览'),
  }))
}
