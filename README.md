# RootLens

RootLens 是工业异常分析的 **backend-first 知识与证据工作台**。Vue 前端与 Python 后端同仓维护，当前产品有两个可执行闭环：

1. **资料 → 可用知识**：导入原始资料，实际解析和调用 LLM，自动校验／编译，再由使用者修改并启用工作图。
2. **样本 → 可追溯解释**：原始图片、过程时序或晶圆网格经过真实模型／adapter 生成 Evidence；也可直接上传中间 Evidence，选择推理器，查看候选、条件、来源与原始数据对应。

前端只有 **素材管理 → 知识图谱 → 推理分析** 三页。浏览器不执行构图、Evidence 临时组装或 RCA。演示按钮加载公开输入，不是预制候选答案。

## 从现有演示开始

完整步骤、实际正负结果、许可与恢复命令见 [双闭环演示手册](backend/docs/two-loop-demo.md)。受管清单是 `backend/data/demo/two_loop/manifest.json`，由后端 `/api/demo-library` 提供。

推荐场景为玻璃边缘缺损、TEP 冷却回路和晶圆近全片失效。原始入口真实运行模型；中间入口重新执行推理。玻璃原图拍摄部位未确认，不能称为已确认瓶口；Emhart Finish 指南是演示迁移的知识来源，制造原因仍是待区分的候选。

```bash
cd backend
# 优先复用本机已有资产，不连接数据库或调用模型
uv run --no-sync python scripts/prepare_two_loop_demo.py
# 缺失公开原始文件或权重时才加 --download
uv run --no-sync python scripts/prepare_two_loop_demo.py --download
```

小型知识包、真实 Frame 和来源说明随仓库提供；原始数据、完整受版权约束资料和大权重放在被 Git 忽略的 `backend/runs/two_loop_demo/`，已有模型优先复用原路径。精确大小和分发条件以 manifest 为准。

## 首次安装

需要 PATH 中可用的 uv、满足根 `package.json` engines 的 Node.js，以及 `backend/pyproject.toml` 支持的 Python。使用项目环境，不用全局 Python 代替依赖。

```bash
# RootLens 根目录
npm ci
cd backend
uv sync --extra dev --frozen
```

基础安装只提供基础 API／开发依赖。运行三场景模型、PDF 和 LLM 需安装相应 extras：

```bash
# backend/
uv sync --frozen --extra dev --extra llm --extra ml --extra parsers --extra vision
```

后端环境是 `backend/.venv/`。已安装 ML extras 后，日常使用 `uv run --no-sync`，或继续声明所需 extras，避免同步移除模型依赖。安装不包含大权重，也不保证外部模型服务已配置。

## 数据库：新库与既有数据分开处理

Neo4j 保存隔离工作图；Postgres 保存素材、工作图登记、任务及完整分析快照。CSV／JSON 用于交换与复算，不替代运行时数据库。

### fresh clone：只给新空库初始化

从 RootLens 根目录执行，连接参数与 `backend/compose.yaml` 保持一致：

```bash
docker compose -f backend/compose.yaml up -d neo4j postgres
# 等待两个数据库健康后，仅对新空库执行
npm run backend:init
npm run backend:check
```

`backend:check` 会读取应用表，初始化前缺表是预期行为。顺序是“数据库健康 → 新库 init → check”。**`backend:init` 仅用于新空库**，会拒绝已有 PG 应用数据、非空 KG 及未知参数；不是日常启动或迁移命令。已有库的新工作图／任务能力使用增量表，不重建原数据。

### 已配置的本机数据库

`backend:db:*` 只管理 `backend/runs/local_runtime/` 中预置的 PG／Neo4j／JDK，不下载软件、不新建库、不导入种子、不设置开机自启，也不管理 Compose。

```bash
# 确认运行目录与连接配置，且服务尚未启动
npm run backend:db:start
npm run backend:check
npm run dev:all
```

已有服务不要重复启动。端口占用时先确认所属实例，不为抢占端口杀进程。

## 启动与连接

数据库可用后，从根目录运行：

| 命令 | 用途 |
| --- | --- |
| `npm run dev` | 仅前端，默认 5174 |
| `npm run dev:backend` | 使用 `backend/.venv/bin/python`，工作目录 `backend/`，默认 `127.0.0.1:8000` |
| `npm run dev:all` | 启动前后端；不自动启动或初始化数据库 |
| `npm run backend:check` | 数据库探活，不代表模型／业务验收 |
| `npm run backend:test` | 后端现有 pytest |
| `npm run backend:db:status` / `start` / `stop` | 仅预置 `runs/local_runtime/` 实例 |
| `npm run build` / `npm test` | 前端类型／构建检查和测试 |

页面右上角“后端已连接／未连接”可设置完整服务地址。当前界面没有 Mock／Demo／Replay 模式切换。

自定义端口需同步后端与前端配置，再重启对应进程：

```bash
ROOTLENS_API_PORT=8100 \
VITE_API_BASE_URL=http://127.0.0.1:8100 \
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8100 \
  npm run dev:all
```

根 `.env.example` 是公开 Vite 模板，`backend/.env.example` 是后端私有设置模板。真实 `.env`／`.env.local` 不提交、不直接覆盖；凭据不能放进 `VITE_` 变量。后端优先级为 **进程环境 > `backend/.env.local` > `backend/.env` > YAML > 默认值**。

本轮演示验收使用独立前端 5186／API 8012、PG 55433／Neo4j bolt 57687，与日常默认库分开。开发命令不是开机或登录自启配置；服务恢复见演示手册。

## 在三页完成工作

### 1. 素材管理

上传 TXT／Markdown、CSV、JSON／JSONL、HTML、文本层 PDF，或登记真实网址。检查原文与定位后，选择场景制作知识图谱。任务展示实际解析、LLM、校验、编译和保存阶段；默认允许一次明确的有界修复。没有人工逐边审核门。

### 2. 知识图谱

查看“候选解释 → 联合现象 → 可测条件”的语义图与来源，编辑实体／别名、绑定、条件和规则，保存后点 **投入使用**。ready 只是包已校验保存，enabled 才允许新分析选择。完整 `rootlens-working-graph.v2` 包支持导入／导出；导入默认创建未启用的新副本。

### 3. 推理分析

明确选择原始样本或 Evidence JSON、已启用的同场景图，以及推理器：

- **统一约束推理** `unified_abduction`：三个场景共用类型、作用域、联合条件、冲突／缺失与 U/C/A/J 代价。
- **TEP RootKGD** `tep_rootkgd`：当前图的有向传播与完整 52 维残差贡献结构比较，复用原 RootKGD 传播、余弦／覆盖／熵评分及路径回溯，不使用 fault 标签或固定旧图记忆。

原始 TEP 需要配套正常参考，窗口是一基闭区间。Wafer 接收 0 背景／1 正常／2 失效的原生网格，分类器不接收原生图案标签。图像使用对应对象的模型；缺模型或必要参考时明确失败。

分析保存原始输入、Frame、图快照、候选与解释。每条路径可追到 observation、scope、来源和媒体／曲线。分数不是概率；无匹配、证据不足与同分候选都是有效结果。之后改图不重算历史分析。“下载本次 Evidence”可从中间入口复算；纯标量 Frame 未附媒体时仍能推理，界面会说明缺附件。

## 当前边界与历史资产

新界面不再提供旧 Mock 快照、Session／runtime Replay、workspace JSON 恢复、浏览器本地建图／Evidence 组装／what-if，也不以旧 v1 图或默认 generic 策略驱动新分析。历史后端模块、记录与成品文件保留，不构成新的界面兼容承诺。原始测量 records 可通过明确的后端 adapter 入口使用，不在浏览器中转换。

U0–U5 的结果保留为历史：32 份同输入的独立平坦对照完全等价，TEP 首位有明确错误；当时前端 95 项／build 通过，后端 442 通过／5 项既有失败／1 跳过。统一架构不等于准确率提升。见 [U5 历史验收](backend/docs/unified-reasoning-u5.md)。M1–M6 的迁移、模型接入和旧回放走查见 [渐进重构历史](backend/docs/progressive-demo-2026-11-10.md)，其旧模式入口说明不覆盖当前产品。

## 仓库与数据安全

```text
src/                         Vue 三页工作台
src/doc/                     当前边界、契约与历史设计
backend/src/kgtracevis/       Python 核心、adapter、模型客户端与 FastAPI
backend/scripts/             开发、准备与复算命令
backend/data/demo/two_loop/   小型知识、真实 Frame、manifest 与许可
backend/data/kg/、examples/   其他小型种子与历史示例
backend/runs/                本机原始数据、模型、任务与实验产物（忽略）
backend/runs/local_runtime/  预置本机数据库与工具（忽略）
```

后端来自 KGTraceVis 的 Python 工作树，保留 `kgtracevis` 包名。旧 React `web/`／`web_legacy/` 未迁入；原来源目录和数据库备份继续保留。**Git 忽略不等于删除数据**：未经明确授权和核对，不删除、覆盖或重建数据库，不清理来源备份或持久化卷。

## 文档入口

- [当前集成边界](src/doc/backend-integration-current.md)：当前行为真值，含迁移／U0–U5 历史摘要。
- [双闭环 API](src/doc/rootlens-two-loop-backend-contract.md)：任务、图启用与完整分析合同。
- [演示资产索引](src/doc/rootlens-two-loop-demo-assets.md)与[现场手册](backend/docs/two-loop-demo.md)。
- [前端交付](src/doc/rootlens-two-loop-frontend.md)、[来源项目与资产](src/doc/source-projects.md)、[迁移记录](backend/docs/rootlens-monorepo-migration.md)。

`module-1/2/3`、`frontend_handoff` 与旧 roadmap 是语义来源和历史背景，不覆盖当前边界。
