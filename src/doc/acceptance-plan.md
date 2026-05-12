# RootLens 验收与推进计划

这份文档只做两件事：

1. 定义 **当前 Phase 1（浏览器本地运行时）** 的验收标准。
2. 明确 **当前实现与目标设计** 之间的缺口，以及后续补齐顺序。

它不是论文方法文档，也不是上游算法说明文档；它是 RootLens 当前仓库的执行基线。

---

## 1. 当前结论

**结论：现有设计文档集还不能直接作为最终验收标准。**

原因不是“方向错了”，而是**目标态设计**和**当前前端实现态**混写在一起了：

- 模块一文档仍然描述从原始 Text / Code / Image / Sequence 素材走完整 L1-L4 建图流水线。
- 模块二文档没有完整覆盖当前运行时强制校验的 Evidence 字段。
- 模块三文档仍然把路线 1 和路线 2 写成接近“完整保留上游算法”的实现，而当前仓库实际是浏览器端启发式版本。
- 系统设计文档列出了工作台能力和路线图，但没有给出明确、可打钩的验收门槛。

因此，**当前应该先验收“浏览器本地运行时原型”是否闭环**，而不是按“完整算法整合系统”验收。

### 1.1 当前进度快照（2026-05-12）

如果以**当前已经收敛的目标**作为 100%：

- 前端本地导入
- 浏览器内统一图谱 / runtime 生成
- Evidence / RCA / 图谱三个工作台联动
- analyst workspace / bundle 导出恢复
- 不引入后端

那么当前整体进度可估算为 **87%**。

这个百分比**不包含**“完整复刻上游算法”“论文实验全部复现”“三类工业 use case 全量固化”这类更高目标；如果把这些也算进同一个 100%，当前比例会明显更低。

当前 87% 的拆分依据：

| 维度 | 权重 | 当前完成度 | 说明 |
|---|---:|---:|---|
| 导入与会话迁移 | 25% | 94% | replay / graphs / evidence append / bundle / workspace restore 已闭环；当前会话内容摘要与恢复告警已补，剩完整浏览器级回归记录 |
| 三个主工作台 | 25% | 91% | `/graphs`、`/evidence`、`/reasoning` 已串通；缺失态 blocker、反馈汇总与 what-if diff 已补，缺更强双路线叠加视图 |
| Analyst Workspace | 20% | 87% | what-if、接受/驳回、跨页焦点、备注持久化、反馈汇总回跳、what-if 变更 diff 已具备，缺批量改写与更系统的批注整理 |
| Contract / 文档对齐 | 15% | 73% | system / acceptance 已较清晰，模块文档已加入阶段说明；仍需继续压平少量目标态描述 |
| 验收与回归保障 | 15% | 80% | service 级回归已补，且已开始浏览器手工回归；已确认 graphs-only 下 reasoning blocker，完整 happy path 记录与自动化仍不足 |

当前最关键的未完成项不是“再加页面”，而是把**剩余交互增强、文档 contract 和浏览器级验收**补齐。

---

## 2. Phase 1 验收标准

Phase 1 的目标不是完整复刻上游算法，而是让 RootLens 成为一个稳定、可演示、可扩展的前端本地原型。

### 2.1 导入闭环

必须满足：

- 用户可在浏览器导入 `rootlens-runtime.json` + `unified-graphs.json`，并直接回放。
- 用户可导入 TEP `nodes.jsonl` + `edges.jsonl`，生成本地图谱。
- 用户可导入 MVTec `nodes.csv` + `edges.csv` + 可选 `mvtec_rca_reference.csv`，生成本地图谱。
- 用户可在已有图谱基础上导入 `evidence*.json` / `case*.json`，按 `case_id` 增量生成或覆盖本地 runtime case。
- `/import` 页面应提供明确的阶段化动作入口，至少区分“完整回放 / 图谱导入 / Evidence 追加”，而不是只暴露通用文件选择器。
- `/import` 页面应支持把已导出的 session bundle / analyst workspace 重新导回当前系统，恢复 graphs/runtime 或分析过程状态。
- 导入后的会话写入 `localStorage`，刷新页面后仍可恢复。
- 当只导入图谱、不导入 runtime/evidence 时，图谱工作台可用，Evidence / RCA 工作台必须给出明确提示。
- 当只导入 runtime、不导入图谱时，Evidence / RCA 工作台可用，图谱工作台必须给出明确提示。

### 2.2 Contract 闭环

必须满足：

- 文档中的 Unified Evidence 字段与运行时 validator 完全一致。
- 文档中的 AnalysisResult / Route1Result / Route2Result 字段与前端消费结构一致。
- 所有导入入口只接受文档中声明过的格式，不允许“代码能跑但文档未定义”的隐式格式。

### 2.3 工作台闭环

必须满足：

- `/import` 能展示当前会话来源、最近摘要、导入结果、警告信息。
- `/import` 能导出当前会话的 `unified-graphs.json`、`rootlens-runtime.json`、analysis workspace 或完整 bundle。
- `/import` 能将已导出的完整 bundle 或 analyst workspace 重新导入并恢复当前会话。
- `/graphs` 能展示当前会话图谱，而不是静默回退到 demo。
- `/evidence` 能展示 observation、facet 过滤、raw refs、linked hints，并反映当前 case 的本地 draft 状态。
- `/reasoning` 能展示 route1 / route2 / cross-route signals，对不可用路线显示清晰状态，并支持本地 what-if / 人工反馈持久化。
- 三个工作台之间必须具备共享分析焦点：当前 case、observation、route1 path、route2 candidate 的选择能跨页保持，并驱动图谱高亮或证据高亮。

### 2.4 验收方式

至少需要完成以下手工验证：

1. `runtime + graphs` 导入回放。
2. `graphs-only` 导入。
3. `graphs + evidence` 导入并生成 runtime。
4. 刷新页面后的会话恢复。
5. 切回 demo 后的状态重置。

当前回归记录（2026-05-12）：

- 已确认 `graphs-only` 导入后的 `/import` 会显示 `graphs only`，且当前会话内容为 graph present / runtime missing。
- 已确认 `graphs-only` 会让 `/evidence` 显示“当前会话只有图谱，没有 runtime case” blocker。
- 已确认 `graphs-only` 会让 `/reasoning` 显示“当前会话只有图谱，无法执行 RCA” blocker。
- `graphs + evidence`、`workspace restore`、`bundle restore`、`demo reset` 仍需补完整浏览器点击记录。

---

## 3. 当前缺口矩阵

| 主题 | 目标设计 | 当前实现 | 结论 |
|---|---|---|---|
| 建图 | 原始多模态素材 → L1-L4 完整建图 | 仅支持已构建图谱文件导入 | 不应按完整建图验收 |
| Evidence | 统一 JSON 作为唯一 RCA 输入 | 已有 validator，但文档字段未完全对齐 | 需先补文档 |
| 路线 1 | 接近 KGTraceVis pipeline 语义 | 浏览器端启发式 linking / consistency / shortest-path ranking | 可按原型验收，不可按算法 parity 验收 |
| 路线 2 | 接近 TEP Root-KGD + RFPA + adjustments | 浏览器端启发式 candidate ranking | 不可按完整 Root-KGD 验收 |
| 工作台 | 图谱、证据、推理、人工反馈、what-if | 图谱 / 证据 / 推理、what-if 草稿持久化、人工反馈持久化、反馈备注持久化、反馈汇总回跳、what-if diff 预览、跨页共享分析焦点、图谱/证据联动高亮、workspace/bundle 导出与恢复已落地；批量修改与更完整的叠加视图未落地 | 当前可按 Phase 1 原型验收，交互增强继续推进 |
| 论文支撑 | 三个 use case + 结果复现 | 当前只有 demo/runtime 层 | 后续阶段再验收 |

---

## 4. 后续推进计划

下面的计划以“把当前前端可视化系统推到可稳定验收的 100%”为目标，而不是一步跳到论文最终态。

### P0：Phase 1 验收收口（84% → 90%）

目标：把当前已经实现的链路变成**可重复验收**的链路。

任务：

- 完成一轮真实浏览器点击回归：`graphs-only`、`graphs+evidence`、`workspace restore`、`bundle restore`、`demo reset`。
- 补齐 restore 后的页面级提示，确保 `/graphs`、`/evidence`、`/reasoning` 都能清楚解释“为什么当前不可用”。
- 在导入页补一份更清晰的“当前会话内容”摘要，明确当前是否包含 graph / runtime / workspace。
- 固化验收记录，避免后续只能靠手工记忆判断“是否通过”。

### P1：Contract 与文档对齐（90% → 94%）

目标：把“当前实现态”和“目标态”从文档上拆开。

任务：

- 更新 `module-1-graph-construction.md`，明确当前仓库只承接“已构建图谱导入”，不承接原始素材建图。
- 更新 `module-2-unified-evidence.md`，补齐 `case_label`、`summary`、`graph_dataset_id`、`linked_entity_hints`、`raw_evidence_refs`。
- 更新 `module-3-rca-engine.md`，把“完整保留”改成“目标语义来源”，单列“当前浏览器启发式版本”。
- 在 `system-design.md` 中增加“当前验收标准”入口，避免继续混用阶段目标。

### P2：分析工作台增强（94% → 98%）

目标：把“能看”推进到“能分析、能记录、能复盘”。

任务：

- 补强 what-if：在现有单 observation diff 基础上支持批量 observation 修改。
- 把当前 feedback summary 扩展为按 verdict / route 分组、过滤与更系统的 analyst 复盘视图。
- 增加双路线叠加高亮、候选交集/差集视图，减少跨区块切换成本。
- 让人工反馈从“单点接受/驳回”扩展到“带备注的复盘记录”。

### P3：验收级交付（98% → 100%）

目标：让当前 scoped product 达到“交给别人也能完整跑通”的程度。

任务：

- 固化至少 2 套演示数据包：`graphs-only` 包、`graphs+evidence` 包。
- 增加会话导出 contract 说明与样例文件说明。
- 增加一组最小浏览器 E2E 或可重复脚本，覆盖主链路 happy path。
- 形成一页式交付说明：导什么文件、会得到什么结果、如何恢复分析过程。

### Phase 2：推理语义增强

目标：逐步逼近上游算法语义，但不在一步内追求完整复刻。

任务：

- 路线 1：补更接近 KGTraceVis 的实体链接、关系规则和路径搜索策略。
- 路线 2：把当前启发式 ranking 拆成可替换模块，为后续接近 Root-KGD / RFPA 做准备。
- 为 route2 增加参数表与来源说明，明确哪些是启发式常量、哪些来自上游定义。

### Phase 3：工作台交互补齐

目标：把“浏览结果”提升为“分析工作台”。

任务：

- 补强 what-if：支持批量 observation 修改与更清晰的 diff 对比。
- 增加人工反馈的二次动作：修正候选备注、反馈批注整理。
- 在现有跨页共享焦点基础上，补更完整的双路线叠加高亮和候选交集/差集视图。

### Phase 4：论文与实验闭环

目标：把原型切换到论文支撑态。

任务：

- 固化 use case 数据包。
- 增加实验结果导出与截图路径。
- 梳理论文中的方法边界，明确“浏览器原型结果”和“正式实验结果”的区别。

---

## 5. 退出条件

### Phase 1 可验收退出条件

以下条件全部满足，才算通过当前阶段验收：

- 本地导入链路闭环完成。
- 文档 contract 与实际 validator 对齐。
- 图谱 / Evidence / RCA 三个工作台都能稳定消费本地会话。
- demo 模式与 import 模式切换行为明确、可恢复。
- 不再把完整上游算法复刻写成“当前已实现能力”。

### 系统级最终验收退出条件

以下条件全部满足，才算可以按“完整系统”验收：

- 建图、Evidence、RCA 三个模块的当前实现与文档完全对齐。
- 路线 1 / 路线 2 的关键算法边界明确，并有可复现的案例验证。
- 工作台具备人工反馈和 what-if 分析能力。
- 论文 use case、结果导出和演示路径完整。
