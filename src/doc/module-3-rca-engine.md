# RCA 推理引擎：Evidence + KG → 根因候选

这份文档描述模块三的设计：**如何把统一 Evidence JSON 和知识图谱结合起来，进行根因推理分析**。这是 RootLens 三条模块链中的最后一环——前两个模块（图谱构建、证据构建）为它提供输入，它产出两条路线各自独立的推理结果供可视化工作台融合呈现。

> 设计原则：**尽量保留 TEP_KG 的 Root-KGD 推理语义和 KGTraceVis 的 pipeline 推理语义。两条路线独立运行、共享同一张图谱和同一份 Evidence。RootLens 当前以浏览器本地运行时承接结果生成，融合统一由前端可视化工作台完成。**
>
> **当前阶段说明**
>
> 本文档中的很多段落描述的是**目标态语义基线**，不是当前仓库已经完整复刻的算法实现。
>
> 当前前端运行时的真实状态是：
>
> - 路线 1：浏览器端启发式 entity linking + consistency + shortest-path ranking
> - 路线 2：浏览器端启发式 candidate ranking，不等同于完整 Root-KGD / RFPA / 10 层 adjustments
>
> 当前实现的目标是先完成“本地导入 -> 本地推理 -> 工作台展示”的闭环；后续阶段再逐步逼近上游算法语义。

---

## 0. Phase 1 当前实现映射

当前仓库里 RCA 引擎的真实交付边界，是浏览器端本地启发式推理，而不是完整的上游算法复刻：

- 本地推理入口：`src/services/local-reasoning.ts`
- 导入时组装 runtime：`src/services/browser-runtime.ts`
- contract 真值：`src/types/rootlens.ts` 与 `src/contracts/runtime.ts`
- 工作台消费：`src/views/ReasoningWorkbenchView.vue`

当前实现的语义边界如下：

- 路线 1：基于节点名/别名的启发式 entity linking，结合固定关系规则做 consistency / correction，再用 shortest-path + confidence / evidence match 计算路径分数。
- 路线 2：只在存在 `facet: "variable"` observation 时启用；基于变量贡献、最短路径衰减和少量类型/角色 bias 生成候选排序。
- 交叉信息：前端本地补 `cross_route_signals` 与 `notes`，供工作台做双路线对照展示。
- what-if：RCA 工作台允许修改当前 case 的 observation，并在重算前展示字段 diff，然后基于当前统一图谱重新执行浏览器端本地推理；草稿会按会话写入浏览器 `localStorage`。
- 人工反馈：RCA 工作台允许对 route1 path / route2 candidate 做接受或驳回标注，并附加 analyst note；工作台会额外生成 feedback summary，支持回跳到对应 path / candidate；这些记录与 what-if 草稿共用同一份本地 analysis workspace。
- 跨页同步：Evidence 工作台消费同一份 draft case，因此 RCA 页里的本地重算结果会同步反映到 Evidence 视图。

因此，本文后续涉及 KGTraceVis pipeline、Root-KGD、RFPA 和 10 层 adjustments 的段落，都应理解为**目标态语义来源**，不是当前浏览器实现已达到的算法 parity。

---

## 1. 整体定位

RCA 推理引擎的输入和输出：

```
┌──────────────────────┐     ┌──────────────────────┐
│   统一 Evidence JSON  │     │   知识图谱 (Full KG)  │
│   (模块二产物)        │     │   (模块一产物)        │
└──────────┬───────────┘     └──────────┬───────────┘
           │                            │
           └──────────────┬─────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │       RCA 推理引擎 (模块三)    │
          │                               │
          │  路线 1: 多模态线索组织        │
          │  路线 2: 过程故障分析          │
          │                               │
          │  两条路线独立运行，各自产出    │
          └───────────────┬───────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │       根因分析结果             │
          │                               │
          │  - 路线 1 结果 (路径+一致性)   │
          │  - 路线 2 结果 (排名+传播)    │
          │  - 证据支撑 (provenance)       │
          │  - 冲突与修正信息              │
          │                               │
          │  融合由前端可视化层完成        │
          └───────────────────────────────┘
```

引擎内部组织为两条推理路线。目标态上，它们分别对齐上游项目的关键语义；当前 Phase 1 则以 contract 兼容的浏览器端启发式实现承接结果生成：

| 路线 | 来源 | 核心思想 | 图谱用途 |
|---|---|---|---|
| 路线 1: 多模态线索组织 | MVTec/KGTraceVis | 在图谱上遍历路径，按边权重 + 证据匹配排序 | 验证器 + 导航器 |
| 路线 2: 过程故障分析 | TEP_KG Root-KGD | 在图谱上仿真故障传播，比较模拟结果与真实数据 | 传播骨架 |

---

## 2. 数据结构

引擎产出供前端可视化工作台消费的结果。**当前 contract 以 `src/types/rootlens.ts` 为准**；这里列出的字段名应与运行时类型保持一致。

### 2.1 AnalysisResult — 顶层输出

```typescript
interface AnalysisResult {
  case_id: string;
  timestamp: string; // ISO 8601
  graph_dataset_id: string;

  // 两条路线各自独立的结果，null = 当前场景不可用
  route1: Route1Result | null;
  route2: Route2Result | null;
  cross_route_signals: CrossRouteSignal[];
  notes: string[];
}

interface CrossRouteSignal {
  candidate_id: string;
  candidate_name: string;
  route1_path_ids: string[];
  route2_rank: number | null;
  shared_obs_ids: string[];
}
```

### 2.2 Route1Result — 多模态线索组织结果

```typescript
interface Route1Result {
  // 实体链接
  linked_entities: LinkedEntity[];

  // 一致性检查
  consistency_score: number;        // [0, 1]
  inconsistent_fields: string[];
  consistency_checks: ConsistencyCheck[];

  // 噪声修正候选
  correction_candidates: CorrectionCandidate[];

  // 路径排序结果
  ranked_paths: RankedPath[];
}
```

每条关键结构：

```typescript
interface LinkedEntity {
  link_id: string;
  field: string;                   // object / anomaly_type / location / morphology / variable / log_event
  mention: string;                 // evidence 中的原始文本
  selected_entity_id: string | null;
  selected_entity_name: string | null;
  score: number;                   // 匹配置信度
  match_type: EntityMatchType;     // "exact" / "fuzzy" / "alias" / "unmatched"
  ambiguous: boolean;              // top-1 与 top-2 差距 < 0.08
  candidates: EntityCandidate[];   // 备选列表
  obs_id?: string;
  facet?: ObservationFacet;
}

interface ConsistencyCheck {
  source_field: string;            // 如 "anomaly_type"
  target_field: string;            // 如 "morphology"
  source_entity_id: string;
  target_entity_id: string;
  relations: string[];             // 期望的关系，如 ["HAS_MORPHOLOGY"]
  passed: boolean;
  matched_relation: string | null; // 实际匹配上的关系
}

interface CorrectionCandidate {
  candidate_id: string;
  source_field: string;
  source_entity_id: string;
  target_field: string;
  original_value: JsonValue;       // 修正前
  suggested_entity_id: string;
  suggested_value: string;         // 修正后
  score: number;
  reason: string;                  // 如 "anomaly_scratch HAS_MORPHOLOGY morphology_linear"
  supporting_edge_ids: string[];
}

interface PathEdgeDetail {
  edge_id: string;
  source: string;
  target: string;
  relation: string;
  confidence: number | null;
}

interface RankedPath {
  path_id: string;
  source_entity_id: string;        // 异常观测锚点
  target_entity_id: string;        // 假设的根因节点
  target_entity_name: string;
  nodes: string[];                 // 路径节点序列
  node_names: string[];
  relations: string[];             // 边关系序列
  score: number;                   // 综合评分
  confidence: number;              // 平均边置信度
  evidence_match: number;          // 路径节点与 evidence 链接节点的重合度
  length: number;                  // 跳数
  source_edges: PathEdgeDetail[];  // 路径上的边详情（用于 provenance）
  support_obs_ids: string[];
}
```

### 2.3 Route2Result — 过程故障分析结果

```typescript
interface Route2Result {
  // 故障特征
  fault_signature: {
    contribution_vector: Record<string, number>;  // entity_id → contribution [0, 1]
    ordered_variables: string[];                    // 排序后的变量列表
    top_channels: ChannelContribution[];            // top 通道
    graph_contributions: Record<string, number>;    // 图谱实体级贡献度
  };

  // 候选根因排名
  ranked_candidates: RootKGDCandidate[];
}

interface RootKGDCandidate {
  // 基础信息
  scenario_id: string;
  fault_number: number;
  simulation_run: number;
  rank: number;

  // 候选身份
  candidate_id: string;
  candidate_name: string;
  candidate_type: string;          // Equipment / Stream / Variable / Component / FaultAnchor
  candidate_role: string;          // root_cause_anchor / equipment_anchor / actuator / observation / support_only

  // 候选生成
  priority_level: number;          // 1/2/3
  seed_variable_id: string;        // 哪个变量触发了该候选
  seed_score: number;

  // 核心评分
  root_score: number;              // 候选的基础支持度
  ranking_score: number;           // 当前工作台按它排序
  structural_ranking_score: number;
  ranking_adjustment: number;

  // 评分构成
  covered_contribution_mass: number;
  active_variable_count: number;
  pattern_entropy: number;
  discriminator_alignment: number;  // TEP 特定：anchor discriminator 对齐度

  // Anchor Memory
  anchor_contribution_alignment: number;
  anchor_dynamic_alignment: number;
  anchor_unique_contribution_alignment: number;
  anchor_memory_bonus: number;
  anchor_memory_scenario_count: number;

  // 传播结果
  top_affected_variables: AffectedVariable[];
  top_support_paths: string[][];   // 候选 → 受影响变量的追溯路径
  support_evidence_ids: string[];  // 支撑证据的 provenance ID 列表
}

interface AffectedVariable {
  entity_id: string;
  name: string;
  propagated_score: number;        // 当前变量被候选解释到的强度
  rbc_contribution: number;        // 输入 evidence 中的变量贡献
}
```

---

## 3. 路线 1：多模态线索组织（目标语义基线）

### 3.1 处理流程

```
统一 Evidence JSON
    │
    ▼
┌──────────────────────────┐
│ Step 1: 实体链接          │  link_evidence_entities()
│                          │
│  - 从 observations[] 中   │
│    提取 mention (name)   │
│  - 针对每个 mention，     │
│    在 KG 上 fuzzy 搜索   │
│  - 记录所有候选（top-k）  │
│  - 标记歧义 (score gap   │
│    < 0.08)              │
│                          │
│  保留: entity_linker.py  │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ Step 2: 一致性检查        │  check_consistency()
│                          │
│  - 检查 field-pair 关系  │
│    是否在 KG 中存在      │
│  - (anomaly_type,        │
│     morphology) →        │
│     HAS_MORPHOLOGY       │
│  - (anomaly_type,        │
│     location) →          │
│     OCCURS_ON /          │
│     HAS_LOCATION         │
│  - (variable, location)  │
│     → MEASURED_IN /      │
│     BELONGS_TO_UNIT      │
│                          │
│  保留: consistency_      │
│        checker.py        │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ Step 3: 噪声修正候选      │  generate_correction_candidates()
│                          │
│  - 对不一致的 field pair  │
│  - 沿 KG 关系边寻找修正   │
│    候选                  │
│  - 如 morphology 不匹配  │
│    → 按 HAS_MORPHOLOGY   │
│      找可能的 morphology │
│                          │
│  保留: correction_       │
│        generator.py      │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│ Step 4: 路径排序          │  rank_root_cause_paths()
│                          │
│  - 从 source entity      │
│    (anomaly_type /       │
│     variable / log_event)│
│    出发                  │
│  - 沿 KG 边找到达 root   │
│    cause node 的所有     │
│    simple paths          │
│  - Score = α * avg_conf  │
│          + β * evidence_ │
│            match         │
│          - γ * length_   │
│            penalty       │
│  - α=0.55, β=0.35,      │
│    γ=0.10               │
│                          │
│  保留: path_ranker.py    │
└──────────────────────────┘
```

### 3.2 目标态配置参数

| 参数 | 值 | 来源 | 含义 |
|---|---|---|---|
| `linkable_facets` | object / anomaly_type / location / morphology / variable / log_event | entity_linker.py:L12 | 可链接的 observation facet |
| `link_top_k` | 3 | entity_linker.py:L35 | 每个 mention 保留的候选数 |
| `link_min_score` | 0.55 | entity_linker.py:L36 | 链接最低置信度 |
| `ambiguous_threshold` | 0.08 | entity_linker.py:L71 | top-1 与 top-2 差距小于此值标记歧义 |
| `field_relation_rules` | 4 条规则 | consistency_checker.py:L12 | 需要检查的 field-pair 关系 |
| `consistency_entity_weight` | 0.4 | consistency_checker.py:L55 | 一致性评分中实体覆盖权重 |
| `consistency_relation_weight` | 0.6 | consistency_checker.py:L55 | 一致性评分中关系通过率权重 |
| `path_max_depth` | 5 | path_ranker.py:L24 | 路径最大跳数 |
| `path_alpha` (confidence) | 0.55 | path_ranker.py:L25 | 路径评分边置信度权重 |
| `path_beta` (evidence match) | 0.35 | path_ranker.py:L26 | 路径评分证据匹配权重 |
| `path_gamma` (length penalty) | 0.10 | path_ranker.py:L27 | 路径评分长度惩罚系数 |
| `root_cause_labels` | RootCause / CauseCategory / FaultType | path_ranker.py:L14 | 根因节点的 label 集合 |
| `source_fields` | anomaly_type / variable / log_event | path_ranker.py:L15 | 路径搜索的起点 field |
| `correction_top_k` | 5 | correction_generator.py:L20 | 每个不一致字段的修正候选数 |

### 3.3 目标态保留逻辑

全部从 KGTraceVis `src/kgtracevis/kg/` 中提取：

| 文件 | 逻辑 | 不可丢失原因 |
|---|---|---|
| `entity_linker.py` | fuzzy 搜索（Levenshtein + alias 匹配）、候选去重、歧义标记 | MVTec 场景的实体链接策略 |
| `consistency_checker.py` | 4 条 field-pair 规则、加权评分公式 | MVTec 的一致性检查语义定义 |
| `correction_generator.py` | 沿 KG 关系边生成修正候选、按 confidence 排序 | MVTec 的噪声修正机制 |
| `path_ranker.py` | `all_simple_paths` + 三元组加权评分 + provenance 保存 | MVTec 的路径排序核心公式 |

**关于 evidence 从模块二到模块三**：Evidence JSON 的 `observations[]` 数组直接作为路线 1 的 (1) linking 的 mention 来源 + (2) path ranking 的 source anchor 集合。

---

## 4. 路线 2：过程故障分析（目标语义基线）

### 4.1 处理流程

```
统一 Evidence JSON (含时序变量贡献)
    │
    ▼
┌──────────────────────────┐
│ Step 1: 故障特征提取     │  compute_rbc_contributions()
│                          │
│  - 从 evidence 中取时序  │
│    贡献向量变量名        │
│  - 若 evidence 中已有    │
│    RBC 贡献值，直接使用  │
│  - 若无（如 MVTec 场景） │
│    则需要回到原始时序    │
│    数据重新计算 RBC      │
│                          │
│  保留: rbc.py            │
│     - fit_fault_free_    │
│       profile()          │
│     - compute_rbc_       │
│       contributions()    │
│     - map_channel_       │
│       contributions()    │
└───────────┬──────────────┘
            │  Cont = {var1: 0.82, var7: 0.54, ...}
            ▼
┌──────────────────────────┐
│ Step 2: 候选枚举         │  enumerate_candidates()
│                          │
│  - 从 top-K 贡献变量出发 │
│  - 第一波: 变量 1-hop    │
│    邻居（设备、物流等）   │
│  - 第二波: 2-hop 邻居    │
│  - root_cause_anchor     │
│    按下游贡献信号纳入    │
│  - 允许类型: Equipment / │
│    Stream / Variable /   │
│    Component / FaultAnchor│
│                          │
│  保留: root_kgd.py:L295  │
└───────────┬──────────────┘
            │  candidates[]
            ▼
┌──────────────────────────┐
│ Step 3: RFPA 传播仿真    │  simulate_propagation()
│                          │
│  对每个候选 e_A:          │
│  - s_0 = seed_score      │
│  - 沿 KG 边向外传播      │
│  - hop 1→4:              │
│    delta = signal *      │
│            edge_weight * │
│            exp(-σ*hop) / │
│            N_receive     │
│  - 按 relation family    │
│    priority 排序传播     │
│  - 全局 cap = 1.0        │
│  - gain < ε 时停止       │
│                          │
│  输出: S_V^A + edge_flow │
│                          │
│  保留: propagation.py    │
│        relation_params   │
│         (7 families)     │
└───────────┬──────────────┘
            │  S_V^A = {var1: 0.35, var7: 0.21, ...}
            ▼
┌──────────────────────────┐
│ Step 4: RootScore 排名   │  ranking_score()
│                          │
│  root_score = cosine(    │
│    Cont, S_V^A)          │
│                          │
│  ranking_score =         │
│    root_score            │
│    - coverage_penalty    │
│    - entropy_penalty     │
│    + type_bias           │
│    + role_bias           │
│    + discriminator_bias  │
│    + anchor_memory_bonus │
│    + adjustments          │
│                          │
│  保留: root_kgd.py       │
│        所有常量参数      │
│        10层调整逻辑      │
└──────────────────────────┘
```

### 4.2 目标态核心算法参数

#### 4.2.1 RBC 参数

| 参数 | 值 | 来源 | 含义 |
|---|---|---|---|
| `window_size` | 100 | rbc.py:L19 | 故障窗口样本数 |
| `row_stride` | 25 | rbc.py:L17 | 正常数据采样步长 |
| `variance_threshold` | 0.95 | rbc.py:L21 | PCA 方差保留阈值 |
| `min_rank` / `max_rank` | 6 / 18 | rbc.py:L22-23 | 主子空间维度范围 |

#### 4.2.2 候选枚举参数

| 参数 | 值 | 来源 |
|---|---|---|
| `ALLOWED_CANDIDATE_TYPES` | Equipment / Stream / Variable / Component / FaultAnchor | root_kgd.py:L35 |
| `DEFAULT_TOP_VARIABLE_COUNT` | 8 | root_kgd.py:L36 |

#### 4.2.3 传播仿真参数（7 种关系族）

| 关系族 | σ (衰减) | priority (优先级) | 来源 |
|---|---|---|---|
| FAULT_SOURCE | 0.10 | 7 (最高) | propagation.py:L24-30 |
| CONTROL | 0.14 | 6 | |
| MATERIAL_FLOW | 0.20 | 5 | |
| ENERGY_TRANSFER | 0.26 | 4 | |
| PHASE_CHANGE | 0.30 | 3 | |
| COMPOSITION | 0.24 | 2 | |
| OBSERVATION | 0.32 | 1 (最低) | |

#### 4.2.4 根因评分配置

| 参数 | 值 | 含义 |
|---|---|---|
| `ROOT_SCORE_COVERAGE_PENALTY` | 0.12 | 覆盖贡献质量的门槛惩罚 |
| `ROOT_SCORE_ENTROPY_PENALTY` | 0.03 | 传播模式过于分散的惩罚 |
| `ROOT_CAUSE_DISCRIMINATOR_WEIGHT` | 0.28 | anchor discriminator 的权重 |
| `CANDIDATE_TYPE_RANKING_BIAS` | 5 种类型各有分数 | 不同类型候选的排序偏好 |
| `CANDIDATE_ROLE_RANKING_BIAS` | 6 种角色各有分数 | 不同语义角色的排序偏好 |

#### 4.2.5 10 层领域调整逻辑（目标态需保留）

每层针对 TEP 特定故障模式的物理特征：

| 调整层 | 触发条件 | 效果 | 保留函数 |
|---|---|---|---|
| Anchor Preference | anchor_target_ids 中 proxy 得分相近 | 提升根因 anchor | `_apply_anchor_preference_adjustments` |
| Separator Family | 多个 separator anchor 共享 diagnostic vars | 按诊断变量质量分配 bonus | `_apply_separator_family_adjustments` |
| Condenser Dynamic | 冷却水出口温度高波动 + 均值下降 | condenser_heat_transfer 加分 | `_apply_condenser_dynamic_adjustments` |
| Stream 4 Cold Response | 汽提塔温度下降 + 蒸汽流量上升 + 流量适中波动 | stream_4_feed_temperature 反超 stripper | `_apply_stream4_cold_response_adjustments` |
| Stream 4 Proxy Chase | stream_4 排第 2-4 + rival 是 separator/multi_valve | stream_4 小幅度追赶 | `_apply_stream4_proxy_chase_adjustments` |
| Stream 2 Competition | reactor 冷却水/offgas B 异常 | stream_2 与 separator/condenser 竞争 | `_apply_stream2_competition_adjustments` |
| Separator Valve Tiebreak | condenser rank 1 + separator rank 2 + gap 很小 | separator 反超 condenser | `_apply_separator_valve_tiebreak_adjustments` |
| Stripper Tiebreak | stream_4 rank 1 + stripper rank 2 | stripper 反超 stream_4 | `_apply_stripper_tiebreak_adjustments` |
| Condenser Moderate | condenser 排第 2-5 + 非极端 cond 信号 | condenser 适度追赶 rival | `_apply_condenser_moderate_adjustments` |
| Separator Warm | stream_2 rank 1 + separator rank 2 + 温差信号 | separator 反超 stream_2 | `_apply_separator_warm_adjustments` |

> **重要**：这 10 层调整逻辑是 TEP_KG 在大量实验中对 TEP 故障物理特性的编码，代表了目标态路线 2 的关键语义来源。RootLens 当前浏览器实现**尚未**落地这 10 层 adjustments；当前 route2 只输出兼容的候选排序结构，后续阶段再决定哪些调整逻辑需要以可替换模块方式承接。

---

## 5. 两条路线的协作：本地运行时提供结果，前端负责融合

两条路线的输出在**融合层**汇合，产生比单条路线更可信的根因候选。

### 5.1 路线交叉信息

引擎在产出结果时会附带轻量的**交叉信息**，帮助前端做融合展示，但不做加权合并排名：

```
当两条路线都可用时，引擎额外标记:
  - route1 每条路径的 target_entity 是否在 route2 候选中出现
  - route2 每个候选是否能从 route1 的 source entity 到达 (simple path ≤ max_depth)
  - 两条路线共享的 evidence observation 集合

这些标记作为元数据随 route1/route2 结果一起返回，前端可用可不用
```

### 5.2 前端融合的建议方向

本地运行时只提供原始结果 + 交叉标记，前端自行决定如何呈现。例如：

- **双栏对比视图**：左栏路线 1 路径列表，右栏路线 2 候选排名，中间高亮交叉的候选
- **同一张图谱上双路线高亮**：路线 1 的 top-k 路径用蓝色，路线 2 的 RFPA 传播流用橙色
- **候选卡片统一展示**：每个候选卡片内同时显示两条路线的证据（"路线 1: 3 条路径指向 ｜ 路线 2: 排名 #2, RootScore 0.87"）
- **场景自适应**：仅一条路线可用时自动切换到单路线视图

### 5.3 场景适配

| 异常场景 | 证据模态 | 可用路线 |
|---|---|---|
| TEP 过程故障 | time_series | 路线 1 + 路线 2 |
| MVTec 产品缺陷 | image | 仅路线 1 |
| WM811K 晶圆缺陷 | image + log | 仅路线 1 |
| 多模态 TEP | time_series + image + log | 路线 1 + 路线 2 |
| 多模态 Wafer | variable + log | 仅路线 1 |

### 5.4 引擎不负责融合

两条路线的逻辑大相径庭——路线 1 是在图上遍历路径，路线 2 是在图上仿真传播——在运行时层强行统一排名会丢失各自的语义信息。RCA 引擎的职责是**产出两条路线各自独立、完整、可追溯的结果**，融合统一由前端可视化工作台完成：

- 引擎交付 `route1: Route1Result` 和 `route2: Route2Result`，两者都是可选的（null = 该路线在当前场景下不可用）
- 前端负责设计统一的交互视图，使用户感觉推理是"一体"的——例如并排对比两条路线的候选、同一张图谱上高亮两条路线的路径、用视觉编码区分路线 1 的路径评分和路线 2 的传播仿真结果
- 当两条路线都可用时，前端可以交出候选的交集和差集，让分析人员自己判断
- 当仅路线 1 可用时，前端只展示路线 1 的面板

---

## 6. 引擎层边界：做什么、不做什么

### 6.1 做什么

- 消费统一 Evidence JSON 和 Full KG（从模块一、二获取）
- 运行两条推理路线的全部逻辑
- 为每条路线产出独立、完整、可追溯的结果
- 附带轻量交叉标记帮助前端做融合展示
- 对外暴露稳定的、可视工作台可直接消费的 JSON 结果

### 6.2 不做什么

- **不建图**（图谱构建是模块一的职责）
- **不构建 evidence**（异常检测 + evidence 归一化是模块二的职责）
- **不渲染 UI**（可视化是工作台的职责）
- **不在推理过程中修改图谱**（推理阶段只读，图谱更新属于离线构建/在线增量构建）

---

## 7. 输入接口约定

### 7.1 必要输入

| 输入 | 来源 | 格式 |
|---|---|---|
| 统一 Evidence JSON | 模块二 | `module-2-unified-evidence.md` 定义的 JSON 结构 |
| 知识图谱 (Full KG) | 模块一 | 节点 JSONL + 边 JSONL（TEP_KG 格式）或 CSV（KGTraceVis 格式），含传播元数据 |
| 关系族参数 (RFPA) | TEP_KG | `relation_family_params.json` 或默认参数 |
| Anchor Discriminators | TEP_KG | `anchor_discriminators.json`（每个 FaultAnchor 的诊断变量列表） |

### 7.2 可选输入

| 输入 | 何时需要 | 格式 |
|---|---|---|
| 训练后的边权重 | 运行路线 2 完整模式 | `rca_edge_weights.jsonl` |
| Anchor Memory Profiles | 应用 anchor memory 调整 | `anchor_memory_profiles.json` |
| 动态特征向量 | 应用动态信号调整（condenser/separaor/stream 竞争等 10 层） | 场景级动态特征向量 |
| 原始时序数据 | evidence 中无 RBC 贡献向量但场景支持路线 2 | CSV（TEP 52 通道） |

---

## 8. 上游语义来源清单

### 8.1 来自 TEP_KG `src/tep_kg/`（路线 2）

| 模块 | 文件 | 核心函数 | 保留原因 |
|---|---|---|---|
| RBC | `rbc.py` | `fit_fault_free_profile()`, `compute_rbc_contributions()`, `map_channel_contributions()`, `build_rbc_scenarios()` | PCA + SPE 重构贡献算法 + 52 通道映射 |
| 传播图构建 | `propagation.py` | `build_propagation_graph()`, `initial_edge_weight()`, `candidate_source_ids()` | 传播图构建 + 边权初始化 + 候选 ID 确定 |
| RFPA 仿真 | `propagation.py` | `simulate_propagation()`, `trace_path()`, `incident_neighbors()` | 涟漪式故障传播核心 + 路径追溯 |
| 关系参数 | `propagation.py` | `default_relation_params()`, `RELATION_LOGIT_PRIORS` | 7 种关系族的衰减系数和优先级 |
| Root-KGD | `root_kgd.py` | `rank_scenario()`, `enumerate_candidates()`, `ranking_score()`, `build_topk_subgraphs()` | 核心排名逻辑：候选枚举 → 传播仿真 → 评分 |
| Anchor Discriminators | `anchor_discriminators.py` | `load_anchor_discriminators()` | FaultAnchor 的诊断变量白名单 |
| Anchor Memory | `anchor_memory.py` | `build_anchor_memory_profiles()`, `anchor_memory_alignment_details()` | 从历史场景中学习的 anchor 响应模式 |
| 10 层调整 | `root_kgd.py` (10 个 `_apply_*` 函数) | 见 4.2.5 节 | TEP 特定故障物理特征的领域编码 |
| 动态特征 | `scenario_dynamic_features.py` | `build_dynamic_features_for_scenarios()` | 窗口内统计量（mean/std）供调整层使用 |
| 信号工具 | `rca_signal_utils.py` | `cosine_similarity`, `contribution_weight`, `weighted_contributions` | 余弦相似度 + 贡献加权 |

### 8.2 来自 MVTec/KGTraceVis `src/kgtracevis/kg/`（路线 1）

| 模块 | 文件 | 核心函数 | 保留原因 |
|---|---|---|---|
| 实体链接 | `entity_linker.py` | `link_evidence_entities()`, `selected_entities_by_field()` | fuzzy 匹配 + 歧义标记 + 候选保存 |
| 一致性检查 | `consistency_checker.py` | `check_consistency()`, `FIELD_RELATION_RULES` | 4 条 field-pair 规则 + 加权评分 |
| 修正生成 | `correction_generator.py` | `generate_correction_candidates()` | 沿 KG 关系的修正候选生成 |
| 路径排序 | `path_ranker.py` | `rank_root_cause_paths()` | all_simple_paths + 三元加权公式 |
| KG 运行时 | `graph.py` | `KnowledgeGraph` (from_default_paths, candidates, has_edge, outgoing, etc.) | 图加载 + 实体搜索 + 关系查询 |
| Evidence Schema | `schema/evidence_schema.py` | `Evidence` (Pydantic model) | 输入 Evidence 的结构合约与校验 |

---

## 9. AI Agent 标识

> 本文档为 Phase 0 框架审阅阶段的产物，由 Claude Code (Opus 4.7) 在 2026-05-11 基于对 TEP_KG (`/Users/bytedance/my_project/TEP_KG`) 和 MVTec/KGTraceVis (`/Users/bytedance/my_project/MVTec/KGTraceVis`) 源码的详细阅读编写。
>
> 本文档中的参数值、流程和函数名都能在对应的上游源代码中找到出处。但在 RootLens 当前仓库中，它们应被理解为**语义来源与目标态参考**，而不是“已经 1:1 落地完成”的现状声明。

---

## 10. 待你审阅的问题

1. **路线 2 对非 TEP 场景的可用性**：MVTec/WM811K 场景没有时序贡献向量，路线 2 完全不可用。但未来如果 MVTec 也有了传感器数据，路线 2 可以按同样的 RFPA 逻辑接入——当前设计中的场景适配表是否合理？

2. **10 层调整逻辑的通用化**：这 10 层目前是针对 TEP 21 种故障编码的领域知识。是否需要在统一引擎中将它们封装为"领域调整插件"，每个工业场景可以注册自己的调整逻辑？

3. **前端融合的交互设计**：既然两条路线的融合统一由前端负责，你希望前端用什么样的交互形态来呈现？并排对比面板、同一图谱叠加高亮、还是统一候选卡片列表？是否需要引擎提供更多的交叉索引信息？

4. **Evidence 中是否必须携带 Cont**：路线 2 依赖 RBC 贡献向量 Cont。对于 TEP 场景，Cont 由模块二在构建 evidence 时计算完成并写入 observations。但如果 evidence 中没有完整的变量贡献（例如只标记了 top-5 偏离变量），路线 2 是否需要回退到原始数据重新计算 RBC？

5. **RCA 引擎的运行时机**：离线批量评估（完整跑两条路线 + 10 层调整）和在线交互（响应 what-if 修改，只跑受影响的候选子集）的计算量差异很大。是否需要设计两套模式？
