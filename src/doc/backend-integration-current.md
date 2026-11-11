# RootLens 当前集成边界（2026-11-11）

## 1. 当前定位与同仓后端

RootLens 当前是一个 **backend-first 工作台**，Vue 前端与 Python 后端在同一仓库维护：

- 前端 `src/`：保留原三个一级入口、Demo／Backend、成品回放和有向力导向图。两条后端闭环仍从原入口发起；Backend 的运行页分为列表与保存详情，见 §1.8–1.9。
- 后端 `backend/src/kgtracevis/`：真实资料解析／LLM 构图、模型／adapter 测量、统一推理和 TEP RootKGD、任务及完整分析持久化。
- 前后端通过 API 协作；**后端代码放在同仓，不等于浏览器执行后端算法**。
- RootLens **不再**在浏览器端执行图谱构建、Evidence 临时组装或 RCA 本地推理。

### 1.1 同仓结构与迁移来源

2026-11-10 的迁移以 `/Users/macintosh/TrivalWork/KGTraceVis` 的 Python 后端**当前工作树**为来源，复制至 `/Users/macintosh/TrivalWork/RootLens/backend/`：

- 保留 Python 包名 `kgtracevis` 与 `backend/src/kgtracevis/` 布局。
- 保留 `backend/scripts/`、`backend/configs/`、`backend/data/` 中的小型 KG 种子及 examples、`backend/tests/`、`backend/docs/`、`backend/pyproject.toml` 和 `backend/uv.lock`。
- 不迁入旧 `web/`、`web_legacy/`、论文、实验输出、Git 历史或 agent 历史。
- RootLens 前端 `src/` 保持原位，不改成旧 React 客户端，不以搬目录或覆盖源码的方式丢失未提交 UI 改动。
- 原 KGTraceVis 目录先保留为来源备份；日常运行与后续后端修改以 RootLens 的 `backend/` 为准。

源码内置不代表大型数据、模型权重、外部依赖或每种模型能力已迁移可用。本次已确认的本机迁移事实见下节；不能将有限验证范围扩写为全部测试或模型能力通过。

### 1.2 历史：迁移验证摘要（2026-11-10）

§1.2–1.8 保留各阶段的结果与入口背景；当前前端以 §1.8–1.9、§2–3 为准。

本节仅保留集成边界所需摘要；过程与证据见[完整核验记录](../../backend/docs/rootlens-monorepo-migration.md)及当时的机器报告路径 `.rootlens-cache/backend-migration-verification.json`（Git 忽略，当前工作树未提供）。以下结果限定于本次迁移，不代表未来每次启动状态：

| 核对项 | 已确认事实 |
| --- | --- |
| 数据库与历史资产 | 既有库已离线复制到 `backend/runs/local_runtime/` 并从新路径启动，数据库 stop/start 与 API 重启后的数据保留核验通过。原有 4 个 run ID、4 条 feedback ID、3 个 material ID 一致，4 份历史输入附件完整保留。 |
| 图谱保留 | 210 个节点、602 条边；迁移未重建图谱、未重导入种子。 |
| 新写入隔离 | 迁移核验时库为 **5 个 Run / 5 条反馈 / 3 份素材**；第 5 组 run 与 `needs_review` 反馈为明确标注的迁移验收测试，应排除出实验统计。该 run 的输入文件仅写入新的 `backend/`，原 KGTraceVis 来源备份未收到新增 run。 |
| 后端与代理链路 | 已用 `RootLens/backend/.venv/` 中的 Python、以 `RootLens/backend/` 为工作目录启动 8000 服务；前端 5174 经代理访问的 8 类接口均返回 HTTP 200。`dev:all` 另在临时前端 5180 / API 8010 端口端到端试启成功，HTML、代理 health / runs 均为 200，停止后两端口均释放；日常默认端口仍为 5174 / 8000。 |
| 安装与初始化保护 | editable 安装及普通 wheel 离线构建成功，不代表从零联网安装或全部模型依赖已具备。`backend:init` 会拒绝已有 PG 应用数据、非空 KG 及未知参数，核验确认既有数据未被覆盖。 |
| 前端构建与测试 | `npm run build` 通过；`npm test`：**17 个文件 / 71 项测试通过**。根 `src/` 的现有 UI 改动保持。 |
| 后端测试基线 | 完整 pytest：**288 passed / 6 failed / 3 skipped**。失败的 pytest node IDs 与原 KGTraceVis 当前工作树基线完全相同，无新增失败，**不是完整测试全通过**。5 个示例在真实 Neo4j 下通过。 |

**核验边界：**Docker Compose 仅做静态配置检查，本机未安装 Docker、未实际运行容器栈；上述结果不是所有模型能力、完整构图发布或工业根因准确率验收。原目录继续保留为备份，不因本次验证而自动授权清理。

### 1.3 历史：MVTec M1 增量（2026-11-10）

本轮在当前 checkout 另用 `backend/compose.test.yaml` 实跑独立 Neo4j/Postgres，不把先前迁移的机器状态、资产或测试数作为本轮结果。

- **已实现**：TXT/Markdown 经既有 LLM compiler 生成可执行视觉画像；自动条件检查/一次有界修复；装载为隔离工作图；指定工作图分析 records 或原图；逐区域几何、可选视觉语义、实际条件执行、源边路径与完整 PG 运行快照。
- 新策略为 `mvtec_feature_graph_v1` / `visual_profile_match`。指定 `graph_id` 或 `working:<graph_id>` 才使用新工作图；旧入口及默认 profile 保持原行为。新策略的无匹配/证据不足不回退为 generic 路径。
- MVTec 观测使用闭合的 `visual_region.v1`：坐标平面、bbox、面积/长宽比/离心率/形态、语义候选及来源；任意 metadata 不参与执行。多个区域有独立 obs ID，输入、绑定、trace 与选择的工作图可在重启后读取。
- 前端只补了工作图装载/选择、ROI 开关、区域详情和候选条件；三页与 Demo/Replay 边界未改变。KG 来源文字不作为现场 observation；诊断反向视图保存原始源边。
- **实跑范围**：公开 capsule STFPM 权重、3 张公开图片及配置的 LLM 服务。正例的下缘开口得到 PokeDefect→MechanicalContact 候选，原生类别为 crack；正常图无候选；另一个 scratch 图被 detector 漏检。不能扩写为全部 MVTec 类别或模型通过。
- **核验**：前端 18 文件/85 项及 build 通过；最终后端 329 passed / 7 failed / 1 skipped，失败分类见使用文档，不是全通过。真实隔离库与页面联动已走查。

以上为 M1 历史验收；后续完成情况见下节。新增工作图表使用增量迁移，不重初始化旧库。

### 1.4 历史：M2–M6 渐进重构（2026-11-10）

- 素材现在实际解析 TXT/Markdown、CSV、JSON/JSONL、HTML 与文本层 PDF（Docling Parse）；URL 实际获取，失败重试、片段定位、重解析历史可查看。扫描件/OCR/Office 未启用。
- 三场景工作图支持持久节点/边/别名、绑定/画像 JSON 编辑和完整 `rootlens-working-graph.v1` 交换。默认导入新图，显式保存前备份；每次新 run 固定图/画像快照，历史结果不随改图重算。
- 实际 LLM 图自动校验并生成视觉/空间/过程画像；运行图只投影全部可执行依赖及物理路径，不依据某个 case 选图。源码、完整原始构图与可执行工作图分开保留。
- MVTec 实跑 capsule/STFPM 与 bottle/PatchCore；第二对象支持正常参考 ROI 比较、安全纯权重加载、对象注册与明确坐标。没有权重的对象不冒用其他对象模型；旧入口原选择合同保留。
- Wafer 新 `wafer-measurements.v1` 固定 0背景/1正常/2失效，联合实际空间统计与独立分类；原生标签不传分类器，不把 nearfull 命名成实测颗粒污染。实际 18 张公开网格中 3 张满足现有画像，15 张无匹配。
- TEP 新 `process-measurements.v1` 保留 52 通道、正常参考/PCA、时序、窗口和全贡献向量；当前图方向/权重/条件参与数值排名，已验证同一真实窗口的改图效果。旧 Root-KGD profile/资产不被新调用替换。
- 现有 Session 格式增加可选 backend_runs 保存原始 RunDetail。后端导出原图快照和内嵌图片，浏览器只回放；大回放用 IndexedDB，失败不混写旧会话。MVTec/TEP 导入、刷新与路径已实屏检查。
- 本轮最终后端 **345 passed / 7 failed / 1 skipped**（与 M1 相同失败项），前端 **19 文件/89 项通过**、build 通过，修改的 Python 文件 Ruff 通过。不是全后端测试通过，也不是工业准确率验证。

使用、实际 JSON/路径、模型来源、负结果、回放文件和恢复入口见 [三场景使用与验收](../../backend/docs/progressive-demo-2026-11-10.md)。[执行计划](rootlens-refactor-execution-plan-2026-11-10.md) 的 T01–T22 已完成；审核、正式版本、置信校准、训练与完整 benchmark 后置。

### 1.5 历史：U0–U5 统一推理 v2（2026-11-11）

- 新闭合 `EvidenceFrame` 和公共知识 IR 把主体、注册特征、类型／单位、scope、procedure、正常参考及来源绑定起来。MVTec／TEP／Wafer 通过不同测量 adapter 接入**同一 grounding、候选展开、联合条件、代价与证明内核**；不按 dataset 更换最终评分。
- 原始公开 PDF／过程程序／论文与模型卡 → LLM 领域蓝图 → 确定性编译的可执行知识。素材页显式选 `unified-v2` 能力契约，沿用原解析／构图／装载服务，无人工审核前提。
- 完整 `rootlens-working-graph.v2` 的 canonical knowledge 持久保存于既有登记／隔离 KG，支持别名、绑定、条件／规则编辑、备份恢复和完整交换。明确选择 v2 工作图才走新内核，v1 包、旧 Evidence 和默认策略保留原合同。
- 三类真实模型／数值观测已运行：bottle 5 张图中 2 张得到 4 个并列候选；TEP 3 序列／9 窗口，正常无候选但后故障首位族仍错误；Wafer 18 网格中 7 匹配（6 原生图案一致、1 分歧），11 未匹配。实际失败不靠 generic fallback 补答案。
- 32 份同输入／知识的独立平坦计算和去中间机制对照均等价；收益落在统一合同、知识维护迁移与推导追溯，未证明图结构本身提高准确率。全局策略、改值／缺失／重复／删规则等检查和完整负结果已保存。
- 前端三页保持，补“推理依据”抽屉展示实测、联合条件、候选 U/C/A/J、反证／缺失及源边。22-case 原始 Session 实际导入和刷新通过，浏览器只消费保存结果，不执行新推理。
- 最终后端 **442 passed / 5 failed / 1 skipped**，5 项为已有资产／默认模型断言失败；已有空 env 配置和单 case 保存不完整问题已修复。前端 **20 文件 / 95 项及 build 通过**。不是全后端测试全通过，也不是工业诊断准确率验收。

使用／实际 JSON／图谱制作／API／回放见 [统一推理 v2](/Users/hhm/code/RootLens/backend/docs/unified-reasoning.md)，比较与负结果见 [U5 验收](/Users/hhm/code/RootLens/backend/docs/unified-reasoning-u5.md)，提交与分期证据见 [执行记录](rootlens-unified-reasoning-execution.md)。本机仍使用 5186／8012 与独立 55433／57687 测试库；日常默认地址未变，原数据未重建。

### 1.6 历史：双闭环重构与验收（还原前）

本节记录已推送的 `codex/demo-two-loops@8cf4d0b` 所对应界面及验收；本次还原只改变前端，以下后端能力和真实数据继续保留。旧界面的当前恢复边界见下一节。

该版界面只连接后端，保留“素材管理 → 知识图谱 → 推理分析”三页；旧 Mock／Replay／runtime 入口从产品界面移除。公开演示按钮提供原始资料、样本或真实 Frame，并实际提交任务，不打开预制根因答案。

- **闭环 A**：资料上传／URL → 真实解析与定位 → LLM 领域蓝图 → 自动校验与一次有界修复 → 确定性编译 → 持久语义编辑 → “投入使用”。ready 与 enabled 分开；新分析只使用已启用的 v2 工作图。
- **制作与编辑合同**：LLM、adapter 和编辑器共用特征类型／单位／有限值目录；开放外观词汇不伪造枚举。视觉／过程候选软建议16、硬限默认32，不静默截断；晶圆仍限8种图案。presence gate 只作前置，具体支持分支还需诊断原子；source 编译收紧原 ANY 时显式记录语义变化，canonical退化分支拒绝执行。等价词汇绑定保留实际来源与应用记录，不由粗外观补成未知部位。候选专属新增／撤销条件创建独立小束，不改共享机制；无来源的作者阈值明确标人工启发式。
- **闭环 B**：原始图像／52通道过程时序／0-1-2晶圆网格 → 实际模型和 adapter → EvidenceFrame；或直接从中间 Frame 开始 → 明确选图和引擎 → 保存候选、条件、来源与原始媒体／曲线对应。
- **统一约束推理 `unified_abduction`**：保留公共合同、联合条件、冲突／缺失与 U/C/A/J 代价。
- **TEP RootKGD `tep_rootkgd`**：在当前 canonical 图上复用原 `simulate_propagation`、全52维贡献余弦／覆盖／传播熵评分和 `trace_path`。当前 `tep_rootkgd_propagation_v2`／`rootkgd-host-channel.v2` 按 host→稳定通道合并逻辑期待，移除沿显式 effect 已由下游覆盖的上游重复声明；主／备选来源路径仍连续保留。重复同通道条件不增加传播票，真实新通道或 effect 仍可改变结构；不执行条件阈值／AND-OR／mode惩罚。不使用固定旧图、fault标签、按故障族调参或 anchor-memory。全部贡献参与计算，不把展示路径截断误写为未使用。
- **快照知识诊断**：解释完成后保存本次条件事实真／假／未知、排名资格、同签名组与真实评分输入；成本先验独立展示。历史 run 缺字段时不以当前知识补算。
- **任务与分析**：Postgres 增量表保存真实事件、输入及完整结果；重启把未完成任务标成 interrupted，失败／中断手动重试创建新任务，不悄悄重复付费步骤。历史分析固定图快照，不随改图重算。
- **资产**：`backend/data/demo/two_loop/manifest.json` 是唯一受管演示清单，小包／真实 Frame 入库，大型／受版权约束资料与权重留在忽略目录；准备脚本不改数据库。原模型、原程序、原始 LLM 蓝图、演示适配与真实失败分开保留。
- **样例与选图**：`/api/demo-library` 的 group／sample `graph_ref` 按完整知识内容解析配套就绪图，不按最新或场景猜。仅隐式默认加载样例时自动配对；手选／携图意图保留并可明确切换。缺失、未启用、歧义或不可读明确显示，不在GET导入或改写图。

玻璃原图的拍摄部位未确认，当前用“玻璃边缘缺损”，不宣称已定位瓶口。厂家 Finish 资料是演示迁移知识，候选仍需工艺证据区分。Wafer 输出图案家族，不直接命名制造原因。数值评分均不是概率；正常、无匹配、证据不足与并列是有效结果。

已实际执行公开 PDF→LLM→别名保存回读→启用，以及三场景原始模型／测量与中间入口。视觉语义存在同图不同判断、TEP 另两序列仍有错误／无匹配；有效结果、选样过程和限制见 [双闭环演示手册](../../backend/docs/two-loop-demo.md)。API 和界面分别见 [后端契约](rootlens-two-loop-backend-contract.md)、[前端交付](rootlens-two-loop-frontend.md)。

本次方法变更后仅重新验证受影响的4个TEP×RootKGD v2组合：正式API与CLI候选、名次、分数、全部组件及outcome精确一致，52曲线／评分输入和真实连续源路径通过。d04另做当前原始 `.dat`＋正常参考→下载实际Frame→普通上传，三窗口结果与52曲线精确一致。原17项（13统一＋4 Root v1）按历史保留，13个未改动统一组合不重跑；默认13Frame／3图未修改。当前4项新旧排名不变，d01／d05错误仍存在；版本与新Run索引在 `backend/data/demo/two_loop/verification-summary.json`。

本次新公开PDF任务实际2调用后因当时硬16失败；从捕获的17候选最终响应离线恢复时，分别修正预算配置与泛presence充分分支，明确记录 `semantic_change=true`，原task仍失败、无新模型调用。恢复图正式导入／启用后，006 Frame执行为不足而非诊断成功：细Finish条件未知，未加粗→细等价绑定。原始响应、编译变化、当前API事实及尚未覆盖的有限值／binding分支见演示手册；可入库完整对照包在 `backend/data/demo/two_loop/graphs/source-finish-recovered.json`，恢复provenance同目录。独立验证图不替换默认演示图。

该版源码完整原生pytest为 **572 passed／4既有optional skipped**，前端Vitest **18文件／97项通过**、类型与生产构建通过；阶段日志与独立消费见[系统评估](../../backend/docs/two-loop-system-assessment.md)。4项跳过为3项指定隔离数据库opt-in和1项缺本机原TEP_KG对照，不是新屏蔽失败。较早阶段的失败与566／84等结果按原候选保留，不改写为本次复测。

### 1.7 历史：先恢复原前端基础（`f5e93aa`）

用户明确要求先恢复大改前的界面，知识图谱应呈现图网络而非层级树。恢复分支为 `codex/restore-original-frontend`，从已推送的 `8cf4d0b` 创建；精确前端基准是 `471e1aaa1dabd22fdb0dd7f00590e7e4cf08ab26`。重大UI提交 `3b3cf76` 的父 `8052e8b` 与此基准在前端源码／依赖／配置上相同。没有回滚整个仓库。

- 恢复原“运行与证据／根因与图谱／素材与构图”布局、卡片、分栏与交互，以及 `KnowledgeForceGraph`／`RunPathGraph` 的有向网络、共享节点与路径高亮。
- Demo／Backend 切换及成品 Session／runtime Replay 恢复；Demo默认读取成品快照，Backend才调用真实服务。浏览器仍不构图、不执行RCA，也不从原始节点／边／Evidence临时拼runtime。
- 保留当前Python后端、双闭环任务、Evidence／知识schema、RootKGD v2、数据库及历史素材／模型／结果。不是把所有新工作台控件重新移进原布局；目录绑定表单、候选局部向导与完整新任务交互仍以已保留的API合同为准。
- 当前旧上传／构图入口与新 `/api/tasks`、`/api/analyses` 各有合同。后者的 `cases[].results/evidence_frames` 不能假装是旧 `RunDetail`；恢复版的兼容仅映射后端已保存结果，不重新推理或修改分数。
- 新分析在原运行列表以“已保存分析”区分；每Frame、原分数／路径和完整快照保留，旧Session导出对新分析明确不支持。Backend总图仍是当前登记图，历史局部路径／依据来自保存结果；不把typed快照重新编译为浏览器总图。
- 工作图完整JSON保存继续保留新字段；typed图不能把投影边当成独立可执行知识改写。PUT为完整包替换，须基于完整GET结果修改，不可从旧视图字段子集重建。

恢复版前端完整原生Vitest为22文件／109项通过，类型与生产构建通过；原全量Arco约796KB主chunk大小警告保留。D3改为项目内锁定7.9.0依赖，不依赖现场CDN。记录与实屏证据见 [前端还原记录](rootlens-original-frontend-restoration.md)。后端源码未更改，复用572／4有效测试；还原前18文件／97项前端测试是历史候选证据，不冒充恢复版检查。

### 1.8 历史：在原界面接通素材和分析闭环

- **资料 → 可用工作图**：在素材库勾选资料，确认本次来源、名称和场景后提交真实异步制作。解析显示实际计数，LLM 阶段不显示百分比；失败可按原输入另建任务。完成只打开 `result.graph_id`，在原图谱页编辑完整包并投入使用。
- **工作图 → 新分析**：只有已启用、就绪的v2工作图可用于新任务。“用这张图分析”携精确图ID与显式新建意图，不加载旧结果。用户明确选图优先；公开样例配套仅适用隐式默认，缺图不回退。
- **原始输入／Frame → 保存解释**：原运行页“新建分析”提交后端任务，保留原接口上传。完成读取确切分析ID与Frame；原图谱展示该次保存路径、条件与观测定位，而当前登记总图仍是另一数据来源。下载本次Evidence可作为中间入口复算，不重跑模型测量。
- **本轮后端仅改source文本请求额度**：SDK传输重发关闭，失败终止；保留最多一次的编译修复与用户显式重试。推理、图存储、默认图与历史数据不回滚。

前端28文件／147项原生Vitest及build通过，原Arco主chunk警告保留。后端575通过／4既有optional skip，Ruff通过。真实任务、受控失败、界面验证与服务恢复见[原界面双闭环记录](rootlens-restored-two-loops.md)。

实际验收复用了已登记公开Emhart PDF的两个片段，唯一制作任务实际1次文本调用，新图完整包保存后启用并精准携图。原图关闭外部语义后得到证据不足；同图下载Frame再普通上传，完整结果精确一致。另用已存外观Frame与d04分别验证真实保存路径和两种引擎；独立短摘上传／解析未参与构图。可打开的图、运行、Frame和限制见[实际操作验收](../../backend/docs/original-ui-loop-acceptance.md)。

### 1.9 当前：运行列表与保存详情

- Backend 的 `/evidence` 用于新建分析、查看真实阶段和筛选历史。`/api/analyses` 只返回列表摘要；保存结论按已有 Frame 结果计数，明确的正常门控单独计数。没有保存结论时打开详情看，不从候选数量推断。
- `/evidence/runs/:runId` 只读取该次 `/api/analyses/{run_id}`。原始 Frame、结果、受管媒体、候选、观测和源边按本次 Run／Frame 的稳定 ID 关联；没有精确匹配就显示缺失。只显示实际保存的条件或传播轨迹，当前登记总图不替换历史。
- 原图／过程／晶圆仍由后端测量；Frame 直入跳过 Backbone，已有附件可以关联。下载的是实际保存的 Frame，不是前端重建。详情不展示未保存的逐字段变换审计或模型原始分数。
- 运行页已下线旧上传工作台。图谱页保留已存旧 Run 的读取、附件和回放；Demo 与 Replay 继续只读成品。新保存分析走详情路由，历史文档中的旧页面 URL 以其 Run ID 换用当前路由。
- 素材创建只走异步提取／构图，分析创建只走新任务。旧同步提取、重复构图／草稿及旧 Run 上传端点已移除；离线研究编译器、已存资产和工作图管理不变。

**真实合验**：在 5186／8012 隔离栈上传一份 272 字节的公开短摘，实际提取一段；移出、恢复后原文件、片段和处理记录不变。另从历史构图任务打开原已启用的适配图，再用这张图普通上传已保存的 006 Frame；未重新构图或运行 Backbone。新 [保存分析](http://127.0.0.1:5186/evidence/runs/2570f81d-7fee-406a-9eab-5132c2b2c223) 得到 8 个并列候选、24 条保存路径、35 条去重源边，下载 Frame 与提交内容相同。本机实屏和请求证据为 `backend/runs/live_materials_inference_acceptance/verification.json`（Git 忽略）。

## 2. 当前输入与分析入口

### 2.1 原始样本入口

Backend 的“新建分析”支持原图、过程序列＋正常参考与原生晶圆网格，经 `/api/tasks/inference` 执行；真实模型仍只在后端。缺模型或参考明确失败，不以演示结果替代。TEP 窗口一基闭区间、完整 52 通道，Wafer 原生标签不传分类器。

### 2.2 中间 Evidence 入口

选择“中间 Evidence”上传原生 EvidenceFrame（单个、数组或 frames 外壳），后端验证、绑定并重新推理。Frame 原值和范围保留，缺媒体不阻止标量推理。详情的“下载 Evidence”供中间入口复算；Session／runtime 导入只回放已保存内容。

### 2.3 历史快照的边界

Demo快照、`rootlens-runtime`／`rootlens-session-export` Replay和原页面工作区随原前端恢复；它们只消费成品。双闭环演示清单及真实任务仍由后端提供，不能把快照回放当作新分析。原始nodes／edges／Evidence的浏览器runtime构造仍不支持。

## 3. 当前三页职责

### `/materials` · 素材与构图

列表用来添加、筛选和勾选来源资料；点名称只打开素材详情，不改变构图选材。提取结果按后端提供的原文位置展示，处理记录和技术详情按需展开。提取与构图走后端异步任务；确认选材时允许同场景和共享素材。新图由任务返回的图 ID 打开，默认未启用。

移出只归档素材，保留原文件、提取结果和历史引用；在「已移出」中恢复后可以继续使用。活动任务引用的素材不能移出。Demo 和成品 Replay 仍只读；待分析样本不混作知识资料。

### `/graphs` · 根因与图谱

原总图、局部子图、方向箭头、路径高亮和来源／反馈联动保留。当前登记图读取 `/api/kg/studio?graph_id=...` 的真实节点与边，不复制共享节点；历史路径只读取保存快照。v2编辑基于完整canonical包，保存后可投入使用并携这张图新建分析。

增强后的词汇绑定、有限目录与候选专属条件operator保留在后端；本次原界面恢复不等于全部新表单和向导已移植。

### `/evidence` · 运行与证据

Backend 列表负责发起任务和打开记录；保存详情按输入、Backbone、Adapter／Evidence、KG 解释器组织，图谱是同一次推理的路径视角。切换窗口重置局部选择，回到列表保留筛选和滚动。成品回放独立于新分析，不改历史分数。

顶部Demo／Backend切换与“修改后端地址”设置完整服务地址。本地偏好／策展草稿不是后端持久知识或分析真值。

## 4. 运行、数据库与数据保留边界

### 4.1 统一开发入口

首次标准后端安装在 RootLens 根目录执行 `cd backend && uv sync --extra dev --frozen`，随后回到根目录执行 npm 命令。Python 环境位于 `backend/.venv/`，不复用来源备份目录中的环境。

| 根目录命令 | 约定职责 |
| --- | --- |
| `npm run dev` | 仅前端，兼容原用法，不启动后端或数据库 |
| `npm run dev:backend` | 使用 `backend/.venv/bin/python`，工作目录为 `backend/`，默认 `127.0.0.1:8000` |
| `npm run dev:all` | 前端 + 后端，数据库需预先就绪，不自动初始化 |
| `npm run backend:check` | 数据库探活 |
| `npm run backend:init` | 仅新库：schema 与 KG 种子初始化 |
| `npm run backend:test` | 在 `backend/` 工作目录执行现有 pytest |
| `npm run backend:db:status` | 查看预置本机数据库状态，仅作用于 `backend/runs/local_runtime/` |
| `npm run backend:db:start` | 启动预置本机数据库，不下载、不新建库 |
| `npm run backend:db:stop` | 停止该本机运行目录对应的数据库，不操作其他服务 |

`dev:all` 默认前端端口为 5174，API 端口为 8000；默认配置下任一端口被占用都会启动失败。已有前后端服务运行时不要重复启动，脚本不会为抢占端口而杀死其他服务。

这些是手动开发入口，不配置系统开机 / 登录自动启动。详细安装与使用步骤见根 `README.md`。

### 4.2 数据库职责与新库初始化

- Neo4j：运行时知识图谱与遍历。
- Postgres：保留历史 Evidence／run／反馈等数据；当前双闭环增量保存任务、完整分析与工作图登记／canonical knowledge。新 run 保存完整输入与绑定快照，重载不依赖临时 Evidence 文件；未带快照的旧 run 保持原文件恢复方式。反馈与运行元数据不依赖旧 session JSON 作为真值。
- CSV / JSON：种子、导入与导出资产，不是运行时数据库的替代品。

fresh clone 不含被 Git 忽略的本机数据库与工具，应从 RootLens 根目录走 Compose 分支：

```bash
docker compose -f backend/compose.yaml up -d neo4j postgres
# 等待 Compose 中 Neo4j / Postgres 健康；仅新库初始化 schema 与 KG 种子
npm run backend:init
npm run backend:check
```

`backend:check` 会读取应用表计数，因此 fresh 库初始化前返回缺表是预期行为，**不能要求它先通过才允许 init**。正确顺序是等待 Compose 数据库健康 → `backend:init` → `backend:check`。`backend:init` **仅用于新空库**，会拒绝已有 PG 应用数据、非空 KG 和未知参数，不覆盖既有数据；不是每次启动都执行的命令，更不是迁移既有数据的手段。本次既有库迁移未运行重建 / 重导入。

### 4.3 本机数据保留与 Git 忽略

- 本次既有数据库已离线复制到 `backend/runs/local_runtime/` 并从新路径启动，核对范围见 §1.2；该本机数据库与运行工具目录 Git 忽略，原目录继续保留备份。
- 数据不丢失优先：原目录先留备份；未核对数据前不得删除、覆盖、重建原数据库或删除持久化卷。
- 本机库入口为 `npm run backend:db:status` / `npm run backend:db:start` / `npm run backend:db:stop`，仅管理 `backend/runs/local_runtime/` 内已配置好的 PG / Neo4j / JDK；不下载、不新建库、不导入种子、不设置开机自启，不管理 Compose 或其他服务。
- 本机运行环境配置好后，且无已运行的前后端服务时，按 `npm run backend:db:start` → `npm run backend:check` → `npm run dev:all` 启动；这是日常启动顺序，不要在已有服务运行时为了重复验收而再启动一套。
- 不对既有数据库直接运行新库初始化；先确认备份、数据位置、连接配置与服务状态。
- 大型原始数据、模型权重、中间产物、运行与实验输出、数据库文件、虚拟环境与真实凭据不进入 Git；小型种子、examples、配置模板与锁文件保留在版本控制中。
- Git 忽略与不随源码迁入都不等于删除本地资产，不能据此推断数据或模型已全部迁移完成。

### 4.4 配置模板与优先级

- 根 `.env.example` 是公开 Vite 配置模板，`VITE_API_BASE_URL` / `VITE_BACKEND_PROXY_TARGET` 不得包含后端凭据。
- `backend/.env.example` 是后端私有设置模板；真实 `.env` / `.env.local` 被 Git 忽略，不提交真实凭据，不覆盖既有本机配置。
- 后端配置优先级：**进程环境变量 > `backend/.env.local` > `backend/.env` > 配置 YAML > 默认值**。
- 自定义 API 端口必须同时统一 `ROOTLENS_API_PORT` 与前端 `VITE_API_BASE_URL` / `VITE_BACKEND_PROXY_TARGET`；修改后重启相关进程，并确认页面顶部的 Backend 地址与实际服务一致。根 Vite 模板与后端私有模板的职责不可混用。

## 5. 模式与浏览器计算边界

当前恢复的界面提供Demo／Backend、成品Session／runtime Replay和原工作区；仍不提供：

- 浏览器从 nodes／edges／Evidence 组装 runtime；
- 浏览器本地构图、RCA／what-if 重算；
- 把快照、旧v1默认策略或视图映射冒充当前v2双闭环新推理。

历史public快照、后端记录、素材、模型和数据库均保留。原始records仍可由后端adapter显式消费；`backend/scripts/`是后端客户端，不是浏览器生成路径。

## 6. 文档真值

当前优先阅读顺序：

1. 本文档 `backend-integration-current.md`
2. 根 `README.md`（当前用法）、`rootlens-restored-two-loops.md`（当前界面闭环）、`rootlens-two-loop-backend-contract.md`（API）与 `rootlens-two-loop-demo-assets.md`（资产）
3. `backend/docs/two-loop-demo.md`（双闭环API演示／服务恢复）、前端历史交付与 `source-projects.md`；其他后端设计／schema依其版本解读，旧Web／论文路径只作背景
4. 需要理解历史设计背景时，再看：
   - `module-1-graph-construction.md`
   - `module-2-unified-evidence.md`
   - `module-3-rca-engine.md`
   - `frontend_handoff.md`
   - 其他旧 roadmap / acceptance 文档

历史资料仅作为背景，不再代表当前前端实现边界，也不能替代本次迁移的实际验证结果。
