# RootLens 素材、图谱与推理能力重构调研

日期：2026-11-10。本文保留重构前的源码差距与技术路线，不作为当前实现清单。后续 M1–M6 已完成；当前能力见 `backend-integration-current.md` 与 [三场景验收](../../backend/docs/progressive-demo-2026-11-10.md)。

## 当前推进边界

用户已明确主线是渐进完善系统，Demo 按已经完成的能力展示，不为固定案例搭建一次性原型。当前重点是 LLM-based 可推理图谱、图谱管理与 Evidence 适配、实际使用特征的推理过程，以及各数据集上能从图/数据讲清依据的 backbone 适配。前端仅小修，主体放在后端；审核、正式版本化和置信校准后置。

当前顺序与三场景 JSON/图谱/路径示例见 [后端渐进重构与阶段展示方案](rootlens-demo-backend-plan-2026-11-10.md)。基本观测契约、特征绑定、持久图谱管理和真实推理依赖属于近期工作；本文件进一步讨论的审阅治理、概率校准与完整因果验证不作为前置条件。

## 总体技术方向

建议把 RootLens 从“结构化记录适配、路径排序与可视化”逐步完善为**明确使用观测特征、图谱约束和场景模型的诊断工作台**。保留 Vue、FastAPI、Postgres、Neo4j 和可以复用的模型包装，不先换技术栈。

四条主线应共同收敛到以下结果：

1. **素材管理与制作**：解析真实资料，LLM 生成图谱和可消费的领域画像；自动检查后可用，后期可微调，不强制人工审核。
2. **图谱管理与 Evidence 适配**：当前工作图支持持久修改和完整导入导出；绑定观测、适用条件及场景推理器。正式版本化和发布治理后续完善。
3. **推理过程**：用数值、时间、空间和多观测条件比较候选，解释支持、冲突和缺失项；通用路径评分作为可替换的起点，不以更流畅的事后文案代替推理。
4. **backbone 与 make sense**：视觉区域/语义、TEP 数值/窗口、Wafer 空间图案分别接实；先让原始数据、特征、图节点与推理依赖对得上，再持续改善模型效果和开展独立评价。

最重要的判断是：**强类型不是目的。一个数值只有绑定了测量对象、坐标/单位、生成模型、正常参考和推理用途，才成为诊断证据。**把 `Any` 改成更长的 JSON，而推理仍只读名字，并不能解决问题。

## 1 当前问题比页面未接通更深

### 1.1 通用推理的可定位缺口

下文源码简称以 `backend/src/kgtracevis/` 为基准；资产路径以仓库根目录为基准。

| 源码事实 | 对诊断的影响 | 位置 |
| --- | --- | --- |
| observation 的 `facet/name/value_type/unit` 为自由字符串，`value` 为 `Any`，时间窗和 metadata 为任意字典 | schema-valid 不等于语义可计算 | `backend/src/kgtracevis/schema/evidence_schema.py:25–40` |
| 通用链接主要读取 observation 的 `facet/name`；通用路径评分不读取观测数值、方向、时间窗或测量不确定性 | 同名观测的数值发生重大变化，也可能给出相同排名 | `kg/entity_linker.py:166–203`；`kg/path_ranker.py:25–99` |
| `selected_entities_by_field()` 用 field 作字典键，多个 variable 覆盖到最后一个 | 多变量信息被压成单变量，结果可能受输入顺序影响 | `kg/entity_linker.py:107–114` |
| 无实体链接、无适用关系检查时，一致性得分仍为 1.0 | “未检查”被展示成“完全一致” | `kg/consistency_checker.py:29–62` |
| 允许标签过滤失败后返回原候选；歧义标记不等于阻止选择 | 类型约束和不确定性尚未形成运行约束 | `kg/entity_linker.py:117–134` |
| `unknown` 与 `good/normal` 一样导致通用路径排序直接返回空 | 缺陷语义未知被混同为无需诊断，阻断无标签原图链路 | `kg/path_ranker.py:37–38,180–184` |
| profile 的 `required_evidence_fields` 仅声明，没有运行检查消费者 | “字段路径写在配置里”不能证明兼容 | `core/reasoning_profile.py`；`workflows/reasoning_registry.py` |

本次从源码抽取两个纯函数做最小行为探针，确认：两个 variable 链接仅剩最后一个，颠倒顺序则保留另一个；零链接/零适用检查返回 `consistency_score=1.0`。探针没有导入项目运行环境，也没有访问数据库或模型；不是完整 pytest 验收。

### 1.2 TEP 不是纯找路径，但收益来源需要重新厘清

TEP 专用 provider 忽略通用 `linked_entities`，读取完整数值贡献与动态特征，因此不能将上述通用链路缺陷直接推广为 TEP 排序无效。实际排序包含：

- 图上的正值衰减传播，以及传播模式与观测贡献的 cosine；
- 候选类型/角色偏置、discriminator 和多组定制判别规则；
- 按 fault label 聚合的历史贡献/动态特征记忆。记忆加分为 `5 × contribution cosine + 4 × dynamic cosine`。

这更接近**故障签名检索加知识图谱先验与定制规则**，应作为有监督/弱监督方法评估，不能把完整方法的成绩全部归给图传播。代码见 `workflows/tep_root_kgd/anchor_memory.py:223–275,326–363`、`workflows/tep_root_kgd/root_kgd.py:488–515,1644–1697`。

当前 producer 计算 `e = z - zPPᵀ`，以各变量的 `mean(e²)` 归一化作为贡献。这是 SPE 残差贡献，不是 Alcala–Qin 标准 reconstruction-based contribution：后者还除以残差投影矩阵的对应对角项，见原论文 §2.3 Eq.24 与 §3.2 Eq.32。[RBC 原论文](https://skoge.folk.ntnu.no/prost/proceedings/ifac2008/data/papers/3979.pdf)

此外，producer 每次从当前正常 CSV 重拟合 scaler/PCA，而冻结 memory 资产没有携带其原始 scaler/PCA 和训练 split。相同字段、相同维度的两个向量，仍可能不在同一特征坐标系。代码见 `producers/tep_records.py:112–120,145–192,267–299` 和 `workflows/tep_root_kgd/__init__.py:25–33`。

历史 20-case / Top-1 0.80 结果暂可作为已知故障到合并 anchor 的既有报告：3/9、4/11、5/12 合并，fault20 没有对应 anchor。expected anchor 来自同一套图节点的 fault 映射，path hit 也主要检查是否含 expected 节点，不验证传播时延或修复效果。必须保留这些结果，但重新标明任务和独立性；当前资产缺训练 run/seed/split，**尚不能确认或排除其与这20例重叠**。保留的 batch helper 先用 scenarios 建 memory 再对同一 scenarios 排名，不能充当 held-out 证据。见 `workflows/tep_evaluation.py:303–395`、`workflows/tep_root_kgd/root_kgd.py:2038–2058`。

### 1.3 视觉端存在输入语义和测量问题

- **两种合法任务被混用**：批量 producer 把目录缺陷标签写入 record，adapter 再将它作为 anomaly type。带明确来源的 native/operator label 可以用于辅助分析；但同一结果不能算作 raw-image 端到端缺陷语义识别。见 `producers/mvtec_records.py:180–195`、`adapters/ds_mvtec_adapter.py:95,139–168`。
- **分数、判断、概率混用**：现有 calibrated confidence 是阈值后的 1/0；PatchCore raw score 还会被裁剪到 [0,1]。一个 detector confidence 又复用于语义、位置与形态 observation。它们不是同一个概率事件。见 `producers/mvtec_calibration.py:216–222`、`producers/backends.py:335–337`、`adapters/ds_mvtec_adapter.py:187–266`。
- **权重文件存在不代表模型适配完成**：任意 `.ckpt` 可被分给 Anomalib engine，但对应路径硬编码 `Patchcore()`；不能据此宣称 EfficientAD/STFPM checkpoint 已支持。见 `producers/mvtec_models.py:187–199`、`producers/backends.py:284–304`。
- **WM811K 的数值语义需先修正**：die count 计入矩阵背景；当没有 >1 的值时，将 >0 当 failed，会把原生 0背景/1正常/2失效编码中的全正常图算错；`nearfull → dense_particles` 还将空间分布越界解释成物理颗粒。见 `mask/wafer_map_features.py:106–108,129–177`。
- 当前 WM811K 八缺陷类路径将 None/Nonpattern 与无标注混合处理。八类闭集可以是明确任务，但不能据此宣称正常检测或完整九类分类。见 `producers/wm811k_records.py:22,45–46,147–150`、`producers/backends.py` 的 label space。

### 1.4 构图到运行库的断点也在数据模型中

extract 只登记 compiler-ready，构图直接读取 UTF-8 文本，publish 明确不支持。更重要的是：当前 Neo4j importer/repository 只存取基础边字段，未完整保留已有的 `kg_build_id/relation_family/propagation_*/rca_score`。因此单独补按钮，仍会在装载时丢失可用的推理信息。见 `service/kg_materials.py:768–838`、`source_kg_compiler/compiler.py:394–426`、`service/kg_construction.py:712–731`、`kg/import_neo4j.py:241–274` 与 `kg/neo4j_repository.py`。

另一条可以直接延续的链路已经存在：compiler 生成 `domain_profiles.json`，含 TEP 故障、Wafer 图案和 MVTec 对象/缺陷画像；当前运行时没有消费这些画像。近期优先把生成的画像、显式观测绑定和运行策略接起来，而不是再建立一个并行框架。见 `source_kg_compiler/compiler.py:750–799,1135–1212`；现有画像还需补可执行条件，不能仅加载文件就算完成推理。

## 2 推荐架构 将知识生产与事件诊断连接起来

```text
知识生产线
素材导入 → 真实解析/定位 → LLM 生成领域知识并对齐概念
                                      ↓
                         当前工作图 + 观测绑定 + 领域推理画像
                                      ↓
事件诊断线
原始事件 → 领域 producer → 可计算 observations → 绑定/适用性检查
                                      ↓
                    场景推理策略 → 候选比较 → 真实依赖生成解释子图
                                      ↓
                         现有前端展示 / 当前工作图微调

后续完善
正式版本治理、人工审阅、校准、独立模型比较与更强因果验证
```

**统一的是证据含义、知识装载和结果契约，不是把所有场景压成一种打分公式。**领域模型的代码负责算法；画像声明候选及可观测条件，不把算法藏进一大段配置。近期可使用特征/约束匹配，后续再增加更强数值或机制模型。

保留现有组件，职责收敛为：

| 组件 | 目标职责 |
| --- | --- |
| Vue | 保持当前三页；补必要编辑入口、字段文案和推理详情，不执行诊断算法 |
| FastAPI 与 Python 核心库 | 解析、自动检查、图谱装载/编辑、binding、特征计算与场景推理的统一入口 |
| Postgres | 素材、图谱管理记录、运行、Evidence 和反馈；近期不要求新增 release 治理体系 |
| 文件资产目录 | 原文件、数组、解析产物、可交换图谱包和模型资产；当前无需另建对象存储平台 |
| Neo4j | 当前工作图的持久节点/边和查询；编辑、导入及推理通过同一后端服务保持一致 |

先实现一个后端管理的可用工作图：生成或导入后能加载，编辑后能保存并影响下一次推理，导出后能恢复。CSV 保留为兼容交换格式，完整包同时携带绑定与画像。不可变 release、分支合并与正式回滚治理后续增加。

## 3 素材导入管理和知识制作

### 3.1 素材必须先成为可定位的资料

首选复用 Docling 作为 PDF/Office 解析适配器，保留其文档树、表格、页码和坐标；CSV/JSON/JSONL 走确定性解析。Unstructured 是合理备选。具体中文扫描件、表格和本机 CPU 时延仍需在代表性素材上比较，不预设某工具最准确。[Docling 技术报告](https://arxiv.org/html/2501.17887v1)、[Docling 文档模型](https://docling-project.github.io/docling/reference/docling_document/)、[Unstructured PDF 解析实现](https://github.com/Unstructured-IO/unstructured/blob/main/unstructured/partition/pdf.py)

原图与时序不是“拿给文本 parser 看”的特殊文件：它们走各自 producer，以图像区域、通道/窗口等真实坐标生成观测。代码解析只在当前任务确实依赖时实现具体格式，不先许诺通用 AST、任意 Simulink 和全部图像理解。

优先扩展现有 `SourceUnit → KnowledgeCard → CanonicalEntity/Edge`，不另建平行 IR。近期保留三类必要信息：

- **素材身份**：逻辑素材 ID、保存的原文件、格式、获取时间和来源；重新解析不丢原文件。
- **来源片段**：文本或表格块、章节路径及原始定位。PDF 页区、CSV 行列、JSON Pointer 分别表达。
- **生成知识**：实体/关系、别名、适用条件、片段引用及生成方式，进一步生成绑定和领域画像。

引文同时保存 exact quote 和位置/上下文，绑定素材修订；只有位置会随资源变动失效。原文定位与引文支持断言是两项不同检查。[Web Annotation §4.2.4–4.2.5](https://www.w3.org/TR/annotation-model/)

### 3.2 LLM 生成能执行匹配的知识 而不只生成三元组

LLM 根据素材、场景词表和实际可计算特征生成实体、关系、别名、观测绑定及领域画像。自动检查 ID/端点/类型、可识别关系、特征名和比较操作；结构错误自动修复或报告该项不可用，不经过人工审核队列。

条件使用注册特征和算子，LLM 不生成任意 Python。数值阈值优先来自明确的测量定义、正常参考或配置，而不是根据案例答案反推。几何、时序和空间特征由 producer 计算，画像负责表达这些特征如何支持或冲突于候选。

来源区分素材抽取、数据统计、既有规则与 LLM 补充的候选解释。素材引用必须指向真实片段；LLM 补充可标为生成的领域假设，但不能回填虚构引文或伪装成本例实测/已验证工业因果。

近期状态为：**已登记 → 已解析 → 已构图 → 可加载使用**，各步对应真实产物与错误。正式断言审阅、知识修订治理及验证等级后置。

## 4 图谱管理与 Evidence 适配

### 4.1 一个可浏览知识图 不等于一个可诊断模型

逻辑上区分三种用途，但不要求部署三个数据库：

1. **来源与声明图**：谁在哪份资料中说了什么，支持、冲突和派生关系是什么。
2. **领域结构图**：设备、部件、传感器、变量、工序、产品和事件身份，以及类型/单位/工况。
3. **诊断视图**：允许参与指定任务的故障假设、可观测结果、约束或机制及参数引用。

`PART_OF`、`MEASURES`、`ASSOCIATED_WITH` 不能因为在一条有向路径上就全部成为 `CAUSES`。诊断候选通过声明的特征条件/图边参与比较；明确哪些是领域关系，哪些只是“当前观测支持某候选”的解释边。三种用途可在当前数据结构上逐步区分，不以独立声明图建设为前提。

PROV 的 entity/activity/agent 与派生关系可用于组织追溯，不必引入 RDF 存储。当前先用 Pydantic/JSON Schema 和 Python 语义检查。SHACL 验证 RDF 结构，是未来有 RDF 交换需求时的工具，不提供因果真实性保证。[PROV-O](https://www.w3.org/TR/prov-o/)、[SHACL](https://www.w3.org/TR/shacl/)

### 4.2 图谱与 Evidence 通过显式绑定相适配

一个领域包至少包含：

- observation schemas、稳定变量/对象词表、单位及坐标/时间规范；
- producer 与模型包兼容条件、输入特征定义及正常参考；
- 图谱端点/关系约束、候选假设与适用工况；
- **ObservationBinding**：观测目标/类型到图谱 observable、模型 feature 和诊断规则的显式映射；
- 当前场景推理策略与所需资产；后续另补校准和独立评价信息。

加载时建立 binding 索引及可执行条件。程序检查当前策略实际依赖的变量顺序、单位、窗口和特征变换，而不只检查 JSON 有某个键。图谱可增加缺少的形态/变量概念、别名和匹配条件，以支持现有 Evidence；也可逐步增加 producer 特征。不能为了匹配而改写实测值，或以 `(filtered or candidates)` 跨类型兜底。

不匹配时分四种处理：

| 现象 | 正确动作 |
| --- | --- |
| 同一变量的已知别名 | 通过自动对齐或编辑加入 alias/binding，保留原提及 |
| 可证明等值的单位/坐标差异 | 按声明的变换转换，记录派生关系 |
| 新变量、陌生工况、歧义同名 | 明确未绑定/有歧义；补图或补绑定，不强行找最近名字 |
| 观测与知识规则冲突 | 同时保留观测和冲突；检查检测、绑定、工况或知识本身，不能直接“纠正”实测以提高一致性 |

每次分析记录绑定、歧义、未绑定、适用条件和未检验项。“无适用检查”应输出 unknown/not assessed，而非 1.0。额外 metadata 可保留，但只有已定义且被策略消费的字段进入推理。

### 4.3 先完成持久编辑和完整导入导出

- 节点、边、别名、观测绑定和画像通过后端持久增删改；改名保留实体 ID。localStorage 仅保留尚未提交的表单。
- 使用 `graph_id` 选择当前工作图，保留构图来源和分析记录，不要求先实现正式 release。
- 装载、编辑和导出保持有效推理元数据；改图后更新或失效派生索引。新分析不得沿用已删除关系或旧绑定。
- 完整工作图包包含节点、边、别名、来源、绑定和画像及包格式说明；CSV 保留兼容导出，不能以 metadata/path 导出代替真实内容。大型原文件/模型不强制打包。
- 导入检查引用、ID 和条件合法性，支持新建工作图及明确的覆盖动作；同名不自动合并。覆盖前保存必要备份，不重建既有数据库，不修改历史分析结果。

后续有正式知识治理需求时，再增加不可变 release、并发修订冲突、差异合并、切换与回滚；届时处理 Postgres/Neo4j 跨存储发布恢复。近期保存操作仍需正确处理失败与数据库事务重试。[Neo4j 事务文档](https://neo4j.com/docs/python-manual/current/transactions/)

## 5 Evidence 从自由描述变成观测契约

### 5.1 有限的观测种类 共享严格语义

首批只为三场景实际需要的种类建模，以 discriminated union 表达，不为每份数据集再发明一个任意 JSON：

| observation kind | 必须表达的内容 |
| --- | --- |
| ScalarMeasurement | 变量 ID、数值、单位、采集时间、测量来源/质量 |
| TimeSeriesWindow | 通道 ID/顺序、数组引用与 shape/dtype、采样周期、起止时间、缺失掩码、工况 |
| ProcessWindowFeatures | 每特征的定义与值、feature schema、normal-reference/model ID、输入窗口和派生关系 |
| VisualAnomalyRegion | 原图与 map/mask 引用、坐标变换、阈值、区域 ID、几何测量；detector 原分数及方向 |
| SemanticPrediction | taxonomy/label space、候选或多标签分数、支持区域、独立模型与校准信息 |
| WaferPatternPrediction | 晶圆编码、有效 die 掩码、pattern label space、类别结果/不确定性 |
| LogEvent / HumanAssertion | 时间、对象、事件码/结构字段；人工主张的作者、依据与审阅状态 |

大数组以资产引用承载，不把52通道时序压成 description。数组引用也有类型、形状与变量顺序，不只是路径字符串。

公共 envelope 负责 case/事件、对象、时间/工况、producer、模型与资产版本。原始未知 metadata 可存档，但不得自动进入 binding、评分和解释。新增 kind 必须注册 schema、变换与消费它的模型，并有合同测试。

`feature_schema` 固定列/通道集合、顺序、dtype、维度、单位和计算定义，不是再包一层任意键值。例如沿用现有 TEP 四个统计量时，应明确其为 z-mean、首尾差/样本数、相邻差绝对值均值和 z-std，而不能将第二项泛称为任意“斜率”。同一模型包固定正常 scaler、PCA、输入特征与可用工况；模型不匹配不能靠字段同名放行。

缺测、未检验、观测为正常/阴性必须分别表达；`unknown` 不等于 normal，空列表也不自动证明没有异常。

JSON Schema 默认并不会因声明 properties 就禁止额外字段或强制其存在；新合同应显式声明 required 和闭合属性策略，另做单位、时间和模型兼容等语义验证。[JSON Schema object](https://json-schema.org/understanding-json-schema/reference/object)

### 5.2 分数含义先说清 校准后置

至少区分 raw anomaly score、binary decision、正常分布尾部 p-value、分类 posterior、测量质量、抽取可靠性、知识来源审阅状态。0–1 的数字不自动成为概率。

近期保留兼容字段，但标明它是原分数、判断还是匹配分，不做统一概率承诺。后续需要校准时，normal-only 检测可用独立正常 calibration 集确定分位阈值和误报预算；这不等于估计 `P(工艺根因 | 图像)`。分类概率可另用冻结 calibration split 比较 Brier/NLL 与温度缩放等方法。[Guo 等，2017](https://proceedings.mlr.press/v70/guo17a.html)

普通 conformal 覆盖依赖 exchangeability；不能对相邻重叠时序窗口直接承诺分布无关覆盖。时序/漂移场景应采用合适方法，并报告实际组别/时间覆盖和拒答表现。[Angelopoulos 与 Bates，§4.6、§5.3](https://arxiv.org/html/2107.07511v6)

### 5.3 真实例子 TEP 特征不是一个可自解释的数字

`XMEAS22 z-mean` 至少依赖原始通道身份、窗口、标准化基准和计算实现。换了一份正常数据重拟合 scaler 后，即使字段名不变，也不能直接与旧 memory 的 centroid 比较。

当前 fault15 `separator_coolant_valve_stiction` 和 fault18 `condenser_heat_transfer` 都涉及冷凝/分离冷却区域。冻结历史 memory 的 XMEAS22 z-mean/std 分别约为 −0.038/1.027 与 −3.544/5.833，每个是50个历史 scenario 的均值，**不是当前事件测量**。现有代码用 memory 相似度及 XMEAS22/XMEAS11 特例区分它们。路径相似并不意味着数值上不可区分，但该规则需要独立验证。见 `data/kg/tep_root_kgd/anchor_memory_profiles.json` 与 `workflows/tep_root_kgd/root_kgd.py:756–834,1090–1145`。

近期先保证原始窗口、特征定义和正常参考配套，再接入图谱画像的多变量/方向条件。后续可增加异常起始时间、正常动态模型下的条件残差和后续窗口预测。当前 producer 没有完整产生这些证据；XMV11 一个操纵变量不能冒充“阀命令”和“实际阀位”两路独立反馈。

## 6 推理从找路径转为检验竞争假设

### 6.1 图结构必须进入模型 而不是事后装饰分数

保留现有通用路径算法作为检索/可视化和旧调用兼容路径，新链路逐步改用领域画像与场景策略。图谱在推理中承担可检查职责：限定变量身份与候选、定义可用结构/约束、声明候选符合哪些观测、保存来源与适用范围。

近期先实现条件执行：从原始数值/几何得到事实，联合匹配支持与冲突，区分缺失和不满足，并记录每个候选使用的 observation/feature/edge。MVTec/Wafer 可从对象、语义、形态和空间条件起步；TEP 延续数值 reasoner，逐步接入工作图和故障画像。相同特征支持多个候选时可保留并列，不为凑出唯一根因而生成新观测。

当有足够数据可拟合时，可用以下概率诊断形式组织候选比较：

\[
P(H\mid Z,C,G,\theta)\propto P_\theta(Z\mid H,C,G)P(H\mid C,G)
\]

这里 `H` 是明确候选，`Z` 是强类型观测特征，`C` 是工况，`G` 是该任务允许使用的结构/约束，`θ` 来自独立训练和校准资产。它是建模方向，不是把旧路径分数套 softmax。没有可估计的 likelihood、类别数据或机制模型时，只提供约束匹配/调查假设，不伪造 posterior。

同一 heatmap 派生的 score、面积、morphology，或同一时序派生的 SPE 与动态特征，是相关证据。应以联合特征模型或明确依赖组处理，不能简单相乘当作多个独立支持。

模型化诊断的要点是比较观测与系统/故障假设的预测；仅沿图连到一个原因名字并不完成诊断。[Reiter，1987，§1–2](https://www.cs.ru.nl/~peterl/teaching/KeR/reiter.pdf)

### 6.2 不能直接把现有 KG 喂给通用因果库

DoWhy-GCM 等方法提供真实的机制拟合、异常归因和机制变化分析，可作为合适任务的实现与基线。它们要求因果结构与机制模型，而不是只有语义边。异常归因方法的基本设定包括因果 DAG、功能机制及可恢复噪声；图结构、函数形式与数据假设都会影响结果。[Budhathoki 等，2022，§1、§3](https://proceedings.mlr.press/v162/budhathoki22a.html)、[DoWhy-GCM](https://www.jmlr.org/papers/v25/22-1258.html)

TEP 有闭环控制，不能把操纵量一律当外生原因、把过程拓扑直接当静态因果 DAG，或删掉环后声称适配成功。首选研究带时滞的正常动态模型，在时间展开后表达反馈；结构和因果含义仍需工艺/仿真依据。DoWhy 的图检验能反驳不匹配假设，也不能仅靠通过检验确认方向正确。[GCM 评估文档](https://www.pywhy.org/dowhy/main/user_guide/modeling_gcm/model_evaluation.html)

### 6.3 解释来自真实执行轨迹

近期内部形成明确 trace，再投影到现有结果 envelope、`scoring_details`、paths 和 source edges，前端无需大改。trace 表达：

- 当前诊断任务与目标粒度：视觉类型、已知 fault、合并 anchor、异常机制或设备；
- 候选及分数的含义，使用的模型、工作图和画像；
- 支持、反驳、未使用和缺失的 observation IDs；
- 具体比较了什么特征、约束、条件分布或故障签名，如何影响候选；
- 结论状态：supported、ambiguous、insufficient evidence、outside scope；
- 如需区分前两名，下一项有实际区分力的测量/核查是什么。

解释图应从这些真实计算依赖生成，而不是排名以后再找一条好看的路径。LLM 可帮助解读来源和将 trace 转为文字，不能读取 evaluator targets、补造未观测数值或自主决定最终可信度。

## 7 backbone 适配的具体路线

### 7.1 MVTec 先接实定位、区域特征与语义

**近期**：延续已接通的 detector，修复模型类/预处理适配；从实际 mask/ROI 提取面积、细长程度、连通域及位置，另接 ROI 语义候选，记录标签来自模型还是显式输入。把这些可回原图的特征绑定到图谱画像。

**后续检测/定位升级**：保留官方 PatchCore 为 incumbent，首选 AnomalyDINO-S 为新的强简单对手。两者都可解释为正常 patch 表征与近邻比较，便于检查表征、正常参考和局部距离。AnomalyDINO 使用冻结 DINOv2 特征，不因其作者成绩就认定优于本项目现有模型。[PatchCore](https://arxiv.org/html/2106.08265v2)、[AnomalyDINO，§3–4](https://arxiv.org/html/2405.14529v3)

EfficientAD 留作低延迟或全局逻辑异常需求明确后的替代项；先修正确模型类和导出格式的适配，不将 `.ckpt` 文件存在视为运行验收。作者 GPU 延迟不是本机承诺。[EfficientAD](https://arxiv.org/html/2303.14535v2)

**缺陷语义层**：独立比较 object-conditioned class prior、geometry-only、小型线性/kNN ROI 分类器，再比较 VLM。DS-MVTec 的细粒度重标注可支持语义任务；但它与原 MVTec 共享图像，划分必须按原图身份，不可当独立外测。[Defect Spectrum，§3.2](https://arxiv.org/html/2310.17316v5)

两条运行轨必须分别报告：

1. raw-image：图像/对象/正常参考是输入，GT defect type、GT caption、GT mask、含答案的路径名仅 evaluator 可见；模型生成的语义另记为预测，不能当 GT；
2. assisted：允许带来源的 native/operator 语义，测的是在已知语义条件下的调查支持。

几何面积首先叫 image coverage；没有物理尺度与损害参考，不直接解释为业务严重度。坐标变换应能回到原图区域，图像边缘也不自动等于产品部件边缘。

**工艺根因层**：MVTec/DS 的视觉类型和 mask 不提供逐例生产原因监督。LOCO 可增加数量/组成等逻辑约束，AD2 可增加微小缺陷、高分辨率和照明偏移压力，但也不能凭数据集名称补齐因果标签。[MVTec AD](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)、[LOCO](https://link.springer.com/article/10.1007/s11263-022-01578-9)、[AD2，§III–V](https://arxiv.org/html/2503.21622v1)

要继续验证真实工艺 RCA，至少需要同一 unit/lot 的图像、工序、tool/recipe、时间、实际参数/报警/维护关联，以及独立调查记录或受控故障/维修恢复证据。还需“同缺陷不同原因”和“同原因不同表现”、正常及未知原因样本。不能用专家写的 plausible 候选表，同时制作和验证一个原因预测器。

### 7.2 WM811K 是晶圆空间图案任务

先修编码、有效 die 掩码和 None/无标注/unknown 的区别，选择明确的八缺陷类闭集或含 Nonpattern 的任务；再比较空间描述特征＋SVM、小型 CNN 和现有 ResNet34。正常自然图像 backbone 不应未经对照就成为默认。

pattern prediction、失效密度、空间区域是合法观测；`nearfull` 不是“颗粒污染”的直接测量。原数据适合空间图案识别与相似检索，逐片工艺根因需额外过程数据。[WM811K 原论文，Fig.2、§VI](https://outlook.stpi.niar.org.tw/pdfview/tdop/1601)

### 7.3 TEP 把已知识别与机制定位分开

**近期**保留 Root-KGD 数值链路，修正诊断窗口和配套正常参考，保留完整通道向量；让当前工作图的变量身份、故障画像和支持条件逐步进入候选比较。路径按真正使用的变量和边生成，而不是候选选好后再随意补图。

**后续已知故障识别比较**保留现有 Root-KGD 为历史基线，对照：

1. memory-only nearest centroid：相同贡献/动态特征、相同训练 runs，去掉图、偏置和定制调整；
2. 相同特征的 logistic regression 或树模型；
3. 现有完整方法；若确有净收益，再分析结构传播、discriminator 与定制规则各自贡献。

**机制定位**优先研究可解释的正常过程动态模型，例如稀疏 VAR、局部条件回归或状态空间模型：

\[
x_t=f(x_{t-1:t-L},u_{t-1:t-L},\text{mode};\theta)+\epsilon_t
\]

工艺拓扑/控制回路限定候选依赖，数据拟合参数和时滞；异常时比较条件残差、局部机制变化及后续响应预测。操纵量可能是控制器响应，不自动视作外生输入。没有可观测的对应部件/机制时，输出异常机制位置或待区分假设，不强制落到某个设备根因。

CIRCA 的 intervention recognition 思想、EasyRCA 的机制变化推断、PCMCI+ 的滞后结构候选值得比较，但应先核查各自的图结构、独立性、因果充分性和反馈假设。EasyRCA 的 loops 不代表支持任意变量间有向反馈环；CIRCA 的服务系统图构造也不能直接搬成工艺图。[CIRCA](https://arxiv.org/html/2206.05871v1)、[EasyRCA，§2、Definition 1](https://proceedings.mlr.press/v206/assaad23a/assaad23a.pdf)、[PCMCI+](https://proceedings.mlr.press/v124/runge20a.html)

TEP 的评价 reference 应来自固定模拟器的故障注入定义及经审查映射，不随待评 KG 节点变化；fault label、anchor 和物理部件粒度分别评分。原始 TEP 是过程控制仿真问题，不直接给出所有变量的因果真值。[Downs 与 Vogel，1993](https://www.sciencedirect.com/science/article/pii/009813549380018I)

## 8 后续如何评价收益与可信度

本节服务于后续模型选择、效果主张和系统完善，不作为近期人工审核或完整 benchmark 门槛。当前功能检查以能解析/保存/往返、特征能定位、输入和改图能影响真实推理、解释与执行一致为主。

### 8.1 先冻结信息条件 再比较模型

所有模型、normal scaler/PCA、memory、阈值、discriminator 和定制规则都必须有训练/验证来源。按独立 run/seed、原图、wafer lot 或时间组拆分；不能把同一对象的重标注或同 run 的重叠窗口拆到训练和测试。

TEP 要按已知注入时刻定义诊断窗口和统一可用延迟。当前 producer 收每 run 最前100行，并不等于故障后100样本。Harvard 数据的 training/testing 注入时刻不同，不能用相同截行数代替时间对齐。[数据原始说明](https://doi.org/10.7910/DVN/6C3JR1)、[Root-KGD §4](https://arxiv.org/html/2406.13664v1)

报告不只给一个汇总准确率：分别记录候选覆盖、检索召回、条件排序、全任务结果、正常事件错误归因、拒答、分组结果和运行代价。候选缺失算真实失败/开放集问题，不从分母静默移除。

### 8.2 每条复杂链路都要有能否定它的简单对照

| 主张 | 必须比较的对照 | 什么结果会改变选择 |
| --- | --- | --- |
| 新图谱比原图更适配 Evidence | 固定输入与模型，对比旧 release、新 release；另测独立 binding/约束问题 | 只增节点/路径而不改善正确绑定、约束或诊断，不称为适配收益 |
| KG 对排名有用 | 同一 backbone/特征/训练信息，无图模型、真实图、适当打乱或移除诊断边 | 无图同样好则去掉排名复杂度；图谱仍可保留检索/溯源价值 |
| Root-KGD 比签名识别强 | memory-only、简单监督模型、完整方法 | 净收益消失则不以图传播为方法贡献 |
| 新视觉 backbone 更好 | PatchCore 与 AnomalyDINO，同正常数据和分辨率/预算 | 只提升易样本 AUROC、未改善固定误报下定位/关键场景，不作为默认升级 |
| VLM 真的看图理解缺陷 | class prior、geometry、ROI 线性/kNN；去图/打乱图/扰动区域控制 | 不看图仍类似，或正常图虚构更多类型，则不进入默认推断 |
| 路径解释可信 | 独立来源支持与矛盾审查；输入依赖变更与计算 trace 对照 | 引文在但不支持结论，或解释不随真实模型依赖变化，则失败 |

近期微服务 RCA 的原始研究也暴露了简单基线、候选先验和评估协议改变结论的问题；这是设计对照的参考，不能把其具体数字直接推广到 TEP。[Fang 等，2025/2026](https://arxiv.org/abs/2510.04711)、[RCAEval 控制研究，2026 预印本](https://arxiv.org/html/2609.27069v1)

### 8.3 各层评价不能互相替代

- parser：原文/页区/表格提取与定位正确性；抽取：独立标注的实体、关系、条件与引用支持。
- 图谱：类型/端点/来源完整性、冲突、版本往返，以及 held-out competency questions。结构检查不验证工业因果真值。
- detector：image AUROC/AP、定位 AP/官方 PRO 或 sPRO、固定阈值误报/漏报、分场景表现、实际延迟/内存。
- semantics：macro-F1/多标签 AP、正常图虚构率、预测区域链路与 GT ROI upper bound 分开、risk–coverage。
- TEP：detection、原 fault、合并 anchor、机制/实体定位分别报告；同延迟比较，按独立 run 估计不确定性。
- 可信度：Brier/NLL、分组校准、拒答后的风险；p-value 不冒充 posterior，稀少/域外样本不自动继承校准承诺。
- 系统：release 固定、引用回跳、发布中断恢复、并发编辑、导入导出往返、重启后旧 run 保留原结果。

## 9 原完整重构路线 作为中长期备选

| 阶段与负责模块 | 交付结果 | 完成条件 |
| --- | --- | --- |
| 1 契约与评估核心 | v2 observations/targets 分离；模型/feature/normal-reference 合同；独立数据划分 | 原始标签不能进入 raw-only 推理；错误单位/模型坐标不匹配被明确拒绝；多变量顺序不改变语义 |
| 2 素材与知识核心 | 真实 parser、素材修订/源片段、候选断言、后端 change set | 能从断言回原文；支持冲突与审阅，extract 状态对应真实产物 |
| 3 发布与图仓储 | release-aware importer/repository、绑定编译、bundle 往返、run pin | 不丢推理元数据，不露半成品，新旧 release 可并存/回滚 |
| 4 TEP 诊断纵切 | 独立重建 normal profile/memory，先打通 memory-only 与完整方法的公平比较；再研究动态机制模型 | 划分/窗口/reference 可追溯，收益来源可分辨，未知故障可拒识 |
| 5 视觉诊断纵切 | 修 score/encoding/model-loader 语义；PatchCore 对强简单对手；独立语义层 | 无 GT 的原图链路可测，正常与未知可处理，工艺假设不冒充观测 |
| 6 可视分析整合 | 用新 trace 驱动证据、图谱和候选联动，显示冲突/缺证/版本和调查动作 | 用户能说明候选为何高于竞争者、依据来自哪里、还需查什么 |

此表保留完整治理与研究路线，**不按原序列作为近期实施清单**。当前按配套方案的 A 构图能用、B 图谱能管、C 推理做实、D 场景深化推进。内部契约先稳定，旧前端字段由 presenter 兼容，不能因外层字段保持就继续保留只看名字的推理语义。

建议的保留和替换：

- **保留并扩展**：素材存储骨架、source compiler IR、正式 feedback ledger、运行持久化、官方模型 wrapper、三页联动基础。
- **替换核心语义**：Evidence 自由字段、静默兼容、通用路径为主的排名、单一 confidence、对 CSV 的原地审阅真值、无版本运行 KG。
- **保留兼容并分离策略**：旧 generic reasoner 维持旧调用，Root-KGD 数值链路继续复用；新画像匹配和后续模型有独立策略入口，不靠无限追加特例混成一个算法。
- **当前不选**：全自动 agent 因果建图、直接 GraphRAG 代替数值诊断、无强基线先上 GNN、再搭一套分布式平台/图数据库。GraphRAG 的文档实体与关系抽取可复用在知识供给层，不能替代上述观测和机制模型。[GraphRAG 官方 indexing 定位](https://microsoft.github.io/graphrag/index/overview/)

### 9.1 兼容与数据安全

v2 新能力使用新合同；旧 v1 调用在其原合同下仍可用，通过显式 legacy adapter 标明其评分含义，不把新增严格条件直接施加给旧调用。历史结果可回放；缺少原模型/知识版本的旧记录标为 legacy-unversioned，不补造 provenance 以声称可精确重算。

实际实施迁移前保留既有数据库、配置和历史 run 的可恢复副本，在独立工作修订/测试库验证。本文不执行初始化、重建图谱、覆盖资产或清理来源备份。

## 10 长期研究中最有辨别力的工作

**先证明图谱是否为诊断增加了信息，而不是先增加图和模型的规模。**

第一组应优先完成的对照，是在同一套冻结 TEP 训练/测试 runs 上比较 memory-only、同特征简单分类器、现有完整方法；同时建立一个没有 GT 语义输入的视觉测试轨。它们会直接区分：现有结果主要来自强输入/历史签名，还是知识结构真的贡献了诊断。

随后检验一个值得持续研究的问题：**在观测不完整、工况变化或候选相近时，经验证的知识约束能否比相同 backbone 的无图基线更准确地定位异常机制，并减少错误的高确信结论？**若排名收益不成立，保留图谱在来源审查、知识管理和调查引导上的价值，不把这些价值改写成 RCA 准确率提升。

## 调研范围与尚未完成的验证

本次采用 AI 辅助源码审阅、原论文/官方文档定向检索和跨线综合；检索日期为 2026-11-10。查询围绕四组问题：source-to-KG/文档解析与 provenance；model-based diagnosis/GCM/机制变化；MVTec/PatchCore/AnomalyDINO/语义与分布偏移；TEP/RBC/数据划分/闭环 RCA。来源优先为作者原文、官方数据说明与维护者文档；本文不是穷尽文献的系统综述。

本轮未重跑模型、GPU 训练、完整 pytest 或端到端业务验收，也未连接运行数据库。当前 checkout 未提供前端 node_modules、backend/.venv 和忽略的本机运行资产。两项纯函数探针用于确认局部行为，不代表系统测试通过。

关键未决事实是现有 TEP memory/阈值资产的原始训练 split、视觉 calibration 与 test 的独立性，以及项目真实文档上的解析质量。新模型收益、因果定位能力和推荐工具的本机性能均需要按本文对照验证；本文提供的是可执行研究方向与验收路径，而非已取得的新实验成绩。
