# RootLens 论文第 5 节与当前前端能力差异、前端设计方案与分期路线

> **历史文档说明（2026-05-17）**
>
> 本文记录的是 RootLens 早期“前端承接本地建图 / 本地推理 / 对齐规划”的阶段性设计或交接语义，**已不代表当前实现边界**。
> 当前请优先以 `src/doc/backend-integration-current.md` 为真值；RootLens 现仅保留 backend-first 工作台、内置 Demo 与成品回放导入。


> 文档定位：**审阅稿 / 决策稿**
>
> 目标：基于论文 PDF `src/doc/RootLens_ChinaVis_2026 (2).pdf` 的 **Section 5: Visual Analytics System**，对照当前仓库里真实存在的前端页面与交互，梳理差异（difference），并给出：
>
> 1. 每个 difference 的前端设计方案（允许先用 mock 数据）；
> 2. 差异之间的依赖关系；
> 3. 按“从易到难”拆分的多期实现计划；
> 4. 若某些差异成本过高或风险过大，论文如何**退守修改**，而不是强行让系统去对齐。
>
> 核心原则：**进可攻，退可守**。
>
> - **攻**：如果要对齐论文第 5 节的完整叙事，本文件给出一条 mock-first 的前端实现路线。
> - **守**：如果某些差异太难、太贵、太不稳，本文件也给出论文文本上的保守改写建议，避免论文 claim 超出系统真实能力。

---

## 0. 本文依据的 source of truth

### 0.1 论文 PDF 第 5 节实际内容

论文 PDF 中，第 5 节实际标题为：

- `5 VISUAL ANALYTICS SYSTEM`
- `5.1 Evidence Overview and Detection Details`
- `5.2 Knowledge Graph Reasoning View`
- `5.3 Provenance and Human Feedback`

第 5 节的核心主张可以压缩为：

1. RootLens 是一个 **linked visual analytics workbench**，不是黑盒结果表。
2. 工作流围绕三类 workspace：
   - evidence review
   - graph/path exploration
   - provenance-centered feedback and graph-material curation
3. Evidence workspace 应支持：
   - uploaded runs / replayed runtime assets
   - run history / workflow progress
   - case-centered entry
   - source / modality / time / confidence / case association filtering
   - modality-specific detail（image regions, masks, heatmaps, time-series windows, snippets）
   - 共享分析状态（case / filters / observation）
4. Graph workspace 应支持：
   - global graph + case-specific explanation subgraph
   - ranked, reviewable candidate hypotheses
   - candidate card 与 path graph 的 linked inspection
   - run / case switching 与跨 case recurrence 对比
   - 显式 claim boundary
5. Provenance & feedback 应支持：
   - source-grounded provenance
   - append-only review state
   - bounded review targets（path / edge / entity link / correction）
   - graph-material workspace 中的 source-grounded build / detail / recipe / review-oriented management

### 0.2 当前前端真实实现依据

以当前代码为准，而不是历史/过时文档：

- 路由：`src/router/index.ts`
- 页面：
  - `src/views/EvidenceManageView.vue`
  - `src/views/GraphExploreView.vue`
  - `src/views/MaterialsManageView.vue`
- 当前路由只有：
  - `/evidence`
  - `/graphs`
  - `/materials`

**注意：当前代码里并没有真正挂出的 `/import` 或 `/reasoning` 路由。**

这意味着：论文第 5 节的整体叙事，当前前端只实现了一个**部分对齐版本**，还没有完整系统化落地。

---

## 1. 当前前端能力快照

### 1.1 已有能力（可直接认为已部分对齐论文第 5 节）

| 论文目标 | 当前前端现状 | 结论 |
|---|---|---|
| evidence workspace | `/evidence` 已有上传、run 列表、case/evidence 列表、基础根因摘要 | 骨架已对齐 |
| graph/path exploration | `/graphs` 已有总图谱、局部子图、根因列表、候选反馈、节点/边选中 | 骨架已对齐 |
| graph-material workspace | `/materials` 已有素材搜索/筛选/上传/选材/build recipe/build list | 骨架已对齐 |
| candidate review | `/graphs` 可对候选进行 accept/reject，并维护本地策展草稿 | 部分对齐 |
| source-grounded graph material list | `/materials` 已有 source upload、source type / format / scenario 等字段 | 部分对齐 |
| mock-first runtime | `mock-backend.ts`、`rootlens-data.ts` 已提供较强本地 mock / imported session 基础 | 非常适合继续扩展 |

### 1.2 当前明显未落地的能力

这部分是论文第 5 节的真正 difference 来源：

- evidence workspace 没有显式的 **replayed runtime assets** 入口
- evidence workspace 没有 observation 级 **modality-specific detail** inspector
- 共享分析状态还没有 observation / filter 级跨页保持
- graph workspace 还没有显式的 **evidence → entity → path → candidate** 推理链路视图
- graph workspace 还没有 **跨 case recurrence** 对比
- provenance 还不是一等公民，缺 provenance drawer / ledger
- feedback 还不是 **append-only bounded review state**
- materials workspace 还没有真正的 **build details / QA / review queue / source-grounded provenance inspection**

---

## 2. Difference 矩阵：论文第 5 节 vs 当前前端

下面每个 difference 都给出：

- **论文要求**：Section 5 的主张
- **当前前端状态**：当前代码里有什么、缺什么
- **前端设计方案**：可以先用 mock 做出来的方案
- **mock-first 可行性**：能否先不依赖后端
- **难度**：Easy / Medium / Hard / Very Hard
- **依赖关系**：这个差异是否依赖别的差异先做
- **退守论文方案**：如果不做，论文应该怎么保守改写

---

### D1. Evidence workspace 缺“replayed runtime assets” 的显式入口

**论文要求**
- 5.1 明确写 analysts 可从 uploaded runs 或 replayed runtime assets 开始。

**当前前端状态**
- `/evidence` 有 upload run。
- 代码底层已有 imported session/local session 能力，但没有显式 UI 入口。
- 当前 router 也没有 `/import`。

**前端设计方案**
- 在 `/evidence` 顶部“上传与运行状态”卡中新增一个 `Session Source Strip`：
  - `Live Upload`
  - `Replay Assets`
- 切到 `Replay Assets` 后显示：
  - `rootlens-runtime.json`
  - `unified-graphs.json`
  - 可选 `workspace-export.json`
- 同卡内显示 replay session summary：
  - source mode
  - datasets
  - cases
  - warnings
  - imported at

**mock-first 可行性**
- **高**。直接复用 `rootlens-data.ts` 中现有 imported session 能力。

**难度**
- **Easy**

**依赖关系**
- 无强依赖。

**退守论文方案**
- 若不实现，建议把论文中 “uploaded runs or replayed runtime assets” 改成：
  - “uploaded runs, with replay capability available in the underlying browser runtime but not yet exposed as a dedicated analyst-facing entry.”

---

### D2. Evidence workspace 缺 source / modality / time / confidence 维度的 progressive narrowing

**论文要求**
- 5.1 明确要求 evidence item 可按 source、modality、time、confidence、case association 浏览与过滤。

**当前前端状态**
- 当前主要只有：
  - graph
  - facet
  - keyword
- 没有 source / time / confidence filter。
- modality 只有 facet 的近似表达，不够直接。

**前端设计方案**
- 把 `/evidence` 过滤区扩为两层：
  1. 全局过滤：Graph / Modality / Source / Time range / Confidence range / Keyword
  2. 当前 Case 下 observation drilldown：按 observation 逐条浏览
- 每条 observation 以紧凑 list item 展示：
  - modality badge
  - source
  - timestamp
  - confidence
  - obs_id
  - linked entity count

**mock-first 可行性**
- **高**。可从当前 `evidence.observations[]` 做前端派生。

**难度**
- **Easy ~ Medium**

**依赖关系**
- 最好和 D3 一起做（因为 observation detail panel 会共用 observation 对象）。

**退守论文方案**
- 若不实现，建议把论文里 “browsed by source, modality, time, confidence” 改为：
  - “browsed by case, graph association, facet, and keyword, with richer modality- and confidence-aware narrowing planned for future iterations.”

---

### D3. Evidence workspace 缺 observation 级 detection details / modality-specific details

**论文要求**
- 5.1 强调 image regions / masks / heatmaps / time-series windows / textual snippets 应贴近 evidence item 展示。

**当前前端状态**
- 当前只有 case/evidence list、tooltip、根因摘要。
- 没有 observation detail inspector。

**前端设计方案**
- 在 `/evidence` 增加 `Observation Detail Panel`，支持按模态切换 detail：
  - image_defect：原图、mask、heatmap、bbox、location
  - variable：变量名、异常窗口、sparkline、direction、severity
  - log_event：event code、equipment、snippet、上下文
  - text/document：source path、snippet、matched terms

**mock-first 可行性**
- **中高**。可复用：
  - `visual_evidence`
  - `raw_evidence_refs`
  - 再补一个 observation detail mock 派生层。

**难度**
- **Medium**

**依赖关系**
- 依赖 D2 的 observation drilldown 会更顺。

**退守论文方案**
- 若不实现，建议把论文里 “displayed close to the corresponding evidence item” 改为：
  - “partially surfaced through compact evidence summaries and linked previews, with modality-specific drill-down panels left to future work.”

---

### D4. 共享分析状态缺 observation / filter 级跨页保持

**论文要求**
- 5.1 结尾要求 selected case 和 evidence filters 被 preserved as shared analysis state。

**当前前端状态**
- 当前共享状态主要是 run / case / candidate / path。
- 没有 observation 级状态，也没有 filter state 跨页保持。

**前端设计方案**
- 扩展 `WorkbenchState`：
  - `selectedObservationId`
  - `evidenceFilterGraph`
  - `evidenceFilterModality`
  - `evidenceFilterSource`
  - `evidenceFilterKeyword`
  - `evidenceFilterConfidenceRange`
  - `evidenceFilterTimeRange`
- `/evidence -> /graphs` 时保留上下文；
- `/graphs` 可知道自己是从哪条 observation 跳入。

**mock-first 可行性**
- **高**。纯前端状态层实现。

**难度**
- **Medium**

**依赖关系**
- 与 D2 / D3 / D5 强相关。

**退守论文方案**
- 若不实现，建议把论文里 “selected case and evidence filters are preserved as shared analysis state” 改为：
  - “selected run and case are preserved across workspaces, while finer-grained observation and filter state sharing remains partial.”

---

### D5. Graph workspace 缺 evidence → entity → path → candidate 的显式 linked inspection

**论文要求**
- 5.2 强调 graph workspace 要让 analyst inspect how evidence is connected to entities, relations, and candidate hypotheses。
- 还强调 selecting a candidate lets analysts traverse from symptoms to intermediate evidence and candidate causes。

**当前前端状态**
- 有总图谱、局部子图、候选根因、基础联动。
- 但没有显式的 reasoning trace / explanation chain。

**前端设计方案**
- 在 `/graphs` 增加 `Reasoning Trace Panel`：
  - symptom / observation
  - linked entity
  - relation
  - intermediate node
  - candidate cause
- 每一步点击后：
  - 图谱高亮对应 node/edge
  - 右侧候选定位
  - 若从 `/evidence` 跳入，则显示 source observation badge

**mock-first 可行性**
- **中高**。可先从 `path_graph + linked_entities + ranked_root_causes` 拼 mock trace。

**难度**
- **Medium ~ Hard**

**依赖关系**
- 依赖 D4（共享 observation 状态）效果最好。

**退守论文方案**
- 若不实现，建议把论文里 “lets analysts traverse from symptoms to intermediate evidence and candidate causes” 改为：
  - “supports candidate-to-graph linked inspection, while a full stepwise symptom-to-cause trace view is still under development.”

---

### D6. Graph workspace 缺跨 case recurrence 对比

**论文要求**
- 5.2 明确说 graph view 可比较 similar entities or paths recur across cases。

**当前前端状态**
- 可以切 run / case。
- 不能看 recurring entities / recurring paths 的比较结果。

**前端设计方案**
- 在 `/graphs` 增加一个 `Cross-case Compare Drawer`：
  - recurring entity chips
  - recurring path list
  - 在其他 case 中出现次数
  - quick jump to case

**mock-first 可行性**
- **高**。对当前 run 的 case 列表做前端派生即可。

**难度**
- **Medium**

**依赖关系**
- 依赖 graph 页已有 case switching，但不依赖其他高难功能。

**退守论文方案**
- 若不实现，建议把论文里 “allowing analysts to compare whether similar entities or paths recur across cases” 改为：
  - “supporting run/case switching, with explicit recurrence comparison reserved for future versions.”

---

### D7. Provenance 还不是一等公民，缺 provenance-centered review UI

**论文要求**
- 5.3 里 provenance 是核心，不只是 tooltip。
- 要能回到 evidence snippets、source materials、document locations、model outputs。

**当前前端状态**
- 只有零散 provenance 痕迹：
  - edge evidence snippet
  - raw refs tooltip
  - materials 列表
- 没有统一 provenance drawer / inspector。

**前端设计方案**
- 新增统一 `Provenance Inspector`，能在 `/graphs` 和 `/materials` 被打开。
- 支持 target：
  - path
  - edge
  - entity link
- 每条 provenance record 展示：
  - source type
  - source id / file path
  - snippet / preview
  - confidence
  - claim boundary
  - linked review target

**mock-first 可行性**
- **中高**。可从 `raw_evidence_refs`、`visual_evidence`、`buildDetail.manifest` 先派生 mock。

**难度**
- **Hard**

**依赖关系**
- 与 D8、D9 强相关，但可以先做只读版 provenance drawer。

**退守论文方案**
- 若不实现，建议把论文里 “surfaces source-grounded provenance” 改为：
  - “surfaces lightweight provenance cues (e.g., snippets and source metadata) for selected graph elements, while a dedicated provenance inspection workspace remains future work.”

---

### D8. Feedback 不是 append-only bounded review state

**论文要求**
- 5.3 说 feedback 应该是 append-only review state。
- strongest review targets 应包括：
  - path
  - edge
  - entity link
  - correction
- candidate card 的反馈要保守描述。

**当前前端状态**
- 当前反馈主要是：
  - candidate accept/reject
  - graph curation local draft
- 没有 review ledger，没有 bounded target history。

**前端设计方案**
- 拆成两层：
  1. `/graphs` 保留 quick review
  2. 新增 `Review Ledger Panel`
- ledger 中按 run / case / target type 展示 append-only 记录：
  - target_type
  - target_id
  - action
  - note
  - reviewer
  - timestamp
- review target 扩展到：
  - path
  - edge
  - entity_link
  - correction

**mock-first 可行性**
- **高**。`mock-backend.ts` 已有 `feedback_records`，只差 UI 组织。

**难度**
- **Hard**

**依赖关系**
- 与 D7 高相关。

**退守论文方案**
- 若不实现，建议把论文里 “append-only review state over bounded review targets” 改为：
  - “lightweight review feedback over candidate and selected graph targets, with append-only bounded target review planned for future work.”

---

### D9. Materials workspace 缺 build details / QA / review queue / provenance drilldown

**论文要求**
- 5.3 后半段强调：
  - build lists
  - build details
  - recipe forms
  - review-oriented graph management

**当前前端状态**
- `/materials` 已有：
  - source search/filter/sort/upload
  - build list
  - recipe form
- 但 UI 里没有把这些 detail 真正展示出来：
  - `buildDetail.summary`
  - `buildDetail.manifest`
  - `buildDetail.qa_report`
  - review queue / edge review

**前端设计方案**
- 在 `/materials` 增加 `Build Detail Panel`，分 3 个 tab：
  1. Manifest
  2. QA / Summary
  3. Review Queue
- 每个 build 可展开 source-grounded detail，支持从 source material 回跳。

**mock-first 可行性**
- **非常高**。这部分是当前 mock 数据最完整的一块。

**难度**
- **Easy ~ Medium**

**依赖关系**
- 基本独立，适合作为第一期优先落地。

**退守论文方案**
- 若不实现，建议把论文里 “build details, and recipe-style forms support lightweight orchestration” 改为：
  - “build lists and recipe-style forms are currently available, while richer build detail and review queue inspection are left for future iterations.”

---

### D10. Claim boundary 还没有成为全局可见的视觉语言

**论文要求**
- 5.2 和 5.3 都强调：candidate ≠ verified root cause。
- claim boundary 应始终 explicit。

**当前前端状态**
- 已经有保守措辞，但视觉上不够系统化。
- 没有统一 badge / legend / status vocabulary。

**前端设计方案**
- 在三个工作台统一增加 Claim Boundary 语义层：
  - candidate only
  - under review
  - reviewed
  - rejected
  - revised
- 落点：
  - root-cause card
  - graph provenance target
  - review ledger
  - materials build detail

**mock-first 可行性**
- **高**。纯前端状态语义整合。

**难度**
- **Easy**

**依赖关系**
- 与 D7 / D8 联动更强，但也可先独立落地。

**退守论文方案**
- 若不实现，建议把论文里 “keep the boundary explicit” 改为：
  - “keep the boundary explicit through conservative language and selected UI cues, rather than through a fully standardized boundary encoding.”

---

## 3. 差异之间的相关性（依赖图）

### 3.1 强依赖链

```text
D2 Evidence filters
   └─→ D3 Observation detail panel
         └─→ D4 Shared observation/filter state
               └─→ D5 Reasoning trace in graph

D7 Provenance inspector
   └─→ D8 Append-only bounded review ledger

D9 Build detail / QA / review queue
   └─→ 可为 D7 提供 materials-side provenance 入口
```

### 3.2 相对独立、适合先做的差异

这些可以先做，收益高、风险低：

- **D1** replay/runtime assets 入口
- **D9** materials build detail / QA / review queue
- **D10** claim boundary badge/legend

### 3.3 高风险、高成本差异

这些如果后端语义没跟上，前端很容易做成“空壳”：

- **D5** evidence → entity → path → candidate 的完整 reasoning trace
- **D7** provenance-centered review 的统一 inspector
- **D8** append-only bounded review state

这些是最适合“**要么系统认真补齐，要么论文谨慎收缩 claim**”的部分。

---

## 4. 从易到难的多期实现计划

下面按“**先做最稳的、最不容易做空壳的**”排序。

---

### Phase A：低风险、高回报、最适合先实现

**目标**：先把最容易落地、最能增强论文可信度的 UI 能力补齐。

**包含差异**
- D1 replay/runtime assets 入口
- D9 materials build detail / QA / review queue
- D10 claim boundary 统一视觉语义

**为什么先做**
- 都有很强现成基础：
  - imported session
  - buildDetail / manifest / qa_report
  - feedback / status state
- 改完后论文第 5 节会立刻更接近真实系统。

**实现结果（攻）**
- `/evidence` 真正成为 uploaded + replay 双入口
- `/materials` 真正具备 review-oriented build management
- 整个系统有统一 claim boundary

**如果只做到这里就停止（守）**
- 论文可以保留“三工作台 + provenance-centered review-oriented materials” 的大框架叙事；
- 但需要把 observation detail / full provenance / bounded review 相关表述降级为：
  - partial
  - lightweight
  - future work

**建议优先级**
- **最高**

---

### Phase B：补齐 Evidence inspection，让论文 5.1 更可信

**目标**：把 5.1 写到的 evidence workspace 真正落到 observation 粒度。

**包含差异**
- D2 richer progressive narrowing
- D3 observation detail panel
- D4 shared observation/filter state

**为什么是第二期**
- 它们互相依赖，适合一起做。
- 做完之后，论文 5.1 的叙事会大幅从“描述性”变成“可证明”。

**实现结果（攻）**
- `/evidence` 不只是 case/evidence list，而是真正的 detection detail workspace。
- `/graphs` 能知道用户是从哪条 observation 来的。

**如果只做到这里就停止（守）**
- 论文 5.1 可以基本保留原写法；
- 但 5.2 / 5.3 仍需保守描述，因为 graph-side reasoning trace 和 provenance review 还没补全。

**建议优先级**
- **高**

---

### Phase C：补齐 Graph reasoning inspection，让论文 5.2 更可信

**目标**：把 graph workspace 从“图谱浏览页”升级成“推理检查页”。

**包含差异**
- D5 reasoning trace panel
- D6 cross-case recurrence compare

**为什么是第三期**
- 这是论文 5.2 的关键，但需要前两期提供更稳定的 evidence/context state。
- D5 的 UI 很容易空心化，必须有 observation/state 基础才值得做。

**实现结果（攻）**
- `/graphs` 不只是总图 + 子图，而是 evidence-linked reasoning view。
- 能支撑论文里 “traverse from symptoms to intermediate evidence and candidate causes”。

**如果只做到这里就停止（守）**
- 论文 5.2 可以保留大部分写法；
- 但 5.3 仍需保守，因为 provenance & bounded review 还不完整。

**建议优先级**
- **中高**

---

### Phase D：补齐 Provenance and Human Feedback，让论文 5.3 完整成立

**目标**：把 provenance 和 feedback 从零散能力提升成系统性工作流。

**包含差异**
- D7 provenance inspector
- D8 append-only bounded review ledger

**为什么最晚做**
- 这是最重、最容易超 scope 的一块。
- 需要稳定的 target semantics、稳定的数据回溯、稳定的 ledger model。
- 如果硬做，很容易出现“UI 很复杂但实际没有足够可信语义”的情况。

**实现结果（攻）**
- 论文 5.3 基本可以按现有写法站得住。
- 系统从“可演示前端”升级成“可信 review workflow”。

**如果决定不做（守）**
- 建议直接修改论文，把 5.3 收缩为：
  - lightweight provenance cues
  - lightweight review feedback
  - materials-oriented construction support
- 不再 claim：
  - append-only bounded review state
  - full provenance-centered inspection

**建议优先级**
- **中 / 可选**（取决于论文投稿策略）

---

## 5. 进可攻，退可守：推荐决策策略

### 方案 A：系统尽量对齐论文（进攻型）

适合场景：
- 你希望论文第 5 节尽量保持现有叙事；
- 也愿意接受多期前端迭代；
- 可以接受 mock-first，再逐步替换真实后端语义。

**推荐路线**
- 先做 Phase A
- 再做 Phase B
- 再做 Phase C
- 最后再决定是否做 Phase D

**结果**
- 到 Phase C 结束时，论文第 5.1 / 5.2 大体可信；
- 5.3 还需视 D7/D8 是否真的做完。

### 方案 B：优先稳住论文可信度，避免系统被拖入高成本实现（防守型）

适合场景：
- 时间有限；
- 后端语义还没准备好；
- 不希望前端去硬撑 provenance / bounded review 这种高语义模块。

**推荐路线**
- 只做 Phase A + Phase B
- Phase C 只挑 D6（cross-case compare）这种前端派生型差异做
- Phase D 不做，直接改论文措辞

**结果**
- 系统仍然是一个很强的可视分析原型；
- 论文会从“强系统 claim”收缩为“partial but practical workbench”。

### 方案 C：最稳妥的折中路线（推荐）

**推荐顺序**
1. Phase A 全做
2. Phase B 全做
3. Phase C 先做 D6，再评估 D5 是否值得做
4. Phase D 默认不承诺，除非投稿前证明确实需要

**为什么推荐这个方案**
- 它能最大化保留论文第 5 节的骨架；
- 同时把最危险的 claim（full provenance / bounded review）放到最后决策；
- 非常符合“进可攻，退可守”。

---

## 6. 哪些 difference 更适合“改论文”而不是“硬实现”

如果必须选几项优先放弃系统实现、转而修改论文，我建议优先考虑这三项：

### 首选可收缩项
1. **D8 append-only bounded review state**
2. **D7 provenance-centered inspector**
3. **D5 full reasoning trace**

### 原因
- 它们最依赖高质量 target semantics 和 provenance semantics；
- 单靠前端 mock 很容易做得“像”，但不够“真”；
- 是最容易让论文 claim 超前于系统实装的部分。

### 推荐论文收缩话术
- “append-only bounded review state” → “lightweight review feedback on selected targets”
- “surfaces source-grounded provenance” → “surfaces lightweight provenance cues when available”
- “traverse from symptoms to intermediate evidence and candidate causes” → “supports linked candidate-to-graph inspection, with richer stepwise trace views left to future work”

---

## 7. 建议的下一步落地方式

如果后续要进入实现，我建议直接按下面方式拆任务：

### 第 1 轮实现（最值当）
- `/evidence` 加 replay/runtime asset 入口（D1）
- `/materials` 加 build detail / QA / review queue（D9）
- claim boundary 全局 badge 化（D10）

### 第 2 轮实现
- `/evidence` observation detail panel（D2 + D3）
- 扩展 `WorkbenchState` 做 observation/filter 跨页状态（D4）

### 第 3 轮实现
- `/graphs` reasoning trace panel（D5）
- `/graphs` cross-case recurrence compare（D6）

### 第 4 轮实现（可选）
- provenance inspector（D7）
- review ledger / bounded review targets（D8）

---

## 8. 最终建议

**如果你的目标是：论文尽快进入一个“既不虚写，也不把系统拖爆”的状态，建议这样做：**

- **一定做**：D1、D9、D10、D2、D3、D4
- **看时间和效果再决定**：D6、D5
- **默认走论文收缩而不是硬做**：D7、D8

这样可以做到：

- 系统层面：前端能力继续增强，且大多能 mock-first 落地；
- 论文层面：保留第 5 节的大框架，但把高风险部分收缩到系统真实可证明的范围内；
- 决策层面：每一期结束后，都有明确的“继续攻”或“开始守”的分叉点。

