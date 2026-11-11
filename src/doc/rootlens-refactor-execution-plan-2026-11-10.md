# RootLens 渐进重构执行计划

日期：2026-11-10。状态：**M1–M6 / T01–T22 已完成并验收**。当时的 JSON、路径和已知失败见 `809fb8d:backend/docs/progressive-demo-2026-11-10.md`；当前操作见[分级演示手册](../../backend/docs/graded-rca-demo.md)。

本文件维护实施顺序、任务和完成证据；[技术方案与三个场景的 JSON/图谱/路径示例](rootlens-demo-backend-plan-2026-11-10.md)维护目标设计，[源码差距与调研](rootlens-rearchitecture-research-2026-11-10.md)保留判断依据。当前已实现能力仍以 [backend-integration-current.md](backend-integration-current.md) 为准。

## 1 先交付一条可复用闭环 再逐步扩展

目标是完善系统，Demo 按已完成的能力取材。近期围绕素材与 LLM 构图、图谱管理与 Evidence 适配、多证据推理、三场景 backbone 四项工作推进。前端保持 `/materials`、`/graphs`、`/evidence` 的现有布局和职责；主体改动在 Python 后端。

**首个场景改为 MVTec，优先满足当前展示需求。**首轮贯通文本素材、实际异常区域、图谱条件匹配与候选解释。先用带 mask/几何的 records 稳定特征接口，再接 LLM 构图装载和原始图片入口；最终交付同时覆盖 records 与 image，不停留在已知标签查路径。

首轮闭环：

```text
TXT/Markdown 素材
→ 现有 source compiler + LLM 生成图谱、观测绑定和诊断条件
→ 自动检查并装载当前工作图
→ 原始图片经 detector 定位，计算区域几何并获得有来源的语义候选
→ 多条件匹配与候选比较
→ 从实际依赖生成路径
→ 现有三页查看特征、候选和依据
```

不以某个固定 case ID 或预写路径选择候选。已提供缺陷标签时可以走辅助分析，标签记录为输入；原图链路中的语义必须来自模型。初期几何测试可用明确标注的合成 mask，实际图片与模型运行情况单独验收。

### M1 的三个交付点与预期

| 交付点 | 具体工作 | 可观察结果 |
| --- | --- | --- |
| M1a 区域特征确实进入推理 | records/mask → 分区域观测 → 当前图上的条件执行；覆盖缺失、冲突、无匹配 | 改变区域形状或大小会改变命中条件；每个候选能列出实际区域和条件 |
| M1b LLM 知识确实进入推理 | TXT/Markdown 素材 → 图、绑定和诊断条件 → 工作图装载 → 对同批输入分析 | 换图或改相关关系后新结果相应变化；源边 ID 可追到构图产物 |
| M1c 原图到页面闭环 | 原图 → 实际 detector → ROI 几何与语义 → 工作图推理 → 现有页面 | 原图、mask/heatmap、区域描述、候选与路径能对应；完成首个完整 MVTec 闭环 |

首轮路径示例为“细长区域特征 → 划痕候选 → 机械接触/表面磨损候选”。当当前图只支持划痕而区域变成斑点时，应输出不匹配或其他有依据的候选；不为维持结果而保留划痕路径。示例仅描述目标行为，不代表模型已取得该结果。

### 已确定的工程选择

- 继续使用 Vue、FastAPI、Postgres、Neo4j 和 `kgtracevis`；复用 source compiler、模型包装、reasoning registry 与运行存储，不另建平行平台。
- 同一领域工作图服务多个案例；图谱生成与案例分析分开。LLM 负责知识生成与可选的解释整理，算子/场景策略执行特征计算和条件比较。
- 新增内部明确模型及显式适配，外层保持 `RunDetail`、`RunCaseDetail`、`KGStudioPayload`；旧 Evidence、records、image 入口及旧 profile 保持可用。
- 新链路先在每个 run 开始时读取当前工作图和画像，不引入跨 run 常驻缓存；同一 run 使用同一份已装载内容，避免中途改图混入结果。
- 生成后自动检查即可使用；人工审核、正式版本发布/回滚体系、置信校准、完整 benchmark 和因果识别验证后置。

## 2 最小共享契约 在首轮确定并随代码维护

这些是内部契约，不要求用户手写 JSON，也不要求先重写所有旧字段。

| 对象 | 首批内容 | 主要消费者 |
| --- | --- | --- |
| 场景输入 | `WaferCaseInput`、`VisualCaseInput`、`ProcessCaseInput`；原始资产、场景身份、明确特征与定位 | producer/adapter、binding |
| 观测绑定 | 特征/变量名、对象/场景约束、图概念 ID、声明的必要变换 | binding 执行器 |
| 领域画像 | anchor/candidate IDs、支持/冲突/必需条件、真实源边引用 | 场景推理策略 |
| 工作图包 | 格式标识、`graph_id`、场景、节点、边、别名、来源、绑定、画像 | 装载、编辑、导入导出 |
| 推理轨迹 | 观测/特征/条件/源边依赖、候选比较、未匹配/缺失原因、实际算法 | presenter、路径与详情 |

### 执行约定

1. 条件只使用注册特征和有限算子，首批为相等、集合匹配、数值比较/区间及 all/any 组合；不执行 LLM 生成的 Python。
2. 缺失、不满足、满足分别记录；缺失不是反向证据，未检查不是一致性 1.0。数值阈值来自明确配置、正常参考或素材中的定义，不按案例答案反推。
3. 首版采用确定性条件评分：适用条件筛选、支持组计分、冲突处理，参数显式声明。同一 mask/窗口派生的相关特征按来源分组，不作为独立概率相乘。
4. 候选来自当前图与画像；路径只使用本次实际命中的关系及明确的解释视图边。数值、几何与本次状态留在 case/临时 overlay，不永久灌入总图。
5. 新推理结果区分匹配、无匹配、证据不足和不适用；有效空结果直接返回，不适用给出明确原因，不因候选为空就自动调用 generic reasoner。旧 reasoner 的原有兜底契约保留。
6. 对外实体/边/路径 ID 保持逻辑身份。compiler 边 ID 与运行边 ID 建立明确映射，不直接假定二者相同；不全局改写旧 `KGEdge.edge_id` 和历史结果 ID。

### 存储与工作图选择

- Neo4j 继续保存运行节点/边；Postgres 扩展工作图登记、绑定和画像存储；文件保存原始资产和交换包。
- 新请求可显式选择 `graph_id`；省略时沿用现有 legacy 图和 profile 的原行为。后续新界面主动传入选择值，不静默改变旧入口默认算法。
- 新工作图在仓储层隔离存储身份，API 与推理仍使用逻辑实体 ID。保留 Neo4j 现有全局 `id` 约束及旧节点：新工作图使用命名空间存储 ID，并保存逻辑 ID；legacy 查询不混入新命名空间。
- 同图引用的 shared 概念随工作图明确装载；不跨工作图凭同名隐式拼接。两个工作图可有相同逻辑节点 ID，读取、编辑和候选检索互不串图。
- `schema_version` 仅标记交换格式；`graph_id` 仅标记工作图身份，不借此引入正式版本治理。

## 3 六个增量及其展示边界

| 增量 | 交付能力 | 完成后可展示 | 前置 |
| --- | --- | --- | --- |
| M1 MVTec 可执行知识闭环 | 文本 LLM 构图、最小工作图装载、区域几何/语义、画像执行、真实路径 | 不同图片/区域的特征与图上条件、候选和路径可对应 | T01 开始 |
| M2 素材管线可用 | 真实解析/获取、片段与状态、重新解析/构图 | 上传支持格式或 URL，查看实际解析内容并用于构图 | M1 共享契约 |
| M3 图谱可管理 | 持久编辑、完整导入导出、绑定/画像微调、现有界面接线 | 改知识、保存、重载、重分析；导出后重新导入仍可用 | M1 工作图与执行器 |
| M4 视觉场景扩展 | 更多 MVTec 模型/对象和语义适配；WM811K 分类与空间统计相结合 | 首轮链路扩展到更多视觉输入与晶圆场景 | M1 特征与条件接口 |
| M5 TEP 数值接实 | 正确窗口/正常参考、完整特征、多变量条件与现有数值 reasoner 联合 | 多变量变化如何汇聚到候选，路径对应实际计算 | M1 契约及图身份 |
| M6 集成与阶段展示 | 三场景串联、必要 UI 细节、可用回放与运行说明 | 只展示验收完成的输入方式、模型与场景能力 | 已完成的场景增量 |

默认执行顺序为 M1 → M2 → M3 → M4 → M5 → M6。M2/M3 的完整管理功能不阻塞已具备输入资产的 M4/M5 核心开发；每轮仍需有一个完整的使用路径，而不是仅增加配置或接口。

## 4 第一批任务：完成 M1

下列路径相对仓库根目录。新增文件名为计划落点，实施时可在同一职责范围内合并，避免无收益的模块拆分。

### T01 最小契约与兼容适配

- [x] 在 `backend/src/kgtracevis/schema/` 增加首批 MVTec 区域观测、绑定条件与画像模型；Wafer/Process 随后扩展。
- 保留 `schema/evidence_schema.py` 的旧入口；选择新策略时，旧记录通过显式适配进入新链路，不把任意 metadata 自动当作可执行特征。未选择新策略的旧调用沿用原合同。
- 首批支持 records 中的 mask、区域列表或明确的几何数据；记录 bbox、坐标空间、面积比例、细长程度、连通域和语义来源。原始数组以 run 资产保存，不塞入解释文本。
- 验收：有效输入可解析；错误特征/算子/端点明确报错；旧 examples 和旧调用的字段、ID 及默认 profile 不变。
- 依赖：无。实施前按锁文件准备本仓库 uv 环境，并记录实际回归基线。

### T02 把现有 LLM 画像产物变成可消费知识

- [x] 扩展 `source_kg_compiler/{models,compiler,workflow}.py` 的现有生成链，输出有明确 schema 的绑定、画像条件及源边映射。
- 延续现有 `SourceUnit → KnowledgeCard → CanonicalEntity/Edge`；结构错误自动修复或显式记录不可用项。素材引用与 LLM 补充的领域假设区分来源，无人工审核门槛。
- 验收：同一编译产物能通过运行装载器，条件引用的字段可计算、实体/边可解析；LLM 测试替身覆盖结构错误和修复，不把替身结果记成真实 LLM 验收。
- 依赖：T01。主要复用 `backend/tests/test_source_kg_compiler.py`、`test_source_kg_llm.py`。

### T03 最小工作图装载与身份连续性

- [x] 在 `kg/` 和 `service/` 实现工作图登记、隔离装载、当前图读取；扩展 `service/postgres_schema.sql`，采用可作用于既有库的增量变更，不重跑新库初始化。
- 保存绑定/画像及有效推理元数据，建立 compiler 边 ID → 运行边 ID 映射；先支持新建图，不做正式 release 或复杂覆盖合并。
- 验收：构图后能注册并装载；进程重启后可读取；同逻辑 ID 的两图不串读；legacy 图与历史 run 不被修改；装载失败不将半成品报告为可用。
- 依赖：T01、T02。复用 `test_import_neo4j.py`、`test_neo4j_repository.py` 和 Postgres 测试注入方式，新增工作图集成测试。

### T04 实现多观测画像执行器与计算轨迹

- [x] 新增 `workflows/profile_match_reasoner.py`，接入现有 `RcaReasoner`/registry；复用图结构做候选及关系约束，执行支持/冲突/必需条件。
- 处理多观测身份，不使用按 field 覆盖的单值选择；排除跨类型静默匹配。明确记录每个候选实际使用的特征、条件、观测与图边。
- 在 `core/{pipeline,result}.py`、profile resolver 中接通有效空结果状态；新策略的“无匹配”不回落到旧路径算法，旧策略的默认调用保持兼容。
- 验收：改变关键值/空间分布会改变条件结果；输入顺序不改变语义；缺失与冲突不同；相同支持可保留并列；空结果不被 generic 路径替换。
- 依赖：T01、T02。新增画像执行测试，扩展 `test_pipeline.py`、`test_reasoning_registry.py`、`test_root_cause_provider_selection.py`。

### T05 从 MVTec 异常区域产生明确几何与语义事实

- [x] 扩展 `mask/`、`producers/mvtec_records.py` 和 `adapters/ds_mvtec_adapter.py`，从实际 mask 得到逐区域 bbox、面积、形态和位置；不只保留一个全图汇总描述。
- 接入 ROI 语义候选及其来源；已提供标签的辅助路线与真正模型预测分开。首次只使用实际可运行的 detector，先核对该模型的类、预处理和输出坐标。
- 验收：细长/斑点/多区域/空 mask 产生对应事实；多个区域不覆盖；bbox 明确属于原图还是 detector grid，并按真实预处理还原可支持的坐标。没有语义模型输出时明确缺失，不能把目录名当预测。
- 依赖：T01；特征词表供 T02/T04 共用。复用 `test_record_producers.py`、`test_adapters.py`，增加小型 mask 和受控图片 fixtures。

### T06 接入真实服务与现有前端契约

- [x] 在 `service/{api,runs,handlers,run_enrichment}.py` 和 `workflows/root_cause_provider_selection.py` 接入 `graph_id` 与新策略；上传、分析、KGStudio 使用同一工作图。
- 首轮沿用 `mode=records`/`mode=image`、`dataset=mvtec` 的现有入口，不新增上传模式。复用 `service/visual_evidence.py` 展示原图、mask/heatmap 与区域资产引用。
- 将真实 trace 投影为现有 observations、linked_entities、ranked_root_causes、top_k_paths、path_graph、source_edge_provenance；路径/候选/观测 ID 对齐。
- `src/api/`、`src/services/rootlens-service.ts` 及已有选择控件只做必要接线；若新算法需要在界面中显式选择，使用现有选项区域，不新增页面。
- 验收：后端结果在现有界面可浏览；实际区域与观测能对应；路径来源可回查；一次 run 不混用其他图的候选或来源。
- 依赖：T03、T04、T05。扩展 `test_service_api.py`、`test_postgres_run_payloads.py` 与受影响的前端服务测试。

### T07 首个闭环验收与实际能力记录

- [x] 用文本素材、工作图和不同 MVTec 图片/区域走通 M1；覆盖满足条件、冲突、缺失、不匹配和正常输入，保留实际结果。
- 定向检查一条诊断关系的修改/移除会影响新推理；此时可通过后端重装载验证，完整编辑交互在 M3 完成。
- 验收：能够逐项展示“原图/检测区域 → 计算特征与语义 → 条件命中 → 图上候选/路径”。本地 fixture 测试、真实模型/LLM 调用、真实数据库服务验收分别记录，未执行项保持未完成。
- 依赖：T06。若当前缺少获授权的 LLM 服务或实际数据，先完成本地代码与 fixture 验证，M1 的相应现场验收项保留，不把该缺口扩成其他开发的阻塞。

## 5 后续任务：补齐管理并深化三个场景

### M2 素材导入与管理

- [x] **T08 实际解析与片段复用**：把 `service/kg_materials.py` 的 extract 状态登记改为真实解析；TXT/Markdown、CSV、JSON/JSONL 产生内容及定位，直接交给 compiler，避免重复分块和丢失引用。依赖 T01/T02。
- [x] **T09 PDF 与 URL 获取**：在统一 parser 适配层接入调研选定的 Docling；首批验收带文本层 PDF 的页码/内容。调用已有 `fetch_remote_material()` 真正获取允许的 URL，保存失败原因。扫描 PDF/OCR 和 Office 扩展在基础链路可用后增加，不预先宣称支持。依赖 T08。
- [x] **T10 素材状态与重新构图**：上传/获取、解析、构图、可加载分别对应真实产物；支持重新解析/构图、失败重试和查看片段，复用现有素材页。验收不同素材能进入同一构图流程，计数与内容一致。依赖 T08/T09。

主要落点：`service/{kg_materials,postgres_material_store,kg_material_build,kg_construction}.py`、`source_kg_compiler/`、`src/views/MaterialsManageView.vue`。扩展现有 materials/compiler/build 测试；网络获取使用可控 HTTP 测试源，PDF 使用小型公开或合成 fixture。

### M3 图谱管理、微调与完整导入导出

- [x] **T11 持久编辑**：复用 `service/kg_runtime_edit.py`，完成节点/边/别名与绑定/画像的持久编辑；验证引用一致性，删除有依赖对象时明确返回依赖或显式级联处理。新 run 重新读取当前内容，历史结果保持。依赖 T03/T04。
- [x] **T12 完整交换包**：后端导出实际节点/边、别名、来源、绑定和画像；默认导入为新工作图，覆盖使用明确动作并先保存必要备份。CSV 保留旧用途；缺画像时说明支持的策略，可自动补生成，不静默切换算法。验收包往返后的逻辑 ID、条件及结果一致，错误包不破坏旧图。依赖 T11。
- [x] **T13 现有界面接线**：Backend 模式下将已有编辑动作接真实 API，补工作图选择及图谱包导入/导出入口；绑定/画像先用现有详情中的简单表单或结构化文本编辑，不制作新编辑器。Demo/Replay 保持快照语义。依赖 T11/T12。

主要落点：`kg/neo4j_repository.py`、工作图服务与存储、`service/{api,kg_runtime_edit,kg_studio}.py`、`src/{api,services}/`、`src/views/{GraphExploreView,MaterialsManageView}.vue`。验收“编辑 → 保存 → 重载 → 重分析”及“导出 → 新图导入 → 再分析”，同时检查重启后保存仍有效。

### M4 MVTec 扩展与 WM811K backbone 适配

- [x] **T14 更多模型适配**：在 M1 所用模型可用后，按具体需求扩展其他 MVTec checkpoint 的模型类、预处理和输出坐标；缺权重不静默换模型或输入标签。依赖 M1。
- [x] **T15 更多对象与语义改进**：扩展 M1 的 ROI 语义适配与对象/缺陷覆盖，处理高分辨率、多区域和近似缺陷；保留原生标签辅助与模型预测两种输入来源。依赖 T05/T14。
- [x] **T16 Wafer 分类与空间联合**：修正 0背景/1正常/2失效编码，计算有效 die 与空间分布，将已有分类器输出接为独立观测；处理 None/无标注/不符合已知图案的区别，不把 nearfull 改写为实测颗粒污染。依赖 T04/T06。

主要落点：`producers/{backends,mvtec_models,mvtec_records,wm811k_records}.py`、`mask/`、`adapters/`。MVTec 验收实际 ROI 与几何/语义对应；Wafer 验收预测和空间条件一致或冲突时的处理。继续复用当前模型，新增 backbone 按具体缺陷或运行瓶颈选择，不先启动训练竞赛。

### M5 TEP 数值链路与知识图谱联动

- [x] **T17 窗口与特征坐标配套**：在 `producers/tep_records.py` 明确样本范围、采样周期、故障前后窗口与完整通道顺序；正常 scaler/PCA 与 memory 使用可配套的资产。旧资产缺少原始配套信息时保留旧 profile，新 profile 另建一致资产，不替换旧调用的数据条件。依赖 T01。
- [x] **T18 数值策略消费当前图**：延续 Root-KGD 数值链路，把当前工作图的变量/设备/故障画像及方向/多变量支持条件接入候选比较。不能仅将新图画在固定资产算出的排名旁边。解释逐项记录哪些数值分量、条件和图关系实际改变结果。依赖 T03/T04/T17。
- [x] **T19 多路径与趋势定位**：保留完整时序/贡献向量，展示 top contributors 但不截断数值推理输入；同一候选可汇聚多条观测路径，趋势预览由后端输出到现有详情。验收窗口、方向或关键知识条件变化能反映到 trace/候选。依赖 T06/T18。

主要落点：`producers/tep_records.py`、`adapters/tep_adapter.py`、`workflows/tep_root_kgd/`、`service/run_enrichment.py`。复用 `test_tep_root_kgd_provider.py`、`test_tep_rca_bridge.py`、`test_record_producers.py`，分别测试新策略与 legacy 行为。

### M6 运行整合与阶段展示

- [x] **T20 最小 UI 完整性**：补 observation 标题/算法文案、候选 reason、必要趋势预览和保存状态；检查实际屏幕上的证据—图节点—候选—路径联动，不重排三页。依赖相应场景接口。
- [x] **T21 已完成场景端到端走查**：实际上传 → 分析 → 保存 → 重启读取；实际素材 → 构图 → 装载；编辑/导入后重分析。为已完成能力生成可消费的回放，既有 session 入口不另造不兼容格式。未完成的场景不阻塞其他场景交付。依赖相应增量。
- [x] **T22 使用说明和能力清单**：更新当前真值文档、必要 README 与本任务状态；逐项注明支持格式、输入方式、模型资产、算法及尚未完成项。展示使用 Backend 或 Replay 时明确对应运行方式。依赖已验收结果。

## 6 验收按功能后果进行

| 变化 | 必须取得的证据 |
| --- | --- |
| LLM 构图 | 产物通过装载与条件检查，生成知识实际用于后续分析；真实调用与测试替身区分 |
| 特征/绑定 | 值与原始区域、cells、通道窗口对应；多观测不覆盖、不同输入不靠同一预写结论 |
| 条件推理 | 支持、冲突、缺失分别处理；关键输入或规则变化影响结果；无匹配不偷偷兜底 |
| 路径解释 | 候选、观测、路径、源边引用一致；解释来自真实依赖；无适用检查不显示完全一致 |
| 图谱管理 | 保存和重启有效；相关编辑影响新分析；完整包往返；两图不串读；历史结果不被重算覆盖 |
| 模型适配 | 实际模型类、权重、预处理和输出坐标匹配；实际运行资产具备后才记模型链路完成 |
| 前端兼容 | 旧入口与回放可用；新字段在当前页面可读、可操作、可联动；不只是 HTTP 200 |

### 执行命令与证据记录

从 `backend/` 使用项目 uv 环境。每项任务先跑直接相关测试，阶段交付时再跑受影响集成测试；新增测试与功能放在同一增量。已有测试按上述落点复用，不另建测试平台。

```bash
# 后端首次安装：按锁文件，增加 llm/ml/parser 依赖时只同步该任务所需部分
cd backend
uv sync --extra dev --frozen

# 第一批已有回归入口；实现新增测试后将其加入同一次定向运行
uv run --extra dev pytest tests/test_source_kg_compiler.py tests/test_pipeline.py tests/test_reasoning_registry.py tests/test_record_producers.py
uv run --extra dev ruff check src tests scripts
```

涉及前端修改时从根目录按 `package-lock.json` 安装，执行受影响 Vitest 测试和 `npm run build`，并检查实际界面。阶段集成时运行完整后端测试一次用于核对回归，不在每个小任务重复完整套件。

迁移文档中的 288 passed / 6 failed / 3 skipped 是历史基线，不代替本次结果。每个完成项在本文件补“实际命令/结果、产物位置、未完成验收”；既有失败与新增回归分别记录。未满足完成条件的任务不勾选。

## 7 外部依赖与本轮授权

- 已按锁文件安装项目 uv 的 dev/llm/ml extras 和前端依赖，下载公开 capsule 测试图片及 STFPM 权重；大文件保存在被忽略的 `backend/runs/`。
- 用户授权下载公开资产及少量 LLM 调用，并已配置服务。本轮只发送公开示例素材、原图上下文和 ROI；没有训练、GPU 或私有素材上传。
- Neo4j/Postgres 使用 `compose.test.yaml` 的独立端口与命名卷；只有新空测试库初始化过种子，不以此代替既有数据迁移。后续既有库仅运行工作图增量迁移。
- 本轮新增 bottle PatchCore、公开 WM811K 模型/测试网格与 TEP 参考数据，均 CPU 实跑。GPU/付费基础设施、训练及私有数据搬运不在本轮授权内。
- 普通开发启动不等于部署；未推送 Git、发布服务或配置自启。

## 8 执行记录

- M1 阶段：按用户要求由 WM811K 首轮改为 MVTec；先完成 T01–T07。当时尚未实施 M2–M6；其后完成情况见本节后半部分。
- M1a：闭合 `VisualRegion / VisualCondition / VisualDiagnosticProfile`、逐区域测量、执行轨迹及有效空结果；形状、阈值、冲突、输入顺序和原因边变化测试通过。
- M1b：真实 LLM 从 Markdown 生成 31 节点/62 边，修复后有 3 份可执行画像；实际装载到 Neo4j/PG，并通过页面装载、选择。真实库测试确认同 ID 两图不串读，移除原因边会改变结果。
- M1c：公开 STFPM 实跑 3 张 capsule 图片；背景区域被排除、胶囊下缘开口产生候选、正常图为空；划痕样例漏检保留。ROI 使用原图上下文和明确坐标，未使用原生缺陷标签生成答案。
- 存储联调修复了完整输入只存摘要、区域 `obs_id` 丢失、同 case 新 run 改写历史输入的问题；在现有 PG parameters 保存输入/绑定快照，不给旧入口增加迁移前提。隔离验收行从原始保存结果回填新字段，未重算旧结果。
- 本机最初基线为 276 passed / 23 failed / 3 skipped；准备隔离数据库与所需资产后，最终完整测试为 **329 passed / 7 failed / 1 skipped**，不是全通过。7 项的具体原因与日志见 M1 验收文档；其中环境敏感的旧配置测试单独清空 Neo4j 变量后通过。
- 前端 **18 文件 / 85 项通过，build 通过**；实际检查了工作图装载/选择、records 上传、ROI/数值详情、候选条件和路径联动。修复长 ID 导致的链路横向溢出。修改的 Python 文件 Ruff 通过。
- 完整结果与截图：`backend/runs/mvtec_m1_public/`；构图产物：`backend/runs/source_kg_build/mvtec_m1_public_20261110/`；历史使用说明：`809fb8d:backend/docs/mvtec-m1-demo.md`。

### M2–M6 完成记录

- T08–T10：真实 TXT/Markdown/CSV/JSON/JSONL/HTML 片段解析、Docling 文本层 PDF 和实际 URL 获取；失败重试与重解析留档。25 项 parser/material/compiler/PG 定向测试通过；实库 3 份 Markdown 均解析和重解析，公开 PDF 内容与页码正确。
- T11–T13：完整工作图包、持久节点/边/别名/画像编辑、依赖校验、范围内单事务替换与旧包备份。实库测试完成保存→重新读取→新分析变化、交换包往返、失败恢复、旧 run 保留原图与结果；页面 JSON 保存已实操。未加入审核/正式版本治理。
- T14–T16：capsule STFPM 之外新增 bottle PatchCore 的安全纯权重加载、对象注册、CPU 预处理/阈值/坐标适配和可选正常参考；真实 bottle 异常/正常图区分。18 张公开晶圆图实跑，0/1/2 计数和独立空间观测进入执行器；3 张满足当前画像，15 张保留无匹配。
- T17–T19：TEP 52 通道完整窗口、正常 500 行/PCA18 配套资产、当前图 Root-KGD 传播和条件联合执行。故障前无候选，故障后两窗口有冷却扰动候选及 3 条实际数值依赖路径。同一真实窗口的权重/方向/阈值消融改变得分或清空候选。
- T20–T22：保留三页，新增必要的测量/趋势、保存状态与回放导出。原 Session 格式增加可选 backend_runs；大型图片/时序回放使用 IndexedDB，刷新后仍可读。TEP 和 MVTec 已通过现有入口导入，图页刷新对 API 为 0 请求。最后交付 MVTec、Wafer、TEP 及三场景合并成品回放。
- LLM：3 份公开素材实际生成 69 节点/143 边，画像 2/4/2；TEP 错误通道绑定自动校验后调用 1 次修复。运行图按全部画像依赖和物理路径投影，不按 case 裁图，去除 schema/流程词；原始抽取保留。
- 最终完整后端 **345 passed / 7 failed / 1 skipped**，7 个失败 node IDs 与 M1 相同；前端 **19 文件 / 89 项通过**，build 通过；修改的 Python 文件 Ruff 通过。日志分别为 `backend/runs/m2-m6-full-pytest-final.log`、`m6-frontend-tests-final.log`、`m6-ui-build-final.log`、`m6-ruff-final.log`。
- 本机产物：`backend/runs/refactor_m2_m6/acceptance-index.json`、`*-package.json`、`*_final-run.json`、`*_final-session.json`、`all-scenes-session.json` 及截图。未覆盖 M1 负结果、未伪造缺失基线资产、未提交权重/凭据/数据库。

本计划范围内无未完成任务。扫描 OCR/Office、全 MVTec 对象权重、完整 benchmark、审核、置信校准和正式版本发布维持后置范围，不列作本轮完成能力。
