# Project Instructions

- `src/doc/*.md` 是本仓库提供给 Codex/LLM 的长期上下文入口。
- 当任务涉及以下内容时，先读取 `src/doc` 中相关文档，再做实现或判断：
  - RootLens 当前定位、运行模式、页面职责、回放边界
  - 上游项目 `TEP_KG`、`MVTec/KGTraceVis` 的职责、路径、复用关系
  - 仓库内出现的项目专有术语或语义约定
  - 论文相关历史设计背景、模块语义来源与投稿上下文
- 不必在每次任务都完整读取全部文档；仅在任务确实依赖这些上下文时按需查阅。
- 如果文档内容与代码直觉或通用惯例冲突，优先以 `src/doc/backend-integration-current.md` 描述的当前边界为准；其余带“历史文档说明”的文档仅作背景参考。

## Doc Map

- `src/doc/backend-integration-current.md`
  - **当前真值文档**：RootLens 当前的 backend-first 边界、Demo / Backend / Replay 三种模式、三大页面职责、已下线能力。
- `src/doc/source-projects.md`
  - 上游项目路径、关键资产、推荐阅读顺序与复用入口。
- `src/doc/module-1-graph-construction.md`
  - 历史背景：图谱构建设计语义与上游来源。
- `src/doc/module-2-unified-evidence.md`
  - 历史背景：统一 Evidence 设计语义与字段约定来源。
- `src/doc/module-3-rca-engine.md`
  - 历史背景：RCA 推理路线、数据结构与论文语义来源。
- `src/doc/frontend_handoff.md`
  - 历史背景：KGTraceVis 前后端交接说明。
