# RootLens 统一工业推理方法：调研、契约与渐进实施方案

日期：2026-11-10。状态：**方法设计与实施规划，尚未实现下述 v2 内核**。

主线：不同 backbone / 数据源经 adapter 生成有明确语义的 Evidence；领域知识不同，但图上的候选生成、联合检验、冲突处理、解释选择采用同一推理机制。MVTec 仍是首个落地入口，TEP 同时约束内核设计，Wafer 用于检验新增场景是否需要改内核。前端保持现有三页结构，审核、正式版本治理、置信校准后置。

当前运行能力以 [当前集成边界](/Users/hhm/code/RootLens/src/doc/backend-integration-current.md) 为准。本方案替代旧规划中“统一接口、保留三个场景评分器”作为最终方法的方向，不把历史实施结果改写成统一方法已完成。

**具体产物与可复算规格已补齐**：§5.6 给出完整 MVTec 例子；同一知识包另含 TEP、Wafer 算例。三类产物是知识包、Evidence、推理结果；另附由知识包生成的 nodes/edges 视图。全部是合成设计样例，JSON 与代价计算已核对，尚未接入运行后端。

## 1. 选择：类型化观测＋可执行知识＋图约束溯因

推荐把方法组织成 **观测落地的图约束溯因推理**：在图谱声明的候选与机制范围内，寻找能够共同解释当前观测、与已测事实少冲突、需要较少额外假设的解释子图。

核心研究问题：**保持推理算法与全局比较策略不变，仅改变观测适配与领域知识，能否在异构工业异常任务上生成有区分力、可追溯的候选解释？**

三个子问题沿用 MVTec、TEP、Wafer 的范围：

1. 数值、区域、空间分布和语义预测如何成为可执行但不混淆含义的观测？
2. 图谱如何表达联合条件、候选的预期表现、冲突和不完整知识？
3. 相比独立路径或独立画像匹配，联合解释能增加什么能力，什么情况下并没有增加收益？

### 1.1 为什么选这条路线

| 路线 | 文献中的机制 | 对本项目的判断 |
| --- | --- | --- |
| KG 检索＋LLM 路径探索 | Think-on-Graph 让 LLM 在 KG 上迭代搜索路径 | 可作对照及知识检索辅助；我们的数值、区域联合条件仍需另外执行，不能把最后判断完全交给生成文字 |
| 完整因果机制模型 | Budhathoki 等使用已知因果 DAG、功能机制及可恢复噪声进行异常归因 | 适合后续有足够过程数据的局部模型；目前不能由语义 KG 自动得到三个场景都可用的机制模型 |
| 概率逻辑／软约束 | ProbLog 为概率程序定义查询概率；PSL 将关系规则编译为软／硬约束 | 借鉴显式规则、约束和联合优化；不直接把 detector score、LLM confidence 填成概率参数 |
| **受限的加权溯因** | 在知识支持下，用假设解释观测并比较解释代价 | **近期首选**：可使用有限、自动生成的领域知识，且不要求先有完整故障训练集或校准概率 |

依据分别见 [Think-on-Graph，ICLR 2024，摘要与方法](https://proceedings.iclr.cc/paper_files/paper/2024/hash/10a6bdcabbd5a3d36b760daa295f63c1-Abstract-Conference.html)、[Budhathoki 等，ICML 2022，§1 A1–A3](https://proceedings.mlr.press/v162/budhathoki22a/budhathoki22a.pdf)、[ProbLog，IJCAI 2007，§1、§3](https://ijcai.org/Proceedings/07/Papers/396.pdf)、[PSL，JMLR 2017，§3–4](https://www.jmlr.org/papers/volume18/15-631/15-631.pdf)。表中“对本项目的判断”是基于当前资产的设计选择。

Reiter 的诊断理论提供了“模型／假设与观测是否相容”的基础；Hobbs 等的 weighted abduction 提供了“以较少代价解释观测”的思路。本方案借鉴两者，不把基于故障表现的溯因称为已实现 Reiter 的完整诊断算法。[Reiter，1987，摘要](https://www.sciencedirect.com/science/article/abs/pii/0004370287900622)、[Hobbs 等，1993，摘要](https://www.isi.edu/people-hobbs/wp-content/uploads/sites/58/2023/11/interp-abduct-ai.pdf)。

LLM 生成形式化知识、确定性程序执行的分工已有 Logic-LM；工业 KG-DML 也使用 LLM 制作带 AND/OR 的系统模型并调用诊断工具。因此论文贡献应由异构观测接入、联合解释与迁移实验建立，不能只靠“LLM＋KG＋规则引擎”的组合命名。[Logic-LM，EMNLP 2023，§3](https://aclanthology.org/2023.findings-emnlp.248/)、[KG-DML，2025，§4–5.1](https://www.mdpi.com/2076-3417/15/17/9428)。

## 2. 当前资产如何保留，方法差距在哪里

| 现有部分 | 处理方式 |
| --- | --- |
| 原图／时序／wafer 解析、模型执行、ROI、空间统计、正常参考与 PCA | 保留为 producer；继续修正测量问题，不复制到推理器 |
| 素材解析、SourceUnit → KnowledgeCard → 实体／关系 | 保留，新增公共可执行知识编译目标 |
| 工作图保存、编辑、导入导出、运行快照 | 保留持久化能力；扩展知识包与编辑依赖，避免独立存两套规则真值 |
| VisualProfileReasoner、MeasuredProfileReasoner、旧 Root-KGD | 保留旧入口及对照；新内核不调用它们的最终排名 |
| API、运行记录、三页前端、Replay | 复用；新增 trace 字段仍投影为现有候选与路径 |

当前 [视觉 reasoner](/Users/hhm/code/RootLens/backend/src/kgtracevis/workflows/profile_match_reasoner.py) 用特征组匹配分，[measured reasoner](/Users/hhm/code/RootLens/backend/src/kgtracevis/workflows/measured_profile_reasoner.py) 对 TEP 使用贡献与图传播对齐、对 Wafer 使用空间特征组；[选择器](/Users/hhm/code/RootLens/backend/src/kgtracevis/workflows/root_cause_provider_selection.py) 按场景选择实现。它们已经消费实际观测和工作图，但尚未采用同一解释选择机制。

此外，[外层 EvidenceObservation](/Users/hhm/code/RootLens/backend/src/kgtracevis/schema/evidence_schema.py) 仍包含 `Any`；新场景靠各自闭合的内部模型校验。下一步要统一的是内部执行语义，而不只是更换外层字段名。

## 3. 完整数据流与责任边界

```text
原图 / 时序 / wafer cells / 日志
  → backbone + producer：检测、定位、测量、统计、感知语义
  → adapter：类型化 Evidence JSON（事实及生成依据，不含根因答案）
  → grounding：身份绑定、单位/参考检查、观测条件求值
  → 公共解释图：观测、派生现象、候选假设、实际可用规则
  → 统一溯因内核：候选检索 → 假设展开 → 联合比较
  → 实际证明 DAG、候选差异、支持/冲突/缺失
  → 现有 ranked_root_causes、top_k_paths、scoring_details
```

知识制作是另一条供给链，不使用当前 case 的答案：

```text
公开资料 / 变量表 / 工艺说明 / 已有知识图
  + producer 能力清单 / 注册特征定义 / 允许的算子
  → 来源解析与定位
  → LLM 抽取结构、可观测表现、候选与适用条件
  → LLM 将条件映射为公共知识 IR
  → 类型/引用/可执行性检查 + 有界修复 + 确定性探针
  → 当前可用知识包（领域图 + 绑定 + 规则 + 来源）
```

### 3.1 Backbone、producer 与 adapter 分工

| 场景 | Backbone / producer 负责 | Adapter 负责 | 不能提前做的事 |
| --- | --- | --- | --- |
| MVTec | 现有 PatchCore/STFPM 定位；坐标还原；区域几何；可选 ROI VLM 与正常参考比较 | 输出区域主体、数值、语义候选集、坐标、方法与输入引用 | 读取目录缺陷名当预测；让 VLM 直接填写机械原因 |
| TEP | 固定正常参考的 scaler/PCA；完整通道统计和 SPE 残差平方贡献；后续可增加起始时间与动态残差 | 输出稳定通道身份、窗口、参考资产、完整向量引用与标量观测 | 输出 fault ID 或 RootScore；重新拟合参考后继续冒用旧参考身份 |
| Wafer | 正确 0/1/2 编码；有效 die 几何、径向密度、聚集与线性统计；可选分类器 | 输出空间主体、统计定义、网格与预测来源 | 把 pattern label 直接写成该片 wafer 的实际制造原因 |

TEP 当前贡献计算是归一化 SPE 残差平方贡献；新契约以 `spe_residual_share` 命名，旧接口中的 RBC 名称只作兼容显示，不继续扩散数学含义混用。

Producer 可有不同实现，但须发布能力清单：`feature_id`、值类型、单位、算法定义、适用主体、依赖资产与前置输入。LLM 只能引用清单中存在的测量能力。

### 3.2 统一 Evidence 的原则

统一的是 **谁的什么属性，在什么范围内，由什么方法得到什么值**。此分解借鉴 SOSA 对 feature of interest、observed property、result、procedure 和 phenomenon time 的区分；本项目继续使用 JSON/Pydantic，不要求迁移为 RDF。[W3C SOSA/SSN，2017，§4](https://www.w3.org/TR/2017/REC-vocab-ssn-20171019/)。

公共模型包含：

- `subjects`：本事件中的对象、区域、变量、空间网格；本地 ID 不冒充已经绑定的 KG ID。
- `observations`：`obs_id`、`subject_id`、`feature_id`、类型化 `value`、`status`、`scope_id`、`procedure_id`、`reference_id`、`dependency_group`、`raw_refs`。
- `scopes`：图像区域的坐标，时序窗口的采样定义，网格区域的坐标与编码。
- `procedures/references/assets`：模型、特征算法、正常参考、输入形状／顺序及文件引用。
- `task`：目标角色与分析范围，如 defect_type、mechanism、fault、component 或 spatial_pattern。它选择候选空间，不切换评分算法。

`value` 采用有判别字段的闭合联合：Number、Boolean、Category、CandidateSet、Interval、TypedArrayRef。注册的 `feature_id` 再限制它允许哪一种值、单位和主体；`number` 不能塞字符串，图像 bbox 不能冒用时序数组。

注册表可扩展，不把所有工业特征固化在一个 `Literal["mvtec...", "tep..."]` 中。新增特征必须有定义和计算实现；未知字段可归档为原始资料，但不自动获得执行资格。

状态固定为 `observed / missing / invalid / not_applicable`。数值为 0、模型报告正常、尚未检测和检测失败是不同情况。模型的 `CandidateSet` 是感知估计，不当成确定的缺陷事实；原始分类分数若保存，须记录分数种类，不直接参与跨模态相加。

`CandidateSet` 默认是开放候选集：未包含 scratch 不等于明确排除 scratch。只有定义了封闭标签空间及有效阴性判断的模型输出，才允许据此生成反面条件。检测器的正常判断也以明确观测保存；没有 ROI 或未执行语义识别不自动成为正常证据。

### 3.3 一个 MVTec 目标 JSON 示例

以下及后文的数值与 ID 均为 **设计样例**，不是本轮真实模型输出；v2 JSON 暂不能直接提交给现有 API。完整 schema 在阶段 U0 固化。

```json
{
  "schema_version": "rootlens-evidence.v2",
  "case_id": "design-mvtec-001",
  "source_dataset": "mvtec",
  "task": {"target_role": "mechanism", "context_subject_id": "object:1",
           "focus_subject_ids": ["roi:1"], "scope_id": "scope:roi1"},
  "subjects": [
    {"subject_id": "object:1", "kind": "object", "external_namespace": "mvtec.object", "external_id": "metal_nut"},
    {"subject_id": "roi:1", "kind": "image_region", "parent_id": "object:1"}
  ],
  "scopes": [
    {"scope_id": "scope:roi1", "kind": "image_region", "subject_id": "roi:1", "asset_id": "image:1",
     "image_shape_hw": [900, 900], "coordinate_space": "original_image_pixels",
     "bbox_xyxy": [210, 180, 570, 230]}
  ],
  "assets": [
    {"asset_id": "image:1", "kind": "image", "uri": "design://image.png"},
    {"asset_id": "mask:1", "kind": "mask", "uri": "design://mask.png"},
    {"asset_id": "semantics:1", "kind": "json", "uri": "design://roi-semantics.json"}
  ],
  "procedures": [
    {"procedure_id": "geometry:v1", "kind": "measurement", "input_asset_ids": ["mask:1"]},
    {"procedure_id": "roi-vlm:v1", "kind": "model_estimate", "input_asset_ids": ["image:1", "mask:1"]}
  ],
  "observations": [
    {"obs_id": "o:aspect", "subject_id": "roi:1", "feature_id": "geometry.aspect_ratio",
     "value": {"kind": "number", "number": 7.2, "unit": "1"},
     "status": "observed", "scope_id": "scope:roi1", "procedure_id": "geometry:v1",
     "dependency_group": "image:1/roi:1", "raw_refs": ["mask:1"]},
    {"obs_id": "o:ecc", "subject_id": "roi:1", "feature_id": "geometry.eccentricity",
     "value": {"kind": "number", "number": 0.97, "unit": "1"},
     "status": "observed", "scope_id": "scope:roi1", "procedure_id": "geometry:v1",
     "dependency_group": "image:1/roi:1", "raw_refs": ["mask:1"]},
    {"obs_id": "o:semantics", "subject_id": "roi:1", "feature_id": "appearance.semantic_candidates",
     "value": {"kind": "candidate_set", "items": ["scratch", "crack"], "exhaustive": false},
     "status": "observed", "scope_id": "scope:roi1", "procedure_id": "roi-vlm:v1",
     "dependency_group": "image:1/roi:1", "raw_refs": ["semantics:1"]},
    {"obs_id": "o:material", "subject_id": "roi:1", "feature_id": "appearance.foreign_material_present",
     "value": {"kind": "boolean", "boolean": false},
     "status": "observed", "scope_id": "scope:roi1", "procedure_id": "roi-vlm:v1",
     "dependency_group": "image:1/roi:1", "raw_refs": ["semantics:1"]}
  ]
}
```

这里没有预写 `root_cause`，也没有把 `7.2` 叫作异常概率。几何与语义仍有区别，但它们共享图像来源，不能自动变成独立支持。特征值不在 adapter 内阈值化为“机械接触”；阈值及其知识含义在后面的可执行图中。显式附着物阴性估计是目标语义能力，未接入时应为 missing；不能从候选集没有 contamination 推出 false。完整样例还包含异常门控观测，见 §5.6。

### 3.4 TEP 与 Wafer 使用同一种 observation

TEP 的一条数值观测可以是：

```json
{
  "obs_id": "t1", "subject_id": "channel:xmeas_9", "feature_id": "statistics.mean_z",
  "value": {"kind": "number", "number": 2.4, "unit": "1"}, "status": "observed",
  "scope_id": "window:161-260", "procedure_id": "window-stats:v1",
  "reference_id": "normal-reference:design-v1", "dependency_group": "process-window:1",
  "raw_refs": ["series:1"]
}
```

配套定义：`subject` 的外部身份为 xmeas_9；窗口从 1 开始、两端包含、采样间隔 180 秒；`mean_z` 表示逐样本按固定正常均值和标准差标准化后再取窗口均值。`series:1` 的 TypedArrayRef 固定 dtype、shape、全部 52 通道顺序与时间轴。归一化残差贡献使用另一 `feature_id`，不与 `mean_z` 混用。

另外两条样例观测可为 xmeas_21 的 `mean_z=3.2`、xmeas_1 的 `mean_z=0.2`。这三个数只演示接口；实际 producer 保留完整通道，不把展示的几个变量当作完整输入。

Wafer 的一条空间观测则是：

```json
{
  "obs_id": "w1", "subject_id": "wafer:1", "feature_id": "spatial.failure_density",
  "value": {"kind": "number", "number": 0.47, "unit": "1"}, "status": "observed",
  "scope_id": "wafer-edge-band:1", "procedure_id": "valid-die-radial-stats:v1",
  "dependency_group": "wafer-grid:1", "raw_refs": ["wafer-cells:1"]
}
```

这里 `scope` 声明归一化半径环带与有效 die 掩码；密度分母为该环带内有效 die，不是整个矩形数组。若另有中心密度 0.03、分类候选 edge-ring，也保留为同格式观测；原生 failureType 留在 evaluation reference，不传给分类器。

## 4. 图谱制作：领域结构、可观测定义与假设规则共同交付

### 4.1 图中必须包含的知识

| 内容 | 用途 |
| --- | --- |
| Entity / Context | 对象、变量、设备、位置、工况及身份、别名；限定规则适用范围 |
| ObservableDefinition / Binding | 哪个注册特征、哪个主体／区域／窗口，对应哪个可观测状态 |
| DerivationRule | 从观测条件推出一个现象，如同一区域同时细长且高离心率 |
| Hypothesis / ExpectationRule | 某候选通过何种机制，可能或应当表现为什么；比较预期与观测 |
| Constraint | 联合、互斥、相对位置、时序及冲突；缺失时保留未知 |
| SourceAssertion | 原片段、知识来源种类及参数依据；支持实际使用的规则／边 |

`PART_OF`、`MEASURES`、`ASSOCIATED_WITH` 可以帮助绑定或限定范围，不能仅因连通就变成原因边。多前提规则用规则节点表达 AND/OR 及变量绑定，不把一条超边拆成几个彼此独立的二元“支持”。

### 4.2 同一份公共 IR，而不是三个诊断 JSON

知识包采用 entities、relations、observable_definitions、bindings、rules、source_assertions 的公共模型。绑定后的规则变量统一指向主体与 scope，不读取数据集名字。

例如，TEP 的绑定首先由可信通道表声明 `xmeas_9 → ReactorTemperature`；`statistics.mean_z` 保持特征身份，`normal-reference:design-v1` 保持标准化含义。ObservableDefinition 再声明：对这个变量在指定正常参考下的窗口均值，怎样求出“升高”“偏离”或“处于正常区间”。因此，推理并不是根据字符串 `xmeas_9` 猜温度含义，也不是靠 LLM 阅读 2.4 后自由解释。

例如，一个用于演示的联合视觉表现定义：

```json
{
  "definition_id": "d:linear_mark",
  "pattern_id": "p:linear_mark",
  "label": "线性表面异常表现",
  "semantics": "iff",
  "body": {"all": ["q:elongated", "q:scratch_cue"]},
  "scope_join": "same_subject_same_scope",
  "source_assertion_ids": ["s:visual-design"]
}
```

其中 `q:elongated` 明确绑定 `eccentricity >= 0.95`，`q:scratch_cue` 绑定开放候选集中包含 scratch；0.95 是声明的示例启发式。相同 `all`、数值比较与 scope join 可以表达多个过程变量的窗口条件，以及边缘高密度且中心低密度的 wafer 条件。

现有区域 producer 的 aspect_ratio 是轴对齐 bbox 边长比，eccentricity 来自坐标协方差特征值；不能把前者误称为旋转不变的主轴比。本例使用离心率判定细长，aspect_ratio 仅展示、不评分，并保留旋转后不应无故改变结论的检验。

`iff` 表示本次原型对这个表现所作的可执行定义，不是工业规律。当且仅当定义的全部观测条件成立才判定该表现为真；普通 `A → B` 蕴含不能因为 A 不成立就宣称 B 为假。知识编译器必须保留这个区别。

假设规则和现象规则区别如下：

```text
观测派生：A(r) AND B(r) → 现象 P(r)
假设期待：H(x) --[在上下文 C 下，可能/预期表现为]→ P(r)
```

第二条不是 `P → H 为真`。P 只让 H 进入解释集合；H 还要与其它观测、竞争候选一起比较。假设还可以经由中间机制推出多个预期状态，而不只连接一个 pattern 名称。

期待规则区分 `possible / expected / necessary`：possible 允许解释已出现表现，不因未出现而制造反证；expected 的明确不符参与软冲突；necessary 在测量有效且规则适用时不符才构成必要条件违反。LLM 从“可能”抽取的关系默认 possible，不擅自升级为 necessary。

### 4.3 如何让图真正适配 Evidence

构图器同时接收：

1. 来源片段及稳定定位。
2. producer 的能力清单、允许单位及特征定义。
3. 当前对象／变量字典，包含可信的外部 ID。
4. 公共规则语法、算子及小型正反例。

然后按以下步骤制作：

1. **抽取**对象、结构、表现、候选、适用条件和原文断言。抽取与实体归一化分开；KGGen 的实体／关系归一化可作为参考，而它的 text-to-KG 输出仍需本项目的可执行编译层。[KGGen，NeurIPS 2025，§4](https://proceedings.neurips.cc/paper_files/paper/2025/file/2b368455e832d2b1a60bcad8c4c6481f-Paper-Conference.pdf)。
2. **绑定**已有观测能力：定量条件绑定注册特征；“细长”等定性词绑定 ObservableDefinition，而非任意文本字段。
3. **形式化**为公共规则 IR：保留 AND/OR、对象／窗口 join、关系方向和期待种类。
4. **给参数找依据**：明确区分 `source_explicit / normal_reference_estimate / declared_heuristic`。正常参考能提供偏离范围，不能自动提供故障原因或制造机制；LLM 的自报 confidence 不作统计参数。
5. **自动编译检查**：类型、单位、坐标、参考资产、引用、变量绑定、源边和算子均可解析；LLM 不生成任意 Python/Cypher 直接执行。
6. **自动探针**：检查完整前提、单项不符、缺失、跨 ROI／窗口误拼、重复证据、删除相关边、无观测自循环。探针验证规则执行合同，不替代真实样本评价。
7. **有限修复并装载**：结构错误反馈一次修复；有效子图可用，失败规则记录问题而不默默放宽。当前不要求人工审核。

原文未覆盖的机制可以作为 LLM 提出的探索性假设保存，标记 `llm_proposed`，不能伪造 source span。它仍可用于原型候选，但解释须列明新增假设，且不自动成为硬约束。

如果 LLM 要求一个没有的特征，例如“金属裂纹深度”，构图结果应报告 `missing_capability`；不能临时把 description 当深度。新增“中间环带”则先注册环带空间定义与密度实现，再增加绑定和规则，推理算法不变。

### 4.4 三场景如何组织知识

- **MVTec**：对象结构／表面 → 可观测几何与语义候选 → 缺陷表现 → 可能机制。资料可从官方数据说明、对象相关公开缺陷资料及现有领域笔记开始。数据集说明支持任务与标注含义，不能独自支撑制造原因。[MVTec AD 官方说明](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)。
- **TEP**：可信变量表／通道字典 → 装置与过程结构 → 候选扰动及预期变量变化 → 正常参考下的数值条件。使用对应数据发行版的说明与控制配置；Ricker 原始过程有 12 个操纵量，当前 Braatz 数据使用的 52 通道合同是另一明确边界，不能混用。[Ricker TE Archive](https://depts.washington.edu/control/LARRY/TE/download.html)、[当前数据发行仓库](https://github.com/camaramm/tennessee-eastman-profBraatz)。
- **Wafer**：有效 die 与空间区域 → 径向／聚集／线性表现 → 空间图案 → 可能的工艺调查假设。原论文的识别／相似检索任务可支撑图案层评价，逐片根因需要额外过程上下文。[Wu 等，2015，摘要、§VI](https://outlook.stpi.niar.org.tw/pdfview/tdop/1601)。

### 4.5 保存、修改与导入导出的真值

沿用现有工作图存储，但知识包是领域结构、绑定、规则的**唯一可编辑逻辑真值**；Neo4j 规则节点及运行 IR 都是同一包的投影，不允许 JSON 规则与图边各存一套且独立修改。

- 修改条件、别名或关系后，重新编译受影响依赖并刷新绑定／候选／规则索引；下一次 run 使用新知识。
- 删除规则依赖边后，相应推导必须失效；不能保留另一份隐藏 profile 继续评分。
- 导出包含上述全部知识、定义与来源；导入后重新编译，得到同等可执行语义。
- 延续现有每次 run 的输入与图快照，不建设新的审核／发布平台。

## 5. 公共推理内核如何执行

### 5.1 Grounding：数值先落到可检查的条件

1. 校验 Evidence、producer、reference 与 feature 定义的兼容性。
2. 通过明确外部 ID／绑定表解析主体；别名歧义保留为绑定候选或未绑定，不靠名称相似度强行确定变量。
3. 在正确对象、ROI、网格区域或时间窗口内求值 ObservableDefinition。
4. 输出 `matched / violated / unobserved / invalid`，并附实际值、阈值、单位、参考、obs ID 与绑定依据。
5. 通过有限规则做正向闭包，生成带证明依据的中间现象。

`unobserved` 不等于 false；显式 NOT 只能来自有效阴性观测或规则定义的明确反面，不能来自“没找到这个字段”。相互矛盾的模型观测保留双方来源，不用输入顺序覆盖。

规则初始算子集限定为：标量／集合比较、区间、all/any/at_least、同一主体／事件／窗口 join、明确时间先后、白名单语义关系链。时间先后只有在起始时刻或时间区间真的可用且分辨率足够时执行，否则为 unobserved。

### 5.2 反向检索候选，正向检查期待

候选由知识包中的 Hypothesis 节点提供，不在每个 case 运行时让 LLM 自由命名答案。先根据 `target_role`、明确对象／设备类别与分析 scope 找到适用候选，再反向利用期待链的观测 footprint 召回；对每个召回候选建立假设世界，沿图正向展开预期表现。

编译时为每个 h 建立索引：`h → 可达机制 → 期待表现 → 表现定义的终端谓词／观测绑定`。运行时只要求其中至少一个观测槽已被有效测量，**不要求该条件已经满足**：明确阴性也能召回一个需要被排除的候选。若只从真值为 true 的表现检索，会把不利候选提前藏起来。没有任何可评估观测的适用候选记录为 unassessed／missing，不算反证。

物理／期待方向始终是候选到表现；反向搜索是诊断操作，不是把因果箭头反转。普通 part-of 边只有经规则明确引用时才限定关系，不自动传播异常。

同时比较的不是几条独立路径，而是一个候选下的解释子图：共享前提只计算一次，AND 前提必须在正确 scope 中共同成立，不同候选解释同一批目标观测。

scope join 的语义也由同一套算子表达：视觉可以要求 `same_subject_same_scope`；TEP 是多个不同变量属于同一装置／事件且 `same_window`；Wafer 是同一 wafer 上不同环带间的关系。不能为了统一字段，把多个变量强塞进“同一主体”，也不能把两个不同窗口的统计量拼成一个联合条件。

第一版枚举单个候选假设，对每个候选搜索可用规则的有限解释子图；候选较小时不依赖新训练或大规模求解器。多原因组合后续在同一表示上扩展，增加组合代价，而不另写一个数据集 reasoner。

循环知识不能靠自身成立：派生事实从实际观测／明确假设种子作最小不动点展开，证明追踪去掉重复自支持。对规则展开设共同的资源上限；截断须返回 `search_incomplete`，不把部分搜索说成完整最优解。

### 5.3 共同的解释比较目标

对候选 h 及其解释子图 E，先计算当前完整知识 K 下的假设期待闭包 `P_h = Close(K, h, context)`，再采用：

```text
J(h, E) = U(E, O) + λc × C(P_h, O) + λa × A(h, E)
```

- **U：未解释量**。任务范围内需要解释的、有效且已绑定的异常／现象，有多少未被该假设通过可执行图规则覆盖。
- **C：明确冲突量**。该假设的预期／必要表现与已测事实不符的程度；未测项目不计反证。
- **A：额外假设代价**。解释所需的、已声明可假设的潜在机制或探索性知识；不能用“假设测量值是另一个值”消除冲突。

冲突项检查假设下**全部适用的 expected／necessary 期待**，不只检查为了展示而选中的支持路径。搜索器不能删去一条不利期待来提高自己的分数；规则中真实存在的备选机制分支，才允许在声明的约束和假设代价下选择。

期待闭包保留 AND/OR 结构，OR 表现按其逻辑整体检验，不误展开成“所有备选表现都必须出现”。硬约束优先用于类型、身份、作用范围和有明确依据的必要条件；LLM 提出的可能机制及不确定感知结果保留软约束与来源。

先处理硬性不适用和真实必要条件违反，再比较可行解释的 J。同一候选有冗余证明时选更精简的证明；不同候选同分则保留并列，不能因其中一种知识写得更长就制造唯一答案。

每项对证据依赖组分配固定预算。组内重复观测与重复证明先按主体、特征、scope、输入与 procedure 的来源身份去重；同源多个特征采用固定的联合条件／组内聚合，而非简单投票。`dependency_group` 表达相关性预算，不声称不同组统计独立。

第一版把计算集合固定为：

- Q：全部上下文适用候选的期待闭包中、可绑定的终端观测谓词的并集；不包含类型门控，也不把中间表现和它的叶子同时计票。
- O：Q 中实际有效求值的事实，包含 true 和 false；unknown／invalid 单列。
- O⁺：O 中为 true 的、当前任务需要解释的表现条件；不只指数值升高，例如“中心密度低”也可以为 true。
- Covered(h,E)：通过完整的联合表现规则实际解释的 O⁺。AND 缺一项不能把另外一项单独算成完整联合支持；部分匹配仍写入 trace。
- V(h,q)：已测事实 q 与 h 的 expected／necessary 期待是否明确冲突，离散 v0 取 0/1；possible 不制造冲突。

对每个来源依赖组 g，固定 `O_g` 和 `O⁺_g`。v0 计算：

```text
U_g = 未被 Covered 解释的 O⁺_g 数量 / |O⁺_g|
C_g = (sum_{q in O_g} V(h,q)) / |O_g|
U = 对 O⁺ 非空的来源组等权平均 U_g
C = 对 O 非空的来源组等权平均 C_g
```

**分母对所有候选相同**，不是“该候选自己愿意检查几项就除以几项”。同一事实的重复观测和重复证明不增加条目；同一测量槽拆出的多个等价条件需合并或共享其预算，不能靠拆谓词增加票数。未绑定或缺测项不进损失分母，单独报告覆盖与缺失；不能以此宣称它们已被解释。

数值冲突可用超出预期区间的距离并按注册的单位尺度／容差截断到 [0,1]；分类或集合条件使用离散不符。这个归一化是约束损失，不是 posterior。全局 λ 与聚合策略跨场景固定；领域阈值来自知识与参考资产，不能另藏一组按 fault ID 调节排名的权重。

起始实现采用全局 `λc=2、λa=0.25`，离散冲突先取 0/1；各可假设项默认代价 1。这是可检查的起始政策，不是拟合出的最优参数。数值距离算子与不同假设成本作为显式后续配置；在 U5 对共用参数做敏感性对照，不逐场景调到测试答案。

单原因 v0 中每个候选的根假设成本 A=1，沿图推出的中间状态不另算一条假设，因此 A 不会凭空区分两个同样符合的候选。多个额外假设与多原因组合后续显式注册，不能随意添加“其实测量错了”来规避冲突。本次可复算样例使用 AND 签名；OR 的完整备选分支必须由图声明，在完整分支之间最小化同一 J，不允许任意删掉不利条件。

没有观测锚点、没有可用规则或证据不足时不产生“最佳猜测”。原始连续值保留在 trace 中，即使第一版主要使用区间条件，也不退回只读标签。

**为什么不直接用普通软蕴含代替溯因？** 只有 `H → P` 时，令 H 为假就能满足蕴含，观察到 P 并不会自动要求解释 H。因此模型必须另外规定观测解释目标、允许假设集合与覆盖／冲突代价；否则接入 PSL 或任意规则库仍可能什么都没有诊断。

### 5.4 证据不足与候选状态

内部保留 `supported / ambiguous / insufficient_evidence / no_match / not_applicable / search_incomplete`。必要条件缺测时标出需要什么证据，不能因无冲突就称为充分支持。语义正常、几何异常等冲突同时进入 trace。

候选召回不等于进入最终排名：至少要有一个完整联合表现被实际支持，且没有硬性必要条件违反。仅有部分条件匹配的候选保留在评估明细；全部缺测的候选单列 unassessed。没有完整支持但仍存在待测联合条件时为 insufficient_evidence；条件已测且不符则 no_match。代价再低也不能绕过这个准入条件。

外层兼容：有支持或并列候选映射为 `matched` 并附内部状态；缺证据映射为 `insufficient_evidence`。`confidence` 暂为 null；`score=-J`，明确 `lower_cost_is_better` 的原始代价和各分量，不转 softmax 冒充概率。前端若将 score 固定显示成百分比，只调整该处文案／格式。

### 5.5 解释是证明 DAG，不是事后补路径

每个推导节点保存：输入观测／派生事实、规则、实际图边、主体／scope 绑定、比较值和结果。候选保存覆盖、冲突、缺失、未使用观测、额外假设以及与第二名的区分点。

现有 `top_k_paths` 是该 DAG 的浏览投影；`scoring_details` 保留完整 AND/OR 结构和共享前提。不能让一条路径的显示形式掩盖“这个条件还需要另外两项同时成立”。LLM 可将 trace 转成中文说明，但不补事实、不改排名。

### 5.6 已补齐的三类产物与逐步算例

这些文件为设计阶段的完整样例；URI 使用 `design://`，不指向实际模型／图片。知识是显式声明的示意知识，观测是合成值，结果由同一个无数据集分支的受限算例计算过程求得。它们定义 U0 的目标合同，不代表运行后端已支持 v2。

| 产物 | 完整文件 | 内容 |
| --- | --- | --- |
| 公共知识包 | [knowledge-package.json](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/knowledge-package.json) | 注册特征、主体绑定、原子观测定义、联合表现、候选、机制、期待、来源与计算政策 |
| 派生图视图 | [knowledge-graph-view.json](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/knowledge-graph-view.json) | 实际 nodes/edges；由前一文件投影，非独立可编辑真值 |
| MVTec 输入／结果 | [Evidence](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/mvtec-evidence.json)、[Expected Result](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/mvtec-expected-result.json) | 区域、几何、语义、候选评估、分数组件、证明 DAG 与路径 |
| TEP 输入／结果 | [Evidence](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/tep-evidence.json)、[Expected Result](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/tep-expected-result.json) | 固定参考、52 通道数组合同、三个显式窗口统计、同一套候选计算 |
| Wafer 输入／结果 | [Evidence](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/wafer-evidence.json)、[Expected Result](/Users/hhm/code/RootLens/src/doc/design-examples/unified-reasoning-v2/wafer-expected-result.json) | 空间区域、密度、同一套联合规则与分数 |

**MVTec 的图实际是什么？** 省略用于执行的规则节点后，相关语义结构为：

```text
H1 机械接触 → 局部接触作用 → 期待 P1 线性表面异常
H2 表面磨损 → 表面磨蚀作用 → 期待 P1 线性表面异常
H3 异物附着 → 物料附着     → 期待 P2 可见附着物

q1 区域细长 AND q2 存在划痕外观候选 ⇔ P1
q3 显式估计存在可见附着物             ⇔ P2
```

完整图保留 Hypothesis、Mechanism、ObservablePredicate、Phenomenon、DefinitionRule、EffectRule、ExpectationRule 与来源节点；`P1` 的两个前提通过同一个 ALL 规则节点相连。来源节点关联实际使用的规则。规则不是塞在 description 里的自然语言。

**从 raw value 得到什么？**

| 终端谓词 | 实际观测 | 执行条件 | 求值 |
| --- | --- | --- | --- |
| q1 | eccentricity=0.97 | >=0.95 | true |
| q2 | 候选集含 scratch、crack | contains scratch | true |
| q3 | foreign_material_present=false | ==true | false |

因此 P1=true、P2=false。q3 为显式模型阴性估计，不是从候选集中缺少 contamination 推断的。aspect_ratio=7.2 保留但不被本知识引用，结果中明确列为未用于推理。

**候选怎样得到？** `metal_nut` 绑定到对象类并继承 surface_object；task 要求 mechanism，因此选中三种适用 Hypothesis。它们分别可达上述观测槽，三者都被召回，H3 不因 q3=false 而在比较前被藏掉。候选来自知识图，不来自本次 LLM 看图后的原因回答。

**分数逐项怎么算？** 三项事实同属一个图像依赖组。O⁺={q1,q2}，O={q1,q2,q3}；所以所有候选的 U 分母为 2，C 分母为 3，根假设 A=1。

| 候选 | 完整解释的事实 | 未解释量 U | 冲突量 C | A | J=U+2C+0.25A | score=-J | 最终排名 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| H1 机械接触 | q1、q2，经同一 P1 联合证明 | 0/2 | 0/3 | 1 | 0.25 | -0.25 | 并列第 1 |
| H2 表面磨损 | q1、q2，经同一 P1 联合证明 | 0/2 | 0/3 | 1 | 0.25 | -0.25 | 并列第 1 |
| H3 异物附着 | 无完整表现得到支持；期待 q3=true 却测为 false | 2/2 | 1/3 | 1 | 1.916667 | -1.916667 | 评估后无支持，不进榜 |

若只有这份图像观测，H1/H2 就应该并列。0.25 的意义是“无未解释项、无冲突、使用一个根假设”；它不是 25% 或 75% 的真实原因概率。代价只在同一任务、同一评估集合内比较。

**返回什么？** 完整结果除候选外，包含 ground facts、observed patterns、所有召回候选的评估、未使用观测，以及 proof_graph。核心结果字段节选如下：

```json
{
  "case_id": "design-mvtec-001",
  "outcome": "ambiguous",
  "candidate_pool": ["h:contact", "h:wear", "h:adhesion"],
  "ranked_root_causes": [
    {"candidate_id": "h:contact", "rank": 1, "score": -0.25, "confidence": null},
    {"candidate_id": "h:wear", "rank": 1, "score": -0.25, "confidence": null}
  ]
}
```

两条观测路径必须指向同一 joint_proof，证明 q1/q2 同时满足。假设分支和观测分支在“期待 P1 是否与观测 P1 相符”的比较节点汇合；不能把 H1 当作已观测事实。路径的诊断反向视图引用实际图边及 reverse 标记。

**同一计算在另外两种输入上会怎样？**

| 场景 | 固定输入与知识期待 | 结果 |
| --- | --- | --- |
| TEP | 反应器温度 2.4、冷却出口温度 3.2、进料流量 0.2；均为 mean_z，偏离条件 abs>=2。冷却签名要求前两项；进料签名要求温度与流量 | 冷却候选 J=0.25；进料候选只有部分条件匹配，无完整联合支持，U=1、C=1/3、J=1.916667 |
| Wafer | edge=0.47、center=0.03、overall=0.22。Edge-ring 签名为 edge>=0.30 且 center<=0.15；nearfull 为 overall>=0.75 且 edge>=0.30 | Edge-ring J=0.25；nearfull 的整体密度条件失败，U=1、C=1/3、J=1.916667 |

此处 TEP 的 target_role 为 fault，Wafer 为 spatial_pattern；改变的是候选角色、观测绑定和知识内容，不改变候选召回、ALL 检查或 J 的计算。它们是合同算例，不是三数据集的真实效果评价。

本次计算还核对：重排观测和复制同源 eccentricity 不改变分数；将 eccentricity 从 0.97 改为 0.70 后，P1 不再完整成立，两个线性表现候选也不再进榜。未测附着物时 q3 为 unknown，不算阴性；H3 应列为缺少可评估观测，而非声称排除。

## 6. 三个场景最终会怎样推理

### 6.1 MVTec：先解释图像确有的表现，机制可以并列

设计样例中，ROI:1 的 eccentricity=0.97 满足示例细长条件；VLM 候选包含 scratch/crack。通过同一区域的规则，得到“线性表面异常”及其候选语义。aspect_ratio=7.2 本轮仅显示，完整评分见 §5.6。

```text
o:ecc --[数值比较]→ 细长区域
o:semantics --[模型候选绑定]→ 划痕外观候选
两个条件 --[同一区域 ALL]→ 线性表面异常表现
机械接触 / 表面磨损 --[原型期待规则]→ 该表现
```

若工作图对机械接触与表面磨损只声明相同外观，二者应并列。仅凭图像细长程度无法制造区分；输出缺少的工艺／接触信息。第二个 ROI 的语义不能偷来满足第一个 ROI 的联合条件。

目标是 defect_type 时比较缺陷表现；目标是 mechanism 时继续沿明确的假设关系检验机制。二者是同一内核的不同候选角色，不把视觉类别识别包装成真实制造根因识别。

### 6.2 TEP：多变量条件用同一套规则，不再调用特设排名

```text
固定参考下的 XMEAS9、XMEAS21、XMV10 等窗口观测
  → 当前窗口的温度／冷却相关异常状态
候选扰动 → 图上的功能／机制 → 多个变量的预期状态
  → 与同一窗口的支持、正常变量和冲突联合比较
```

哪些变量、何种方向、何种联合条件由知识包声明；求值、解释覆盖、冲突与假设代价仍是公共内核。缺少可靠方向知识时只能使用较弱的“偏离”期待，并相应保留歧义。

沿用 §3.4 的设计数字，可声明两个示意假设：冷却相关扰动预期反应器温度及冷却出口温度偏离；进料**流量**扰动预期进料流量及反应器温度偏离。若共同使用示例条件 `abs(mean_z) >= 2`，2.4／3.2 支持前一表现组合，进料 0.2 则与后一假设的流量期待不符。内核不认识“冷却故障编号”，只执行同窗口条件与图中期待；这些期待与阈值本身仍需在知识包中声明依据。

新内核不继续做 TEP 专有的 `Σ contribution × propagation_gain` 最终排序，也不读取 fault memory 特例。贡献向量保留为观测／注意线索；若没有一个明确规则消费它，就显示未用于最终判断，不能因保留了 52 通道而声称 52 通道全部参与诊断。

TEP 的控制补偿、时滞及条件残差后续由正常动态模型提供额外观测，再进入同一规则与假设比较流程。过程拓扑可以有反馈环；当前没有机制／时滞时不把它强改为静态因果 DAG。

### 6.3 Wafer：空间规则同样进入假设比较

```text
有效 die 网格 → 边缘密度高、中心密度低、连通／环带统计
  → 同一 wafer 上的联合空间条件
  → edge-ring 与 donut、nearfull 等候选图案比较
  → 有额外工艺知识与观测时，再比较工艺机制假设
```

同一组 all、数值区间和 scope join 执行空间条件；若分类器说 nearfull、统计却只支持边缘集中，产生可见冲突，不由任一标签覆盖统计量。没有工艺变量时，机制层只保留图谱允许的调查假设。

## 7. 先用反例约束设计，再做真实性能评价

### 7.1 已做的最小代价算例推演

本次用合成 A/B 观测进行了数值计算，尚未实现规则搜索器。设 H1 期待 A、B 均异常；H2 期待 A 异常、B 正常；U 为已观测阳性目标未解释比例，C 为已测 A/B 与期待冲突比例，λc=2，额外假设代价 λaA=0.25：

| 变更 | H1 代价 | H2 代价 | 应有解释 |
| --- | ---: | ---: | --- |
| A、B 均异常 | 0.25 | 1.75 | H1 更能共同解释 |
| B 缺测 | 0.25 | 0.25 | 无法区分，不把缺测当正常 |
| B 明确正常 | 1.25 | 0.25 | 阴性观测改变选择 |
| 重复同源 A | 0.25 | 1.75 | 不重复加分 |
| 删除 H1 到 B 的期待边 | 0.75 | 1.75 | H1 的覆盖和证明必须变化，排名不一定翻转 |
| 没有有效观测 | — | — | 证据不足，不因零冲突给满分 |

这只验证最小目标的几项设计性质。联合 scope、图规则搜索与真实 backbone 必须在后续实现中分别验证；不能将本表作为实际诊断效果。

### 7.2 通用性验收，比增加案例数量更重要

1. 同一内核、同一候选比较目标和全局参数运行 MVTec 与 TEP。
2. Wafer 接入时只增加 producer／注册特征／绑定／知识，核心不新增 dataset 分支或最终评分插件。
3. 对主体、特征和候选 ID 一致重命名，推理语义保持不变。
4. 重排观测、复制同源事实、增加同一证明的另一条展示路径，不能改变证据权重。
5. 改变联合条件的关键数值、加入反证、删规则依赖边，应改变相应计算和证明；不要求每次都翻转第一名。
6. 规则的每个叶子都能回到有效 observation 或明确知识假设；未入图变量、未使用特征和缺失能力有完整清单。

## 8. 论文验证：把统一方法的价值与其他收益分开

### 8.1 公平对照

- 现有 generic path ranker：确定纯路径方法缺少了什么。
- 当前三个场景 reasoner：作为已有系统参照，不把 TEP memory 的额外信息藏起来。
- 平坦条件／签名匹配：与新方法共享可用观测和知识，比较联合推导、缺失和冲突处理。
- 同样 Evidence 与知识条件下的 LLM 判断：作为后续少量公开样本对照，不在本轮发起调用。
- 新方法内部去掉中间机制、多观测联合、阴性／冲突、依赖去重：分别检验设计项的作用。

特别保留强反例：**若把相同知识完全展开为平坦规则后可以获得同等结果，不能把等价计算包装成准确率贡献。** 此时图的价值主要是知识维护、迁移与推导追溯；要继续寻找真正需要共享机制、部分观测和联合约束的任务。

### 8.2 固定输入条件，区分四种结果

1. **感知结果**：detector 是否定位、VLM 是否识别外观、时序特征是否正确。已知漏检继续保留。
2. **知识制作结果**：从原始资料生成的规则有多少可执行、需要多少缺失特征、可用子图能否覆盖目标观测。与人工整理好的笔记构图分开报告。
3. **推理结果**：同一冻结 Evidence 下的候选、歧义、反证与图修改响应；有对应标签时报告 top-k／MRR 等。
4. **端到端结果**：原始数据到最终候选。原生缺陷／图案标签不作为工艺根因真值，TEP 单条测试序列的几个窗口不当作独立仿真运行。

MVTec／Wafer 可评价原生支持的外观／图案目标，机制路径以明确的知识相容性和假设粒度报告。TEP 的定量 fault 评价单列；训练、阈值形成与评价按原始运行／来源样本分离，禁止重叠窗口跨集合泄漏。

第三场景接入冻结内核是架构迁移检验，不自动等于统计上的跨域泛化；后者还需要适当的留出样本及任务设计。完整 benchmark 不阻塞每阶段 Demo。

## 9. 渐进实施：每阶段都有可展示能力

| 阶段 | 实现范围 | 完成条件／当时可展示的能力 |
| --- | --- | --- |
| **U0 契约与参考知识包** | 固化 Evidence v2、特征／主体／scope 注册、公共规则 IR；用 MVTec 和 TEP 共同走查 | 同一语法表达视觉联合条件和过程多变量条件；明确旧字段转换及信息不足处理 |
| **U1 公共最小内核，MVTec 首个落地** | grounding、有限规则闭包、候选假设展开、覆盖／冲突比较、证明 DAG；使用现有视觉 producer | 原图到公共内核输出；多个特征与多个候选可见，改图影响新分析；旧入口仍可用 |
| **U2 LLM 制作公共可执行知识** | 扩展现有 compiler；能力感知抽取、参数来源、自动编译与有界修复；知识包编辑和交换 | 原始公开资料 → 可装载知识；不仅从人工写好实体／阈值的笔记重排 JSON |
| **U3 TEP 同核验收** | 将现有 ProcessMeasurements 转为公共观测；过程知识编译为相同 IR | 不调用 TEP 特设排序，完整展示多变量支持／正常／冲突；同内核和全局参数运行两场景 |
| **U4 Wafer 冻结内核接入** | 注册空间特征与区域定义；添加空间知识包；检验 scope 与同源依赖 | 不修改候选推理算法便接入第三场景；展示分类与空间观测一致或冲突 |
| **U5 方法评价与深化** | 冻结输入、知识和参数；执行对照、扰动、资料构图与迁移实验 | 明确收益来自何处；若表达力不足，再有依据地增加多原因、时间机制或学习参数 |

U0 就同时使用 TEP 的反例约束设计，不等视觉内核写完再发现装不下过程数据。U1 优先满足 MVTec 展示；U3、U4 检验它是否真正通用。

### 9.1 代码落点与旧调用保留

建议新增公共模块，而非在两个现有 reasoner 内继续堆分支：

- `/Users/hhm/code/RootLens/backend/src/kgtracevis/schema/`：Evidence v2、注册特征、公共知识 IR 与推导 trace。
- `/Users/hhm/code/RootLens/backend/src/kgtracevis/producers/`、`/Users/hhm/code/RootLens/backend/src/kgtracevis/adapters/`：复用感知／统计，输出 v2；adapter 不做根因判断。
- `/Users/hhm/code/RootLens/backend/src/kgtracevis/kg/`：公共知识编译、依赖索引、工作图投影及同源包编辑。
- `/Users/hhm/code/RootLens/backend/src/kgtracevis/core/`：公共 grounding、规则执行与溯因比较内核。
- `/Users/hhm/code/RootLens/backend/src/kgtracevis/source_kg_compiler/`：将现有分场景 runtime profile 生成逐步迁移到公共编译目标。
- `/Users/hhm/code/RootLens/backend/src/kgtracevis/workflows/`：注册一个 `unified_abduction_v1` 调用公共内核；负责协调，不复制算法。
- `/Users/hhm/code/RootLens/backend/src/kgtracevis/service/`：识别新输入合同、保存知识／证据快照、投影现有结果。

上述路径是拟议落点。旧 Evidence 与旧策略保持原有合同；新路线通过显式策略／新合同启用。旧资料缺少 v2 必需测量时，转换器报告缺失，不伪造默认数值，也不改变旧调用的准入条件。

不需要立刻增加 Neo4j 以外的图平台、GNN 训练或专用 Java 规则服务。第一版在现有 Python/Pydantic/图结构上实现受限执行与搜索；确实出现搜索瓶颈后，再根据同一 IR 接约束求解器。

## 10. 预期、风险与下一步

**近期可预期的结果**是三个场景采用同一观测语义与推理流程，能联合使用实际特征、显示竞争候选与反证，并使知识编辑真实改变推导。单靠更换内核不会修复 detector 漏检，也不会从缺少机理资料的外观图像中产生唯一制造原因。

最需要提前暴露的风险：

- **图仍然只是人工画像换个写法**：用原始公开资料构图验收 U2，并报告可执行覆盖，不以节点数验收。
- **规则语法看似统一，算子里藏三个算法**：公共算子只返回观测／局部约束，不允许输出最终候选排名；第三场景冻结内核接入。
- **知识太宽导致什么都能解释**：记录候选覆盖与额外假设，不把 possible 当 necessary；同条件无法区分时保留歧义，评价候选集合大小。
- **软约束权重决定结果**：采用跨场景固定策略并做敏感性对照；不按测试 fault 单独调权，不声称代价是概率。
- **形式正确、含义错误**：自动检查保证可执行，不保证领域断言真实；机制知识的效果与失败必须在真实观测和对照中暴露。

建议接下来执行 U0＋U1：先得到能容纳视觉与过程观测的公共契约和最小内核，再接现有 MVTec 链路。新增构图、图谱编辑与 backbone 能力都围绕这份公共合同收敛。

## 附录：本次调研范围与证据记录

本次为面向方法选择与本仓库实施的定向调研，不是穷尽文献综述。检索日期为 2026-11-10；检索词覆盖 model-based diagnosis、weighted abduction、PSL/HL-MRF、ProbLog、LLM symbolic solver、KG generation、SOSA observation，以及三个数据集的原始说明。主要使用作者页面、会议／期刊原文、W3C 固定版标准与数据发行方说明。

纳入依据是能解释观测语义、可执行知识或候选推理机制；没有将二手综述中的诊断准确率转引为本项目预期。主要阅读定位已附各处链接；经典诊断与加权溯因仅引用已核对的摘要／引言层原则。Reiter 大学镜像获取超时，采用出版社摘要；MVTec 旧 PDF URL 返回 404，数据范围以官方数据页核对。未使用程序化书目数据库验证或进行穷尽新颖性检索。

AI 辅助完成了源码核对、公开文献检索、方法综合和合成代价算例。本轮未调用项目配置的付费 LLM、未下载模型、未执行新的真实数据诊断实验；本文件中的 v2、推理过程示例与 U0–U5 均为后续设计。
