# RootLens 系统设计

> 系统名：**RootLens**
>
> 投稿目标：**ChinaVis**（可视化领域会议）
>
> 当前阶段：**Phase 1 — 浏览器本地运行时落地**

---

## 1. 论文元信息

### Title

**A Knowledge Graph-Based Method for Industrial Anomaly Detection and Root-Cause Analysis with Multi-Source Heterogeneous Evidence**

### Abstract（Final）

In complex industrial systems, root-cause analysis relies on heterogeneous clues from visual inspection, process monitoring, equipment logs, and engineering knowledge. Semantic, granularity, and reliability differences impede the interpretable connection of anomalies to plausible causes. This paper presents an interactive, knowledge graph-based visual analytics framework for multi-source industrial root-cause analysis. It organizes visual defects, process variable deviations, log events, and device relations in a shared graph space, combining two reasoning routes: multimodal clue organization via entity linking, consistency checking, and path ranking; and process fault analysis via contribution- and propagation-based candidate ranking. Centered on cognitive collaboration between analyst and system, the system supports interactive inspection of linked observations and comparison of alternative reasoning paths. Rather than pursuing full automation, the prototype serves as an exploratory workspace for root cause analysis and process fault case studies, helping analysts organize cross-source clues and examine plausible causes. We evaluate the framework on three industrial use cases, and the results confirm its effectiveness in guiding analysts toward correct and explainable root causes.

---

## 2. 项目定位

RootLens 是一个交互式知识图谱可视分析原型，用于多源异构工业根因分析。当前仓库承担四件事：

1. 作为两个上游项目（TEP_KG、MVTec/KGTraceVis）的前端整合壳。
2. 把源项目内容、路径和阅读入口显式记录，供后续 LLM/Agent 使用。
3. 在浏览器内承接本地文件导入、统一图谱归一化、Evidence 会话构建与 RCA 结果生成。
4. 沉淀融合设计文档，明确两条推理路线——多模态线索组织（entity linking + 一致性检查 + 路径排序）和过程故障分析（contribution + propagation 候选排序）——的运作流程。

**系统定位**：不追求全自动化，原型定位为根因分析和过程故障案例研究的**探索性工作台**，帮助分析人员组织跨源线索、审查合理的根因候选。认知协同是设计核心——图谱提出结构化假设，分析人员补充上下文并验证输出。

---

## 3. 两个上游项目

### 3.1 TEP_KG

- 路径：`/Users/bytedance/my_project/TEP_KG`
- 定位：工业流程时序场景下的知识图谱根因诊断与实验资产仓库。
- 核心价值：RBC + Root-KGD 根因排序与传播逻辑、边权训练、holdout 评估、TEP ontology、graph build。

### 3.2 MVTec / KGTraceVis

- 路径：`/Users/bytedance/my_project/MVTec/KGTraceVis`
- 定位：多源 evidence schema、路径排序与可视化工作台原型。
- 核心价值：图像/时序/日志统一 evidence schema、producer/adapter/path ranking/correction/feedback 流程、React 工作台。

### 3.3 分工映射

| 上游 | 提供什么 | 用到哪里 |
|---|---|---|
| TEP_KG | Code 解析规则、RBC 贡献度算法、PIKG 本体定义、RFPA 传播仿真 | L2 Code 提取器、路线 2（过程故障分析） |
| MVTec/KGTraceVis | Image/Sequence/Log adapter、Evidence schema、一致性打分/噪声修正/路径排序管线 | L2 Image/Sequence 提取器、路线 1（多模态线索组织） |

---

## 4. 系统分层架构

### 4.1 整体架构

```
                        多源异构素材
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
       Text/Code        Image          Sequence
           │               │               │
           └───────────────┼───────────────┘
                           │
              ┌────────────┼────────────┐
              │            ▼            │
              │   L2 模态提取层          │  ← 保留两个项目原有解析逻辑
              │   (graph-construction)  │
              │            │            │
              │            ▼            │
              │   L3 图谱组装 → L4 投影  │
              │   (Full KG + Backbone   │
              │    + RCA Graph)         │
              └────────────┼────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 ▼                 │
         │    ┌─────────────────────┐        │
         │    │  统一 Evidence JSON  │        │
         │    └──────────┬──────────┘        │
         │               │                   │
         │               ▼                   │
         │    ┌─────────────────────┐        │
         │    │  路线 1: 线索组织    │        │
         │    │  链接→一致性→排序   │        │
         │    └──────────┬──────────┘        │
         │               │                   │
         │               ▼                   │
         │    ┌─────────────────────┐        │
         │    │  路线 2: 故障分析    │        │
         │    │  RBC→传播→RootScore │        │
         │    └──────────┬──────────┘        │
         │               │                   │
         └───────────────┼───────────────────┘
                         │
                         ▼
              ┌────────────────────────┐
              │   RootLens 可视化工作台  │  ← Vue 3 + Arco Design
              │   图谱浏览 + 路径对比    │     交互式探索 + 人工反馈
              │   + 证据审查 + 认知协同  │
              │   + 双路线融合展示       │
              └────────────────────────┘
```

### 4.2 三层模块

系统按功能划分为三个模块，各有一份设计文档：

| 模块 | 文档 | 职责 | 输入 → 输出 |
|---|---|---|---|
| **模块一：图谱构建** | `src/doc/module-1-graph-construction.md` | 四种模态异构素材 → 统一知识图谱（L1-L4 流水线），保留两个项目的原有解析逻辑 | 原始素材 → Full KG + Backbone + RCA Graph + Scenario KG |
| **模块二：证据构建** | `src/doc/module-2-unified-evidence.md` | 多源异常观测（时序/图像/日志）→ 统一 Evidence JSON | 异常检测器输出 → 统一 Evidence JSON |
| **模块三：RCA 推理** | `src/doc/module-3-rca-engine.md` | Evidence + KG → 两条路线各自独立的推理结果，供前端工作台直接消费 | Evidence + Full KG → Route1Result + Route2Result |

> 验收时请以 `src/doc/acceptance-plan.md` 为准。上表描述的是模块目标态边界；当前 Phase 1 仓库实际交付的是“浏览器导入已构建图谱/Unified Evidence -> 本地生成启发式 route1/route2 结果 -> 工作台展示”的闭环。

### 4.3 两条推理路线

| 维度 | 路线 1：多模态线索组织 | 路线 2：过程故障分析 |
|---|---|---|
| 推理方式 | 在图谱上遍历路径，按边权重排序 | 在图谱上仿真故障传播，比较模拟结果与真实数据 |
| 输入来源 | 多源（图像、时序、日志） | 时序传感器数据 |
| 图谱用途 | 验证器 + 导航器（验证 evidence + 寻找路径） | 传播骨架（仿真在图上跑） |
| 噪声处理 | 内置一致性检查和噪声修正机制 | 依赖图谱质量 |
| 输出 | 按权重排序的解释路径 | 按相似度排序的根因节点 |
| 上游来源 | MVTec/KGTraceVis pipeline | TEP_KG Root-KGD |
| 适用场景 | 多模态 evidence 融合、噪声纠偏、交互审查 | 过程故障诊断、变量级根因定位 |

两条路线逻辑大相径庭，在 RootLens 当前实现中由浏览器本地运行时分别执行，融合统一由前端可视化工作台完成。

### 4.4 分层清单

| 层 | 说明 | 文档 |
|---|---|---|
| Source Registry | 记录上游项目路径、关键目录、入口文档、复用点 | `src/doc/source-projects.md` |
| 图谱构建（L1-L4） | 素材摄取 → 模态提取 → 组装 → 投影 | `src/doc/module-1-graph-construction.md` |
| 统一 Evidence | 多源异常观测 → 统一 JSON（三种 facet） | `src/doc/module-2-unified-evidence.md` |
| 推理路线 1 | 线索组织：实体链接 → 一致性 → 修正 → 路径排序 | `src/doc/module-3-rca-engine.md` §3 |
| 推理路线 2 | 故障分析：RBC → 候选枚举 → RFPA → RootScore | `src/doc/module-3-rca-engine.md` §4 |
| RootLens 可视化工作台 | 本地导入 + 图谱浏览 + 路径对比 + 证据审查 + 双路线融合展示 + 人工反馈 | 本文档 §6 |

---

## 5. 端到端运作流程

整个系统做一件事：**当工业过程发生异常时，利用知识图谱找出最可能的根因**。

### 5.1 流程概览

```
原始工业数据
    │
    ▼
┌──────────────────────────────────────────────────┐
│  阶段一：知识图谱构建（模块一）                      │
│                                                    │
│  从设备文档、工艺连接关系、变量清单等异构来源，        │
│  构建一张描述"工厂里什么东西连着什么东西"的图。         │
│                                                    │
│  L1 素材摄取 → L2 模态提取 → L3 图谱组装 → L4 投影  │
└──────────────────────────────────────────────────┘
    │
    │  共享 KG
    ▼
┌──────────────────────────────────────────────────┐
│  阶段二：证据构建 + RCA 推理（模块二 + 模块三）      │
│                                                    │
│  多源异常检测输出 → 统一 Evidence JSON              │
│         │                                          │
│         ├─→ 路线 1：实体链接 → 一致性 → 路径排序    │
│         │                                          │
│         └─→ 路线 2：RBC → 候选枚举 → RFPA → 排序   │
│                                                    │
│  两条路线在浏览器本地独立运行，产出各自的推理结果      │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│  阶段三：RootLens 交互式可视分析                     │
│                                                    │
│  图谱探索 + 路径对比 + 证据审查 + 双路线融合展示      │
│  + 人工反馈 → 认知协同：图谱假设 + 专家验证           │
└──────────────────────────────────────────────────┘
    │
    ▼
根因候选（可解释、可追溯、可审查）
```

### 5.2 详细数据流

```
                        ┌──────────────────┐
                        │  多源原始数据      │
                        │  时序/图像/日志    │
                        └────────┬─────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
   ┌──────────────┐     ┌──────────────┐      ┌──────────────┐
   │ 图像异常检测  │     │ 时序异常检测  │      │ 日志异常检测  │
   └──────┬───────┘     └──────┬───────┘      └──────┬───────┘
          │                    │                      │
          └────────────────────┼──────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ 统一 Evidence JSON   │  ← 模块二
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    ▼                    │
          │         ┌──────────────────┐            │
          │         │  实体链接 → KG   │            │
          │         └────────┬─────────┘            │
          │                  │                      │
          │    ┌─────────────┼─────────────┐        │
          │    ▼             ▼             ▼        │
          │ ┌────────┐ ┌──────────┐ ┌──────────┐   │
          │ │一致性   │ │ 噪声修正  │ │ 路径排序  │   │  ← 路线 1
          │ │打分     │ │          │ │          │   │
          │ └────────┘ └──────────┘ └────┬─────┘   │
          │                             │          │
          │                             ▼          │
          │                  ┌──────────────────┐   │
          │                  │  路线 1 推理结果  │   │
          │                  └────────┬─────────┘   │
          │                           │             │
          │          ┌────────────────────────────┐  │
          │          │       共享知识图谱          │  │
          │          └────────────┬───────────────┘  │
          │                       │                  │
          │                       ▼                  │
          │          ┌────────────────────────┐      │
          │          │  RBC → RFPA → RootScore│      │  ← 路线 2
          │          │  路线 2 推理结果        │      │
          │          └───────────┬────────────┘      │
          │                      │                   │
          └──────────────────────┼───────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  RootLens 可视化工作台    │
                    │                         │
                    │  - 图谱浏览 + 路径对比    │
                    │  - 证据审查 + 冲突高亮    │
                    │  - 路线 1 & 2 融合展示   │
                    │  - 人工反馈（接受/驳回）  │
                    └─────────────────────────┘
```

### 5.3 关键衔接点

1. **统一 Evidence JSON 是路线的分叉点**：路线 1 从 observations 起步做实体链接和路径排序；路线 2 中的 RBC 贡献向量也从 observations 中 `facet: "variable"` 的条目获取。

2. **共享知识图谱是两条路线的共同基础**：路线 1 在图上做遍历和一致性验证，路线 2 在图上做传播仿真。

3. **路线交叉信息帮助前端融合**：引擎附带轻量交叉标记（路线 1 的 target_entity 是否在路线 2 候选集中、路线 2 的候选是否能从路线 1 source entity 到达），前端据此进行融合展示。

4. **RootLens 工作台是认知协同的载体**：分析人员在界面中对比两条路线的输出，审查证据冲突，接受或驳回系统建议。

---

## 6. 可视化工作台

交互式可视分析原型（Vue 3 + Arco Design），支持：

- **图谱浏览**：力导向图展示 Full KG / RCA Graph / Scenario KG，支持数据集切换、节点标签控制、搜索与详情检查
- **路径对比**：并排或叠加展示路线 1 和路线 2 的候选，高亮两条路线交叉的节点
- **证据审查**：查看每条 observation 如何链接到图谱节点、一致性评分详情、冲突字段及修正候选
- **人工反馈**：接受/驳回/修正系统输出、what-if 分析（修改 observation 后重新推理）、路径/候选备注持久化
- **共享分析焦点**：在 `/graphs`、`/evidence`、`/reasoning` 之间保持当前 case / observation / path / candidate 的选择，并驱动图谱节点边高亮与证据 support observation 高亮
- **阶段化入口与会话迁移**：`/import` 支持完整回放、图谱导入、Evidence 追加，以及当前 graphs/runtime/workspace/bundle 导出和回灌恢复
- **认知协同**：图谱提出结构化假设，分析人员补充领域上下文

### 6.1 现有页面

当前导航已经收敛到主链路，只保留用户完成端到端分析所需的四个页面。原先用于评审和设计展示的 `/overview`、`/source-map`、`/architecture`、`/roadmap` 不再作为主系统导航页面。

| 路由 | 内容 |
|---|---|
| `/import` | 系统入口：分阶段导入（回放 / 图谱 / Evidence / 恢复导出结果）、会话生成、会话导出、demo 切换、主链路状态 |
| `/graphs` | 图谱可视化：已归一化的力导向图、切换、搜索与属性检查 |
| `/evidence` | Evidence 审查：统一 Evidence 浏览、facet 过滤、raw refs、linked hints 与 draft case 对照 |
| `/reasoning` | RCA 分析：路线 1 / 路线 2 结果、what-if、人工反馈与 cross-route signals |

### 6.2 后续扩展

- Evidence 工作台（统一 evidence 浏览 + 校验）
- Path Trace 工作台（双路线路径可视化对比）
- Experiment Console（RCA 实验运行与评估结果展示）
- Case Study 面板（三个工业 use case 的案例陈列）

---

## 7. 技术选型

- `@arco-design/web-vue` — UI 组件库
- `vue-router` — 路由
- `@vueuse/core` — Vue 工具集
- `D3.js`（运行时懒加载）— 图谱力导向图渲染
- `csv-parse` — 浏览器端 CSV 解析

原则：先满足导航、状态、基础 UI、图表、本地文件解析与浏览器会话，不引入后端依赖。

---

## 8. 改造路线

### Phase 0

框架审阅 + 设计文档沉淀：

- 系统设计（本文档）
- 论文标题与 abstract
- 图谱构建流程（`module-1-graph-construction.md`）
- 统一 Evidence 合约（`module-2-unified-evidence.md`）
- RCA 推理引擎（`module-3-rca-engine.md`）
- 源项目索引（`source-projects.md`）

### Phase 1（当前）

浏览器本地运行时落地：

- 统一 Evidence JSON schema + validator
- 本地文件导入与浏览器会话持久化
- `/import` 的阶段化导入控制台、当前会话导出与导出结果恢复能力
- 图谱归一化与 demo/runtime 双模式切换
- 路线 1（线索组织）与路线 2（故障分析）的本地启发式推理管线落地
- RCA 工作台中的单 case what-if 重算闭环（修改 observation -> 本地重算 -> 恢复原始 case）
- RCA 工作台中的人工反馈备注持久化（route1 path / route2 candidate）
- `/graphs`、`/evidence`、`/reasoning` 三页共享分析焦点，支持 observation/path/candidate 跨页定位与联动高亮

### Phase 2

RootLens 可视化工作台：

- 交互式图谱浏览 + 路径对比
- 证据审查 + 冲突字段高亮
- 人工反馈（接受/驳回/修正）+ 持久化 what-if 分析
- 双路线融合展示（并排对比 + 叠加高亮 + 统一候选卡片）
- 三个 use case 的案例研究面板

### Phase 3

论文实验与评估。

---

## 9. 设计文档索引

| 文档 | 内容 |
|---|---|
| `src/doc/acceptance-plan.md` | 当前 Phase 1 验收标准、缺口矩阵与后续推进计划 |
| `src/doc/frontend-benchmark-ads-brain.md` | 对标 `ads_brain_fe` 提炼出的工作台布局、面板层级与交互技巧 |
| `src/doc/module-1-graph-construction.md` | 模块一：多源异构素材 → 知识图谱（L1-L4 建图流程） |
| `src/doc/module-2-unified-evidence.md` | 模块二：多源异常观测 → 统一 Evidence JSON（三种 facet） |
| `src/doc/module-3-rca-engine.md` | 模块三：Evidence + KG → 双路线根因推理 |
| `src/doc/source-projects.md` | 上游项目路径、关键资产、推荐阅读顺序 |

---

## 10. AI Agent 标识

> 本文档为 Phase 0 框架审阅阶段的产物，由 Claude Code (Opus 4.7) 在 2026-05-11 编写。
>
> 整合了原 `framework.md`（系统架构 + 分层 + 路线 + 页面 + 阶段）、`pipeline-overview.md`（端到端流程 + 两条路线协作）和 `paper-meta.md`（标题 + abstract）的内容。三条模块文档（`module-1-graph-construction.md`、`module-2-unified-evidence.md`、`module-3-rca-engine.md`）提供详细的模块级设计。
