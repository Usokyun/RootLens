# 当前路径、后端来源与资产索引

这份文档是给后续 LLM/Agent 使用的长期上下文入口，目标是避免反复扫描当前后端与两个上游研究项目。

> **当前边界说明（2026-11-10）**
>
> RootLens 以 `src/doc/backend-integration-current.md` 为真值。当前同仓维护 Vue 前端与内置 Python 后端：真实建图、Evidence 处理与 RCA 推理由 `backend/` 承接，前端仍为 backend-first 工作台，Demo / Replay 边界不变。后端内置不是把推理搬到浏览器，也不代表全部模型能力已迁移可用。

## 1. 当前主要路径

| 对象 | 当前路径 | 职责与使用规则 |
| --- | --- | --- |
| RootLens 仓库 | `/Users/macintosh/TrivalWork/RootLens` | 当前前后端开发与运行根目录 |
| RootLens 前端 | `/Users/macintosh/TrivalWork/RootLens/src` | Vue 工作台，原地保留未提交 UI 改动 |
| RootLens 内置后端 | `/Users/macintosh/TrivalWork/RootLens/backend` | 当前 Python 后端开发、安装、测试与运行目录 |
| 后端 Python 包 | `/Users/macintosh/TrivalWork/RootLens/backend/src/kgtracevis` | 保留包名 `kgtracevis`，承接 schema、adapters、core、service 等实现 |
| KGTraceVis 来源备份 | `/Users/macintosh/TrivalWork/KGTraceVis` | 本次 Python 后端复制的来源；原目录先保留备份，不再作为默认运行目录 |
| TEP_KG 研究来源 | `/Users/macintosh/TrivalWork/TEP_KG` | 工业流程时序根因推理、知识图谱构建、评估与研究资产 |
| 本机数据库与工具位置 | `/Users/macintosh/TrivalWork/RootLens/backend/runs/local_runtime` | 既有数据库已离线复制并从此启动；Git 忽略，原目录保留备份 |

### 1.1 本次 KGTraceVis 后端内置范围

迁移来源是 KGTraceVis 的**当前工作树**，不是仅取 Git HEAD：

- 复制 Python 后端至 RootLens `backend/`，保留 `src/kgtracevis/`、`scripts/`、`configs/`、`data/` 小型种子与 examples、`tests/`、`docs/`、`pyproject.toml`、`uv.lock`。
- 旧 `web/`、`web_legacy/`、论文、实验输出、Git 与 agent 历史不迁入；这些未迁入的来源资产仍应从原目录按需查阅。
- RootLens 前端 `src/` 不搬家，不由来源 React 前端替换。
- 日常后端运行与后续修改以 RootLens `backend/` 为准。既有库离线复制、新路径启动、记录标识／图谱核对及新写入隔离见[迁移验收](../../backend/docs/rootlens-monorepo-migration.md)；不代表全部外部数据、模型权重或模型能力已迁移可用。

### 1.2 历史路径标记

旧资料中的 `/Users/bytedance/my_project/...` 以及 `MVTec/KGTraceVis` 层级是**历史机器与目录布局**，不是当前运行入口。当前 KGTraceVis 来源目录直接位于 `/Users/macintosh/TrivalWork/KGTraceVis`，不需要经过 `MVTec/` 容器目录。

阅读旧文档时，按“RootLens 当前仓库 / 内置 backend / KGTraceVis 来源备份 / TEP_KG 研究来源”区分路径，不要将失效的历史绝对路径复制进运行配置。

## 2. 推荐阅读顺序

1. RootLens `AGENTS.md` 与 `src/doc/backend-integration-current.md`。
2. RootLens `README.md` 与本文档：先确认当前安装启动方式、数据边界和来源路径。
3. 按任务阅读内置 `backend/docs/project_design.md`、`backend/docs/evidence_schema.md` 及其他后端设计 / 接口文档。
4. 进入内置 `backend/src/kgtracevis/`、`backend/configs/`、`backend/scripts/` 与 `backend/tests/` 对照实际实现。
5. 需要追溯来源时，再读 KGTraceVis 来源备份的 `README.md`、`AGENTS.md`、`docs/`；其中旧 Web / Streamlit / 论文布局和旧安装命令不是当前 RootLens 的运行指令。
6. 涉及 TEP 研究语义时，读 TEP_KG 的 `docs/Root-KGD.md`、`docs/kg-build-status.md` 与相关源码。
7. 需要理解历史设计背景时，再读 RootLens：
   - `src/doc/module-1-graph-construction.md`
   - `src/doc/module-2-unified-evidence.md`
   - `src/doc/module-3-rca-engine.md`
   - `src/doc/frontend_handoff.md`
   - 其他旧 roadmap / acceptance 文档

原则：先看当前边界、设计文档和 schema，再看实现；`outputs/`、`runs/`、`data/external/` 是数据与生成物索引，不应先作为项目事实文档。来源备份中的历史规则不覆盖 RootLens 当前边界。

## 3. 内置后端资产与运行入口

本节路径以 RootLens 仓库根目录为基准。

| 路径 | 用途 |
| --- | --- |
| `backend/src/kgtracevis/` | schema、adapters、core、KG construction、service、viz、feedback 等后端核心代码 |
| `backend/scripts/` | KG 构建 / 导入、Evidence 处理、服务启动与其他 Python 命令入口 |
| `backend/configs/` | KG、Neo4j、Postgres、paths 等配置；核对是否仍含来源目录依赖 |
| `backend/data/kg/` | 小型 KG 种子与来源登记资产 |
| `backend/data/examples/` | 小型 Evidence 与 adapter record 示例 |
| `backend/tests/` | 已完成与来源工作树的完整 pytest 基线对照，仍有既有失败，不是全通过；结果见真值文档 §1.2 |
| `backend/docs/project_design.md` | 核心库、scripts 与服务客户端的职责边界 |
| `backend/docs/evidence_schema.md` | 统一 Evidence 结构说明 |
| `backend/docs/rootlens-monorepo-migration.md` | [完整迁移核验记录](../../backend/docs/rootlens-monorepo-migration.md)：数据保留、安装、启停 / 重启、联调与测试基线 |
| `.rootlens-cache/backend-migration-verification.json` | [本机机器报告](../../.rootlens-cache/backend-migration-verification.json)，Git 忽略、不随 clone 提供 |
| `backend/pyproject.toml`、`backend/uv.lock` | Python 包、依赖与可复现安装依据 |
| `backend/compose.yaml` | fresh clone 的 Neo4j / Postgres 启动方案 |
| `.env.example` | 根目录公开 Vite 配置模板，不存放后端凭据 |
| `backend/.env.example` | 后端私有设置模板；真实 `.env` / `.env.local` 不提交 |
| `backend/runs/local_runtime/` | 既有本机数据库与工具迁移位置，Git 忽略 |

首次标准后端安装：在 RootLens 根目录执行 `cd backend && uv sync --extra dev --frozen`，之后回到根目录。

根目录统一命令约定：

- `npm run dev`：仅前端，兼容原用法。
- `npm run dev:backend`：使用 `backend/.venv/bin/python`，工作目录 `backend/`，默认 `127.0.0.1:8000`。
- `npm run dev:all`：前后端一起启动；数据库须提前就绪，不自动初始化。
- `npm run backend:check`：数据库探活。
- `npm run backend:init`：仅新库初始化 schema 与 KG 种子。
- `npm run backend:test`：在 `backend/` 执行现有 pytest。
- `npm run backend:db:status`：查看预置本机数据库运行状态。
- `npm run backend:db:start`：启动预置本机数据库。
- `npm run backend:db:stop`：停止该本机运行目录对应的数据库，不操作其他服务。

上述三个 `backend:db:*` 命令只管理 `backend/runs/local_runtime/` 内已配置好的 PG / Neo4j / JDK，不下载软件、不新建库、不导入种子、不设置开机自启，也不管理 Compose。本次本机数据库已从新路径启动，真实验证范围见真值文档 §1.2，不能据此推断其他机器已具备该运行环境。

- **fresh clone**：走 `docker compose -f backend/compose.yaml up -d neo4j postgres`，等待 Compose 数据库健康后，仅对新库执行 `npm run backend:init`，再执行 `npm run backend:check`。后者会读取应用表计数，初始化前缺表是预期行为，不以 check 先通过作为 init 前置条件。init 会拒绝已有 PG 应用数据、非空 KG 与未知参数；本次 Compose 只做静态配置检查，本机未安装 Docker、未实际运行容器。
- **已有本机运行环境**：确认数据、配置与备份后，按 `npm run backend:db:start` → `npm run backend:check` → `npm run dev:all` 启动；有历史数据的库不要直接初始化，原数据与来源目录先留备份。
- **避免重复启动**：`dev:all` 默认使用前端 5174 / API 8000，默认配置下端口占用会失败，脚本不会为抢占端口杀死其他服务。已有前后端服务时直接复用，不重复执行 `dev:all`。

后端配置优先级为 **进程环境变量 > `backend/.env.local` > `backend/.env` > 配置 YAML > 默认值**。根 `.env.example` 仅为公开 Vite 配置，后端私有设置由 `backend/.env.example` 示范，真实环境文件不提交。自定义 API 端口需同时统一 `ROOTLENS_API_PORT`、`VITE_API_BASE_URL`、`VITE_BACKEND_PROXY_TARGET`，重启相关进程并确认页面 Backend 地址。项目不配置系统开机 / 登录自动启动。

## 4. TEP_KG 研究来源

本节路径均相对于 `/Users/macintosh/TrivalWork/TEP_KG`，是研究与实现来源索引，不表示其资产已全部内置到 RootLens。

### 4.1 关键目录与文件

| 路径 | 用途 |
| --- | --- |
| `src/tep_kg/` | Root-KGD、RBC、传播、图构建与评估主代码 |
| `scripts/` | KG / build / features / evaluation / delivery / RCA 等批处理入口 |
| `docs/Root-KGD.md` | TEP 根因推理方法总结 |
| `docs/kg-build-status.md` | 图谱构建状态与边界 |
| `ontology/` | TEP ontology 与 KG schema 资产 |
| `data/processed/rca/nodes.jsonl`、`data/processed/rca/edges.jsonl` | 历史最终 RCA Graph 节点与边资产，可用于理解图谱来源 |
| `src/tep_kg/root_kgd.py` | 根因排序核心逻辑来源入口 |
| `src/tep_kg/rbc.py` | 变量贡献提取相关逻辑来源入口 |
| `src/tep_kg/graph_build.py`、`src/tep_kg/parsing.py`、`src/tep_kg/ontology.py` | 图谱构建、代码解析与本体校验来源入口 |
| `src/tep_kg/tep_variables.py` | TEP 通道变量映射与实体对齐来源 |
| `pyproject.toml` | 该研究项目自身的依赖分层 |
| `outputs/`、`data/` | 评估输出与 raw / processed / interim / datasets 数据分层，不是当前服务运行真值 |

### 4.2 复用时的边界

- 可追溯 TEP ontology、解析、变量贡献、传播、Root-KGD、评估与图资产的设计来源。
- 不因历史资产可读，就把它们当作当前 API 的直接运行依赖或已迁移资产。
- TEP 当前运行能力及其数据 / 路径依赖以内置后端实现与配置为准；预计算排序结果不是前端本地 RCA 输入。

## 5. KGTraceVis 来源备份与未迁入资产

本节路径均相对于 `/Users/macintosh/TrivalWork/KGTraceVis`。

| 路径 | 用途与当前状态 |
| --- | --- |
| `README.md`、`AGENTS.md` | 追溯来源定位、设计约束与原始运行说明；不替代当前 RootLens 入口 |
| `src/kgtracevis/`、`scripts/`、`configs/`、`data/kg/`、`data/examples/`、`tests/`、`docs/` | 本次后端当前工作树的复制来源；后续优先查内置 backend 对应目录 |
| `web/`、`web_legacy/` | 来源 React 工作台与旧版本，仅作交互参考，不迁入、不替换当前 Vue 前端 |
| `paper/` | 论文源文件、图表与投稿背景，不迁入 |
| `runs/`、`outputs/`、`artifacts/` | 历史运行与实验输出，不随源码迁入，不代表可以删除 |
| 大型数据与模型资产所在本地目录 | 需单独确认位置、备份与可用性，不能从源码迁移推断已迁入 |

仍可复用或追溯的语义包括统一 Evidence schema、adapters / producers、entity linking、consistency、correction、path ranking、反馈与服务 API 设计。可复用逻辑应在内置 `backend/src/kgtracevis/` 中维护，脚本与服务作为客户端，不把核心算法重复实现到前端或脚本中。

## 6. 来源映射与后续操作规则

| 目标 | 当前优先入口 | 历史来源 |
| --- | --- | --- |
| 运行时服务与统一 Evidence | `backend/src/kgtracevis/` 下的 `schema/`、`adapters/`、`core/`、`service/` | KGTraceVis schema / pipeline / API 设计 |
| 图谱构建与来源约束 | 内置后端 KG construction、configs 与 KG 种子 | TEP_KG 解析 / ontology / graph build；KGTraceVis source-to-KG |
| RCA 与解释路径 | 内置后端实际推理实现与配置 | TEP_KG Root-KGD / RBC / propagation；KGTraceVis path ranking |
| 可视分析工作台 | RootLens `src/views/`，通过 API 或快照消费结果 | KGTraceVis 旧 `web/` 仅供交互结构参考 |
| 论文与实验解释 | 经核对的来源资料，不作为运行目录 | KGTraceVis `paper/`、TEP_KG `docs/` 与旧实验记录 |

给后续 Agent 的规则：

1. 修改后端时以 RootLens `backend/` 为工作目录，不继续默认修改或启动 KGTraceVis 来源备份。
2. 调整接口前对齐 schema、core、service 与前端消费契约，不从页面行为倒推或臆造算法。
3. 保留来源、Evidence、confidence 与 review 语义；候选 / plausible 原因不能表述为已验证真实根因。
4. 未迁入、被 Git 忽略和保留备份是不同概念；不得因整理目录而删除既有数据库、大型数据、模型或原来源备份。
5. 历史文档中的模块映射是背景，不自动恢复浏览器建图、Evidence 组装或 RCA / what-if 重算能力。
6. 命令落地、数据库迁移核对、测试结果与模型可用性须分别记录。本次范围见真值文档 §1.2 与完整核验记录：前端 build 及 17 文件 / 71 项测试通过，后端 pytest 无新增失败但不是全通过；Docker 容器未实跑，不把迁移核验推广为所有模型或完整构图发布验收。
