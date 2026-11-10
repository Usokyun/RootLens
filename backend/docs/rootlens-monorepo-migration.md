# RootLens 同仓后端迁移记录

迁移与核验日期：2026-11-10（Asia/Shanghai）。这是本次验证记录，不代表未来每次启动状态或完整模型验收。

## 结构与来源

- 后端源码：`backend/src/kgtracevis/`，保持原 Python 包名及 HTTP/schema 语义。
- CLI、配置、测试、小型 KG 种子、Evidence 示例与后端设计文档分别位于 `scripts/`、`configs/`、`tests/`、`data/`、`docs/`。
- 本次复制来源工作树的实际文件，包含当时未提交的后端修复与测试，不只复制 Git HEAD。
- 核对来源目录与新目录：108 个 Python 核心文件、52 个测试文件、13 个配置文件、33 个小型数据文件无缺失、内容一致。
- 没有迁入旧 React UI、论文排版、实验输出、嵌套 `.git`、Agent 历史。没有修改已有 RootLens UI 工作。
- 旧 `/Users/macintosh/TrivalWork/KGTraceVis` 保留为迁移前来源/数据备份，不再是日常运行目录。不要同时启动新旧目录的数据库，也不要未经核对清理旧目录。

## 现有本机数据

停止旧 API、Neo4j 和 Postgres 后，离线复制原数据库、JDK/Neo4j 本机运行工具、Run 输入文件和素材文件到忽略目录 `backend/runs/`。没有重建数据库或重导入 KG。

复制前后核对：

| 内容 | 迁移前 | 迁移后（验收写入前） |
|---|---:|---:|
| analysis runs | 4 | 4 |
| evidence cases | 2 | 2 |
| feedback records | 4 | 4 |
| source materials | 3 | 3 |
| runtime KG nodes | 210 | 210 |
| runtime KG relationships | 602 | 602 |

历史 Run、反馈、素材 ID 完全一致；四份历史 Run 输入附件均经新 API 下载并与新目录文件逐字节核对。

迁移后额外创建了一个明确标注为联调测试的 Run `acce5279-c6a0-46c0-a3ee-8dcdd6ba2fc7` 和一条 `needs_review` 反馈，验证新后端的上传、推理、保存与读回。**这两条是测试记录，不是专家认可或准确率评价，应排除出实验统计。** 它们只写入新运行目录，来源备份没有收到新增 Run。此后新库包含 5 个 Run、5 条反馈，素材仍为 3 份。

已验证本机数据库停止→启动及 API 重启后的数据保留。数据库、`.venv`、私有配置与本机 JDK/Neo4j 不纳入 Git；源码提交体积约 4.3 MB，不含这些运行依赖。

## 启动与安装核验

- API 的解释器与工作目录均位于 `RootLens/backend/`，不依赖原 KGTraceVis checkout。
- 根命令：`dev:backend`、`dev:all`、`backend:check`、`backend:test`、`backend:db:start/stop/status`。
- `dev:all` 在临时前端 5180 / API 8010 端口实测：HTML、代理 health 和 Run 列表成功，停止后两个子监听均退出。日常默认端口仍是前端 5174、API 8000。
- 新 `.venv` 复用了已有依赖文件；随后离线构建并重新安装 editable 包，普通 wheel 也构建成功，包含 API、SQL schema 和 CLI scripts。没有进行模型权重下载或从零联网安装。
- 前后端私有/公开配置分开：根 `.env.example` 仅放 Vite 公开地址，`backend/.env.example` 是后端连接配置模板。
- `backend:init` 仅适用于新空库：已有应用记录或非空 Neo4j KG 会被拒绝；未知参数也会被拒绝，避免把 `--dry-run` 误当有效参数而实际初始化。

## 验证结果

- 前端 `npm run build` 通过；`npm test`：17 个文件、71 项测试通过。
- 后端完整 pytest：288 通过、6 失败、3 跳过；与来源工作树基线的失败 node ID 完全一致，**无新增失败，不是全通过**。
- 五个 checked-in Evidence 示例通过，运行时 KG 为真实 Neo4j。
- 新 API 经前端代理的 health、bootstrap、runs、KG Studio、materials、construction builds、drafts、feedback 均返回 200。这不是完整构图发布、原始模型推理或工业根因准确率验收。
- 新增开发脚本通过 Ruff 与 Node 语法检查；Docker Compose 文件已静态校验，本机未安装 Docker，因此没有实际启动容器栈。

来源已有失败（本次未改动算法或测试来消除）：

- `tests/test_service_api.py::test_case_detail_returns_analysis_for_real_outputs`
- `tests/test_service_api.py::test_case_index_includes_checked_in_and_real_output_cases`
- `tests/test_service_api.py::test_image_upload_mode_defaults_to_unknown_label_when_unspecified`
- `tests/test_service_api.py::test_mvtec_model_preset_route_reports_available_default`
- `tests/test_service_api.py::test_upload_run_prepares_visual_evidence_artifacts`
- `tests/test_wafer_user_study_workflow.py::test_prepare_wafer_user_study_can_persist_a_wafer_run_with_testing_store`

## 本机证据位置

- `.rootlens-cache/backend-migration-verification.json`：数据保留、接口、新 Run/反馈、启动与重启检查。
- `.rootlens-cache/backend-migration-manifest.json`、`backend-source-integrity.json`：来源指纹。
- `.rootlens-cache/backend-source-pytest.log`、`backend-target-pytest.log`：原/新目录基线。
- `backend/runs/local_runtime/api-process.json` 与 `api.log`：新后端进程信息和日志。

以上本机证据被 Git 忽略；此文档只记录可复查的迁移范围和当次结果。
