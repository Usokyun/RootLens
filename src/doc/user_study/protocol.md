# RootLens User Study Protocol

## 1. Study Positioning

### 1.1 研究目标

本 study 旨在验证 RootLens 作为一个 evidence-centered visual analytics workbench，是否能帮助参与者完成以下工作：

1. 从多源异常输出中更快定位当前 case 的关键 evidence
2. 解释 evidence、KG entity、candidate path 与 ranked hypothesis 之间的关系
3. 在 provenance 和 claim boundary 明确的前提下做出 review decision
4. 在需要时对图谱素材或 candidate edge 进行轻量、可追溯的 curation

### 1.2 不验证的内容

为了与当前系统边界一致，本 study **不用于**声明以下结论：

- RootLens 自动给出真实因果正确的 root cause
- RootLens 的 detector 或 RCA 排名优于领域 SOTA
- 用户反馈会直接修正或写回生产知识图谱

## 2. Research Questions

### RQ1

与孤立 detector 输出相比，RootLens 是否更有助于参与者理解跨源 evidence 并形成 case context？

### RQ2

evidence detail、provenance、confidence 与 claim boundary 是否能帮助参与者把候选解释视为“可审查假设”而不是“已验证事实”？

### RQ3

`/evidence` 到 `/graphs` 的 linked workflow 是否让参与者更容易解释 evidence -> entity -> path -> candidate 的链路？

### RQ4

bounded feedback、review ledger 与 correction / consistency 相关信息，是否有助于参与者做出更清晰的 review decision？

### RQ5

对具有 KG 构建或知识整理背景的参与者而言，`/materials` 是否足以支持轻量、source-grounded 的 graph curation？

## 3. Study Design

### 3.1 推荐设计

推荐采用 **mixed-method、within-subject、expert-feedback-oriented** 设计：

- 条件 A：`Baseline packet`
  仅给参与者静态 detector / extraction 输出，不给 unified evidence、path graph 或 provenance workflow
- 条件 B：`RootLens interactive`
  让参与者使用 RootLens 当前前端进行同类任务

### 3.2 为什么建议 baseline 在前

建议采用固定顺序 `Baseline -> RootLens`，原因是：

- RootLens 一旦暴露 unified evidence 和 linked path，会显著改变参与者后续对 baseline 材料的理解方式
- 本研究更接近 formative / expert feedback，而不是严格去学习效应的可交换实验
- 如果担心顺序效应，应 **轮换 domain 顺序**，而不是把工具顺序完全对调

### 3.3 Counterbalance 方式

推荐只轮换场景顺序：

- 顺序 1：TEP -> WM811K -> MVTec
- 顺序 2：WM811K -> MVTec -> TEP
- 顺序 3：MVTec -> TEP -> WM811K

若包含 `/materials` builder task，则统一放在最后，避免打断核心 analyst workflow。

## 4. Participants

### 4.1 目标人数

- 正式版建议：`8-12` 人
- 最小 paper-facing 版本：`6` 人
- pilot：`2-4` 人

### 4.2 参与者构成

尽量覆盖以下角色中的 2-3 类：

- 工业过程 / RCA 相关研究者或工程师
- 视觉质检 / 缺陷分析相关研究者或工程师
- 知识图谱 / 数据治理 / 文档策展相关研究者或工程师
- 使用过 anomaly dashboard、incident review、quality investigation 工具的分析人员

### 4.3 纳入标准

满足任意两项即可：

- 有 1 年以上异常分析、RCA、质检、产线分析或相关研究经验
- 能阅读图结构、日志、表格、图像证据中的至少两类
- 曾参与过 root-cause review、质量复盘、知识整理或 failure analysis

## 5. Study Materials

### 5.1 Baseline Packet

每个场景准备 1 份静态材料，建议为 PDF 或幻灯片，内容只包含：

- detector / extractor 原始输出
- 基础 case 描述
- 必要的原图、heatmap、变量表或 pattern label
- 不包含：
  - unified evidence 列表
  - KG path
  - provenance inspector
  - feedback ledger
  - correction candidates

### 5.2 RootLens Interactive

建议使用 replay bundle 保持每位参与者看到的内容一致：

- 一致的 case 顺序
- 一致的图谱资产
- 一致的 evidence 与 path
- 一致的 review target

### 5.3 案例包建议

| Pack | 正式 study 建议 | 当前仓库 pilot 备选 | 主要验证点 |
| --- | --- | --- | --- |
| TEP pack | 1 个 top-1 成功 case + 1 个 near-miss case（如 fault 10/15） | `tep_0001` | 证据过滤、候选路径解释、claim boundary |
| WM811K pack | 1 个 consistency < 1.0 或 correction cue 明显的 case（如 scratch / random） | `wafer_0001` | mismatch inspection、traceability、review action |
| MVTec pack | 1 个 visual evidence 明确、path 可解释的 case（优先 cable 或 scratch 类） | `mvtec_fixture_clean_scratch`、`mvtec_noisy_0001` | image evidence、provenance、candidate plausibility |
| Materials pack | 1 个带 build detail / review queue 的 curation case | mock/backend 中现有 build queue | source-grounded KG curation |

### 5.4 环境配置

建议统一实验环境：

- 14-16 英寸笔记本
- 浏览器缩放 100%
- 中文界面
- 使用录屏与音频记录
- 主持人预先导入 replay bundle，并清空历史反馈或工作区草稿

## 6. Session Length

### 6.1 核心版

总时长建议 `60-70` 分钟：

| 环节 | 时长 |
| --- | --- |
| 介绍、同意与背景 | 10 分钟 |
| baseline 任务 | 10 分钟 |
| RootLens 训练与热身 | 5 分钟 |
| RootLens 核心任务 | 25 分钟 |
| 总结问卷 | 8 分钟 |
| 半结构化访谈 | 10 分钟 |

### 6.2 扩展版

若加入 `/materials` builder task，总时长建议 `75-85` 分钟。

## 7. Task Set

### 7.1 核心任务概览

| Task | 适用对象 | 页面 | 核心能力 | 对应论文点 |
| --- | --- | --- | --- | --- |
| T1 Evidence triage | 全部参与者 | `/evidence` | 过滤、定位、详情理解 | R1, R2 |
| T2 Hypothesis inspection | 全部参与者 | `/graphs` | candidate/path 比较与链路解释 | R3, R4 |
| T3 Provenance and bounded feedback | 全部参与者 | `/graphs` | provenance、review decision、ledger 理解 | R2, R5 |
| T4 Materials curation | builder / advanced 参与者 | `/materials` | source-grounded graph curation | R5 |

### 7.2 Task T1: Evidence Triage

#### 任务目标

让参与者从当前 case 中找到最关键的 1-2 条 evidence，并解释为什么它们值得继续追查。

#### 推荐操作路径

1. 进入 `/evidence`
2. 选择指定 run / case
3. 使用以下过滤维度缩小范围：
   graph、modality、source、confidence、time、keyword
4. 打开 `Observation Detail`
5. 说出：
   - 最值得继续看的 observation 是哪一条
   - 它的来源是什么
   - 它有多可靠
   - 下一步最想跳去哪里继续看

#### 记录指标

- 完成时间
- 是否主动使用过滤器
- 是否能说出 source / confidence / raw context
- 是否把 observation 当作“证据”而不是“最终原因”

#### 成功标准

参与者能够在限定时间内指出至少 1 条关键 observation，并给出带来源依据的解释。

### 7.3 Task T2: Hypothesis Inspection

#### 任务目标

让参与者从 evidence 上下文切换到 graph/path workspace，比较多个 candidate hypotheses，并解释当前最值得 review 的 candidate。

#### 推荐操作路径

1. 从 `/evidence` 直接跳转到 `/graphs`
2. 观察当前 candidate list、path graph、global graph
3. 选中 1 个 candidate
4. 打开 `trace` 视图，查看 evidence -> entity -> path -> candidate 链路
5. 如案例包支持 recurrence，再打开 `Cross-case Compare`
6. 说明：
   - 哪个 candidate 目前最值得关注
   - 是哪些 evidence / path 支撑了这个判断
   - 当前判断仍有哪些不确定性

#### 记录指标

- 完成时间
- 是否使用 candidate list 与 path graph 联动
- 是否显式提到 claim boundary
- 是否能区分“最优候选”和“已证实结论”

#### 成功标准

参与者能够选择 1 个当前最可解释的 candidate，并明确指出其支持线索与不确定点。

### 7.4 Task T3: Provenance and Bounded Feedback

#### 任务目标

让参与者检查一条 candidate path 或 graph edge 的来源依据，并记录一个 bounded review decision。

#### 推荐操作路径

1. 保持在 `/graphs`
2. 打开 provenance inspector 或 trace 中的来源信息
3. 选择 1 个 review target：
   path、edge、entity link、correction 或 root cause candidate
4. 给出 `accept`、`reject` 或 `needs further review` 的判断
5. 写下简短 note
6. 检查 `Review Ledger`，确认自己的操作被记录为 append-only state

#### 记录指标

- 是否查看 provenance 后再做判断
- note 是否引用了 source / uncertainty / mismatch
- 是否理解 feedback 不会直接改写 KG
- 是否认为 ledger 对复盘有帮助

#### 成功标准

参与者能给出一条有理由的 review decision，并能解释为什么这不是“直接修改图谱”的动作。

### 7.5 Task T4: Materials Curation

#### 任务目标

让有 builder / curator 背景的参与者使用 `/materials` 审查一条 source-grounded candidate edge 或 build queue 条目。

#### 推荐操作路径

1. 进入 `/materials`
2. 搜索或选择指定 material / build
3. 查看 `Detail / Extractions / Artifacts / Draft History / Source Draft Preview`
4. 打开 build detail、QA 或 review queue
5. 对 1 条 edge 或 draft 做出：
   accept / reject / keep as draft
6. 说明该判断依赖了哪些 source-grounded 证据

#### 记录指标

- 是否能说出 material、source、edge 之间的关系
- 是否能接受“review-oriented curation”而非“直接生产编辑器”
- 是否觉得该 workspace 足够支撑轻量策展

#### 成功标准

参与者能够基于 source-grounded 信息说明一条 curation decision，而不是只看 edge 名称做判断。

## 8. Recommended Session Flow

### 8.1 0-10 分钟：介绍与背景

1. 说明 study 目的
2. 告知系统不会自动证明真实因果
3. 完成同意与背景问卷

### 8.2 10-20 分钟：Baseline Packet

1. 展示指定场景的静态 detector / extractor 材料
2. 要求参与者完成与 T1/T2 等价的问题
3. 记录理解成本、切换成本与不确定点

### 8.3 20-25 分钟：RootLens 热身

1. 简要介绍三页：
   `/evidence`、`/graphs`、`/materials`
2. 明确：
   candidate != verified cause
3. 不对具体案例给分析提示

### 8.4 25-50 分钟：RootLens 核心任务

1. T1 Evidence triage
2. T2 Hypothesis inspection
3. T3 Provenance and bounded feedback

### 8.5 50-60 分钟：总结问卷

收集 baseline 与 RootLens 的对比感受、工作负荷、自信程度、claim-boundary 理解情况。

### 8.6 60-70 分钟：访谈

围绕以下主题追问：

- 什么地方最帮助你建立 case context
- 什么地方仍然模糊或过载
- 哪些元素最能帮助你决定 accept / reject / hold
- 你是否希望 feedback 直接改图，为什么

### 8.7 70 分钟以后：Builder 扩展任务

若参与者具备 KG / material curation 背景，再继续 T4。

## 9. Study Outputs

每次 session 至少收集以下产物：

- 背景问卷
- 任务完成记录
- 任务评分表
- 屏幕录制
- think-aloud 语音
- 最终比较问卷
- 访谈摘要
- 至少 2 条可引用的代表性原话

## 10. Paper-Facing Notes

### 10.1 建议写法

如果样本量较小，论文建议使用：

- `expert feedback sessions`
- `formative user study`
- `qualitative and task-based evaluation`

避免直接写成：

- `controlled user study proves`
- `statistically significant improvement`

### 10.2 结果边界

无论结果多积极，都应坚持：

- 参与者评价的是 **reviewability、traceability、sensemaking support**
- 不是对因果正确性的最终认证
