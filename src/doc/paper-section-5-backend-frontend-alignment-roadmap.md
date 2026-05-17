# RootLens 前后端打通与论文第 5 章对齐路线图

> **历史文档说明（2026-05-17）**
>
> 本文记录的是 RootLens 早期“前端承接本地建图 / 本地推理 / 对齐规划”的阶段性设计或交接语义，**已不代表当前实现边界**。
> 当前请优先以 `src/doc/backend-integration-current.md` 为真值；RootLens 现仅保留 backend-first 工作台、内置 Demo 与成品回放导入。


> 文档定位：**执行路线图 / 联调分期稿**
>
> 时间快照：**2026-05-16**
>
> 目标：基于 RootLens 当前 Vue 前端与 KGTraceVis 当前 FastAPI 后端的真实代码，按阶段把“后端已有能力”和“前端已实现工作台”真正打通，并最终让系统真实能力尽量覆盖论文第 5 章（`5 VISUAL ANALYTICS SYSTEM`）的主张。

---

## 0. 本文依据的 source of truth

### 0.1 RootLens 侧

- 路由与页面
  - `src/router/index.ts`
  - `src/views/EvidenceManageView.vue`
  - `src/views/GraphExploreView.vue`
  - `src/views/MaterialsManageView.vue`
- 前端 API contract / client
  - `src/api/contracts.ts`
  - `src/api/client.ts`
  - `src/services/rootlens-service.ts`
- 当前工作台能力与共享状态
  - `src/services/evidence-observation.ts`
  - `src/services/graph-reasoning-inspection.ts`
  - `src/services/provenance-inspector.ts`
  - `src/services/review-ledger.ts`
  - `src/services/workbench-state.ts`
- 当前项目文档
  - `src/doc/module-2-unified-evidence.md`
  - `src/doc/module-3-rca-engine.md`
  - `src/doc/acceptance-plan.md`
  - `src/doc/frontend_handoff.md`
  - `src/doc/paper-section-5-frontend-gap-roadmap.md`

### 0.2 KGTraceVis 后端侧

后端项目根：`/Users/bytedance/my_project/MVTec/KGTraceVis`

- API 入口：`src/kgtracevis/service/api.py`
- Dashboard 元数据：`src/kgtracevis/service/dashboard.py`
- 分析/反馈 DTO：`src/kgtracevis/service/handlers.py`
- Run detail contract：`src/kgtracevis/service/run_models.py`
- Run enrichment：`src/kgtracevis/service/run_enrichment.py`
- Visual evidence：`src/kgtracevis/service/visual_evidence.py`
- KG Studio：`src/kgtracevis/service/kg_studio.py`
- KG Construction：`src/kgtracevis/service/kg_construction.py`
- Material Library：`src/kgtracevis/service/kg_materials.py`
- Draft / Source Draft：
  - `src/kgtracevis/service/kg_drafts.py`
  - `src/kgtracevis/service/kg_source_drafts.py`

### 0.3 关于系统设计文档缺口

`AGENTS.md` 中提到的 `src/doc/system-design.md` 当前仓库中并不存在，因此本文以：

1. `module-2-unified-evidence.md`
2. `module-3-rca-engine.md`
3. `acceptance-plan.md`
4. 当前代码实现

作为这次分期规划的事实基线。

---

## 1. 先说结论

> **2026-05-16 对齐更新**
>
> - KGTraceVis 后端已补齐 review ledger、candidate feedback、material read-side、kg draft history、Section 5 acceptance bundle 等能力；
> - RootLens 当前已补接 backend mode 所需的 material library / extract / build-sources / kg drafts read-side，并已放开 `root_cause_candidate` feedback 与 bounded ledger 展示；
> - 因此，本文中早先一些“后端缺口”判断已转为历史状态，后续阅读应把重点放在**最终系统级验收与论文 claim 收口**，而不是继续假设后端能力缺失。

### 1.1 当前真实状态

**前端已经明显跑在“交互壳”前面了，后端现在的主要问题不是“没有能力”，而是“有些能力还没完全按前端当前工作台的用法打通”。**

更具体地说：

1. `/evidence`、`/graphs`、`/materials` 三个页面的 UI 骨架已经不是早期原型，而是已经具备了：
   - observation 级过滤与细节查看
   - reasoning trace / recurrence / provenance drawer
   - build detail / QA / review queue
   - replay session / shared workbench state
2. KGTraceVis 后端已经具备：
   - analysis 主链路 API（bootstrap / runs / upload / detail）
   - RCA 结果 DTO（`ranked_root_causes`、`path_graph`、`review_targets`、`visual_evidence`）
   - KG Studio / construction API
   - material library 与 source-to-KG 的一批 API
3. 真正阻塞“前后端彻底打通”的，是几类**contract 与 read-side 缺口**：
   - review ledger 的读取接口没开出来
   - `root_cause_candidate` 反馈枚举没有前后端完全统一
   - material library / extract / build-sources / source-draft 这条链路后端有、RootLens 当前还没真正接
   - 一些字段虽然有，但前后端对“哪个字段是浏览器可直接消费的 canonical 字段”还没完全收口

### 1.2 推荐路线

建议按 **4 期** 推进：

1. **第 1 期：Analysis 主链与 Evidence/Graph 后端模式收口**
2. **第 2 期：Feedback / Ledger / bounded review 打通**
3. **第 3 期：Materials / Source-to-KG 工作台打通**
4. **第 4 期：论文第 5 章验收闭环**

如果只完成前 2 期：

- 论文 **5.1 / 5.2** 基本可以由真实系统支撑；
- 论文 **5.3** 仍然只能算“部分成立”。

如果完成前 3 期：

- 系统能力才比较接近“论文第 5 章整体成立”。

---

## 2. 当前前后端对齐快照

### 2.1 已经基本打通的部分

| 能力 | 后端现状 | RootLens 现状 | 结论 |
| --- | --- | --- | --- |
| Dashboard bootstrap | `GET /api/dashboard/bootstrap` 已有 | `/evidence` 已消费 | 已打通 |
| Run history / run detail | `GET /api/runs`、`GET /api/runs/{run_id}` 已有 | `/evidence`、`/graphs` 已消费 | 已打通 |
| Upload | `POST /api/runs/upload` 已有 | `/evidence` 已消费 | 已打通 |
| RCA 结果消费 | `RunDetail` 已包含 `cases[]`、`ranked_root_causes`、`path_graph`、`review_targets`、`visual_evidence` | `/evidence`、`/graphs` 已消费 | 已打通 |
| KG Studio overview | `GET /api/kg/studio` 已有 | `/materials`、`/graphs` 已消费部分信息 | 已打通 |
| KG construction build | build / list / detail / validate / review-queue / review / publish / source-upload 已有 | `/materials` 已接 build/detail/QA/review queue/source upload | 大体打通 |
| shared workbench state | 前端本地状态为主，不强依赖后端 | 已有 `selectedCaseId`、`selectedObservationId`、filters 等 | 前端已落地 |
| replay assets | 前端本地能力，不依赖后端 | `/evidence` 已落地 | 前端已落地 |

### 2.2 前端已经做出来、但后端模式还没完全跟上的部分

### G1. Review ledger 只有写接口，没有读接口

- RootLens `GraphExploreView.vue` 已经有 bounded review ledger 区块。
- RootLens client 已经封装了 `listReviewLedger()`，默认会请求 `GET /api/feedback`。
- 但 KGTraceVis 当前 `api.py` 只有：
  - `POST /api/feedback`
- 没有：
  - `GET /api/feedback`

**直接影响**：

- backend 模式下，Graph 页的 review ledger 只能报“当前后端暂未提供 review ledger 列表接口”；
- 这会直接削弱论文 5.3 里“append-only review state” 的真实性。

### G2. `root_cause_candidate` 反馈目标还没彻底打通

当前状态是：

- 后端 `run_enrichment.py` 已经会生成 `target_type = "root_cause_candidate"`
- Postgres schema 也支持该枚举
- 但 `dashboard.py` 的 `supported_feedback_targets` 还没把它暴露出去
- `handlers.py` 的 `FeedbackRequest.target_type` 仍未接受该枚举

与此同时，RootLens：

- `src/api/contracts.ts` 已经把 `root_cause_candidate` 写进 `ReviewTargetType`
- Graph 页已经围绕 candidate 构建了 selection / review target 选择逻辑
- 但当前提交侧仍然被 gate 掉，只允许 path / edge / entity_link / correction

**直接影响**：

- 候选根因可以看、可以选，但还不能在 backend 模式下作为完整 review target 提交。
- 论文 5.2 / 5.3 中“candidate hypotheses are reviewable”的说法，目前仍然不算完全闭环。

### G3. visual evidence 的 canonical browser 字段没有完全收口

KGTraceVis 的 `visual_evidence` 同时返回：

- `url`：浏览器安全的工件访问路径，如 `/api/runs/{run_id}/artifacts/{artifact_name}`
- `preview_path`：后端本地磁盘路径

RootLens 当前 Evidence 页对图片预览的读取顺序是：

- `preview_path || url`

这在 mock / 本地回放里通常没问题，但在真实 backend 模式下，**浏览器真正可信的字段应当是 `url`，而不是本地磁盘路径**。

**直接影响**：

- 真实联调时可能出现“后端工件已生成，但前端优先拿了浏览器不可访问的本地路径”的问题。
- 这是 5.1 detection details 展示链路中的一个典型小 contract 问题。

### G4. `/materials` 当前接的是 construction workflow，不是完整 material library workflow

KGTraceVis 后端已经提供：

- `GET /api/kg/materials`
- `POST /api/kg/materials/upload`
- `POST /api/kg/materials/register-url`
- `GET /api/kg/materials/{material_id}`
- `POST /api/kg/materials/{material_id}/extract`
- `POST /api/kg/materials/build-sources`
- `POST /api/kg/source-draft`
- `POST /api/kg/drafts`

但 RootLens 当前 `/materials` 页面主要接的是：

- `GET /api/kg/studio`
- `GET /api/kg/construction/builds`
- `GET /api/kg/construction/builds/{run_id}`
- `POST /api/kg/construction/builds/{run_id}/review`
- `GET /api/kg/construction/builds/{run_id}/review-queue`
- `GET /api/kg/construction/sources`
- `POST /api/kg/construction/sources/upload`
- `POST /api/kg/construction/build`

也就是说，当前页面更像：

- “候选 KG build 管理器”

而不是论文 5.3 叙事里更完整的：

- “source-grounded material / extraction / build / review workspace”

### G5. Source Draft / Draft Adjustment 仍停留在后端或旧前端语义里，RootLens 未接入

KGTraceVis 的文档与 API 已经有：

- `POST /api/kg/source-draft`
- `POST /api/kg/drafts`

但 RootLens 当前没有真正把这两条流程放进 `/materials` 的主线。

**直接影响**：

- 当前 RootLens 能做“上传结构化 source -> build candidate KG -> review queue”，
- 但还不能完整展示“从 source material 文本/文档抽 candidate edges，再做 draft adjustment”的那一层。

### G6. backend 模式缺少一轮以 RootLens 为准的 smoke / acceptance 闭环

现状：

- KGTraceVis 自己有 backend contract smoke 思路；
- RootLens 自己也有 mock / replay 路径；
- 但缺一轮以 **RootLens 当前三工作台** 为验收对象的 backend-mode 联调基线。

**直接影响**：

- 很容易出现“后端接口存在”“前端页面也存在”，但实际上组合起来有细节掉链子的情况。

---

### 2.3 相比 `paper-section-5-frontend-gap-roadmap.md`，哪些前端 gap 已经被补上了

前一份文档主要讨论“前端差异”。从当前代码看，下面这些项已经不再是主要阻塞，而是已经进入“前端已做，等待后端或联调收口”的状态：

| 前端 gap 文档中的项 | 当前状态 |
| --- | --- |
| replay/runtime assets 入口 | 已落地在 `/evidence` |
| observation 级过滤（source / modality / confidence / time） | 已落地在 `/evidence` |
| observation detail panel | 已落地在 `/evidence` |
| shared observation/filter state | 已落地在 `workbench-state.ts` |
| reasoning trace panel | 已落地在 `/graphs` |
| cross-case recurrence | 已落地在 `/graphs` |
| provenance inspector | 已落地在 `/graphs`、`/materials` |
| materials build detail / QA / review queue | 已落地在 `/materials` |
| claim boundary 统一展示 | 三页都已有明显接入 |
| bounded review ledger | 前端 UI 已有，后端 read-side 未打通 |

**因此，当前主问题已经从“补前端 UI 壳”切换成“把真实 backend 数据与这些 UI 壳完全对齐”。**

---

## 3. 论文第 5 章的系统目标，按真实系统能力重写一遍

为了避免继续把“前端视觉存在”误判成“系统能力已经闭环”，这里把第 5 章目标拆成更适合执行的三层：

### 3.1 对应 5.1 Evidence Overview and Detection Details

系统真实完成态应满足：

- 能从真实 `run` / `case` 进入 Evidence workspace；
- observation 过滤与 detail panel 不是本地假数据，而是来自真实 `RunDetail` / `cases[]` / `visual_evidence`；
- image / wafer preview 的浏览器路径稳定可用；
- 当前 case / observation / filter 状态可跨页保持。

### 3.2 对应 5.2 Knowledge Graph Reasoning View

系统真实完成态应满足：

- 当前 case 的 `path_graph`、`ranked_root_causes`、`review_targets` 都来自真实后端；
- candidate / path / edge inspection 可以在 backend 模式下持续使用；
- candidate 反馈不是只对 path/edge 生效，而是 candidate 自身也可被 review；
- recurrence / trace 等派生视图至少建立在真实 run detail 之上。

### 3.3 对应 5.3 Provenance and Human Feedback

系统真实完成态应满足：

- provenance drawer 建立在真实 `source_edge_provenance`、`visual_evidence`、build manifest / QA report 之上；
- feedback 是 append-only 且可回读；
- bounded review target 不只存在于前端状态，而是可从 backend ledger 重新拉回；
- materials workspace 覆盖 material -> extract -> build-sources -> build -> review -> publish 的主链。

---

## 4. 分期路线图

### 第 1 期：Analysis 主链与 Evidence/Graph backend 模式收口

#### 目标

把 `/evidence` 和 `/graphs` 的**真实后端模式**跑通到“可稳定演示”的程度，先支撑论文 **5.1** 和 **5.2** 的主体叙事。

#### 后端任务（KGTraceVis）

1. 固化 `RunDetail` / `RunCaseDetail` 的关键字段语义：
   - `cases[]`
   - `ranked_root_causes`
   - `path_graph`
   - `review_targets`
   - `visual_evidence`
2. 明确 `visual_evidence` 的浏览器可消费字段：
   - `url` 作为 canonical browser URL
   - `preview_path` 退为调试/本地信息
3. 为 `GET /api/runs/{run_id}` 的典型场景补稳定样例：
   - records 多 case
   - evidence 单 case
   - 至少 1 个带 visual evidence 的 run
4. 补一份 RootLens 导向的 OpenAPI/DTO 说明，避免前端继续靠代码猜字段。

#### 前端任务（RootLens）

1. Evidence 页与 Graph 页全部以后端 `RunDetail` 为准，不再隐式依赖 mock-only 字段习惯。
2. backend 模式下，视觉工件读取优先使用 `url`；`preview_path` 仅在 mock / replay 下兜底。
3. 对 `cases[]` 做更明确的 run/case 切换策略，避免顶层聚合字段与 case 局部字段混用。
4. 固化 backend-mode 联调 happy path：
   - 上传 records
   - 进入 run detail
   - 切 case
   - Evidence observation detail
   - Graph candidate/path inspection

#### 涉及文件

- 后端：
  - `src/kgtracevis/service/run_models.py`
  - `src/kgtracevis/service/run_enrichment.py`
  - `src/kgtracevis/service/visual_evidence.py`
  - `src/kgtracevis/service/api.py`
- 前端：
  - `src/views/EvidenceManageView.vue`
  - `src/views/GraphExploreView.vue`
  - `src/api/contracts.ts`
  - `src/api/client.ts`

#### 退出条件

- backend 模式下，`/evidence` 与 `/graphs` 不需要借助 mock fallback 就能完整浏览真实 run/case；
- visual evidence 在浏览器可稳定展示；
- 论文 5.1 / 5.2 的主体截图可以开始从真实 backend mode 获取。

---

### 第 2 期：Feedback / Ledger / bounded review 打通

#### 目标

让 Graph workspace 真正具备论文 **5.3** 所要求的“append-only, bounded review state”，并补齐 candidate review 的最后一段 contract。

#### 后端任务（KGTraceVis）

1. 新增 `GET /api/feedback`：
   - 支持 `run_id`
   - 支持 `case_id`
   - 支持 `target_type`
   - 支持 `target_id`
   - 支持 `offset / limit`
2. 在 dashboard bootstrap 中补齐：
   - `supported_feedback_targets` 包含 `root_cause_candidate`
3. 在 `FeedbackRequest.target_type` 中补齐：
   - `root_cause_candidate`
4. 返回的 ledger 记录中保持：
   - append-only
   - 稳定 `target_key`
   - reviewer / note / source / metadata 可回读

#### 前端任务（RootLens）

1. Graph 页切换到真实 backend ledger，不再把 ledger 当成 mock-only 能力。
2. 当 backend bootstrap 声明支持 `root_cause_candidate` 时，开放 candidate 级反馈提交。
3. 统一处理 bounded review target 的筛选与展示：
   - path
   - edge
   - entity_link
   - correction
   - root_cause_candidate
4. provenance drawer 对 ledger record 的回跳与解释保持一致。

#### 涉及文件

- 后端：
  - `src/kgtracevis/service/api.py`
  - `src/kgtracevis/service/handlers.py`
  - `src/kgtracevis/service/dashboard.py`
  - `src/kgtracevis/service/postgres_run_store.py`
- 前端：
  - `src/views/GraphExploreView.vue`
  - `src/services/review-ledger.ts`
  - `src/services/rootlens-service.ts`
  - `src/api/contracts.ts`
  - `src/api/client.ts`

#### 退出条件

- backend 模式下可以提交并重新读取 review ledger；
- candidate/path/edge/link/correction 的 bounded review 语义一致；
- 论文 5.3 中关于 human feedback / append-only review state 的表述开始有真实系统支撑。

---

### 第 3 期：Materials / Source-to-KG 工作台打通

#### 目标

把 `/materials` 从“construction build 管理器”升级成更接近论文 **5.3** 叙事的“source-grounded material / extraction / build / review workspace”。

#### 后端任务（KGTraceVis）

后端大部分接口已经存在，这一期后端重点不是“从零开发”，而是“把缺的 read-side 和 contract 说明补齐”。

建议补齐或确认以下内容：

1. material library 主链接口稳定：
   - `GET /api/kg/materials`
   - `POST /api/kg/materials/upload`
   - `POST /api/kg/materials/register-url`
   - `GET /api/kg/materials/{material_id}`
   - `POST /api/kg/materials/{material_id}/extract`
   - `POST /api/kg/materials/build-sources`
2. source draft / draft adjustment 主链接口稳定：
   - `POST /api/kg/source-draft`
   - `POST /api/kg/drafts`
3. 如果 RootLens 需要把 draft history 做成真正的工作台面板，建议补一个 read-side API：
   - `GET /api/kg/drafts`（当前还没有）

#### 前端任务（RootLens）

1. 重构 `/materials` 信息架构，明确分开三层对象：
   - **Source Registry / Source Documents**（KG Studio 只读来源）
   - **Material Library**（上传/注册 URL/抽取）
   - **Construction Build**（build / validate / review / publish）
2. 把后端已有但当前未用的流程接进来：
   - material upload
   - register-url
   - extract
   - build-sources
   - source-draft
   - draft adjustment
3. 保持现有 build detail / QA / review queue / provenance drawer 能力不退化，而是在其上补前置流程。
4. 对用户清晰展示 claim boundary：
   - material 是 provenance record
   - extracted relations 是 candidate only
   - build 不是 publish
   - publish 也不等于 verified fact

#### 涉及文件

- 后端：
  - `src/kgtracevis/service/api.py`
  - `src/kgtracevis/service/kg_materials.py`
  - `src/kgtracevis/service/kg_source_drafts.py`
  - `src/kgtracevis/service/kg_drafts.py`
  - `src/kgtracevis/service/kg_construction.py`
- 前端：
  - `src/views/MaterialsManageView.vue`
  - `src/api/contracts.ts`
  - `src/api/client.ts`
  - `src/services/provenance-inspector.ts`

#### 退出条件

- 用户能从真实 source material 出发，走到 extract -> build-sources -> build -> review；
- `/materials` 不再只是 build 后半段页面，而是完整承接论文 5.3 的 graph-material workspace；
- 论文 5.3 关于 source-grounded material / build / review-oriented management 的说法基本站得住。

---

### 第 4 期：论文第 5 章验收闭环

#### 目标

不再只看“接口通没通”，而是按**论文第 5 章的三段叙事**做一次真实系统验收。

#### 任务

1. 固化一套 backend-mode 演示数据与截图路径：
   - 5.1：Evidence overview + detection details
   - 5.2：candidate + path + trace + recurrence
   - 5.3：provenance + feedback ledger + materials/build/review
2. 补 RootLens × KGTraceVis 联调 smoke：
   - 至少覆盖 `/evidence`、`/graphs`、`/materials`
3. 对照论文第 5 章逐段核查“系统真实能力是否足够支持文字表述”。
4. 对仍未完全实现的部分，明确是：
   - 系统补齐
   - 或论文收缩措辞

#### 退出条件

- 论文第 5 章三段都能找到真实系统截图与真实交互路径；
- 不再依赖“mock 中有、backend mode 没有”的能力来支撑论文表述；
- 可以明确回答：**系统真实能力已经和第 5 章对齐到什么程度**。

---

## 5. 每一期和论文第 5 章的对应关系

| 分期 | 主要支撑章节 | 说明 |
| --- | --- | --- |
| 第 1 期 | 5.1、5.2 | 把真实 run/case/evidence/path 先在 backend mode 跑通 |
| 第 2 期 | 5.2、5.3 | 把 feedback / ledger / candidate review 做成真实可回读流程 |
| 第 3 期 | 5.3 | 把 materials workspace 从“build 后半段”扩成“source-grounded full workflow” |
| 第 4 期 | 第 5 章整体 | 把系统截图、交互链路、论文表述一起收口 |

---

## 6. 我建议的优先级

### 必做

1. **第 1 期**
2. **第 2 期**

原因：如果这两期不做完，RootLens 当前很多已经实现出来的高级 UI，只能继续停留在 mock / replay 更好用、backend mode 反而打折的状态。

### 强烈建议做

3. **第 3 期**

原因：如果不做第 3 期，论文 5.3 只能被解释为：

- 有 build/review 片段
- 但还不是完整的 source-grounded material workspace

### 最后收口

4. **第 4 期**

原因：论文与系统最容易出现“都各自很努力，但最后还是没完全对齐”的地方，就在最后这一步验收没有单独做。

---

## 7. 如果时间不够，论文应该在哪里收缩

如果最终只完成到：

- **第 1 期 + 第 2 期**

那么建议：

- 论文 **5.1 / 5.2** 可以保持较强表述；
- 论文 **5.3** 应保守描述为：
  - lightweight provenance cues
  - append-only review feedback on bounded targets
  - partial materials/build management

如果连第 2 期都没做完，那么不建议在论文里强调：

- append-only review ledger
- candidate-level reviewability
- fully grounded feedback workflow

因为这些点最容易被系统真实能力反证。

---

## 8. 最终建议

**这次不应该再按“补前端页面”思路推进，而应该按“前端已到位、后端 contract 与 read-side 补齐”思路推进。**

我的建议是：

1. 先把 **第 1 期** 做成 backend-mode 的稳定主链；
2. 立刻做 **第 2 期**，把 ledger 与 candidate review 补齐；
3. 再做 **第 3 期**，让 `/materials` 真正承接论文 5.3；
4. 最后用 **第 4 期** 做论文第 5 章的系统验收与文字收口。

这样推进的好处是：

- RootLens 当前已经做出来的大量工作不会停留在 mock-only；
- KGTraceVis 后端已有能力能被系统化接住；
- 最终对齐的是“真实系统功能”，而不是“前端看起来像做了”。

