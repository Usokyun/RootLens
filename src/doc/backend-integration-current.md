# RootLens 当前集成边界（2026-11-11）

## 1. 当前定位与同仓后端

RootLens 当前是一个 **backend-first 工作台**，Vue 前端与 Python 后端在同一仓库维护：

- 前端 `src/`：素材管理、知识语义编辑与启用、样本／Evidence 上传、任务和解释联动。
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

§1.2–1.5 保留各阶段当时的结果与入口背景；当前产品入口以 §1.6、§2–3 为准。

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

### 1.6 当前：资料与分析的两个完整闭环

当前界面只连接后端，保留“素材管理 → 知识图谱 → 推理分析”三页；旧 Mock／Replay／runtime 入口从产品界面移除。公开演示按钮提供原始资料、样本或真实 Frame，并实际提交任务，不打开预制根因答案。

- **闭环 A**：资料上传／URL → 真实解析与定位 → LLM 领域蓝图 → 自动校验与一次有界修复 → 确定性编译 → 持久语义编辑 → “投入使用”。ready 与 enabled 分开；新分析只使用已启用的 v2 工作图。
- **闭环 B**：原始图像／52通道过程时序／0-1-2晶圆网格 → 实际模型和 adapter → EvidenceFrame；或直接从中间 Frame 开始 → 明确选图和引擎 → 保存候选、条件、来源与原始媒体／曲线对应。
- **统一约束推理 `unified_abduction`**：保留公共合同、联合条件、冲突／缺失与 U/C/A/J 代价。
- **TEP RootKGD `tep_rootkgd`**：在当前 canonical 图上复用原 `simulate_propagation`、全52维贡献余弦／覆盖／传播熵评分和 `trace_path`。不使用固定旧图、fault标签、按故障族调参或 anchor-memory。全部贡献参与计算，不把展示路径截断误写为未使用。
- **任务与分析**：Postgres 增量表保存真实事件、输入及完整结果；重启把未完成任务标成 interrupted，失败／中断手动重试创建新任务，不悄悄重复付费步骤。历史分析固定图快照，不随改图重算。
- **资产**：`backend/data/demo/two_loop/manifest.json` 是唯一受管演示清单，小包／真实 Frame 入库，大型／受版权约束资料与权重留在忽略目录；准备脚本不改数据库。原模型、原程序、原始 LLM 蓝图、演示适配与真实失败分开保留。

玻璃原图的拍摄部位未确认，当前用“玻璃边缘缺损”，不宣称已定位瓶口。厂家 Finish 资料是演示迁移知识，候选仍需工艺证据区分。Wafer 输出图案家族，不直接命名制造原因。数值评分均不是概率；正常、无匹配、证据不足与并列是有效结果。

已实际执行公开 PDF→LLM→别名保存回读→启用，以及三场景原始模型／测量与中间入口。视觉语义存在同图不同判断、TEP 另两序列仍有错误／无匹配；有效结果、选样过程和限制见 [双闭环演示手册](../../backend/docs/two-loop-demo.md)。API 和界面分别见 [后端契约](rootlens-two-loop-backend-contract.md)、[前端交付](rootlens-two-loop-frontend.md)。

## 2. 当前输入与分析入口

### 2.1 原始样本入口

上传真实图片、过程序列＋正常参考、原生晶圆网格。后端运行已配置模型／测量算子和 adapter；缺模型或参考时明确失败，不用演示结果替代。TEP 窗口采用一基闭区间，保留全52通道；Wafer 原生标签不传分类器。

### 2.2 中间 Evidence 入口

上传原生 EvidenceFrame（单个、数组或 frames 外壳）或结构化 Evidence，经后端验证和绑定后重新推理。模型 records 由显式 records 适配入口消费。Frame 原值和范围保留；没有媒体附件时仍可计算标量依据，界面显示附件缺失。“下载本次 Evidence”用于这一入口，不是旧 Session 回放。

### 2.3 历史快照的边界

旧 Mock、Demo 快照、`rootlens-runtime`／`rootlens-session-export` Replay、workspace 恢复与浏览器 runtime 构造不再是当前界面入口。历史文件和后端模块可保留，不据此承诺新界面继续兼容。演示清单加载输入并提交真实后端任务，不恢复本地建图或推理。

## 3. 当前三页职责

### `/materials` · 素材管理

知识资料库、文件／URL 导入、真实解析与原文定位、多选 LLM 制作和任务阶段。原始待分析图片／时序／网格到推理页上传，不混作知识资料。

### `/graphs` · 知识图谱

查看候选、机制、联合现象和条件的语义图及来源；持久编辑实体／别名、关系、绑定、条件和规则。完整 v2 包导入默认创建新副本，保存后“投入使用”；启用后可携图前往分析。图的派生投影不是第二份可独立改写的真值。

### `/evidence` · 推理分析

选择原始样本或 Evidence JSON、场景、已启用图及两个明确引擎；跟踪真实任务，查看媒体／变量／网格、候选条件和路径联动；下载本次 Evidence，重新打开服务端“已保存分析”。浏览器只显示后端结果。

右上角连接按钮设置完整 Backend URL。浏览器仅保存服务地址与选择状态，不把 localStorage 草稿当作持久图谱或分析真值。

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

## 5. 已下线的前端能力

当前界面不再提供：

- Mock／Backend 模式切换与旧演示快照读取；
- Session／runtime Replay 和 workspace JSON 恢复；
- 浏览器从 nodes／edges／Evidence 组装 runtime；
- 浏览器本地构图、RCA／what-if 重算；
- 以旧 v1 图包或默认 generic 策略代替明确的 v2 图和所选推理器。

历史 public 快照、旧后端记录与源码资产不因入口移除而删除。原始 records 的后端适配仍可显式使用；`backend/scripts/` 是后端客户端，不属于已移除的浏览器生成路径。

## 6. 文档真值

当前优先阅读顺序：

1. 本文档 `backend-integration-current.md`
2. 根 `README.md`（当前用法）、`rootlens-two-loop-backend-contract.md`（API）与 `rootlens-two-loop-demo-assets.md`（资产）
3. `backend/docs/two-loop-demo.md`（当前演示／恢复）、前后端交付与 `source-projects.md`；其他后端设计／schema 依其版本解读，旧 Web／论文路径只作背景
4. 需要理解历史设计背景时，再看：
   - `module-1-graph-construction.md`
   - `module-2-unified-evidence.md`
   - `module-3-rca-engine.md`
   - `frontend_handoff.md`
   - 其他旧 roadmap / acceptance 文档

历史资料仅作为背景，不再代表当前前端实现边界，也不能替代本次迁移的实际验证结果。
