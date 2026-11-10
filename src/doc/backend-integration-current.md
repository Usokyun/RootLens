# RootLens 当前集成边界（2026-11-10）

## 1. 当前定位与同仓后端

RootLens 当前是一个 **backend-first 工作台**，Vue 前端与 Python 后端在同一仓库维护：

- 前端 `src/`：上传、浏览、筛选、联动展示、反馈提交、素材与构图工作台 UI。
- 后端 `backend/src/kgtracevis/`：真实的图谱构建、Evidence 处理、RCA 推理、运行记录持久化、反馈与构图相关接口。
- 前后端通过 API 协作；**后端代码放在同仓，不等于浏览器执行后端算法**。
- RootLens **不再**在浏览器端执行图谱构建、Evidence 临时组装或 RCA 本地推理。

### 1.1 本次内置迁移范围

2026-11-10 的迁移以 `/Users/macintosh/TrivalWork/KGTraceVis` 的 Python 后端**当前工作树**为来源，复制至 `/Users/macintosh/TrivalWork/RootLens/backend/`：

- 保留 Python 包名 `kgtracevis` 与 `backend/src/kgtracevis/` 布局。
- 保留 `backend/scripts/`、`backend/configs/`、`backend/data/` 中的小型 KG 种子及 examples、`backend/tests/`、`backend/docs/`、`backend/pyproject.toml` 和 `backend/uv.lock`。
- 不迁入旧 `web/`、`web_legacy/`、论文、实验输出、Git 历史或 agent 历史。
- RootLens 前端 `src/` 保持原位，不改成旧 React 客户端，不以搬目录或覆盖源码的方式丢失未提交 UI 改动。
- 原 KGTraceVis 目录先保留为来源备份；日常运行与后续后端修改以 RootLens 的 `backend/` 为准。

源码内置不代表大型数据、模型权重、外部依赖或每种模型能力已迁移可用。本次已确认的本机迁移事实见下节；不能将有限验证范围扩写为全部测试或模型能力通过。

### 1.2 本次迁移验证摘要（2026-11-10）

本节仅保留集成边界所需摘要；过程与证据见[完整核验记录](../../backend/docs/rootlens-monorepo-migration.md)及[本机机器报告](../../.rootlens-cache/backend-migration-verification.json)（后者 Git 忽略、不随 clone 提供）。以下结果限定于本次迁移，不代表未来每次启动状态：

| 核对项 | 已确认事实 |
| --- | --- |
| 数据库与历史资产 | 既有库已离线复制到 `backend/runs/local_runtime/` 并从新路径启动，数据库 stop/start 与 API 重启后的数据保留核验通过。原有 4 个 run ID、4 条 feedback ID、3 个 material ID 一致，4 份历史输入附件完整保留。 |
| 图谱保留 | 210 个节点、602 条边；迁移未重建图谱、未重导入种子。 |
| 新写入隔离 | 当前迁移后库为 **5 个 Run / 5 条反馈 / 3 份素材**；第 5 组 run 与 `needs_review` 反馈为明确标注的迁移验收测试，应排除出实验统计。该 run 的输入文件仅写入新的 `backend/`，原 KGTraceVis 来源备份未收到新增 run。 |
| 后端与代理链路 | 已用 `RootLens/backend/.venv/` 中的 Python、以 `RootLens/backend/` 为工作目录启动 8000 服务；前端 5174 经代理访问的 8 类接口均返回 HTTP 200。`dev:all` 另在临时前端 5180 / API 8010 端口端到端试启成功，HTML、代理 health / runs 均为 200，停止后两端口均释放；日常默认端口仍为 5174 / 8000。 |
| 安装与初始化保护 | editable 安装及普通 wheel 离线构建成功，不代表从零联网安装或全部模型依赖已具备。`backend:init` 会拒绝已有 PG 应用数据、非空 KG 及未知参数，核验确认既有数据未被覆盖。 |
| 前端构建与测试 | `npm run build` 通过；`npm test`：**17 个文件 / 71 项测试通过**。根 `src/` 的现有 UI 改动保持。 |
| 后端测试基线 | 完整 pytest：**288 passed / 6 failed / 3 skipped**。失败的 pytest node IDs 与原 KGTraceVis 当前工作树基线完全相同，无新增失败，**不是完整测试全通过**。5 个示例在真实 Neo4j 下通过。 |

**核验边界：**Docker Compose 仅做静态配置检查，本机未安装 Docker、未实际运行容器栈；上述结果不是所有模型能力、完整构图发布或工业根因准确率验收。原目录继续保留为备份，不因本次验证而自动授权清理。

## 2. 当前保留的三种数据来源

### 2.1 Backend 模式

- 真实数据与逻辑均来自后端 API。
- 这是当前默认的产品形态。
- 内置后端默认地址仍为 `http://127.0.0.1:8000`；前端配置的 API 地址应与实际服务一致。

### 2.2 Mock / Demo 模式

- 保留为仓库内置的演示快照。
- 仅用于无后端时的 UI 展示与论文演示。
- 不代表前端仍然具备本地图谱构建或本地推理能力。

### 2.3 成品回放（Replay）

当前仅支持两类回放输入：

1. `rootlens-runtime.json` + `unified-graphs.json`
2. `rootlens-session-export.v1`

说明：

- `workspace export` 仍可单独恢复 analyst workspace。
- 不再支持从 `nodes/edges/evidence` 在浏览器端临时组装 runtime。
- 回放消费已生成结果，不触发浏览器端 RCA 或 what-if 重算；本次迁移不扩大 Demo / Replay 边界。

## 3. 当前页面职责

### `/evidence`

- 上传运行文件（backend 模式）
- 查看 run / case / observation
- 导入完整回放资产或 session bundle

### `/graphs`

- 查看总图谱、局部子图、path graph、候选根因、反馈 ledger
- 图谱与 case 选择联动
- backend 模式消费后端返回结果；demo/replay 模式消费快照结果

### `/materials`

- 查看 material library / construction / build / review queue
- 相关构图能力以 **后端接口** 为准
- mock 模式仅保留最小演示数据

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
- Postgres：Evidence case、分析运行记录、反馈、草稿与 review 状态；运行历史与反馈不依赖旧 session JSON 作为真值。
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

以下能力仍从 RootLens **前端**移除，不因同仓后端而恢复：

- 浏览器端从 `nodes.jsonl / edges.jsonl` 或 `nodes.csv / edges.csv` 建图
- 浏览器端从 `evidence*.json / case*.json` 组装 runtime case
- 浏览器端本地 RCA 推理 / what-if 重算
- 前端侧的 graph/evidence/runtime 生成脚本

`backend/scripts/` 是 Python 后端命令入口，不属于上述已下线的前端生成脚本。

## 6. 文档真值

当前优先阅读顺序：

1. 本文档 `backend-integration-current.md`
2. 根 `README.md`（安装、启动和数据说明）与 `source-projects.md`（当前路径及来源索引）
3. `backend/docs/` 中相关后端设计、schema 与接口资料；复制文档中的旧仓路径按当前目录重定位，旧 Web / 论文说明仅作来源背景
4. 需要理解历史设计背景时，再看：
   - `module-1-graph-construction.md`
   - `module-2-unified-evidence.md`
   - `module-3-rca-engine.md`
   - `frontend_handoff.md`
   - 其他旧 roadmap / acceptance 文档

历史资料仅作为背景，不再代表当前前端实现边界，也不能替代本次迁移的实际验证结果。
