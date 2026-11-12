import type { RunCaseDetail, RunSummary } from "@/api/contracts";

const terms: Record<string, string> = {
  manual_curation: "人工整理 · 开发知识",
  "Glue removal insufficient": "去胶不足",
  "Stream 1 A-feed loss disturbance": "1 号流股 A 进料损失",
  "Stream 4 A/B/C composition disturbance": "4 号流股 A/B/C 组分扰动",
  "Stream 4 A/C-ratio disturbance": "4 号流股 A/C 比例扰动",
  process: "过程",
  process_fault: "过程异常",
  reactor: "反应器",
  SUGGESTS_PLAUSIBLE_MECHANISM: "提示可能机制",
  HAS_SPATIAL_SIGNATURE: "具有空间特征",
  markdown: "文档",
  "Annular ring signature": "环状空间特征",
  "Process nonuniformity": "工艺不均匀",
  "Resist strip insufficient": "去胶不足",
  "Tooling or mask pattern": "工具或掩膜图案",
  "Wet clean residue": "湿洗残留",
  "Center cluster signature": "中心聚集特征",
  "Process interruption": "工艺中断",

  "Scratch defect": "划痕缺陷",
  ScratchDefect: "划痕缺陷",
  MechanicalContact: "机械接触",
  HAS_PLAUSIBLE_CAUSE: "可能关联原因",
  completed: "已完成",
  succeeded: "已完成",
  registered: "已登记",
  extracted: "已抽取",
  failed: "失败",
  nearfull: "大面积异常",
  wafer_surface: "晶圆表面",
  bottle: "瓶体",
  scratch: "划痕",
  surface: "表面",
  linear: "线状",
  mvtec: "视觉缺陷",
  tep: "过程故障",
  wafer: "晶圆缺陷",
  image: "图像",
  time_series: "时序",
  log: "日志",
  document: "文档",
  "Mechanical contact": "机械接触",
  "Handling damage": "搬运损伤",
  "Surface wear": "表面磨损",
  "Near-full": "大面积异常",
  near_full: "大面积异常",
  plausible_mechanism: "候选机制",
  fault_anchor: "故障候选",
  SUGGESTS_PLAUSIBLE_CAUSE: "提示可能原因",
  HAS_MORPHOLOGY: "具有形态",
  OCCURS_ON: "发生于",
  HAS_LOCATION: "位于",
  HAS_ANOMALY: "出现异常",
  HAS_POSSIBLE_CAUSE: "可能关联",
  CAUSES: "可能导致",
  RELATED_TO: "关联",
  accepted: "已接受",
  reviewed: "已审阅",
  rejected: "已拒绝",
  needs_review: "待核验",
  auto: "待审阅",
};

export function readable(
  value: string | null | undefined,
  fallback = "未命名",
): string {
  if (!value || !value.trim() || value === "None" || value === "null")
    return fallback;
  if (value.includes(" / "))
    return value
      .split(" / ")
      .map((v) => readable(v))
      .join(" · ");
  return terms[value] ?? value.replace(/_/g, " ");
}

export function runTitle(run: RunSummary | null | undefined) {
  if (!run) return "选择分析记录";
  const label = run.label?.trim();
  if (
    label &&
    label !== run.run_id &&
    !/\b(?:mvtec|tep|wafer)_[\w-]+\b/i.test(label) &&
    !/^[\da-f]{8}-[\da-f-]{27,}$/i.test(label)
  )
    return label;
  const file = run.source_filename?.split(/[\\/]/).pop();
  if (file && file !== run.run_id && !file.includes(run.run_id))
    return file.replace(/\.[^.]+$/, "");
  return `${readable(run.dataset, "多源")}分析 · ${shortDate(run.created_at)}`;
}

export function caseTitle(item: RunCaseDetail | null | undefined) {
  if (!item) return "选择案例";
  if (item.case_id === "mvtec_fixture_clean_scratch")
    return item.generated_evidence?.fixture_type === "controlled_synthetic"
      ? "瓶体划痕 · 合成样本"
      : "瓶体划痕";
  if (item.case_id === "mvtec_noisy_0001") return "瓶体划痕 · 冲突示例";
  const evidence = item.generated_evidence ?? {};
  if (evidence.object && evidence.anomaly_type)
    return `${readable(String(evidence.object))} · ${readable(String(evidence.anomaly_type))}`;
  const label = item.case_label ?? item.label;
  if (label && label !== item.case_id)
    return label
      .split(" / ")
      .map((s) => readable(s))
      .join(" · ");
  return `${readable(item.dataset, "异常")}案例`;
}

export function shortDate(value: string | null | undefined) {
  if (!value || !Number.isFinite(Date.parse(value))) return "时间未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
    hour12: false,
  }).format(new Date(value));
}

export function scoreText(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(2)
    : "未提供";
}
