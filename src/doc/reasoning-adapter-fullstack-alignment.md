# RootLens × KGTraceVis Reasoning Adapter 双轨对齐协作文档（基于最新后端 `/Users/bytedance/my_project/KGTraceVis`）

> 状态：**Active / Frontend Frozen / Backend Current Truth Identified**
>
> 更新时间：**2026-05-17**
>
> 适用对象：
> - 负责 **RootLens 前端** 的 agent
> - 负责 **KGTraceVis 后端** 的 agent
> - 最后负责联调收口的集成 agent

---

## 0. 文档定位

这份文档的作用是：

1. 固定 **RootLens 当前前端真值面**；
2. 基于最新后端项目 `'/Users/bytedance/my_project/KGTraceVis'` 识别**当前真实后端实现边界**；
3. 明确 **前端页面已经包含哪些能力**；
4. 明确 **后端为了完美承接这些页面，需要达到什么目标**；
5. 作为后续双轨 agent 并行开发与联调的共同真值文档。

这份文档不是论文草稿，也不是旧后端交接稿；它是**当前 RootLens × 最新 KGTraceVis 的工程对齐文档**。

---

## 1. 文档优先级

如果多个文档之间冲突，按下面顺序处理：

1. `src/doc/backend-integration-current.md`
   - RootLens 当前产品边界真值；
   - 决定前端还负责什么、不再负责什么。
2. **本文档** `src/doc/reasoning-adapter-fullstack-alignment.md`
   - 决定前端冻结契约、页面能力、后端目标、联调口径。
3. 新后端项目中的真实代码：
   - `'/Users/bytedance/my_project/KGTraceVis/src/kgtracevis/service/api.py'`
   - `'/Users/bytedance/my_project/KGTraceVis/src/kgtracevis/service/dashboard.py'`
   - `'/Users/bytedance/my_project/KGTraceVis/src/kgtracevis/service/runs.py'`
   - `'/Users/bytedance/my_project/KGTraceVis/src/kgtracevis/service/run_models.py'`
   - `'/Users/bytedance/my_project/KGTraceVis/src/kgtracevis/service/run_enrichment.py'`
   - `'/Users/bytedance/my_project/KGTraceVis/src/kgtracevis/workflows/reasoning_registry.py'`
   - `'/Users/bytedance/my_project/KGTraceVis/src/kgtracevis/workflows/root_cause_provider_selection.py'`
4. 新后端项目文档：
   - `docs/rootlens_dashboard.md`
   - `docs/frontend_handoff.md`
   - `docs/project_design.md`
5. 其他历史文档
   - 只作背景参考。

---

## 2. 当前总目标

当前总目标不是重新设计系统，而是：

> **在保持 RootLens 当前前端交互面基本稳定的前提下，让最新 KGTraceVis 后端完整承接 `/evidence`、`/graphs`、`/materials` 三个页面所需要的能力，并确保 reasoning adapter / reasoning profile 在上传、结果展示、图谱审阅、素材构图链路中稳定可用。**

拆成 4 条：

1. **冻结前端面**：优先保住当前 RootLens 页面和交互。
2. **识别后端真值**：不再凭旧后端记忆做判断，全部以后端最新代码为准。
3. **明确页面能力**：把前端页面已经包含的能力写清楚。
4. **明确后端目标**：把后端必须稳定交付的接口、字段、行为与验收标准写清楚。

---

## 3. 明确不做什么

本轮对齐中，默认**不做**以下事情：

1. 不重做 RootLens 页面结构。
2. 不回退已经落地的 reasoning profile 选择器与 reasoning summary UI。
3. 不恢复浏览器端本地 RCA 推理、本地建图、本地 what-if RCA。
4. 不把后端自带 `web/` 前端当作 RootLens 的替代品。
5. 不要求 RootLens 去消费后端所有扩展能力；只对齐当前冻结页面真正调用的那部分。
6. 不把“后端当前有的额外接口”自动纳入 RootLens 必须支持的范围。

---

## 4. RootLens 当前冻结页面能力（前端真值）

这一节描述的是**当前 RootLens 前端已经包含的能力**，默认视为冻结基线。

## 4.1 `/evidence` 页面当前能力

当前 `/evidence` 页面已经包含：

1. **backend mode 上传工作台**
   - 选择上传模式：`records / evidence / image`
   - 选择 `dataset`
   - 设置 `top_k`
   - image 模式下填写 `object_name / defect_type / model_preset`
   - 选择 `Reasoning Profile`
2. **运行历史浏览**
   - 拉取 bootstrap
   - 拉取 run 列表
   - 选择一个 run 并查看详情
3. **case / observation 浏览**
   - 当前 run 下的 case 列表
   - observation drilldown
   - 当前 case 的根因列表
4. **reasoning 摘要展示**
   - Adapter
   - Profile
   - Mode
   - fallback 轻提示
5. **视觉工件预览**
   - 按 `url ?? preview_path ?? source_path` 读取图片/工件
6. **回放兼容**
   - replay / demo / mock 模式都能兜底显示

## 4.2 `/graphs` 页面当前能力

当前 `/graphs` 页面已经包含：

1. **run detail 驱动的 RCA 工作台**
   - 当前 case 切换
   - 候选根因列表
   - path graph / 局部图谱 / reasoning trace
   - provenance drawer
2. **total graph 视图**
   - 基于 KG Studio payload 的图谱总览
3. **reasoning 摘要展示**
   - Adapter
   - Profile
   - Mode
   - fallback 轻提示
4. **review ledger 读取**
   - 读取 append-only feedback ledger
5. **review 提交**
   - 提交 path / edge / entity_link / correction / root_cause_candidate 审阅反馈

## 4.3 `/materials` 页面当前能力

当前 `/materials` 页面已经包含：

1. **material library 浏览**
   - 素材列表
   - material detail
   - chunks / extractions / artifacts 浏览
2. **素材登记与抽取**
   - 上传本地素材
   - register URL
   - extract 到 structured records
3. **source draft / build-sources**
   - 生成 source draft 预览
   - 从 selected materials 生成 build-sources
4. **construction build 工作台**
   - 触发 construction build
   - 查看 build detail / validate / review queue
   - review edge
   - publish build
5. **draft history**
   - 读取 draft history
   - 提交 KG draft

## 4.4 前端不负责的能力

RootLens 前端当前明确**不负责**：

- 本地 RCA 推理
- 本地建图
- 本地 what-if RCA 重算
- 本地计算 path graph
- 直接修改 KG runtime 数据

---

## 5. 前端冻结契约（后端必须对齐或明确映射）

这一节描述的是**当前 RootLens 已经固定的接口消费方式**。

## 5.1 Bootstrap 侧前端消费面

前端当前期望存在 reasoning profile 选项：

```ts
interface DashboardReasoningProfileOption {
  profile_id: string
  reasoner_adapter: string
  default: boolean
}

interface DashboardBootstrap {
  reasoning_profile_options: Record<string, DashboardReasoningProfileOption[]>
}
```

前端当前约束：

1. 以 `dataset` 为 key 读取 profile 列表。
2. 不允许用户手输 profile id。
3. 若未选 dataset，上传区默认只展示“自动（按数据集默认）”。
4. 若已选 dataset，则展示该 dataset 对应的 profile options。

## 5.2 Upload 侧前端发送面

前端当前会发送：

```ts
interface UploadRequest {
  file: File
  mode: UploadMode
  dataset?: string
  object_name?: string
  defect_type?: string
  model_preset?: string
  reasoning_profile_id?: string
  top_k: number
}
```

前端当前约束：

1. `reasoning_profile_id` 是可选的；
2. 选择“自动”时可不发送；
3. 显式选择 profile 时，会透传 `reasoning_profile_id`；
4. 这个行为已经落地，不建议回退。

## 5.3 Run detail / case 侧前端读取顺序

前端当前对 reasoning metadata 的读取优先级固定为：

### 第一优先：case 级

```text
case.reasoning_metadata.*
```

### 第二优先：summary.pipeline 级

```text
runDetail.summary.pipeline.*
```

### 第三优先：analysis.reasoning_metadata 级

```text
runDetail.analysis.reasoning_metadata.*
```

前端主要关心的键包括：

```text
reasoning_profile_id
reasoner_adapter
selection_mode
requested_reasoning_profile_id
requested_reasoner_adapter
fallback_applied
fallback_reason
```

## 5.4 文案与展示约束

前端当前仍坚持以下边界：

- reasoning adapter/profile 只回答“当前候选结果通过哪条 reasoning 路线产生”；
- 不回答“结果是否已验证为真实根因”；
- claim boundary 不得被 reasoning UI 弱化。

当前前端默认展示映射：

| 原值 | 前端展示 |
| --- | --- |
| `generic_graph_path` | `Generic Path` |
| `tep_root_kgd` | `TEP Root-KGD` |
| `default` | `Auto` |
| `explicit` | `Explicit` |
| `direct` | `Direct` |

未知值允许直接回退显示原值。

## 5.5 前端需要的后端接口清单（冻结需求面）

### FE-API-1：Bootstrap 初始化接口

```text
GET /api/dashboard/bootstrap
```

前端最少需要：

- `status`
- `api_version`
- `claim_boundary`
- `supported_datasets`
- `supported_feedback_targets`
- `supported_feedback_actions`
- `upload_modes`
- `reasoning_profile_options`
- `mvtec_model_presets`
- `recent_runs`

### FE-API-2：Run 列表接口

```text
GET /api/runs
```

前端最少需要：

- `RunSummary[]`
- 包含 `run_id / created_at / mode / dataset / case_count / evidence_count / label`

### FE-API-3：Run 详情接口

```text
GET /api/runs/{run_id}
```

前端最少需要：

- `run`
- `claim_boundary`
- `workflow_steps`
- `summary`
- `analysis`
- `cases`
- `visual_evidence`

以及 case 级至少能稳定消费：

- `ranked_root_causes`
- `top_k_paths`
- `path_graph`
- `review_targets`
- `visual_evidence`
- `reasoning_metadata`

### FE-API-4：上传接口

```text
POST /api/runs/upload
Content-Type: multipart/form-data
```

前端当前会发送：

```text
file                  required
mode                  required
top_k                 required
dataset               optional
object_name           optional
defect_type           optional
model_preset          optional
reasoning_profile_id  optional
```

当前前端上传成功后期望**直接返回 `RunDetail`**。

### FE-API-5：Reasoning metadata 最小可读面

新的后端至少要保证下面三层里**有一层稳定可读**：

```text
A. cases[*].reasoning_metadata
B. summary.pipeline.*
C. analysis.reasoning_metadata
```

### FE-API-6：工件/图片可访问接口

当前前端固定按以下优先级读取：

```text
url ?? preview_path ?? source_path
```

因此后端至少需要满足下面二选一：

- **方案 A**：直接在 `visual_evidence[*].url` 中返回浏览器可访问地址；
- **方案 B**：提供稳定工件路由，并确保前端可推导或后端直接填充 `url`。

### FE-API-7：现有页面附带依赖接口

当前冻结前端还会用到：

```text
GET  /api/feedback
POST /api/feedback
GET  /api/kg/studio
GET  /api/kg/materials
GET  /api/kg/materials/{material_id}
GET  /api/kg/materials/{material_id}/chunks
GET  /api/kg/materials/{material_id}/extractions
GET  /api/kg/materials/{material_id}/artifacts
POST /api/kg/materials/upload
POST /api/kg/materials/register-url
POST /api/kg/materials/{material_id}/extract
POST /api/kg/materials/build-sources
GET  /api/kg/drafts
POST /api/kg/drafts
POST /api/kg/source-draft
POST /api/kg/construction/build
GET  /api/kg/construction/builds
GET  /api/kg/construction/builds/{run_id}
POST /api/kg/construction/builds/{run_id}/validate
GET  /api/kg/construction/builds/{run_id}/review-queue
POST /api/kg/construction/builds/{run_id}/review
POST /api/kg/construction/builds/{run_id}/publish
```

---

## 6. 最新后端项目真值（基于 `/Users/bytedance/my_project/KGTraceVis`）

## 6.1 后端项目与关键文件

最新后端项目根：

```text
/Users/bytedance/my_project/KGTraceVis
```

本轮与 RootLens 对齐最关键的真实代码入口：

- API 路由：
  - `src/kgtracevis/service/api.py`
- dashboard bootstrap：
  - `src/kgtracevis/service/dashboard.py`
- run 上传 / 详情 / 工件：
  - `src/kgtracevis/service/runs.py`
  - `src/kgtracevis/service/run_models.py`
  - `src/kgtracevis/service/run_enrichment.py`
- feedback / review ledger：
  - `src/kgtracevis/service/handlers.py`
- KG Studio：
  - `src/kgtracevis/service/kg_studio.py`
- materials / construction / drafts：
  - `src/kgtracevis/service/kg_materials.py`
  - `src/kgtracevis/service/kg_construction.py`
  - `src/kgtracevis/service/kg_drafts.py`
  - `src/kgtracevis/service/kg_source_drafts.py`
- reasoning adapter / profile 解析：
  - `src/kgtracevis/workflows/reasoning_registry.py`
  - `src/kgtracevis/workflows/root_cause_provider_selection.py`

## 6.2 当前后端已经实现的 reasoning adapter 真值

基于当前代码，最新后端已经明确存在：

### 当前 profile

- `generic_graph_path_default`
- `tep_root_kgd_default`

### 当前 adapter

- `generic_graph_path`
- `tep_root_kgd`

### 默认路由规则

在 `resolve_default_reasoning_profile_id(dataset)` 中，当前规则是：

- `tep` → `tep_root_kgd_default`
- 其他数据集 → `generic_graph_path_default`

### selection mode

当前主流程明确会产出：

- `default`
- `explicit`

另外 `direct` 仍可能出现在更底层 generic path 直接结果中，但不是 RootLens 对齐主路径的第一优先模式。

## 6.3 当前后端已经实现的 RootLens 核心接口真值

### 已明确存在的核心 route

```text
GET  /api/dashboard/bootstrap
GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/artifacts/{artifact_name}
POST /api/runs/upload
GET  /api/feedback
POST /api/feedback
GET  /api/kg/studio
```

### 已明确存在的 materials / construction route

```text
GET  /api/kg/materials
GET  /api/kg/materials/{material_id}
GET  /api/kg/materials/{material_id}/chunks
GET  /api/kg/materials/{material_id}/extractions
GET  /api/kg/materials/{material_id}/artifacts
POST /api/kg/materials/upload
POST /api/kg/materials/register-url
POST /api/kg/materials/register
POST /api/kg/materials/{material_id}/extract
POST /api/kg/materials/build-sources
POST /api/kg/materials/build
GET  /api/kg/drafts
POST /api/kg/drafts
POST /api/kg/source-draft
POST /api/kg/construction/build
POST /api/kg/construction/build-jobs
GET  /api/kg/construction/build-jobs/{job_id}
GET  /api/kg/construction/builds
GET  /api/kg/construction/builds/{run_id}
POST /api/kg/construction/builds/{run_id}/validate
POST /api/kg/construction/builds/{run_id}/validate-overlay
GET  /api/kg/construction/builds/{run_id}/artifacts/{artifact_key}
POST /api/kg/construction/builds/{run_id}/publish
POST /api/kg/construction/builds/{run_id}/review
GET  /api/kg/construction/builds/{run_id}/review-queue
GET  /api/kg/construction/sources
POST /api/kg/construction/sources/upload
```

## 6.4 当前后端如何暴露 reasoning metadata

基于当前代码，后端已经提供的 reasoning metadata 面如下：

### A. bootstrap 级

`service/dashboard.py` 当前会返回：

- `reasoning_profile_options`

### B. upload 参数级

`service/api.py` 的 `/api/runs/upload` 当前明确接受：

- `reasoning_profile_id`

### C. evidence / image 单 case run

- `service/runs.py` 中 evidence/image 路径会调用 `dashboard_fields_from_analysis(...)`
- `service/run_enrichment.py` 会把：
  - `analysis.reasoning_metadata`
  - 同步到单 case 合成出的 `cases[*].reasoning_metadata`

因此，**单 case run 当前可以满足 RootLens 的 case-first 读取方式**。

### D. records run

- `experiments/adapter_pipeline.py` 的 summary 中当前会写入：
  - `summary.pipeline.reasoning_profile_id`
  - `summary.pipeline.reasoner_adapter`
  - `summary.pipeline.selection_mode`
- case 行本身也会带：
  - `cases[*].reasoning_metadata`

因此，**records run 当前同时满足 case 级和 summary.pipeline 级读取面**。

### E. 顶层 `RunDetail.reasoning_metadata`

`service/run_models.py` 当前模型中还存在：

- `RunDetail.reasoning_metadata`

但当前冻结的 RootLens 前端**并不依赖这个顶层字段**；
RootLens 仍然以：

1. `cases[*].reasoning_metadata`
2. `summary.pipeline.*`
3. `analysis.reasoning_metadata`

作为主读取顺序。

## 6.5 当前后端对前端页面的直接支撑能力

### 对 `/evidence`

当前后端已经能够支撑：

- bootstrap 初始化
- run list
- upload
- 直接返回 RunDetail
- reasoning profile options
- reasoning metadata
- visual evidence 工件预览

### 对 `/graphs`

当前后端已经能够支撑：

- run detail 拉取
- path graph / ranked_root_causes / review_targets
- feedback ledger list / submit
- KG Studio graph payload（总图谱来源）
- `root_cause_candidate` 作为 feedback target

### 对 `/materials`

当前后端已经能够支撑：

- materials list / detail / chunks / extractions / artifacts
- material upload / register-url / extract
- build-sources
- source draft
- draft history
- construction build / validate / review queue / review / publish

## 6.6 当前后端有但不是 RootLens 冻结前端必需项的能力

以下能力在当前后端存在，但**不是当前 RootLens 冻结前端对齐的必需项**：

- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `POST /api/analyze`
- `POST /api/what-if`
- `POST /api/model-assets/download`
- `/api/kg/runtime/*` 运行时 KG 直接编辑接口
- `POST /api/kg/materials/build` 直接 material build
- `POST /api/kg/construction/build-jobs` 与 job 轮询
- `POST /api/kg/construction/builds/{run_id}/validate-overlay`

它们可以保留，但**不应成为 RootLens 完美对接的前置阻塞项**。

## 6.7 本地联调真值（基于当前后端项目）

### 启动依赖

```bash
docker compose up -d neo4j postgres
uv run python scripts/init_postgres.py
uv run python scripts/import_kg.py
```

### 启动 API

```bash
uv run python scripts/run_web_api.py
```

当前 API 默认地址：

```text
http://127.0.0.1:8000
```

Swagger：

```text
http://127.0.0.1:8000/docs
```

### 重要集成提示

当前 RootLens 默认 API base 已更新为 `127.0.0.1:8000`。旧的本地 `8081/8001` 配置会自动迁移到新的默认地址。

因此要联调最新后端，必须二选一：

当前默认情况下，RootLens 会直接对齐到 `http://127.0.0.1:8000`。

如果用户本地仍保存旧地址，则前端会自动迁移；如果需要自定义端口，仍可在页面顶部手动修改后端地址。

### 推荐 smoke 输入

优先用：

```text
/Users/bytedance/my_project/KGTraceVis/data/examples/records/mvtec_records.jsonl
/Users/bytedance/my_project/KGTraceVis/data/examples/records/wm811k_records.jsonl
/Users/bytedance/my_project/KGTraceVis/data/examples/tep_example.json
/Users/bytedance/my_project/KGTraceVis/data/examples/mvtec_noisy_morphology_demo.json
/Users/bytedance/my_project/KGTraceVis/data/examples/wafer_example.json
```

最稳定 smoke 路径仍建议：

- 先 `records`
- 再 `evidence`
- 最后再测 `image`

---

## 7. 前端页面能力 × 后端目标矩阵（核心部分）

这一节是本轮最重要的执行矩阵。

## 7.1 `/evidence` 页面：后端目标

### 前端当前页面能力

- 上传 records / evidence / image
- 选择 dataset / top_k / model_preset / reasoning_profile_id
- 查看 run list
- 查看单 run detail
- 浏览 case / observation / root cause list
- 展示 effective reasoning
- 预览 visual evidence

### 后端必须达到的目标

1. **上传可直接落 RunDetail**
   - `POST /api/runs/upload` 成功后直接返回 `RunDetail`
   - 不要求前端再轮询任务状态才能进入详情页
2. **bootstrap 可驱动上传 UI**
   - `reasoning_profile_options` 必须可用于 dataset → profile 下拉
   - `upload_modes` 与 `mvtec_model_presets` 必须稳定可读
3. **run detail 可驱动 evidence 工作台**
   - `cases[]`、`ranked_root_causes`、`visual_evidence`、`reasoning_metadata` 必须稳定可读
4. **视觉工件必须浏览器可访问**
   - 优先保证 `visual_evidence[*].url` 可直接访问
5. **claim boundary 必须稳定输出**
   - 前端不能自己编造 candidate boundary 文案

## 7.2 `/graphs` 页面：后端目标

### 前端当前页面能力

- 读取 selected run detail
- 展示 total graph / local graph / path graph
- 展示 candidate root causes 与 reasoning trace
- 打开 provenance
- 读取 review ledger
- 提交 review
- 展示 effective reasoning

### 后端必须达到的目标

1. **run detail 必须提供 RCA 工作台核心数据**
   - `ranked_root_causes`
   - `top_k_paths`
   - `path_graph`
   - `source_edge_provenance`
   - `review_targets`
   - `cases[*].reasoning_metadata`
2. **KG Studio payload 必须可生成 total graph**
   - `/api/kg/studio` 至少要稳定返回：
     - `graph_nodes`
     - `graph_edges`
     - `review_targets`
3. **feedback ledger 必须可读可写**
   - `GET /api/feedback`
   - `POST /api/feedback`
4. **review target 类型必须覆盖当前前端**
   - 至少包括：
     - `path`
     - `edge`
     - `entity_link`
     - `correction`
     - `root_cause_candidate`
5. **target_key / target_id 需要稳定**
   - 否则前端图谱审阅状态会漂移

## 7.3 `/materials` 页面：后端目标

### 前端当前页面能力

- 浏览 material library
- 浏览 material detail / chunks / extractions / artifacts
- upload material / register url
- extract material
- generate source draft
- build-sources
- trigger construction build
- inspect build / validate / review queue / review / publish
- read / submit draft history

### 后端必须达到的目标

1. **material library 必须可完整浏览**
   - list / detail / chunks / extractions / artifacts 必须稳定
2. **素材到 structured records 的链路必须可走通**
   - upload / register-url / extract 必须成功
3. **source draft 与 build-sources 必须可走通**
   - 当前前端已经将它们纳入主流程
4. **construction build 工作流必须稳定**
   - build
   - list builds
   - get build detail
   - validate
   - review queue
   - review edge
   - publish
5. **draft history 必须 append-only 可读可写**
   - list drafts
   - submit draft

### 当前不是强制目标的项

- runtime KG node/edge 直接编辑
- build job 异步轮询 UI
- overlay validate 的单独前端工作台

这些可以存在，但不是 RootLens 当前页面对齐的阻塞项。

---

## 8. 当前对齐结论：后端需要达到什么目标

如果要实现“RootLens 当前三页能力全部可用”，最新后端至少要达到下面这组目标：

### G1. 契约层目标

- bootstrap 字段稳定
- upload 字段稳定
- run detail / case detail 字段稳定
- reasoning metadata 至少一层稳定可读，最好同时满足 case + summary/analysis

### G2. reasoning 层目标

- dataset → default profile 规则稳定
- 显式 `reasoning_profile_id` 可用
- records / evidence / image 三条路径都能带出 reasoning metadata
- fallback 时有可读元信息，不让前端只看到空白结果

### G3. 页面支撑层目标

- `/evidence`：上传、run 浏览、effective reasoning、工件预览可用
- `/graphs`：RCA、graph、provenance、ledger、review 可用
- `/materials`：materials、extract、build-sources、construction build、drafts 可用

### G4. 运行环境层目标

- Postgres 可用
- Neo4j 可用
- API 默认端口与 RootLens 配置打通
- `records` / `evidence` smoke 路径稳定

### G5. 非目标控制

- 不要求为了对齐 RootLens 而强制接入后端所有扩展实验接口
- 不要求 RootLens 消费 runtime KG edit / build-jobs 等当前未使用能力
- 不要求前端为后端新能力重做页面结构

---

## 9. 最终验收清单

### A. `/evidence`

- [ ] 可以拉到 bootstrap
- [ ] 可以拉到 run list
- [ ] 可以成功 upload run
- [ ] upload 后直接进入 RunDetail
- [ ] 可以看到 effective reasoning（Adapter / Profile / Mode）
- [ ] 可以正常浏览 case / observation / root causes
- [ ] visual evidence 通过 `url` 优先正常显示

### B. `/graphs`

- [ ] 可以拉到 run detail
- [ ] 可以拉到 KG Studio payload
- [ ] total graph 正常显示
- [ ] path graph / candidate root cause / provenance 正常显示
- [ ] ledger 可读
- [ ] review 可提交
- [ ] `root_cause_candidate` 不被 gate 掉

### C. `/materials`

- [ ] materials list / detail / chunks / extractions / artifacts 可读
- [ ] upload / register-url / extract 可用
- [ ] source draft 可生成
- [ ] build-sources 可生成
- [ ] construction build / validate / review / publish 可用
- [ ] drafts 可读可写

### D. reasoning adapter/profile

- [ ] bootstrap 有 `reasoning_profile_options`
- [ ] upload 接受 `reasoning_profile_id`
- [ ] 默认 profile resolution 正常
- [ ] explicit profile selection 正常
- [ ] records / evidence / image 三条路径都能回传 reasoning metadata

### E. 集成环境

- [ ] RootLens 实际连到 `KGTraceVis` API
- [ ] RootLens 已实际连到 `127.0.0.1:8000` 或明确配置的自定义后端地址
- [ ] Postgres / Neo4j 已启动
- [ ] records / evidence smoke 通过

---

## 10. 下一步双轨开发建议

如果接下来要开两个 agent 并行做最终对齐，建议按这个方式拆：

### 前端 agent

只做：

- 验证最新后端是否满足冻结前端契约
- 如有必要，仅补最小 mapping / 端口 / 错误兜底
- 不改页面结构

### 后端 agent

只做：

- 保证 `/evidence`、`/graphs`、`/materials` 三页当前实际调用的接口全部稳定
- 保证 reasoning profile / metadata / upload / run detail 真正闭环
- 优先满足 frozen RootLens contract，而不是继续扩展边缘能力

### 集成 agent

负责：

- 端口与环境打通
- page-by-page smoke
- mismatch 归因（前端修 / 后端修）
- 最终验收收口

---

## 11. 一句话版执行摘要

> **RootLens 当前前端页面能力已经固定；基于最新后端项目 `/Users/bytedance/my_project/KGTraceVis`，后端当前已经具备大部分承接能力。接下来要做的不是重设计，而是围绕 `/evidence`、`/graphs`、`/materials` 三页，把 bootstrap、upload、run detail、reasoning metadata、feedback、materials/construction 链路稳定打通，并完成端口与环境层的最终联调。**
