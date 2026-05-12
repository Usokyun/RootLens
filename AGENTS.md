# Project Instructions

- `src/doc/*.md` 是本仓库提供给 Codex/LLM 的长期上下文入口。
- 当任务涉及以下内容时，先读取 `src/doc` 中相关文档，再做实现或判断：
  - RootLens 项目定位、系统架构、两条推理路线、页面信息架构
  - 上游项目 `TEP_KG`、`MVTec/KGTraceVis` 的职责、路径、复用关系
  - 三个模块的设计：图谱构建（模块一）、统一 Evidence（模块二）、RCA 推理引擎（模块三）
  - 论文标题、abstract、投稿目标
  - 仓库内出现的项目专有术语或语义约定
- 不必在每次任务都完整读取全部文档；仅在任务确实依赖这些上下文时按需查阅。
- 如果文档内容与代码直觉或通用惯例冲突，优先以 `src/doc` 中的项目文档为准。

## Doc Map

- `src/doc/system-design.md`
  - 系统总设计：论文元信息、项目定位、上游项目分工、分层架构、三个模块概览、两条推理路线、端到端流程、可视化工作台、技术选型、改造路线。
- `src/doc/module-1-graph-construction.md`
  - 模块一设计：L1 素材摄取 → L2 模态提取 → L3 图谱组装 → L4 图谱投影。四种模态（Text/Code/Image/Sequence）的提取器职责与保留逻辑清单。
- `src/doc/module-2-unified-evidence.md`
  - 模块二设计：统一 Evidence JSON。三种 facet（variable / image_defect / log_event）→ 各模态处理流程、与建图和 RCA 的衔接。
- `src/doc/module-3-rca-engine.md`
  - 模块三设计：RCA 推理引擎。路线 1（多模态线索组织：实体链接 → 一致性 → 修正 → 路径排序）和路线 2（过程故障分析：RBC → 候选枚举 → RFPA → RootScore）的完整算法保留，数据结构定义，前端融合策略。
- `src/doc/source-projects.md`
  - 上游项目路径、关键资产、推荐阅读顺序与复用入口。