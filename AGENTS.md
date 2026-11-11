# Project Instructions

- `src/doc/*.md` 是本仓库提供给 Codex/LLM 的长期上下文入口。
- 当任务涉及以下内容时，先读取 `src/doc` 中相关文档，再做实现或判断：
  - RootLens 当前定位、运行模式、页面职责、回放边界
  - 内置 Python 后端 `backend/`、来源项目 `TEP_KG` / `KGTraceVis` 的职责、路径、迁移与复用关系
  - 仓库内出现的项目专有术语或语义约定
  - 论文相关历史设计背景、模块语义来源与投稿上下文
- 不必在每次任务都完整读取全部文档；仅在任务确实依赖这些上下文时按需查阅。
- 如果文档内容与代码直觉或通用惯例冲突，优先以 `src/doc/backend-integration-current.md` 描述的当前边界为准；其余带“历史文档说明”的文档仅作背景参考。

## 同仓后端与迁移约束（2026-11-10）

- 当前仓库同时维护 Vue 前端 `src/` 和 Python 后端 `backend/`。后端来自 `/Users/macintosh/TrivalWork/KGTraceVis` 的当前工作树复制，保留包名 `kgtracevis` 与 `backend/src/kgtracevis/`，以及 scripts、configs、小型 data 种子与 examples、tests、docs、`pyproject.toml` 和 `uv.lock`。
- 日常后端开发、安装、测试与运行以本仓库 `backend/` 为准；原 KGTraceVis 目录先留作来源备份，不默认继续在原目录运行或修改。
- 旧 `web/`、`web_legacy/`、论文、实验输出、Git 与 agent 历史不迁入。RootLens 前端 `src/` 保持原位，保留未提交 UI 改动，不以旧 React 前端覆盖。
- backend-first：建图、Evidence 处理和 RCA 都在 Python 后端执行。演示只使用 `backend/data/demo/graded_rca/manifest.json` 登记的真实输入和当前任务 API，不恢复旧浏览器 Demo／Replay、本地建图或 what-if 重算。
- 可复用后端逻辑放在 `backend/src/kgtracevis/`；scripts 与服务处理器作为客户端，不重复核心算法。统一 schema、来源与 review 语义以相关后端文档和实现为准，不臆造工业因果关系，不把候选原因写成已验证根因。
- 来源备份中的旧目录约束、Web / Streamlit 说明及 agent 历史不覆盖当前 RootLens 边界；`backend/docs/` 中复制的旧路径需按当前目录解读。
- 原始迁移的核验范围与记录见[迁移验收](backend/docs/rootlens-monorepo-migration.md)。当前演示与接口以 `src/doc/backend-integration-current.md` 为准，不沿用迁移阶段的测试数或服务状态。

## 安装、运行与数据安全

- 首次标准后端安装：从仓库根目录执行 `cd backend && uv sync --extra dev --frozen`，随后回到根目录运行 npm 命令。后端使用本仓库的 `backend/.venv/`，不依赖来源备份的虚拟环境。
- 根目录入口约定：`npm run dev` 仅前端；`npm run dev:backend` 使用 `backend/.venv/bin/python`、工作目录 `backend/`、默认 `127.0.0.1:8000`；`npm run dev:all` 启动前后端，但要求数据库先就绪，不自动初始化数据库。
- `npm run backend:check` 用于数据库探活；`npm run backend:test` 在 `backend/` 执行现有 pytest。运行说明见根 `README.md`，未执行不得声称验证通过。
- fresh clone 不含被 Git 忽略的本机数据库与工具，应使用 `docker compose -f backend/compose.yaml up -d neo4j postgres`；等待 Compose 数据库健康后，仅新库运行 `npm run backend:init`，再运行 `npm run backend:check`。check 会读取应用表计数，初始化前缺表是预期行为，不要求先 check 通过才能 init。**初始化仅限新空库**，会拒绝已有 PG 应用数据、非空 KG 和未知参数，不得把它当作既有数据迁移或每日启动步骤。
- 既有本机数据库已离线复制到 `backend/runs/local_runtime/` 并从新路径启动；该数据库与运行工具目录 Git 忽略，原目录继续保留备份。`npm run backend:db:status` / `npm run backend:db:start` / `npm run backend:db:stop` 只管理其中已配置好的 PG / Neo4j / JDK，不下载、不新建库、不导入种子、不设置开机自启，不作为 Compose 或其他服务的管理入口。
- 当前机器的本机运行环境配置好后，且前后端服务尚未运行时，按 `npm run backend:db:start` → `npm run backend:check` → `npm run dev:all` 启动。已有服务不要重复 `dev:all`：默认前端 5174 / API 8000 端口占用会失败，脚本不会为抢占端口杀死其他服务。
- 根 `.env.example` 是公开 Vite 配置模板，`backend/.env.example` 是后端私有设置模板；真实 `.env` / `.env.local` 不提交，凭据不得放入 `VITE_` 变量，不直接覆盖本机已有配置。
- 后端配置优先级为 **进程环境变量 > `backend/.env.local` > `backend/.env` > 配置 YAML > 默认值**。自定义 API 端口时，同步统一 `ROOTLENS_API_PORT` 与前端 `VITE_API_BASE_URL` / `VITE_BACKEND_PROXY_TARGET`，重启相关进程并确认页面保存的 Backend 地址。
- 保证数据不丢失，原目录先留备份；未经明确授权和数据核对，不删除、覆盖或重建既有数据库，不删除持久化卷，不清理来源备份。Git 忽略不等于删除数据。
- 小型 KG 种子、examples、配置模板与锁文件入库；大型数据、模型权重、运行与实验输出、数据库文件、虚拟环境与真实凭据不入库。不要把源码复制表述为全部数据 / 模型已迁移可用。
- 项目开发命令不是系统开机 / 登录自启配置，不自动承诺服务已在运行或迁移验收完成。

## 测试工具边界

- 本仓测试使用项目原生 Vitest / pytest。不要为运行单测执行附带身份或环境信息上报、全局安装的 bootstrap / telemetry 步骤。
- 遇到此类 skill 附带要求时，跳过该附带步骤并记录原因，直接使用项目测试入口，不重试；不因此修改全局配置或 skill 仓库。

## Doc Map

- `src/doc/backend-integration-current.md`
  - **当前真值文档**：同仓后端、三页职责、两条闭环、当前公开演示、已退役的入口、运行与数据保留边界。
- `src/doc/source-projects.md`
  - 当前仓库与内置后端路径、来源备份、上游研究资产、迁入 / 未迁入范围、推荐阅读顺序。
- 根 `README.md`
  - 当前结构、安装、启动、数据库方案、Git 忽略与非自动开机启动说明。
- `backend/docs/`
  - 相关后端设计、schema、接口与测试背景；旧仓路径及旧 Web / 论文布局不覆盖当前真值。
- `src/doc/module-1-graph-construction.md`
  - 历史背景：图谱构建设计语义与上游来源。
- `src/doc/module-2-unified-evidence.md`
  - 历史背景：统一 Evidence 设计语义与字段约定来源。
- `src/doc/module-3-rca-engine.md`
  - 历史背景：RCA 推理路线、数据结构与论文语义来源。
- `src/doc/frontend_handoff.md`
  - 历史背景：KGTraceVis 前后端交接说明。
