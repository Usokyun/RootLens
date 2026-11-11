# RootLens

RootLens 是工业异常分析的知识与证据工作台。Vue 前端保留 **运行与证据、根因与图谱、素材与构图** 三页；模型、Evidence 转换、构图和推理在 Python 后端运行。

## 先跑一个演示

启动服务后打开 `http://127.0.0.1:5174/evidence`。在 **演示案例** 选场景，首次点击 **安装并启用配套图**，然后用默认的 **中间 Evidence → 分级解释溯因** 开始分析。这个入口会从保存的实测观测重新推理，不用 LLM 密钥、模型权重或旧数据库。

| 场景 | 现场值得看什么 |
| --- | --- |
| [MVTec · Bottle 006](backend/data/demo/graded_rca/mvtec/README.md) | 同一个异常 ROI 的三项几何如何支持块状解释；两个工位假设为何仍并列。 |
| [TEP · d04、d05](backend/data/demo/graded_rca/tep/README.md) | 正常窗不推荐；d04 支持反应器补偿，d05 用三个实际观测支持冷凝侧。也可用 RootKGD 看 52 通道图传播。 |
| [WM811K · 248536、31707](backend/data/demo/graded_rca/wafer/README.md) | 近全片获支持；边缘环的正证与反证同时显示，31707 仍待核验。 |

[演示手册](backend/docs/graded-rca-demo.md)提供原始数据和权重的准备命令、真实构图步骤和 CLI。发布资产由 [`backend/data/demo/graded_rca/manifest.json`](backend/data/demo/graded_rca/manifest.json) 统一登记；同一案例可选择原始输入或原生 Evidence。

## 首次安装

准备符合 `package.json` 的 Node.js、uv 和 Python 3.10–3.12：

```bash
# RootLens 根目录
npm ci
cd backend
uv sync --extra dev --frozen
cd ..
```

只运行演示 Evidence 时，基础／开发依赖就够。实跑图像和晶圆需要 `ml`、`vision`；文本构图需要 `llm`；PDF 文本层解析需要 `parsers`。需要全部可选能力时，在 `backend/` 一次同步：

```bash
uv sync --frozen --extra dev --extra llm --extra ml --extra parsers --extra vision
```

日常命令使用 `backend/.venv/`，执行 `uv run --no-sync` 不会重同步掉模型依赖。大权重另外准备。

### 启动数据库与服务

从仓库根目录为**全新空库**执行：

```bash
docker compose -f backend/compose.yaml up -d --wait neo4j postgres
npm run backend:init
npm run backend:check
npm run dev:all
```

已有库只需启动并检查，不重跑 `backend:init`；初始化会拒绝已有应用数据或非空 KG。已预置的本机实例可用 `npm run backend:db:start`、`backend:db:status`、`backend:db:stop`；它们只管理 `backend/runs/local_runtime/` 内的数据库，不管理 Compose，也不设置开机自启。`dev:all` 不启动或初始化数据库；已有服务不要重复启动。

默认前端 5174、API `127.0.0.1:8000`。`npm run dev` 只起前端，`npm run dev:backend` 只起 API。自定义端口要同步两端：

```bash
ROOTLENS_API_PORT=8100 \
VITE_API_BASE_URL=http://127.0.0.1:8100 \
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8100 \
  npm run dev:all
```

页面顶部可修改后端连接。根 `.env.example` 是公开的 Vite 模板；后端私有配置参考 `backend/.env.example`。真实 `.env`、`.env.local` 不提交，密钥不放进 `VITE_` 变量。后端优先级：进程环境 > `backend/.env.local` > `backend/.env` > YAML > 默认值。

## 在三页完成两个闭环

- **素材与构图**：上传文件或登记网址，也可添加演示素材。提取后查看原文片段，勾选同场景及共享资料，发起真实文本构图。构图记录显示实际阶段，完成后打开待启用的工作图。移出素材只影响选材，原文件、提取和历史引用保留，可恢复。
- **根因与图谱**：搜索、缩放和检查有向图。在工作图编辑名称与别名，或用完整 v2 图包调整规则、绑定和分级曲线。导入创建新图；只有显式启用后才用于新分析。编辑不重算保存结果。
- **运行与证据**：上传原图、52 通道序列与正常参考、0/1/2 晶圆网格，或直接上传原生 `EvidenceFrame`。分级引擎比较合法联合分支，展示支持、反证和覆盖。保存详情能从贡献定位实际源边和 ROI、曲线或网格。**下载 Evidence** 后可同图同引擎复算，不重跑测量。

TEP 的 **RootKGD 图传播** 是独立可选推理器，不与分级相容分混算。旧离线演示、旧回放导入、旧版 API 和格式已退役；没有删除本机数据库或历史文件。当前格式的保存分析仍在原运行页查看。

## 开发与文档

- `npm test`、`npm run build`、`npm run backend:test`：前端单测、类型／构建和后端 pytest。
- [`src/doc/backend-integration-current.md`](src/doc/backend-integration-current.md)：当前边界和三页职责。
- [双闭环 API](src/doc/rootlens-two-loop-backend-contract.md)：输入、任务、图包、演示和保存结果。
- [演示手册](backend/docs/graded-rca-demo.md)、[构图和评分设计](src/doc/rootlens-graded-rca-demo-proposal-2026-11-11.md)。
- [来源项目](src/doc/source-projects.md)、[迁移记录](backend/docs/rootlens-monorepo-migration.md)：后端来自 KGTraceVis，保留 `kgtracevis` 包名；历史研究文档不定义当前产品接口。

Neo4j 保存隔离工作图；Postgres 保存素材、图登记、任务及分析快照。仓库只带小型图包、Frame、许可允许的样本和种子；大数据、模型、数据库、运行产物和凭据留在本机。
