# RootLens 后端渐进重构与阶段展示方案

实施顺序、任务状态与完成条件见 [渐进重构执行计划](rootlens-refactor-execution-plan-2026-11-10.md)；本文件保留技术设计与三场景示例。M1–M6 已实施；实际 JSON、运行图、路径及验收结果见 [三场景使用与验收](../../backend/docs/progressive-demo-2026-11-10.md)。

## 当前目标

主线是**持续完善系统，Demo 展示当时已经完成的能力**，不以几个固定案例或预生成故事作为终点。前端布局和三页职责保持，主体改动放在后端。

近期围绕四件事推进：LLM-based 制作实际推理可用的知识图谱；图谱的管理/修改/导入导出及 Evidence 适配；使用真实特征的多证据推理；MVTec、TEP、WM811K 等场景的 backbone 适配。人工审核、正式版本化治理、置信校准与论文级因果验证后置。

这里的 make sense 有三个可检查含义：特征能在原图/原始数据中定位；图谱关系和匹配条件确实支持相应候选；解释图来自实际执行的绑定与推理过程。它不要求近期证明准确率提升或因果识别。

持续完善的系统链路为：

> 导入素材 → 自动生成领域图谱 → 上传案例 → 模型/算子得到结构化观测 → 按观测选出候选与路径 → 在现有界面联动查看。

现场可以使用现有 Backend 模式，预生成结果使用现有 Replay；不改变两种模式的含义。尚未完成的部分不作为展示中的已实现功能。

以下 JSON、数值、排序和图形均为**目标设计示例，不是本轮模型实测结果**；引用的图片/时序资产未随示例提供。它们描述后端内部输入，通常由 producer/adapter 自动生成，不要求用户手写；既有输入继续通过兼容适配接入。

## 1 保留前端 通过后端兼容层承接新内容

### 外层 API 不推倒重来

继续返回 `RunDetail`、`RunCaseDetail` 和 `KGStudioPayload`，保留：

- `generated_evidence.observations`：现有 Evidence 列表和详情；
- `linked_entities`：观测与图节点关联；
- `ranked_root_causes`：候选卡片与排序；
- `top_k_paths`、`path_graph`：路径列表、局部图和联动；
- `source_edge_provenance`：来源抽屉；
- `visual_evidence`：原图、热图、mask、wafer map；
- `workflow_steps`：已有工作流摘要。

新输入和内部事实由三种明确模型解析，再由后端 presenter 投影到上述旧字段。不是让前端直接理解新 JSON。

```text
VisualCaseInput / ProcessCaseInput / WaferCaseInput
    → 场景特征与事实
    → 候选选择 / 排序 / 路径选择
    → 原有 RunCaseDetail / RunDetail
```

源码契约见 `src/api/contracts.ts`；图投影可继续复用 `backend/src/kgtracevis/service/run_enrichment.py:path_graph_from_paths()`。

### 必须照顾现有字段读取方式

当前 `src/services/evidence-observation.ts` 将 `facet=image_defect` 识别为 image，将 `facet=variable` 识别为 time_series，将 `facet=log_event` 识别为 log。只往 observation 加 `kind` 或任意 metadata，不会自动出现新视图。

后端输出展示 observation 时需补齐当前实际读取的 `object/anomaly_type/location/morphology` 或 `variable_name/direction/contribution/time_window`，并写入 `linked_entity_hints`、`raw_evidence_refs`。内部 canonical observation 与展示 observation 允许由 presenter 映射，但必须保留 obs ID 或显式 parent ID，供路径和候选追踪。

前端仅预留三类小改：

1. observation 标题优先使用后端 `display_name`，否则沿用原逻辑；
2. 增加少量评分方法/关系名的中文文案；
3. 在现有候选详情中显示后端 `reason` 一段话（若现有来源/路径说明足够，连这项也可不加）。

不增加页面、不重排面板、不引入新的大型时序分析组件。TEP 必要的趋势图可以由后端输出 PNG，至多补一个现有详情区的预览。

## 2 LLM 自动构图 自动检查后即可使用

### 制作的是适合三种 Evidence 的领域图

LLM 输入包括原文素材、当前场景的节点/关系约束、实际可提取的特征词表和少量结构示例。构图不是只要求它“抽取一些三元组”，而是生成能够被当前 Evidence 和推理器消费的三组产物：

- **领域图**：设备/对象、缺陷/空间图案、形态、变量、过程机制、候选原因，以及三元组、别名、说明和素材引用。
- **观测绑定**：特征/变量 ID 到图概念的明确映射，例如区域 elongation/形态到线性形态、径向分布到环带特征、TEP 通道到已有变量 ID。
- **领域推理画像**：每种缺陷/图案/故障涉及哪些可观测条件、哪些条件共同支持它、哪些冲突、关联哪些候选与源边。缺失观测与反向证据分开处理。

当前 `backend/src/kgtracevis/source_kg_compiler/compiler.py:750–799,1135–1212` 已经生成 `domain_profiles.json`，其中包含 TEP `fault_profiles`、Wafer `pattern_profiles`、MVTec `object_defect_profiles`。这些目前主要作为构图产物输出，尚未成为运行推理的数据来源。**优先扩展并接通这条现成链路，不再另起一套平行的图谱框架。**

`domain_profiles` 表达领域知识，`reasoning adapter` 实现如何使用它；配置引用了一个文件，不等于算法已经消费了该知识。

画像的结构方向例如：

```json
{
  "profile_id": "mvtec:linear-surface-mark",
  "object_ids": ["MetalNutObject"],
  "anchor_concept_id": "ScratchDefect",
  "evidence_conditions": [
    {"feature": "region.morphology", "op": "eq", "value": "linear"},
    {"feature": "region.location", "op": "eq", "value": "surface"}
  ],
  "candidate_ids": ["MechanicalContact", "SurfaceWear"],
  "source_edge_ids": ["edge:scratch-contact", "edge:scratch-wear"]
}
```

这是拟议画像示例，不表示线性区域唯一对应划痕或能区分这两个原因。运行时结合语义/几何和其他画像比较；二者获得相同支持时，可同时保留，而不是生成一个额外观测强行拉开分数。

LLM 不生成任意可执行 Python。自动匹配仅使用注册的特征名、比较操作和图节点 ID；无法解析的项返回自动修复或跳过该项，不进入运行图。

最小自动检查覆盖：JSON/schema、重复 ID、端点存在、场景/类型、关系及特征/算子可识别、真实引用可回指。LLM 补充的领域假设单独标明生成方式，不回填虚构资料引文。**没有人工 accept 后才能发布的门槛。**生成关系保留 `review_status=auto` 和真实生成来源，不伪装成人工审阅。

现有存储如要求 `confidence/weight`，保留兼容字段或默认值；本轮不围绕它们校准、调门槛或设计审核流程。候选排序分数表达匹配/排序信号，不统一解释成概率。

### 当前工作图的管理是真功能 版本治理后置

- 素材可上传、列出、重新解析、重新构图；URL 要真的获取内容，PDF 要真的解析文本。
- 构图产生可加载的工作图包，包含节点、边、别名、来源、观测绑定和领域推理画像。`graph_id` 只用于选择工作图，不要求先实现不可变 release 制度。
- 节点/边/别名/绑定及画像可以持久修改；前端只补必要入口，不把 localStorage 草稿当成实际改图成功。
- 改图后更新或失效相关索引/画像，下一次推理使用修改结果；删除的边不得继续出现在新解释路径中。
- 导出必须带实际节点/边和绑定/画像，导入后能继续推理；不能只导出 summary 或文件路径。
- 保留旧图和历史结果，已有库不重建。覆盖导入采用明确动作和必要备份；正式审阅、复杂分支合并和完整版本治理不作为前置工作。

图谱制作与案例分析解耦：同一工作图服务多个案例，新增/修改素材时才重新构图或补图。系统应支持后期微调词表、映射和关系，但无需逐条人工审核后才能使用。

## 3 三类案例共用的后端推理流程

```text
模型/确定性算子提取观测并保留原始定位
→ 将数值/几何绑定为图上事实概念
→ 检索当前工作图的候选和领域推理画像
→ 联合匹配支持条件、冲突条件和所需观测
→ 场景 backbone/策略比较候选，形成真实计算记录
→ 由命中的图边与观测依赖生成解释子图和路径
→ 原契约返回前端
```

近期先实现可理解的画像匹配，不要求先训练通用因果模型。MVTec/Wafer 联合使用形态、空间位置、语义和对象约束；TEP 以当前数值 reasoner 为起点，接入当前工作图的变量、设备和故障画像，逐步改进其数值策略。LLM 可帮助比较检索到的候选和整理解释，但不能替代特征计算、条件执行和实际路径构建。

从 Toy 推进到可用系统的近期差别是：数值/空间关系真正参与计算；多个观测不会被同一字段覆盖；候选有支持、冲突和未检验项；结果随输入和图谱变化；输出能指回实际区域/窗口及真正使用的边。单独把一条路径的文字写得更合理，不算完成推理改造。

总图保存共用概念与领域关系；区域面积、贡献值、上升/下降等本次观测留在 case。局部图可在同一变量/概念 ID 上显示当前状态；确需案例特征节点时使用临时 overlay，不把每个案例的新节点永久堆进总图。

区分两类图边：

- 领域边，如 `PART_OF`、`MEASURED_IN`、`HAS_PLAUSIBLE_CAUSE`；
- 解释边，如 `SUPPORTS_SIGNATURE`、`INDICATES_PATTERN`、`EXPLAINED_BY`。

后者表示从观测到候选的诊断联系，不把“症状支持故障”画成“症状造成故障”。反向检查一条领域边时，后端可生成带 `origin_edge_id` 的解释视图边，来源抽屉仍能回到原边；不能静默调换物理因果方向。

## 4 MVTec 金属螺母线性表面异常

### 4.1 后端新增的明确输入模型

```json
{
  "schema_version": "rootlens-case-input.v1",
  "case_id": "mvtec_demo_scratch_01",
  "dataset": "mvtec",
  "graph_id": "mvtec-demo-01",
  "visual": {
    "object": "metal_nut",
    "image_asset_id": "design:metal-nut:image",
    "regions": [
      {
        "obs_id": "mvtec-r1",
        "bbox_xyxy_px": [146, 112, 364, 148],
        "location": "surface",
        "area_ratio": 0.018,
        "elongation": 8.1,
        "component_count": 1,
        "semantic_candidates": ["scratch"]
      }
    ]
  }
}
```

`area_ratio/elongation/component_count` 来自 mask 算子；`semantic_candidates` 来自 ROI 语义模型或显式提供的标签，记录来源。PatchCore 本身只提供异常与定位，不把其输出自动说成缺陷类型。

从已接通的 detector 开始，先完善 ROI 几何和语义层；随后按实际缺陷表现、分辨率与速度需求替换或增加 backbone。不能只换模型名称而沿用错误的模型类/预处理。系统比较可后续补，近期先验证框和描述的特征确实对应原图。

### 4.2 总图中的相关部分

```text
金属螺母 ──HAS_ANOMALY──────────→ 划痕
线性形态 ──SUPPORTS_DEFECT─────→ 划痕
表面位置 ──COMPATIBLE_WITH─────→ 划痕
划痕 ──HAS_PLAUSIBLE_CAUSE─────→ 机械接触
划痕 ──HAS_PLAUSIBLE_CAUSE─────→ 表面磨损
机械接触 ──PART_OF─────────────→ 搬运损伤
```

划痕、机械接触、表面磨损及其候选关系可复用当前 `backend/data/kg/mvtec_rca_reference.csv` 的词汇/关系。新增 feature→concept 边是拟议的自动匹配关系。

### 4.3 案例路径及页面解释

候选路径一：**线性形态 → 划痕 → 机械接触**。

补充路径：**金属螺母 → 划痕 → 机械接触**。

候选路径二：**线性形态 → 划痕 → 表面磨损**。

页面文字示例：“当前是单个细长表面区域，并有 scratch 语义候选，支持划痕相关解释；机械接触与表面磨损都与现有观测相容，暂不能进一步区分。”这是拟议结果说明；实际顺序由当次输入与策略给出，不把展示先后当作已获得区分证据。

如果改成分散斑点/颜色异常，后端应切换到污染或材料/涂层相关候选，而不是仍返回划痕路径。

## 5 TEP A 进料异常

### 5.1 后端输入保留数值和窗口

```json
{
  "schema_version": "rootlens-case-input.v1",
  "case_id": "tep_demo_feed_01",
  "dataset": "tep",
  "graph_id": "tep-demo-01",
  "process": {
    "normal_profile_id": "design:tep:normal-profile",
    "window": {
      "start_sample": 161,
      "end_sample_exclusive": 261,
      "sample_period_seconds": 180
    },
    "channels": [
      {"obs_id": "tep-v1", "variable_id": "variable:xmeas_1", "contribution": 0.42, "direction": "decrease", "z_mean": -3.1},
      {"obs_id": "tep-v4", "variable_id": "variable:xmeas_4", "contribution": 0.26, "direction": "decrease", "z_mean": -2.2},
      {"obs_id": "tep-v7", "variable_id": "variable:xmeas_7", "contribution": 0.14, "direction": "decrease", "z_mean": -1.4}
    ],
    "other_channels_contribution": 0.18,
    "series_asset_id": "design:tep:window"
  }
}
```

通道身份来自现有 TEP 资产：XMEAS1 为 A 进料流量，XMEAS4 为 A/B/C 进料流量，XMEAS7 为反应器压力。示例窗口和数值仅用于说明格式；现场计算需使用实际注入时刻与窗口。

完整时序和完整贡献向量仍由后端保留；这里的 channels 是讲解用的 top contributors，不能用前三项替换现有数值 reasoner 的完整输入。贡献合计中剩余0.18也明确保留。

### 5.2 图谱有领域结构 也有解释视图

```text
领域结构：
A进料流股 ──FEEDS──────────────→ 反应器
XMEAS1 ──MEASURES──────────────→ A进料流股
XMEAS7 ──MEASURES──────────────→ 反应器压力
A进料损失候选 ──AFFECTS────────→ A进料流股

案例解释视图：
XMEAS1下降 ──SUPPORTS_SIGNATURE─→ 进料异常特征组合
XMEAS4下降 ──SUPPORTS_SIGNATURE─→ 进料异常特征组合
XMEAS7下降 ──SUPPORTS_SIGNATURE─→ 进料异常特征组合
进料异常特征组合 ──EXPLAINED_BY─→ A进料损失候选
```

这些新增解释边为设计示例；领域语义在制作时从当前素材和已有 TEP 资产生成。候选可复用 `faultanchor:stream_1_a_feed_loss`。特征组合是否成立由本次窗口决定，不凭 case ID 或 fault number 直接选答案。

### 5.3 演示应突出多变量汇聚

同一个候选展示2–3条观测支持路径，而不是只显示一条最长路径。候选说明可以写：“A进料流量下降是主要贡献，混合进料与反应器压力变化共同支持进料相关故障方向。”

后端先保留 Root-KGD 数值排序，补齐正确窗口、配套 normal profile 和图节点映射；随后改进多变量签名、变化方向和必要时序特征的利用，并让当前图/画像参与候选比较。用真实排序依赖制作路径。若策略实际选出其他候选，解释跟随结果，不强制套用本示例顺序。

## 6 WM811K 环带图案

### 6.1 输入是空间分布 不把图案写成物理污染物

```json
{
  "schema_version": "rootlens-case-input.v1",
  "case_id": "wafer_demo_donut_01",
  "dataset": "wafer",
  "graph_id": "wafer-demo-01",
  "wafer": {
    "obs_id": "wafer-map-1",
    "map_asset_id": "design:wafer:map",
    "cell_encoding": {"background": 0, "pass": 1, "fail": 2},
    "valid_die_count": 640,
    "failed_die_count": 96,
    "failure_ratio": 0.15,
    "predicted_pattern": "Donut",
    "spatial_features": {
      "dominant_zone": "middle_annulus",
      "shape": "annular",
      "center_sparser_than_ring": true,
      "outer_edge_sparser_than_ring": true
    }
  }
}
```

先修现有背景/有效die/失败编码问题，保留当前分类器；确定性空间统计和分类结果共同支持图案。`predicted_pattern` 与 `spatial_features` 是分别定义的字段，不由一段 caption 自解释。

### 6.2 图谱和路径

```text
Donut图案 ──HAS_SPATIAL_SIGNATURE──────→ 环带特征
环带特征 ──SUGGESTS_PLAUSIBLE_MECHANISM→ 工艺不均匀
环带特征 ──SUGGESTS_PLAUSIBLE_MECHANISM→ 湿法清洗残留
Donut图案 ──OCCURS_ON──────────────────→ 晶圆中间环带
```

前两类候选和相关空间特征词汇可复用当前 `backend/data/kg/wafer_edges.csv`；“中间环带”是拟议的更细空间概念。LLM 可从现有素材补充解释，不要求人工逐条审核。

主路径示例：**Donut图案 → 环带特征 → 工艺不均匀**。

备选：**Donut图案 → 环带特征 → 湿法清洗残留**。

页面说明强调“图案和空间统计为什么支持这两个调查方向”。没有本例设备日志，就不补造停机、阀门未开启等事件来让路径更丰富。

## 7 返回前端的 JSON 仍然长得像现在

以下截取 MVTec `RunCaseDetail` 的关键字段；完整 Run 外壳、其他字段和 `path_graph` 仍由后端统一包装。

```json
{
  "case_id": "mvtec_demo_scratch_01",
  "dataset": "mvtec",
  "generated_evidence": {
    "case_id": "mvtec_demo_scratch_01",
    "dataset": "mvtec",
    "source": "image",
    "graph_dataset_id": "mvtec-demo-01",
    "observations": [
      {
        "obs_id": "mvtec-r1",
        "facet": "image_defect",
        "display_name": "细长表面异常，面积占比1.8%",
        "object": "metal_nut",
        "anomaly_type": "scratch",
        "location": "surface",
        "morphology": "linear",
        "confidence": null,
        "linked_entity_hints": ["LinearMorphology", "ScratchDefect", "MetalNutObject"],
        "raw_evidence_refs": []
      }
    ]
  },
  "linked_entities": [
    {
      "link_id": "link:mvtec-r1:linear",
      "obs_id": "mvtec-r1",
      "field": "morphology",
      "mention": "linear",
      "selected_entity_id": "LinearMorphology",
      "selected_entity_name": "线性形态",
      "match_type": "feature_binding",
      "ambiguous": false,
      "candidates": []
    }
  ],
  "ranked_root_causes": [
    {
      "ranking_id": "ranking:mvtec-demo:mechanical-contact",
      "rank": 1,
      "candidate_id": "MechanicalContact",
      "candidate_name": "机械接触",
      "candidate_role": "plausible_mechanism",
      "support_evidence_ids": ["mvtec-r1"],
      "scoring_method": "visual_feature_graph_match",
      "scoring_details": {
        "reason": "单个细长表面区域与划痕语义相符；机械接触与表面磨损均与现有观测相容，当前特征不能进一步区分。"
      }
    }
  ],
  "top_k_paths": [
    {
      "path_id": "path:mvtec-demo:linear-scratch-contact",
      "source_entity_id": "LinearMorphology",
      "target_entity_id": "MechanicalContact",
      "nodes": ["LinearMorphology", "ScratchDefect", "MechanicalContact"],
      "node_names": ["线性形态", "划痕", "机械接触"],
      "relations": ["SUPPORTS_DEFECT", "HAS_PLAUSIBLE_CAUSE"],
      "source_edge_ids": ["edge:linear-scratch", "edge:scratch-contact"],
      "support_obs_ids": ["mvtec-r1"]
    }
  ]
}
```

此处为字段设计节选，省略 score、其他候选和完整 source edges，不是可直接导入的完整运行结果。实际 presenter 必须补齐 core/RunDetail 要求的字段，且：

- `source_edges` 与每条路径的相邻节点、relation 一一对应；
- 用同一组路径派生 `path_graph` 和 `source_edge_provenance`；
- candidate 的 `explanation_paths`、`support_evidence_ids` 与它所选路径一致；
- 总图节点与 path graph 使用同一实体 ID；
- case observation IDs 与路径 `support_obs_ids` 一致；
- 资料来源写回现有 source/evidence 字段，供当前抽屉展示。

TEP presenter 将 channels 映射为 `facet=variable`，填 `variable_name/direction/contribution/time_window`；Wafer 暂映射为 `facet=image_defect`，`object=wafer`、`anomaly_type=Donut`，配合现有 `kind=wafer_map` 图片资产，不新增晶圆专属页面。

## 8 渐进实施顺序和每一步能展示的能力

四条工作线持续推进，先稳定特征词表和绑定接口，避免构图器与 backbone 各自定义同一个字段。每步提供可复用能力，Demo 按其完成情况选内容：

| 阶段 | 后端完成的系统能力 | 对应的阶段展示 |
| --- | --- | --- |
| A 构图能用 | 真实素材解析；LLM 生成图、绑定与领域画像；自动结构/引用检查；工作图能加载 | 换一份相关素材能构图，生成概念能与支持的 Evidence 字段绑定 |
| B 图谱能管 | 当前工作图持久增删改、别名/绑定/画像微调；完整导入导出；更新索引 | 修改或导入知识后重新分析，实际图与结果相应变化 |
| C 推理做实 | 运行时消费生成的领域画像，多观测联合匹配、冲突处理和场景策略；从真实计算依赖生成路径 | 不同输入得到对应支持链，多个特征共同解释候选，能说明为什么某条路径被选 |
| D 场景逐步深化 | MVTec 区域/语义，TEP 数值/时间窗口，Wafer 空间图案各自完善 backbone 与特征 | 原图或数据上的特征与节点/候选逐项对得上；未完成的场景只展示已有能力 |

阶段A先固定知识/观测接口；领域特征和 backbone 工作可以随之并行推进，不必等图谱管理全部完成。阶段C先用 MVTec/Wafer 的图案/形态画像建立共同执行链，再接 TEP 特有数值策略；不将它们硬压成一个通用公式。

近期功能验收关注：

- 解析、构图、修改、导入导出都有可继续使用的真实产物，不是只完成展示元数据。
- 同场景用多组不同输入，包括条件不吻合的情况；匹配/不匹配能解释，不以单个固定案例完成为退出条件。
- 观测能回原图区域/时序窗口/wafer cells，特征数值和空间描述一致。
- 绑定、候选、实际图边与路径 ID 对齐；后台改图后新结果使用新内容。
- 前端仍使用现有三页和契约，只为新能力补必要字段文案/详情。

审核、正式版本化、置信校准、完整 benchmark 和更强因果验证属于后续完善。近期仍保留基本输入检查、来源、保存与备份，它们服务于系统正确运行，不构成人工审核工作流。
