# RootLens × KGTraceVis Reasoning Adapter 双轨对齐协作文档（2026-05-17）

> 状态：**Active / 当前联调真值补充文档**
>
> 适用对象：**负责 RootLens 前端的 agent**、**负责 KGTraceVis 后端的 agent**、以及最后做联调收口的集成 agent。
>
> 本文是“reasoning adapter / reasoning profile 改造”在 **RootLens 前后端联调阶段** 的共享执行文档。

---

## 0. 文档优先级与用途

### 0.1 优先级

如果多个文档之间出现冲突，按下面顺序处理：

1. `src/doc/backend-integration-current.md`
   - RootLens 当前产品边界真值；
   - 决定“哪些事仍由前端做，哪些事已经彻底交给后端做”。
2. **本文档** `src/doc/reasoning-adapter-fullstack-alignment.md`
   - 决定本轮 reasoning adapter 改造时，前后端如何对齐契约、UI、联调路径与验收标准。
3. `/Users/bytedance/my_project/MVTec/KGTraceVis/docs/reasoning_adapter_profile_refactor_plan_cn.md`
   - 决定 reasoning adapter/profile 的叙事约束、术语边界与默认行为不变原则。
4. `src/doc/source-projects.md` 与其他历史设计文档
   - 作为背景资料，不覆盖当前联调边界。

### 0.2 本文用途

本文不是论文草稿，也不是单边技术方案；它的用途是：

- 给两个并行开发 agent 一个**共享合同**；
- 避免前端按想象做 UI、后端按想象出字段；
- 把“reasoning adapter / reasoning profile”收束成**最小可用、最小返工**的落地方案；
- 让最终联调时可以按同一份验收 checklist 收口。

---

## 1. 本轮总目标

本轮目标只有一个：

> **让 RootLens 作为 backend-first 工作台，完整消费 KGTraceVis 已经引入的 reasoning adapter / reasoning profile 能力，并以极简 UI 呈现，完成前后端打通。**

展开为 4 条：

1. **前后端共享同一套术语**
   - `reasoning adapter` = 代码实现；
   - `reasoning profile` = 外部配置/资产描述；
   - 二者都不能被前端误展示成“新算法编辑器”。
2. **前端可显式选择或默认继承 reasoning profile**
   - 上传时可选；
   - 默认行为保持与后端当前默认一致。
3. **前端可读到实际生效的 adapter/profile 元数据**
   - 不只是在上传时传参；
   - 运行结果页、图谱页要能看到“最终到底走了哪条 reasoning 路线”。
4. **UI 极简**
   - 不新增页面；
   - 不做复杂配置器；
   - 只在已有上传/运行详情/图谱页做紧凑补充。

---

## 2. 明确不做什么

本轮**明确不做**以下事情，避免范围失控：

1. 不重写 `GenericGraphPathReasoner`。
2. 不重写 `TepRootKgdRcaProvider`。
3. 不新增“用户自定义算法 DSL / JSON 定义算法”。
4. 不新增独立的 reasoning-profile 管理后台。
5. 不在前端新增复杂“比较实验工作流”。
6. 不恢复浏览器端本地推理、what-if RCA 重算、或本地图谱构建。
7. 不做大规模 UI 重设计，只允许在现有页面上做**低侵入式增强**。

---

## 3. 当前事实快照（2026-05-17）

## 3.1 RootLens 当前边界

RootLens 当前仍然是 **backend-first 的前端工作台**：

- `/evidence`：上传、run/case/observation 浏览、回放导入；
- `/graphs`：总图谱、局部 path graph、候选根因、反馈账本；
- `/materials`：material library、extract、build-sources、construction build/review。

**前端不负责**：

- 本地 RCA 推理；
- 本地建图；
- 从散乱 nodes/edges/evidence 临时组装 runtime。

## 3.2 KGTraceVis 当前 reasoning adapter 事实

KGTraceVis 后端已经完成了 reasoning adapter/profile 的第一轮包装，当前真实事实是：

1. 已有 registry / profile 机制：
   - `src/kgtracevis/workflows/reasoning_registry.py`
   - `src/kgtracevis/core/reasoning_profile.py`
   - `src/kgtracevis/workflows/root_cause_provider_selection.py`
2. 当前内置 profile：
   - `generic_graph_path_default`
   - `tep_root_kgd_default`
3. 当前内置 adapter：
   - `generic_graph_path`
   - `tep_root_kgd`
4. 默认行为保持不变：
   - `tep` → `tep_root_kgd_default`
   - 其他数据集 → `generic_graph_path_default`
5. 上传接口已经支持显式传入：
   - `reasoning_profile_id`
6. dashboard bootstrap 已经暴露：
   - `reasoning_profile_options`
7. 运行输出中已经存在 reasoning metadata：
   - case 级 `reasoning_metadata`
   - records summary 级 `summary.pipeline.reasoning_profile_id / reasoner_adapter / selection_mode`
   - evidence/image 分析级 `analysis.reasoning_metadata`

## 3.3 RootLens 当前缺口

RootLens 侧当前仍有以下缺口：

1. `src/api/contracts.ts` 还没把 `reasoning_profile_options` 明确建模。
2. `UploadRequest` 还没带 `reasoning_profile_id`。
3. `src/api/client.ts` 上传表单还没把 `reasoning_profile_id` 发给后端。
4. `/evidence` 上传 UI 还没有 reasoning profile 选择器。
5. `/evidence` 和 `/graphs` 还没有稳定展示“实际生效的 adapter/profile/selection mode”。
6. 图片类 `visual_evidence` 仍有旧读取顺序残留：
   - 当前前端存在 `preview_path || url`
   - backend 模式下应改为 **`url || preview_path`**，优先浏览器可访问地址。
7. mock bootstrap 还未与 backend bootstrap 完整对齐 reasoning-profile 字段。

---

## 4. 共享术语与对外表述

这部分是前后端共同遵守的文本边界，避免 UI 文案和接口命名相互打架。

## 4.1 标准术语

### Reasoning Adapter

- 是**代码实现**；
- 决定具体推理逻辑；
- 例如：
  - `generic_graph_path`
  - `tep_root_kgd`

### Reasoning Profile

- 是**外部配置 / 资产描述**；
- 决定 adapter 读取哪些先验资产与参数；
- 例如：
  - `generic_graph_path_default`
  - `tep_root_kgd_default`

### Selection Mode

- 表示这次运行是如何确定最终 reasoning profile 的；
- 目前重点关注：
  - `default`
  - `explicit`
  - `direct`（只用于更底层直接调用语义；前端只需兼容显示，不必主推）

## 4.2 不允许的误导性说法

前端文案、接口说明、提示文案中，不要出现以下含义：

- “用户通过 JSON 自定义任意推理算法”
- “profile 本身就是算法”
- “切换 profile 会自动提升准确率”
- “当前 RCA 结果已经被验证为真实根因”

## 4.3 推荐的前端展示话术

为了极简与低返工，前端只展示三类短标签：

- **Adapter**：`Generic Path` / `TEP Root-KGD`
- **Profile**：显示稳定 id，例如 `generic_graph_path_default`
- **Mode**：`Auto` / `Explicit` / `Fallback`

claim boundary 仍沿用现有系统表述：

> 候选/合理解释，仅供研判；并非已验证的根因标签。

---

## 5. 前后端共享契约（本轮必须对齐）

## 5.1 Dashboard Bootstrap

前端必须把下面字段视为可用：

```ts
interface DashboardReasoningProfileOption {
  profile_id: string
  reasoner_adapter: string
  default: boolean
}

interface DashboardBootstrap {
  ...
  reasoning_profile_options: Record<string, DashboardReasoningProfileOption[]>
}
```

约束：

- key 为 dataset 名：`mvtec | tep | wafer`
- value 为该 dataset 可选的 reasoning profiles
- `default=true` 仅表示该 dataset 的默认 profile
- 前端**不要**自己重写默认路由逻辑，只消费后端给定选项

## 5.2 Upload 请求

前端上传契约补齐：

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

规则：

1. `reasoning_profile_id` 可空；空表示让后端按默认规则解析。
2. 前端只允许用户从 bootstrap 返回的候选项中选；**不允许手输**。
3. 若用户未指定 dataset，则前端 UI 默认保持 `Auto`，不强行暴露复杂 profile 列表。
4. 若用户显式选了 dataset，则仅展示该 dataset 兼容的 profiles。
5. backend 仍是最终校验者；若 dataset/profile 不兼容，以后端 400 为准。

## 5.3 Run / Case 结果中的 canonical reasoning 字段

前端读取 reasoning 元数据时，按下面顺序读：

### A. 当前 case 优先

```text
case.reasoning_metadata.reasoning_profile_id
case.reasoning_metadata.reasoner_adapter
case.reasoning_metadata.selection_mode
case.reasoning_metadata.requested_reasoning_profile_id
case.reasoning_metadata.requested_reasoner_adapter
case.reasoning_metadata.fallback_applied
case.reasoning_metadata.fallback_reason
```

### B. records run 级回退

如果 case 上没有，再读：

```text
runDetail.summary.pipeline.reasoning_profile_id
runDetail.summary.pipeline.reasoner_adapter
runDetail.summary.pipeline.selection_mode
```

### C. evidence/image 单 case 回退

如果 summary 里没有，再读：

```text
runDetail.analysis.reasoning_metadata.reasoning_profile_id
runDetail.analysis.reasoning_metadata.reasoner_adapter
runDetail.analysis.reasoning_metadata.selection_mode
```

## 5.4 visual_evidence 的浏览器可访问地址

**统一规则：backend 模式下，前端展示图片时必须优先使用 `url`。**

读取顺序统一为：

```text
url ?? preview_path ?? source_path
```

原因：

- `url` 是浏览器可访问的 API 工件路径；
- `preview_path` 可能是后端机器本地磁盘路径；
- 旧逻辑 `preview_path || url` 在真实联调时容易失效。

## 5.5 review / RCA claim boundary 不能被 reasoning UI 稀释

即使用户显式选择了 `tep_root_kgd_default`，前端也**不能**把 RCA 结论写成“已验证根因”。

reasoning adapter/profile 只回答：

- 这次是**通过哪种推理路线**得到候选结果；
- 不是回答“这个结果是否已经被证明”。

---

## 6. UI 设计原则（极简、低返工）

## 6.1 只允许在现有页面做轻量增强

只在以下位置动 UI：

1. `/evidence` 上传表单：新增一个紧凑 `Reasoning Profile` 选择器；
2. `/evidence` 当前 run / case 摘要区：新增小型标签，显示实际生效 adapter/profile；
3. `/graphs` reasoning / candidate 区：新增小型标签，显示当前 case 的实际推理路线；
4. 如有 fallback，最多加一条低强调提示文案。

**不允许**：

- 新增独立 reasoning 页面；
- 新增 profile 编辑器；
- 新增展开式复杂参数表单；
- 新增全局设置页。

## 6.2 控件风格

沿用现有 RootLens 风格：

- 使用现有 `SectionCardTitle`、`WorkbenchHero`、`a-tag`、`a-select`、`a-alert`；
- 使用紧凑型 1 行或 2 行摘要，不做长文案；
- adapter/profile 信息优先显示为 tag，而不是大段说明。

## 6.3 推荐的最小 UI 方案

### 上传区

在 `dataset` / `top_k` 同一层级增加：

- 字段名：`Reasoning Profile`
- 默认值：`自动（按数据集默认）`
- 有 dataset 时：
  - 展示该 dataset 对应 profiles
- 无 dataset 时：
  - 仅保留 `自动`，并用一行次级说明提示：
    - “如需显式选择，请先指定 dataset”

### 运行结果区

在当前 active run 或 active case 摘要中展示：

- `Adapter: TEP Root-KGD`
- `Profile: tep_root_kgd_default`
- `Mode: Explicit`

### 图谱页

在 reasoning trace / root cause summary 附近增加一组小标签即可，不新增卡片层级。

## 6.4 最小 label 建议

前端可本地做一个轻量映射：

| 原值 | UI 标签 |
| --- | --- |
| `generic_graph_path` | `Generic Path` |
| `tep_root_kgd` | `TEP Root-KGD` |
| `default` | `Auto` |
| `explicit` | `Explicit` |
| `direct` | `Direct` |

若遇到未知值，直接回退显示原值，不额外阻塞联调。

---

## 7. 双轨开发拆分（agent ownership）

## 7.1 前端 agent 负责范围（RootLens 仓库）

前端 agent 只改 RootLens，不改 KGTraceVis。

建议 ownership：

- `src/api/contracts.ts`
- `src/api/client.ts`
- `src/services/rootlens-service.ts`
- `src/services/mock-backend.ts`
- `src/services/ui-copy.ts`
- `src/views/EvidenceManageView.vue`
- `src/views/GraphExploreView.vue`
- 必要时：
  - `src/services/provenance-inspector.ts`
  - `src/services/evidence-observation.ts`

前端 agent 目标：

1. 接住新的 bootstrap / upload 契约；
2. 在 `/evidence` 加最小 reasoning profile 选择；
3. 在 `/evidence` 与 `/graphs` 显示实际生效 reasoning 元数据；
4. 修正 visual evidence 的 URL 优先级；
5. 保证 mock / replay 不炸。

## 7.2 后端 agent 负责范围（KGTraceVis 仓库）

后端 agent 只改 KGTraceVis，不改 RootLens。

建议 ownership：

- `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis/service/api.py`
- `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis/service/dashboard.py`
- `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis/service/runs.py`
- `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis/service/run_enrichment.py`
- `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis/workflows/reasoning_registry.py`
- `/Users/bytedance/my_project/MVTec/KGTraceVis/src/kgtracevis/workflows/root_cause_provider_selection.py`
- `/Users/bytedance/my_project/MVTec/KGTraceVis/configs/reasoning_profiles/*`
- 必要时相关 tests / docs

后端 agent 目标：

1. 确认 dashboard / upload / run detail 的 reasoning 契约稳定；
2. 确认默认行为完全不变；
3. 确认 records/evidence/image 三条路径都能带出 reasoning metadata；
4. 确认 dataset/profile 不兼容时报错清晰；
5. 只做包装层与契约补齐，不引入算法漂移。

## 7.3 集成 agent / 主线程负责范围

集成方负责：

1. 维护本文档；
2. 做前后端字段真值确认；
3. 处理小范围 glue code；
4. 启动联调、构建、smoke、回归；
5. 收敛最终验收结论。

---

## 8. 前端落地要求（必须满足）

## 8.1 Contract 层

- `DashboardBootstrap` 明确声明 `reasoning_profile_options`
- `UploadRequest` 明确声明 `reasoning_profile_id`
- 新增必要的前端 helper type：
  - `DashboardReasoningProfileOption`
  - 可选的 `RunReasoningSummary` / helper resolver

## 8.2 行为层

- 调用 `uploadRun()` 时，如果用户显式选中 profile，就把 `reasoning_profile_id` 带上；
- 若是 `Auto`，则不要发送或发送空值；
- mock 模式下 bootstrap 也要给出兼容字段，至少保证 UI 不报错；
- replay 模式保持只读，不额外要求显式 profile 选择能力。

## 8.3 展示层

- `/evidence`：展示“请求值”和“生效值”时，以**生效值优先**；
- `/graphs`：展示当前 case 的生效 adapter/profile/mode；
- 如果 `fallback_applied=true`，可以显示一个轻提示：
  - “当前结果已回退到通用路径推理”
- 但不要把 fallback 做成红色错误，除非后端明确返回失败。

## 8.4 兼容层

- 旧 run 没有 reasoning metadata 时，UI 允许显示 `--` 或 `Auto`；
- 不因为历史 run 缺字段而阻塞页面渲染。

---

## 9. 后端落地要求（必须满足）

## 9.1 Bootstrap

- `GET /api/dashboard/bootstrap` 返回稳定的 `reasoning_profile_options`
- 选项按 dataset 分组
- 每组至少包含一个 `default=true` 的 profile

## 9.2 Upload

- `POST /api/runs/upload` 接受 `reasoning_profile_id`
- records / evidence / image 三条路径都正确透传
- dataset/profile 不兼容时返回明确 400

## 9.3 Run detail / case detail

- `RunDetail.cases[*].reasoning_metadata` 尽量稳定存在；
- `summary.pipeline.*` 对 records run 稳定可读；
- `analysis.reasoning_metadata` 对 evidence/image run 稳定可读；
- 至少保证以下键可读：
  - `reasoning_profile_id`
  - `reasoner_adapter`
  - `selection_mode`
- 若发生 fallback，补充：
  - `fallback_applied`
  - `fallback_reason`
  - `requested_reasoning_profile_id` / `requested_reasoner_adapter`（如存在）

## 9.4 默认行为不变

- `tep` 默认仍走 `tep_root_kgd_default`
- 非 `tep` 默认仍走 `generic_graph_path_default`
- 不新增 `provider_mode`、`tep_rca_provider` 等并行开关
- 不改变现有 `scoring_method` 兼容值

---

## 10. 联调 smoke 路径（按优先级执行）

## 10.1 第一优先：records 上传

推荐先打通：

1. 前端 backend 模式打开 `/evidence`
2. 选择 `records`
3. 指定 dataset（例如 `tep` 或 `mvtec`）
4. 选择 `Reasoning Profile`
   - `Auto`
   - 再测一次显式 profile
5. 上传后检查：
   - run 成功生成；
   - `/evidence` 可看到生效 adapter/profile/mode；
   - `/graphs` 可看到同一组信息；
   - RCA / path graph / review 流程不受影响。

## 10.2 第二优先：evidence 上传

重点检查：

- 没有显式 dataset override 时，默认 `Auto` 仍能工作；
- 若前端允许选择 dataset + profile，则后端能正确校验与回传 metadata。

## 10.3 第三优先：image 上传

重点检查：

- `mvtec` image 场景下 reasoning profile UI 不与 model preset 冲突；
- 图片预览使用 `url` 优先，浏览器端能加载。

---

## 11. 最终验收清单（必须全部满足）

### A. 合同层

- [ ] RootLens 已声明 `reasoning_profile_options`
- [ ] RootLens 上传请求已支持 `reasoning_profile_id`
- [ ] KGTraceVis bootstrap / upload / run detail 契约稳定

### B. 交互层

- [ ] `/evidence` 有极简 reasoning profile 选择器
- [ ] `/evidence` 能显示实际生效 adapter/profile/mode
- [ ] `/graphs` 能显示当前 case 实际生效 adapter/profile/mode
- [ ] UI 没有新增复杂页面或长表单

### C. 数据流层

- [ ] `Auto` 时默认映射正确
- [ ] `Explicit` 时后端能正确消费
- [ ] dataset/profile 不兼容时报错清晰
- [ ] fallback metadata 能在前端被兼容显示

### D. 兼容层

- [ ] mock 模式不报错
- [ ] replay 模式不报错
- [ ] 历史 run 缺 metadata 时页面仍可打开

### E. 媒体预览层

- [ ] backend 模式图片预览优先走 `url`
- [ ] 不再优先使用后端本地磁盘 `preview_path`

---

## 12. 给两个开发 agent 的最后约束

### 对前端 agent

- 不要发明新工作流；
- 不要设计“reasoning lab”；
- 不要要求后端额外返回一堆 label/description 字段才能开工；
- 先用最小 contract 跑通，再做文案映射。

### 对后端 agent

- 不要借此机会改算法；
- 不要引入新 provider mode；
- 不要把 profile 说成 algorithm generator；
- 先保证默认行为不变，再补合同稳定性。

### 对集成 agent

- 若前后端产生冲突，优先保住：
  1. 默认行为不变；
  2. UI 极简；
  3. 合同稳定；
  4. 旧 run / mock / replay 兼容。

---

## 13. 一句话版执行摘要

> **本轮不是做“新推理系统”，而是把 KGTraceVis 已经存在的 reasoning adapter/profile 契约，以最小 UI、最小返工、最小行为漂移的方式接入 RootLens，并完成前后端联调打通。**
