# RootLens

RootLens 是面向工业异常分析的 **backend-first 工作台**。自 2026-11-10 的后端内置迁移起，Vue 前端与 Python 后端在同一仓库维护：

- 前端 `src/` 负责上传、浏览、筛选、联动展示、反馈与图谱工坊 UI。
- 后端 `backend/src/kgtracevis/` 负责真实的图谱构建、Evidence 处理、RCA 推理与持久化。
- **同仓不等于浏览器执行推理**：前端仍通过后端 API 获取真实分析结果。

本文说明迁移后的结构与使用方式。核验摘要见 `src/doc/backend-integration-current.md` §1.2，[完整核验记录](backend/docs/rootlens-monorepo-migration.md)包含数据保留、安装、重启、前后端联调与测试结果。前端 build / test 已通过，后端 pytest 仍有与来源基线一致的失败；不代表全部模型或构图发布验收。

## 仓库结构与来源

```text
RootLens/
├── src/                         Vue 前端，原地保留，包含未提交的 UI 改动
│   └── doc/                     当前集成边界与历史设计背景
├── public/                      前端静态资产与演示快照
├── backend/
│   ├── pyproject.toml           Python 包与依赖配置，包名仍为 kgtracevis
│   ├── uv.lock                  后端锁文件
│   ├── src/kgtracevis/          可复用核心逻辑与 FastAPI 服务
│   ├── scripts/                后端命令入口
│   ├── configs/                后端配置
│   ├── data/kg/                小型 KG 种子
│   ├── data/examples/          小型 Evidence / record 示例
│   ├── tests/                  现有 pytest 测试
│   ├── docs/                   后端设计与接口资料
│   ├── compose.yaml            本地 Neo4j / Postgres 启动配置
│   └── runs/local_runtime/     既有本机数据库与运行工具的迁移位置，Git 忽略
├── package.json                 前端与统一开发命令
└── AGENTS.md                    仓库级协作约束
```

后端来源是 `/Users/macintosh/TrivalWork/KGTraceVis` 的 **Python 后端当前工作树**，不是仅取某个已提交版本；复制后保留 `kgtracevis` 包名及上述后端布局。旧 `web/`、`web_legacy/`、论文、实验输出、Git 历史和 agent 历史不迁入。RootLens 的前端 `src/` 不搬家、不用旧 React 前端覆盖，以保留现有未提交 UI 改动。

原 KGTraceVis 目录继续保留为来源备份；后续开发与运行以 **RootLens 的 `backend/`** 为准。本机既有数据库已另行离线复制并从新路径启动，未重建 / 重导入；这不表示所有大型数据、模型权重或外部依赖均已迁移可用，也不授权删除原目录。

## 首次安装

前置条件：Node.js 满足根 `package.json` 的 `engines`，已安装 uv，Python 版本满足 `backend/pyproject.toml`。推荐使用 Docker Compose 启动新数据库；已有本机数据库的处理见下节。

```bash
# 在 RootLens 根目录安装前端依赖
npm ci

# 后端首次标准安装，按锁文件安装基础依赖与 dev extra
cd backend && uv sync --extra dev --frozen
cd ..
```

后端环境位于 `backend/.venv/`。上述安装不等于安装全部可选模型依赖，也不包含大型数据集或模型权重；相关能力仍需按后端配置与实际资产另行确认。

## 配置模板、优先级与 API 端口

- 根目录 `.env.example` 是**公开的 Vite 配置模板**，包括 `VITE_API_BASE_URL` 与 `VITE_BACKEND_PROXY_TARGET`；`VITE_` 配置不是存放数据库密码、API 密钥等私密信息的位置。
- `backend/.env.example` 是**后端私有设置的模板**，用于数据库连接及后端运行设置。模板可入库，但真实凭据只放在被 Git 忽略的 `.env` / `.env.local` 中；根目录与后端目录中的真实环境文件均不提交，也不要直接覆盖既有本机配置。
- 后端配置优先级从高到低为：**进程环境变量 > `backend/.env.local` > `backend/.env` > 配置 YAML > 默认值**。已导出的进程变量不会被环境文件覆盖；排查配置时先检查当前进程环境。
- 自定义 API 端口时，必须同时统一后端 `ROOTLENS_API_PORT`、前端 `VITE_API_BASE_URL` 和 `VITE_BACKEND_PROXY_TARGET` 的目标端口。仅改后端端口不会自动更新 Vite 配置；修改后需重启相关开发进程，并确认页面顶部保存的 Backend 地址也一致。

例如，在确认没有已有开发服务占用端口后，可显式使用自定义 API 端口：

```bash
ROOTLENS_API_PORT=8100 \
VITE_API_BASE_URL=http://127.0.0.1:8100 \
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8100 \
npm run dev:all
```

## 数据库：新库与既有数据分开处理

运行时职责不变：

| 存储 | 职责 |
| --- | --- |
| Neo4j | 运行时知识图谱与图遍历 |
| Postgres | Evidence case、分析运行记录、反馈、草稿与 review 状态 |
| CSV / JSON | 可复现的种子、导入和导出资产，不替代运行时数据库 |

### 新环境 / fresh clone：使用 Docker Compose

fresh clone 不包含被 Git 忽略的本机数据库与运行工具，应走 Compose 分支；不要期待 `backend:db:start` 下载软件或新建数据库。先前迁移验收仅静态检查默认 Compose；后续 MVTec M1 已在独立 `compose.test.yaml` 实跑数据库，记录见 [M1 使用与验收](backend/docs/mvtec-m1-demo.md)，不混用两次范围。以下命令均在 RootLens 根目录执行：

```bash
docker compose -f backend/compose.yaml up -d neo4j postgres

# 等待 Compose 中 Neo4j / Postgres 健康后，仅对首次创建的新库初始化 schema 并导入 KG 种子
npm run backend:init

# 初始化后探活；该检查也会读取应用表
npm run backend:check
```

`backend:check` 会读取应用表计数，fresh 库初始化前返回缺表是预期行为，不应要求它先通过才执行初始化。正确顺序是 **等待 Compose 数据库健康 → `backend:init` → `backend:check`**。

数据库连接参数应与 `backend/compose.yaml`、`backend/configs/` 和实际环境变量保持一致。不要把本机密码或服务凭据写入版本库。**`backend:init` 仅用于新空库，会拒绝已有 PG 应用数据、非空 KG 和未知参数；不是日常启动或既有数据迁移命令。**

### 当前机器既有库：仅管理预置的本机运行环境

仅当 `backend/runs/local_runtime/` 内已经配置好 PG / Neo4j / JDK 时使用本分支。本次当前机器的既有数据库已离线复制到此目录并从新路径启动，迁移核对摘要见真值文档 §1.2；该目录不进入 Git，也不会随 fresh clone 提供。

| 根目录命令 | 职责 |
| --- | --- |
| `npm run backend:db:status` | 查看预置本机数据库的运行状态；不替代 API 所用连接的 `backend:check` |
| `npm run backend:db:start` | 启动该本机运行目录中已配置好的数据库 |
| `npm run backend:db:stop` | 停止该本机运行目录对应的数据库，不作为其他数据库服务的停止入口 |

这些命令**只管理 `backend/runs/local_runtime/` 内已配置好的 PG / Neo4j / JDK 运行环境**，不下载软件、不新建库、不导入种子、不设置开机自启，也不管理 Compose 容器。

确认数据位置、连接配置与备份，且前后端开发服务尚未运行时，启动顺序为：

```bash
npm run backend:db:start
npm run backend:check
npm run dev:all
```

- **已有前后端服务运行时，不要重复执行 `dev:all`**；可只查看数据库状态与探活，再复用现有开发服务。
- 优先保证数据不丢失：原目录先留备份，迁移核对完成前不要删除、覆盖或重建原数据库，也不要删除持久化卷。
- 不要在有历史数据的库上直接运行 `backend:init`，也不要把本机库管理命令当作迁移完成的证明。
- 本机已有实例占用数据库端口时，先确认所属实例并决定复用或切换方案，不要同时启动冲突的 Compose 实例。

## 启动与常用命令

除安装步骤中的 `uv sync` 外，以下 npm 命令都从 RootLens 根目录执行：

| 命令 | 约定职责 |
| --- | --- |
| `npm run dev` | 仅启动前端，兼容原用法；不自动启动后端或数据库 |
| `npm run dev:backend` | 用 `backend/.venv/bin/python` 启动 Python 后端，工作目录为 `backend/`，默认监听 `127.0.0.1:8000` |
| `npm run dev:all` | 同时启动前端与后端；数据库需预先就绪，不自动初始化数据库 |
| `npm run backend:check` | 数据库探活，不代表模型或完整业务流程已通过验证 |
| `npm run backend:init` | 仅新库：初始化 schema 与 KG 种子 |
| `npm run backend:test` | 在 `backend/` 工作目录运行现有 pytest 测试 |
| `npm run backend:db:status` | 查看预置本机数据库状态，仅适用于 `backend/runs/local_runtime/` |
| `npm run backend:db:start` | 启动预置本机数据库，不下载、不新建库 |
| `npm run backend:db:stop` | 停止预置本机数据库，不操作其他服务 |
| `npm run build` | 前端类型检查与生产构建 |
| `npm test` | 前端测试 |
| `npm run preview` | 预览前端构建产物 |

新库完成初始化，或既有数据库确认可用，且没有已运行的前后端开发服务时，可使用：

```bash
npm run dev:all
```

`dev:all` 默认前端端口为 **5174**，API 端口为 **8000**。默认配置下任一端口被占用都会启动失败；脚本不会为抢占端口而杀死其他服务，不要用重复启动替代状态检查。应先确认端口所属进程，复用已有服务，或由操作者明确停止自己管理的旧实例后再启动。

也可在两个终端分别运行 `npm run dev` 与 `npm run dev:backend`，不要与已运行的 `dev:all` 重复启动同一套服务。默认后端地址为 `http://127.0.0.1:8000`，在页面顶部选择 Backend 模式并确认地址；自定义 API 端口须同步上节所列前后端配置。

**这些是按需执行的开发命令，不是开机自启配置。** 项目不配置系统开机 / 登录自动启动；重启后需按所选数据库方案恢复服务，再启动后端与前端，不要把 `dev:all` 理解成数据库守护或自启服务。

## 当前运行模式

- **Backend**：连接真实后端 API，推荐的产品形态。
- **Demo**：使用仓库内置演示快照，无后端时展示 UI，不执行真实建图或 RCA。
- **Replay**：导入已生成的成品回放资产，不在浏览器端重新分析。

当前仅支持两类回放输入：

1. `rootlens-runtime.json` + `unified-graphs.json`
2. `rootlens-session-export.v1`

`workspace export` 仍可单独恢复 analyst workspace。不再支持从 `nodes/edges/evidence` 在浏览器端临时组装 runtime，也不恢复浏览器端 RCA / what-if 重算。

## 统一工业推理 v2（U0–U5）

MVTec、TEP 和 Wafer 现在通过注册 adapter 进入同一强类型 Evidence、公共可执行知识、候选展开／联合条件／代价与证明内核。LLM 从原始公开资料制作知识；完整工作图可持久修改／交换，前端保持三页并增加“推理依据”。旧策略／v1 包保留，显式选择 v2 工作图才启用新路线。

先用随仓库的真实测量 JSON，无需数据库或模型调用：

```bash
cd backend
uv run --no-sync python scripts/run_unified_reasoning.py \
  --knowledge data/kg/unified/bottle-working-graph.v2.json \
  --evidence data/examples/unified/mvtec-chipped.json \
  --output-dir runs/my-unified-demo
```

得到 4 个并列候选、score = −0.25 和实际联合证明。TEP／Wafer 的知识与真实输入也在 `backend/data/`。完整步骤、原始数据／构图／API／回放见 [统一推理使用说明](backend/docs/unified-reasoning.md)，真实失败和公平对照见 [U5 评价](backend/docs/unified-reasoning-u5.md)。

本机新回放文件为 `backend/runs/unified_reasoning/u5_replay/all-scenes-session.json`（3 Run／22 case，不随 Git 提供），经现有导入入口刷新后仍可读取；运行服务沿用 5186／8012 的隔离测试栈。

32 份同输入的平坦对照完全等价；TEP 故障首位仍有明确负结果，不能把统一架构当作准确率改进。最终前端 95 项／build 通过；后端 442 通过、5 项既有失败、1 跳过，详见 U5 文档。

## 前期三场景渐进重构 Demo（M1–M6）

已完成 M1–M6：**实际素材解析 → LLM 可执行知识 → 持久图谱管理 → 三场景测量/条件推理 → 原始图与结果回放**，保留三页布局。

- 支持 TXT/Markdown、CSV、JSON/JSONL、HTML、文本层 PDF（Docling Parse）和实际 URL 获取；片段定位、重解析与失败重试可查看。
- Graphs 页可编辑/保存节点、边、别名、绑定和画像，完整导入/导出工作图包；改图影响新分析，历史 run 保留当时的图和结果。
- 实跑模型为 capsule/STFPM、bottle/PatchCore、WM811K ResNet；TEP 使用完整 52 通道、匹配的正常参考/PCA 和当前图传播。新策略不使用原生标签冒充测量。
- Evidence 页导出完整 Session；现有回放入口直接导入，图片/大时序由 IndexedDB 保存，浏览器不重新推理。

安装 Demo 依赖：`cd backend && uv sync --frozen --extra dev --extra llm --extra ml --extra parsers`。已有库只执行 `backend/scripts/migrate_working_graphs.py --apply` 增量迁移，不执行新库初始化。

本机演示前端 `http://127.0.0.1:5186`、API `http://127.0.0.1:8012` 使用独立测试数据库；日常默认端口不变。最省事的展示文件是 `backend/runs/refactor_m2_m6/all-scenes-session.json`，MVTec 单场景为 `mvtec_final-session.json`；大文件不随 Git 提供。

使用步骤、图谱 JSON/路径、实际正负结果与恢复说明见 [三场景使用与验收](backend/docs/progressive-demo-2026-11-10.md)；任务记录见[渐进执行计划](src/doc/rootlens-refactor-execution-plan-2026-11-10.md)。最终前端 89 项及 build 通过；后端 345 通过、7 项既有失败，详见验收文档。

## 数据与 Git 边界

- 版本控制保留后端源码、脚本、配置模板、测试、文档、`pyproject.toml`、`uv.lock`、小型 `backend/data/kg/` 种子与 `backend/data/examples/` 示例。
- 本地 Python 环境、真实凭据、大型数据、模型权重、中间产物、运行与实验输出、数据库文件及 `backend/runs/local_runtime/` 应被 Git 忽略。
- **忽略 Git 不等于删除数据。** 本机数据库与运行工具迁移须保留原目录备份；未随源码复制的模型和数据资产需单独核对，不因其未入库就视为已迁移或可丢弃。

## 文档

优先阅读：

- `src/doc/backend-integration-current.md` — 当前集成边界、同仓后端与运行模式真值。
- `src/doc/source-projects.md` — 当前运行路径、来源备份与资产索引。
- `backend/docs/` — 后端设计、schema 与服务资料；迁移详情见[完整核验记录](backend/docs/rootlens-monorepo-migration.md)，[本机机器报告](.rootlens-cache/backend-migration-verification.json)被 Git 忽略、不随 clone 提供。旧仓路径与旧 Web / 论文描述按当前边界解读。

历史背景文档：`src/doc/module-1-graph-construction.md`、`src/doc/module-2-unified-evidence.md`、`src/doc/module-3-rca-engine.md`、`src/doc/frontend_handoff.md` 及其余旧 roadmap / acceptance 文档。这些资料不代表当前前端实现边界，也不构成迁移验收结论。
