# RootLens Backend

RootLens 的 Python / FastAPI 后端，来源于 KGTraceVis。包名继续保留 `kgtracevis`，避免破坏 API、导入路径和既有数据语义。这里是实际源码，不是原仓库的软链接或 Git 子模块。

## 目录

```text
backend/
├── src/kgtracevis/     # 可复用算法、schema、图谱与 API 服务
│   ├── core/          # 分析 pipeline
│   ├── service/       # FastAPI、运行记录、素材与反馈持久化
│   ├── kg/            # 图谱访问、链接、一致性与路径处理
│   ├── adapters/      # 多数据集 Evidence 适配
│   └── workflows/     # 含已移植的 TEP Root-KGD 流程
├── configs/           # 可提交的默认配置与配置示例
├── data/              # 小型 KG 种子、示例与参考数据
├── scripts/           # 开发命令、初始化、导入与实验 CLI
├── tests/             # 原有后端回归测试
├── docs/              # 后端设计、schema 与来源文档
├── user_study/        # 后端工作流使用的小型配置
├── pyproject.toml     # Python 3.10–3.12 依赖
├── uv.lock            # 锁定依赖
├── compose.yaml       # 可选的容器化后端与数据库
├── runs/              # 忽略：上传文件、运行数据、本机数据库
├── outputs/           # 忽略：实验输出
└── artifacts/         # 忽略：模型及生成产物
```

## 开发

首次安装：在本目录执行 `uv sync --extra dev --frozen`。若需要覆盖连接设置，将 `.env.example` 复制为 `.env`，不要提交真实凭据。

回到 RootLens 根目录：

```bash
npm run backend:check       # 检查真实数据库及表结构（只读）
npm run dev:backend         # 仅 API，默认 127.0.0.1:8000
npm run dev:all             # API + Vue 前端，默认前端 5174
npm run backend:test        # 后端 pytest；支持追加 -- -q 等参数
```

工作目录统一为 `backend/`，Run、素材和反馈使用同一个 Postgres 配置。优先级为进程环境变量、`.env.local`、`.env`、本地 `configs/*.yaml`、示例配置。Vite 代理默认也是 8000；非默认端口要同时调整前端地址和代理目标。

### 数据库

新机器建议使用容器（需要事先安装 Docker）：

```bash
docker compose -f backend/compose.yaml up -d neo4j postgres
npm run backend:init       # 仅新库：初始化 schema 并导入种子 KG
```

**已有数据不要为了启动而重跑初始化或导入。** `backend:init` 会拒绝已有应用记录或非空 Neo4j KG 的数据库，不自动覆盖；未知参数（如误传 `--dry-run`）也会直接报错，而不是忽略后继续写入。 本机已迁移的 Postgres / Neo4j / JDK 位于忽略目录 `backend/runs/local_runtime/`，可从根目录使用：

```bash
npm run backend:db:status
npm run backend:db:start
npm run backend:db:stop
```

这些命令只管理本仓库内已准备好的数据库，不下载软件、不创建新库、不设置开机自启。数据库与 `.venv` 不会通过 Git 分发；新环境按容器或自行安装的数据库配置即可。

## 来源和迁移边界

见 [UPSTREAM.md](UPSTREAM.md) 和 [本次迁移核验记录](docs/rootlens-monorepo-migration.md)。只迁入后端需要的代码、配置、文档、种子和测试，未迁入旧 React 前端、论文排版、历史实验输出、原 Git/Agent 元数据。现有模型推理能力仍取决于额外依赖、模型权重和数据是否齐备；同仓不等于浏览器侧推理，也不表示已完成模型或工业根因准确率验证。
