# 统一 Evidence 构造：多源异构异常观测 → 统一 JSON

> **历史文档说明（2026-05-17）**
>
> 本文记录的是 RootLens 早期“前端承接本地建图 / 本地推理 / 对齐规划”的阶段性设计或交接语义，**已不代表当前实现边界**。
> 当前请优先以 `src/doc/backend-integration-current.md` 为真值；RootLens 现仅保留 backend-first 工作台、内置 Demo 与成品回放导入。


这份文档描述：当工业过程发生异常时，来自不同检测系统（图像、时序、日志）的观测结果，如何被归一化成同一种 JSON 结构。这个统一 JSON 是 RCA 系统的**唯一输入**——拿到它，系统就知道"发生了什么"，然后去图谱上追溯根因。

> **当前运行时说明**
>
> RootLens 当前前端运行时对 Unified Evidence 的校验，比本文最初的概念示意更严格。当前仓库里真正会被 validator 强制要求的字段，还包括：
>
> - 顶层：`case_label`、`summary`、`graph_dataset_id`
> - 每条 observation：`linked_entity_hints`、`raw_evidence_refs`
>
> 因此，本文档后续示例中的“最小结构”应理解为概念说明；真正用于导入的 JSON，需要满足当前运行时 contract。

---

## 0. Phase 1 当前实现映射

当前仓库里 Evidence 这一层的真实职责是“导入结构化 observation -> 校验 contract -> 组装本地 runtime case -> 交给浏览器端推理工作台消费”：

- 导入与 case 组装：`src/services/browser-runtime.ts`
- contract 校验：`src/contracts/runtime.ts` 中的 `parseUnifiedEvidenceContract()`
- runtime 持久化与读取：`src/services/rootlens-data.ts`
- 前端消费：`src/views/EvidenceWorkbenchView.vue`、`src/views/ReasoningWorkbenchView.vue`

当前导入链路支持两种浏览器端组装方式：

- 同批次导入图谱 + evidence，直接生成本地 runtime。
- 先导入图谱，再单独导入 `evidence*.json` / `case*.json`，复用当前会话图谱按 `case_id` 增量新增或覆盖 runtime case。

当前浏览器端**不会**从原始时序、原始图像或原始日志重新运行 RBC / PatchCore / 日志检测算法；它接受的是已经结构化好的 observation 记录，然后在前端本地完成实体链接、路径组织和候选排序。

---

## 1. 为什么需要统一 Evidence

当前两个项目的异常观测格式完全不同：

```
TEP_KG 的异常描述方式：
  Cont = {xmeas_1: 0.82, xmeas_7: 0.54, xmv_3: 0.31, ...}
  → 一个浮点向量，表达"哪些传感器偏离了正常"

MVTec 的异常描述方式：
  {
    object: "bottle",
    anomaly_type: "scratch",
    location: "body",
    severity: 0.87,
    confidence: 0.95,
    image_region: [x, y, w, h]
  }
  → 一个结构化记录，描述"在产品的什么位置看到了什么缺陷"
```

RCA 系统不能同时理解两种格式。统一 Evidence JSON 的目的就是**把所有异常观测翻译成同一种语言**。

---

## 2. 统一 Evidence 的结构设计

### 2.1 核心思路

一条统一 Evidence 描述一次异常事件中的一个**观测点**。一个异常事件可以包含多个观测点（例如同一个故障同时影响了 3 个传感器 + 1 个视觉缺陷）。

```json
{
  "case_id": "tep_fault_01_run_03",
  "case_label": "TEP Fault 01 / Run 03",
  "dataset": "tep",
  "source": "time_series",
  "timestamp": "2024-01-15T09:32:00Z",
  "summary": "Feed ratio drift with dominant sensor deviations.",
  "graph_dataset_id": "local-tep",

  "observations": [
    {
      "obs_id": "obs_001",
      "facet": "variable",
      "variable_name": "xmeas_1",
      "contribution": 0.82,
      "direction": "increase",
      "confidence": 0.95,
      "linked_entity_hints": ["xmeas_1", "reactor pressure"],
      "raw_evidence_refs": []
    },
    {
      "obs_id": "obs_002",
      "facet": "image_defect",
      "object": "bottle_body",
      "anomaly_type": "scratch",
      "location": "center",
      "morphology": {
        "area_ratio": 0.03,
        "eccentricity": 0.72,
        "component_count": 1
      },
      "severity": 0.87,
      "confidence": 0.95,
      "linked_entity_hints": ["bottle_body", "scratch"],
      "raw_evidence_refs": []
    }
  ]
}
```

### 2.2 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `case_id` | string | 唯一标识一次异常事件 |
| `case_label` | string | 当前 case 的展示标题 |
| `dataset` | enum | 数据集来源：`tep` / `mvtec` / `wafer` / `wm811k` |
| `source` | enum | 观测模态：`time_series` / `image` / `log` / `multimodal` |
| `timestamp` | iso8601 | 异常发生时间（时序场景为窗口中心，图像场景为采集时间） |
| `summary` | string | 当前 case 的摘要描述，供工作台和 runtime 显示 |
| `graph_dataset_id` | string | 当前 evidence 应绑定到哪张统一图谱 |
| `observations` | array | 观测点列表，每个观测点描述一个具体的异常表现 |

### 2.3 observation 的三种 facet

每个 observation 有一个 `facet` 字段，区分它描述的是什么类型的异常表现：

所有 observation 还有一组**通用字段**：

| 字段 | 说明 |
|---|---|
| `obs_id` | observation 唯一 ID |
| `facet` | 当前 observation 的类别 |
| `confidence` | 当前 observation 的可信度 |
| `linked_entity_hints` | 供前端和推理层参考的实体提示词 |
| `raw_evidence_refs` | 原始证据引用（文件路径、标签、行号等） |
| `attributes` | 可选扩展字段 |

当前运行时里，`raw_evidence_refs` 的每个元素都需要满足以下结构：

| 字段 | 类型 | 说明 |
|---|---|---|
| `ref_id` | string | 当前原始证据引用的唯一 ID |
| `label` | string | 给工作台显示的标签 |
| `role` | string | 引用在当前 case 中扮演的角色，例如 `sensor-window` / `mask` / `log-line` |
| `file_path` | string | 原始文件路径或逻辑来源标识 |
| `line` | number \| null | 若引用来自文本/日志行，则记录具体行号；否则为 `null` |

**facet = `"variable"`** — 时序变量偏离

| 字段 | 说明 | 例子 |
|---|---|---|
| `variable_name` | 传感器/变量名 | `"xmeas_1"`, `"reactor_temp"` |
| `contribution` | 该变量对异常的贡献度 [0, 1] | `0.82` |
| `direction` | 偏离方向 | `"increase"` / `"decrease"` / `"unknown"` |
| `confidence` | 贡献度的可信度 | `0.95` |
| `time_window` | 观测窗口（可选） | `{"start": "...", "end": "..."}` |

**facet = `"image_defect"`** — 图像缺陷

| 字段 | 说明 | 例子 |
|---|---|---|
| `object` | 缺陷所在对象 | `"bottle_body"`, `"wafer_center"` |
| `anomaly_type` | 缺陷类型 | `"scratch"`, `"contamination"`, `"missing_pattern"` |
| `location` | 缺陷位置 | `"center"`, `"edge"`, `"corner"` |
| `morphology` | 形态特征 | `area_ratio`, `eccentricity`, `component_count`, `centroid` |
| `severity` | 严重度 [0, 1] | `0.87` |
| `confidence` | 检测置信度 | `0.95` |
| `image_region` | 缺陷区域（可选） | `{"x": 100, "y": 80, "w": 45, "h": 30}` |

**facet = `"log_event"`** — 日志事件

| 字段 | 说明 | 例子 |
|---|---|---|
| `event_type` | 事件类型 | `"alarm"`, `"warning"`, `"state_change"` |
| `event_code` | 事件编码 | `"E1023"` |
| `message` | 事件原文 | `"Reactor pressure exceeds threshold"` |
| `equipment` | 关联设备 | `"reactor_r1"` |
| `confidence` | 事件可信度 | `0.80` |

### 2.4 为什么这样设计

1. **每个 observation 独立可链接**：RCA 的实体链接步骤会把 `variable_name` → 图谱中的变量节点，`object`/`anomaly_type` → 图谱中的设备和缺陷节点。所以字段必须能和图谱节点的 name/aliases 对得上。

2. **contribution 和 severity 都是 [0, 1]**：这样 RFPA 仿真播种时，不管证据来自时序还是图像，初始强度有统一的量纲。

3. **observations 是数组**：一次异常可能有多种表现（传感器偏离 + 外观缺陷 + 日志告警），多源证据天然共存。

---

## 3. 每种模态如何变成统一 Evidence

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   原始数据                     模态提取器              统一 JSON     │
│                                                                     │
│   ┌──────────────┐         ┌──────────────┐       ┌──────────────┐ │
│   │ 时序传感器读数 │ ──────→ │ Sequence     │ ────→ │ facet:       │ │
│   │ (m×n 矩阵)   │         │ Extractor    │       │ "variable"   │ │
│   └──────────────┘         └──────────────┘       │              │ │
│                                                   │ observations │ │
│   ┌──────────────┐         ┌──────────────┐       │   []         │ │
│   │ 缺陷图像      │ ──────→ │ Image        │ ────→ │              │ │
│   │ (+mask)      │         │ Extractor    │       │              │ │
│   └──────────────┘         └──────────────┘       └──────────────┘ │
│                                                                     │
│   ┌──────────────┐         ┌──────────────┐                        │
│   │ 日志事件流    │ ──────→ │ Text         │ ────→ （同上，合并进     │
│   │              │         │ Extractor    │       同一个 observations│
│   └──────────────┘         └──────────────┘       数组）            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.1 Sequence → facet: "variable"

**输入**：故障窗口内的多变量时序数据（m 个时间步 × n 个变量）

**处理步骤**：

```
时序数据矩阵 X (m × n)
    │
    ▼
┌─────────────────────────────┐
│ Step 1: 故障检测            │  确定异常窗口的起止时间
│                              │  → timestamp, time_window
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ Step 2: 变量贡献计算        │  RBC (PCA + SPE 重构) 或替代算法
│                              │  输出：每个变量的贡献度 cont_i ∈ [0,1]
│                              │  → variable_name, contribution, direction
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ Step 3: 变量 → 图谱实体映射  │  variable_name 与 TEP 52 通道映射表对齐
│                              │  确保变量名能在图谱中找到对应节点
└─────────────────────────────┘
    │
    ▼
每个变量生成一个 observation：{ facet: "variable", variable_name, contribution, direction, confidence }
```

**保留的特定逻辑**：TEP_KG 的 `rbc.py`（PCA + SPE 重构的核心算法）、`tep_variables.py`（XMEAS_TITLES / XMV_NAMES 硬编码映射）。

### 3.2 Image → facet: "image_defect"

**输入**：产品/晶圆的缺陷图像，可能附带 heatmap（异常热力图）、mask（分割掩码）、bbox（检测框）

**处理步骤**：

```
缺陷图像 + heatmap/mask/bbox
    │
    ▼
┌─────────────────────────────┐
│ Step 1: 异常区域定位         │  从 mask/bbox 或检测框提取缺陷位置
│                              │  → location (center/edge/corner)
│                              │  → image_region {x, y, w, h}
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ Step 2: 形态特征提取         │  从 mask 计算面积比、质心、离心率、
│                              │  连通分量数等形态描述
│                              │  → morphology {area_ratio, eccentricity, ...}
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ Step 3: 缺陷分类 + 严重度    │  确定缺陷类型（划痕/污染/缺失等）
│                              │  基于面积或分类器置信度评估 severity
│                              │  → anomaly_type, severity, confidence
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ Step 4: 对象映射             │  确定缺陷出现在什么对象上
│                              │  → object (bottle_body, wafer_center ...)
└─────────────────────────────┘
    │
    ▼
生成 observation：{ facet: "image_defect", object, anomaly_type, location, morphology, severity, confidence }
```

**保留的特定逻辑**：MVTec `ds_mvtec_adapter.py`（30+ 字段别名映射、mask feature summary → observation 派生）、`wm811k_adapter.py`（晶圆 bin map 分类）。

### 3.3 Log / Text → facet: "log_event"

**输入**：带时间戳的日志事件流（告警、状态变更、错误码）

**处理步骤**：

```
日志事件流
    │
    ▼
┌─────────────────────────────┐
│ Step 1: 事件解析             │  从日志行中提取事件类型、编码、消息
│                              │  → event_type, event_code, message
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ Step 2: 设备关联             │  从消息中识别涉及的设备名
│                              │  → equipment (映射到图谱设备节点)
└─────────────────────────────┘
    │
    ▼
生成 observation：{ facet: "log_event", event_type, event_code, message, equipment, confidence }
```

**保留的特定逻辑**：MVTec `wafer_adapter.py`（log_events 提取 + 双模态 observation 生成）。

---

## 4. 多模态 Evidence 的合并

一次异常事件可能同时触发多种检测系统。例如 TEP 故障 1（A/C 进料比漂移）可能产生：

- 时序：5 个传感器显著偏离（RBC 贡献度高）
- 图像：反应器视窗有异常沉积（如果安装了摄像头）
- 日志：DCS 系统记录到进料阀开度告警

这些不同模态的 observation 全部放入同一个 Evidence JSON 的 `observations` 数组：

```json
{
  "case_id": "tep_fault_01_run_03_multimodal",
  "dataset": "tep",
  "source": "multimodal",
  "timestamp": "2024-01-15T09:32:00Z",
  "observations": [
    {"facet": "variable", "variable_name": "xmeas_1",  "contribution": 0.82, ...},
    {"facet": "variable", "variable_name": "xmeas_7",  "contribution": 0.54, ...},
    {"facet": "variable", "variable_name": "xmv_3",    "contribution": 0.31, ...},
    {"facet": "image_defect", "object": "reactor_window", "anomaly_type": "deposit", ...},
    {"facet": "log_event", "event_type": "alarm", "equipment": "feed_valve_a", ...}
  ]
}
```

RCA 系统拿到这个 JSON 后，把每个 observation 链接到图谱上的对应节点，然后综合所有证据一起推理根因。多模态 evidence 之间可以形成**交叉验证**：时序和图像指向同一个设备时，该设备是根因的可信度更高。

---

## 5. Evidence 与建图、RCA 的衔接

三者的关系：

```
                    ┌─────────────────────┐
                    │   知识图谱（离线）    │  ← 模块一产物
                    │   Full KG + RCA     │
                    │   Graph + Backbone  │
                    └──────────┬──────────┘
                               │
                               │ 提供结构先验（谁连着谁）
                               │
   ┌───────────────────────────┼───────────────────────────┐
   │                           ▼                           │
   │  ┌──────────────────────────────────────────────┐    │
   │  │          统一 Evidence JSON（运行时）          │    │
   │  │                                              │    │
   │  │  多源异常观测 → 本层归一化 → 结构化异常描述     │    │
   │  └──────────────────────┬───────────────────────┘    │
   │                         │                            │
   │                         │ 每个 observation 指向       │
   │                         │ 图谱中的实体                │
   │                         ▼                            │
   │  ┌──────────────────────────────────────────────┐    │
   │  │              RCA 推理引擎                     │    │
   │  │                                              │    │
   │  │  1. 实体链接: observation → 图谱节点          │    │
   │  │  2. 候选枚举: 被链接节点 → 候选根因集合        │    │
   │  │  3. 路径排序: 图谱遍历 + 传播仿真              │    │
   │  │  4. 根因排名: RootScore 降序输出              │    │
   │  └──────────────────────────────────────────────┘    │
   │                                                     │
   └─────────────────────────────────────────────────────┘
```

几个关键衔接点：

1. **Evidence 的字段必须和图谱节点的 name/aliases 对齐**。`variable_name: "xmeas_1"` 必须能匹配到图谱中的 `variable:xmeas_1` 节点。这正是 TEP_KG `entity_resolution.py` 和 MVTec `entity_linker.py` 要做的事——如果对不上，RCA 第一步就断了。

2. **contribution 和 severity 是 RFPA 仿真的种子强度**。Root-KGD 的传播仿真以 `s_0 = cont_A` 为初始强度。现在 `image_defect` 的 `severity` 字段可以扮演同等的角色——图像缺陷越严重，从这个缺陷节点出发的传播强度越大。

3. **多 observation 支持多根因假设**。如果两条 observation 链接到图谱中不相邻的设备，可能暗示多个独立根因。RCA 的联合解释机制（Root-KGD 的多根因扩展）可以直接利用。

---

## 6. 统一 Evidence 这一层做什么、不做什么

**做**：
- 把异构异常观测翻译成统一字段名和统一量纲
- 保证每个 observation 携带足够信息（名称、强度、置信度），使 RCA 能独立使用
- 保留原始数据引用（`raw_evidence_refs` 可存储文件路径、标签、行号，用于溯源）

**不做**：
- 不做异常检测本身（RBC、PatchCore 等算法在"上游"运行，这一层只做格式转换）
- 不做实体链接（链接是 RCA 引擎的事，evidence 层只给变量名/对象名，不解析到图谱 ID）
- 不做根因推断（根因是 RCA 的事，evidence 只描述"看到了什么"）

---

## 7. 待你审阅的问题

1. **observation 的粒度**：一个故障窗口内可能有 52 个传感器，每个传感器一条 observation 是否太多？还是只保留 contribution 高于阈值的 top-K？

2. **contribution ≠ severity 的语义差异**：时序变量贡献度（RBC 算出的数学偏离）和图像缺陷严重度（物理大小）本质不同。它们都映射到 [0, 1] 用于仿真强度是否合理？还是需要分字段保留语义差异，在 RCA 层再做统一？

3. **raw_evidence_refs 引用**：统一 JSON 是否需要保留原始数据的引用（文件路径 + 行号），类似 TEP_KG 的 provenance 机制？当前 contract 已要求这一层存在；如果论文需要展示“证据可追溯”，需要进一步约束其字段规范和最小覆盖率。

4. **evidence 层的归属**：这一层是放在"建图"阶段（作为建图的输入素材之一），还是放在"RCA"阶段（作为推理的输入）？从流程上看它横跨两者——建图时用它验证实体链接质量，RCA 时用它驱动传播仿真。你倾向怎么归类？
