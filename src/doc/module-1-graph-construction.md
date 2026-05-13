# 知识图谱构建：多源异构素材 → 统一图谱

这份文档描述**建图阶段的运作流程**，只关注：素材有哪些模态、每种模态怎么处理、两个项目的建图逻辑如何保留、最终如何汇成一张图。不涉及具体代码。

> **当前阶段说明**
>
> RootLens 当前 Phase 1 前端实现**还没有**在浏览器里直接执行从原始 Text / Code / Image / Sequence 素材出发的完整 L1-L4 建图流水线。
>
> 当前仓库实际支持的是：
>
> - TEP 侧通过 `scripts/build-graphs.py` 调用上游 `tep_kg.graph_build.build_kg()`，再导入其最终 `nodes.jsonl` + `edges.jsonl`
> - MVTec 侧导入 KGTraceVis 默认 KG CSV，并在有 records 素材时复用其 candidate KG 构建链路，生成 `nodes_candidate.csv` + `edges_candidate.csv` overlay 后再统一归一化
> - 将这些图谱文件在前端归一化成统一图谱 contract
>
> 因此，本文档中的 L1-L4 描述应视为**目标态设计基线**，不是当前仓库已完整交付的能力。

---

## 0. Phase 1 当前实现映射

当前仓库里真正落地的是“已构建图谱导入 -> 统一图谱归一化 -> 浏览器会话持久化”这条链路：

- 导入与归一化：`src/services/browser-runtime.ts`
- contract 校验：`src/contracts/runtime.ts` 中的 `parseUnifiedGraphsFile()`
- 会话持久化与读取：`src/services/rootlens-data.ts`
- 图谱工作台消费：`src/views/KnowledgeGraphsView.vue`

当前前端支持的输入格式只有三类：

- `unified-graphs.json`
- TEP `nodes.jsonl` + `edges.jsonl`
- MVTec `nodes.csv` + `edges.csv` + 可选 `mvtec_rca_reference.csv`

当前构建脚本额外支持的 build-time 上游素材为：

- MVTec `records.jsonl`
- 可选 `adapter_pipeline_table.csv`
- candidate KG overlay 产物 `nodes_candidate.csv` + `edges_candidate.csv`

因此，本文后续所有关于 Text / Code / Image / Sequence 的 L1-L4 说明，都应理解为**后续阶段的上游语义来源与目标态设计**，而不是当前浏览器端已经执行的素材解析流程。

---

## 1. 素材模态全景

两个项目在建图阶段面对的原始素材覆盖四种模态：

```
                        建图素材来源

  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐
  │  Text   │  │  Code   │  │  Image  │  │  Sequence   │
  │  文本   │  │  代码   │  │  图像   │  │   时序      │
  └────┬────┘  └────┬────┘  └────┬────┘  └──────┬──────┘
       │            │            │              │
       ▼            ▼            ▼              ▼
  工艺文档      MATLAB/C    缺陷图像       传感器读数
  设备说明      Simulink    热力图         变量贡献
  日志文本      C 头文件    晶圆图         故障窗口
  外部知识      .h/.c       掩码           过程变量
```

| 模态 | TEP_KG 中的素材 | MVTec/KGTraceVis 中的素材 |
|---|---|---|
| **Text** | 工艺文档 `.txt/.md`、PDF 文档、外部 prior JSON（文本形式的知识） | 外部知识 JSON、source registry 中的 thesis_text / manual_curation 记录 |
| **Code** | MATLAB `.m`、Simulink `.mdl`、C `.c/.h` | 无（不解析代码） |
| **Image** | 无（不处理图像） | MVTec 缺陷图像（含 heatmap、mask、bbox）、WM811K 晶圆 bin map |
| **Sequence** | `.mat` 数据文件（当前仅元数据） | TEP 时序传感器数据（52 通道）、Wafer 过程变量 + fab log 事件 |

**关键观察**：两个项目的素材模态是互补的——TEP_KG 强在 code 解析，MVTec 强在 image/sequence 处理。融合后覆盖全部四种模态。

---

## 2. 建图的通用流程

不管素材是什么模态，建图都遵循同一个四层流水线：

```
┌──────────────────────────────────────────────────────────────────┐
│                       L1: 素材摄取层                              │
│                                                                  │
│   扫描素材目录 → 分类（按扩展名/MIME/数据集标记）→ 生成素材清单      │
│   每条素材记录：ID、路径、模态类型、内容哈希、信任度                  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       L2: 模态提取层                              │
│                                                                  │
│   每种模态有一个"通用提取器"，产出统一中间格式：                      │
│                                                                  │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│   │ Text     │  │ Code     │  │ Image    │  │ Sequence     │    │
│   │ 提取器   │  │ 提取器   │  │ 提取器   │  │ 提取器       │    │
│   │          │  │          │  │          │  │              │    │
│   │ 实体识别 │  │ AST/正则 │  │ 异常检测 │  │ 贡献度计算   │    │
│   │ 关系抽取 │  │ 符号提取 │  │ 特征提取 │  │ 事件检测     │    │
│   │ 术语链接 │  │ 调用图   │  │ 形态描述 │  │ 窗口分割     │    │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘    │
│        │             │             │               │             │
│        └─────────────┼─────────────┼───────────────┘             │
│                      │             │                              │
│                      ▼             ▼                              │
│               ┌──────────────────────────┐                       │
│               │  统一中间产物             │                       │
│               │  ExtractionRecord[]      │                       │
│               │  - 实体候选 + 类型        │                       │
│               │  - 关系候选 + 方向        │                       │
│               │  - 证据指针（出处行号等）  │                       │
│               │  - 置信度                │                       │
│               │  - 来源素材 ID           │                       │
│               └──────────────────────────┘                       │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       L3: 图谱组装层                              │
│                                                                  │
│   所有 ExtractionRecord 汇入，做：                                 │
│   - 本体校验（实体类型、关系类型是否在白名单内）                      │
│   - 实体消歧（同一个东西的不同叫法 → 合并）                         │
│   - 关系合并（多条证据支撑的同一条边 → 聚合）                       │
│   - 置信度融合（多源证据的置信度加权）                              │
│   - 质量门禁（孤立节点检查、端点缺失检查、schema 校验）              │
│                                                                  │
│   输出：Full KG（全量知识图谱）                                    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       L4: 图谱投影层                              │
│                                                                  │
│   从 Full KG 派生出面向不同用途的子图：                             │
│   - Semantic Backbone（只保留设备/物流/变量骨干关系）               │
│   - RCA Graph（增加 FaultAnchor / SemanticConcept 推理节点）       │
│   - Scenario KG（按场景筛选：TEP / MVTec / Wafer）                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 四种模态提取器的职责边界

每个模态提取器是一个**通用处理模块**，内部封装该模态的处理逻辑，但输出统一格式。

### 3.1 Text 提取器

**输入**：自然语言文档（工艺说明、设备手册、论文、外部知识描述）

**处理逻辑**（通用部分）：
- 实体识别：从文本中抽取设备名、变量名、物流名、故障类型等术语
- 关系抽取：识别"包含""连接""控制""导致"等工艺关系
- 术语归一化：缩写、别名统一映射

**保留的项目特定逻辑**：
- TEP_KG：`parse_text_doc()` 的文件名模式匹配规则——识别文档中引用了哪些其他素材文件（AssetMention），这是 TEP 场景下文档之间的交叉引用逻辑
- MVTec：source registry 中的 `thesis_text` / `manual_curation` 置信度赋值策略——外部文本知识在 MVTec 场景下有特定的可信度层级

### 3.2 Code 提取器

**输入**：工业控制代码（MATLAB `.m`、Simulink `.mdl`、C `.c/.h` 等）

**处理逻辑**（通用部分）：
- 函数/模块识别：从代码中提取功能单元
- 变量/参数识别：提取数据定义和配置常量
- 调用/连接关系：函数调用图、模块间信号连线
- 注释中的领域知识：识别注释里的设备名、变量含义

**保留的项目特定逻辑**：

> 这一层主要承载 TEP_KG 的解析逻辑。MVTec 没有代码解析。

- TEP_KG `parse_matlab()`：识别 `TEdata.title{...}` / `TEmvs.title{...}` 变量命名模式、`load('...mat')` 素材引用、setpoint 赋值——这些是 TEP 工业流程特有的代码模式
- TEP_KG `parse_c_like()`：C 函数签名、`#define` 宏、`typedef` 提取规则
- TEP_KG `parse_mdl()`：Simulink 模块名（Name 块）、信号类型（BlockType）、回调函数引用（PreLoadFcn/StopFcn/InitFcn）、模块间连线（SrcBlock/DstBlock）——这些正则规则是 Simulink 模型文本格式特有的
- TEP_KG 的扩展类型映射：`record_type` → `entity_type` 的映射表（Function→Function、Parameter→Parameter 等）

### 3.3 Image 提取器

**输入**：工业缺陷图像（产品表面、晶圆图），可能附带 heatmap、mask、bbox

**处理逻辑**（通用部分）：
- 缺陷检测：定位图像中的异常区域
- 特征提取：面积、质心、离心率、连通分量数等形态特征
- 严重度评估：基于缺陷大小/位置的严重程度量化

**保留的项目特定逻辑**：

> 这一层主要承载 MVTec 的 image adapter 逻辑。TEP_KG 没有图像处理。

- MVTec `ds_mvtec_adapter`：30+ 字段别名映射（case、object、anomaly、location、morphology 等多组 key），mask 特征摘要 → 观察项的派生逻辑（当原始记录没有显式 location/morphology/severity 时，从 mask 几何推导）
- MVTec `wm811k_adapter`：晶圆 bin map 的特定字段映射和缺陷分类逻辑

### 3.4 Sequence 提取器

**输入**：时序传感器数据（多变量时间序列）、带时间戳的日志事件流

**处理逻辑**（通用部分）：
- 异常检测：识别时序中的异常窗口
- 变量贡献计算：量化每个变量对异常的贡献度
- 事件提取：从日志流中提取关键事件和告警
- 时间窗口分割：确定故障前/故障后的时间边界

**保留的项目特定逻辑**：

- TEP_KG RBC：`rbc.py` 中的 PCA + SPE 统计量重构逻辑——这是 TEP 时序场景的贡献度计算方式，贡献向量 `Cont` 是后续 RFPA 传播仿真的输入
- MVTec `tep_adapter`：TEP 变量贡献归一化、per-variable observation 生成（含 rank 元数据）、时间窗口结构化
- MVTec `wafer_adapter`：双模态（variables + log_events）的统一 observation 生成

---

## 4. 两个项目的建图逻辑如何共存

核心原则：**保留原有逻辑不变，通过统一中间格式对接**。

```
                    TEP_KG 建图路径                MVTec 建图路径
                    ════════════════              ═══════════════

  素材        materials/*.m, .c, .mdl        JSON/JSONL/CSV records
                │                                    │
                ▼                                    ▼
  L1         素材扫描 + 治理                      source registry
             (assets.py)                          (source_loader.py)
                │                                    │
                ▼                                    ▼
  L2         Code 提取器                         Image / Sequence 提取器
             parse_matlab / parse_c_like         ds_mvtec / tep / wafer
             parse_mdl / parse_text_doc          adapter
                │                                    │
                ▼                                    ▼
  统一        ExtractionRecord[]                ExtractionRecord[]
  中间        (record_type, name,               (entity candidate,
  格式          source_file, line_span,           observation facets,
               provenance)                        confidence)
                │                                    │
                └──────────────┬─────────────────────┘
                               │
                               ▼
  L3          ┌─────────────────────────────────────┐
              │          图谱组装（通用）             │
              │                                     │
              │  - 本体校验（entity_types +          │
              │    relation_whitelist）              │
              │  - 实体消歧（别名 → 规范 ID）         │
              │  - 证据链（每条边关联 provenance）     │
              │  - 外部 prior 并入                   │
              │  - 质量门禁                          │
              │                                     │
              │  输出：Full KG                       │
              └─────────────────┬───────────────────┘
                                │
                                ▼
  L4          ┌─────────────────────────────────────┐
              │          图谱投影（通用 + 特定）       │
              │                                     │
              │  通用：                               │
              │  - Semantic Backbone（设备/物流/变量） │
              │  - Scenario 分面（TEP/MVTec/Wafer）   │
              │                                     │
              │  TEP_KG 特定（保留）：                 │
              │  - TEP 52 通道变量映射                │
              │  - RCA Graph（FaultAnchor +           │
              │    SemanticConcept + 传播桥）          │
              │                                     │
              │  MVTec 特定（保留）：                  │
              │  - mvtec_rca_reference 参考边层       │
              │  - 多场景 shared 节点                 │
              └─────────────────────────────────────┘
```

### 保留的具体逻辑清单

**TEP_KG 不可丢失的逻辑**（位于 `src/tep_kg/`）：

| 模块 | 保留原因 |
|---|---|
| `parsing.py` — 四种解析器 + record_type → entity_type 映射 | TEP 代码/模型的领域解析规则 |
| `ontology.py` — 12 种实体类型 + 20 种关系的白名单约束 | TEP 工业本体定义 |
| `entity_resolution.py` — xmeas/xmv 别名消歧规则 | TEP 52 通道的命名变体消除 |
| `tep_variables.py` — XMEAS_TITLES / XMV_NAMES 硬编码映射 | TEP 变量到图谱实体的精确对应 |
| `prior.py` — 外部 prior 图谱的适配映射 | 外部知识的实体组/关系族转换 |
| `semantic_lift.py` — 全图 → 骨干图投影规则 | TEP 场景的语义 lift 逻辑 |
| `rca_graph.py` — 15 个 FaultAnchor 定义 + 6 个主题组 + 3 条传播桥 | TEP 故障根因的领域定义 |
| `assets.py` — 素材治理、扩展名分类、信任度 | 素材摄取层的 TEP 特定规则 |

**MVTec/KGTraceVis 不可丢失的逻辑**（位于 `src/kgtracevis/`）：

| 模块 | 保留原因 |
|---|---|
| `adapters/ds_mvtec_adapter.py` — 30+ 字段别名 + mask 派生逻辑 | MVTec 图像缺陷的 evidence 提取 |
| `adapters/tep_adapter.py` — 变量贡献归一化 + per-variable observation | TEP 时序的 evidence 提取 |
| `adapters/wafer_adapter.py` — 双模态（变量 + 日志）observation | Wafer 场景的 evidence 提取 |
| `adapters/_common.py` — 共享 adapter 工具 + REASONING_OUTPUT_KEYS 过滤 | Adapter 层的基础设施 |
| `schema/evidence_schema.py` — 统一 Evidence 模型 | 多源 evidence 的结构合约 |
| `kg_construction/confidence_assigner.py` — 12 种来源类型的置信度映射 | MVTec 的置信度赋值策略 |
| `kg_construction/triple_cleaner.py` — PascalCase/UPPER_SNAKE 规范化 | MVTec 的图格式规范 |
| `kg/graph.py` — NetworkX 图加载 + 实体搜索（fuzzy） | MVTec 的图运行时 |

---

## 5. 融合后的运行模式

建图有两种运行模式，共享同一套 L3 + L4：

### 模式 1：离线全量构建

```
素材目录 → L1(素材扫描) → L2(全模态提取) → L3(图谱组装) → L4(投影)
                                                              │
                                         ┌────────────────────┘
                                         ▼
                              Full KG + Backbone + RCA Graph
                              (导出为 JSONL/CSV/Neo4j)
```

适用场景：论文实验的图谱构建、批量评估

### 模式 2：在线增量构建（evidence 驱动）

```
新异常数据 → L2(对应模态提取器) → ExtractionRecord → L3(增量并入) → L4
                                                              │
                                                              ▼
                                                    更新后的 KG + RCA 路径
```

适用场景：运行时异常分析、交互式工作台

---

## 6. 这一层与 RCA 的关系

建图层的输出直接决定了 RCA 能做什么：

| 图谱产物 | 支撑的 RCA 能力 |
|---|---|
| Full KG（全量三元组） | 实体链接：evidence 中的对象/变量/缺陷类型 ↦ 图谱节点 |
| Semantic Backbone（设备-物流-变量图） | RFPA 故障传播仿真：在骨干图上模拟故障涟漪扩散 |
| RCA Graph（FaultAnchor + SemanticConcept） | 候选枚举 + 根因排名：已知故障类型作为搜索锚点 |
| Scenario KG（按场景分面） | 跨场景一致性检查 + 场景特定的路径排序 |
| TEP 52 通道映射 | RBC 贡献向量 Cont 到图谱变量的精确对应 |

---

## 7. 待你审阅的问题

1. **模态提取器的粒度**：Code 提取器内部是放一个"通用代码解析器"还是保留 TEP_KG 的三个独立解析器（MATLAB / Simulink / C）作为子模块？我倾向后者——文件夹内按语言分，但都实现同一个 Extractor 接口。

2. **Text 提取器的深度**：当前两个项目的文本解析都偏弱（TEP 只做文件名匹配，MVTec 的 text 来源基本是手写 CSV）。后续是否需要引入 NLP/NER 能力，还是保持规则为主？

3. **Image 提取器的归属**：图像缺陷检测（PatchCore 等）本身是模型推理，是否算"建图"的一部分，还是应该放在单独的"异常检测层"？目前我把它放在模态提取器里，但它实际上是"异常检测 → evidence → 实体链接"这条线的前半段。

4. **统一中间格式 ExtractionRecord 的字段**：目前设想包含实体候选、关系候选、证据指针、置信度。还有没有你关心的字段（例如时间戳、版本号、实验 ID）？
