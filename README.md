# RootLens

RootLens 是工业异常分析的 **backend-first 知识与证据工作台**。当前前端按用户要求恢复到 `471e1aa` 的原布局与交互基础：**运行与证据 → 根因与图谱 → 素材与构图**，知识图谱恢复有向力导向网络，不以层级树代替。

`codex/restore-original-frontend` 保留 `8cf4d0b` 的后端、数据库、知识与分析结果，并在原三页接通两个可执行闭环：

1. **资料 → 可用知识**：导入原始资料，实际解析和调用 LLM，自动校验／编译，再由使用者修改并启用工作图。
2. **样本 → 可追溯解释**：原始图片、过程时序或晶圆网格经过真实模型／adapter 生成 Evidence；也可直接上传中间 Evidence，选择推理器，查看候选、条件、来源与原始数据对应。

页面顶部可切换 **Demo / Backend**；Demo 显示成品快照，Backend 连接真实服务。浏览器不执行构图、Evidence 临时组装或 RCA。当前操作与验收见[原界面双闭环记录](src/doc/rootlens-restored-two-loops.md)。

## 演示数据与后端复演

完整步骤、实际正负结果、许可与恢复命令见 [双闭环演示手册](backend/docs/two-loop-demo.md)。受管清单是 `backend/data/demo/two_loop/manifest.json`，由后端 `/api/demo-library` 提供。

推荐场景为玻璃边缘缺损、TEP 冷却回路和晶圆近全片失效。原始入口真实运行模型；中间入口重新执行推理。玻璃原图拍摄部位未确认，不能称为已确认瓶口；Emhart Finish 指南是演示迁移的知识来源，制造原因仍是待区分的候选。

Demo 模式读取原有成品快照。要真实复演，在 Backend 的“新建分析”中选择受管公开样本和原始／中间入口，再点击“开始分析”。配套图只填入隐式默认；明确携带或手选的图保留，切换需用户确认。缺配套图时说明状态，不按最新同场景图猜测，也不自动导图。图像原始样例如使用外部ROI模型会明示；手动图像上传默认关闭外部ROI语义。

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

页面顶部选择 **Backend** 后，可通过“修改后端地址”设置完整服务地址；Demo 模式与成品 Replay 不会发起新模型推理。

自定义端口需同步后端与前端配置，再重启对应进程：

```bash
ROOTLENS_API_PORT=8100 \
VITE_API_BASE_URL=http://127.0.0.1:8100 \
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8100 \
  npm run dev:all
```

根 `.env.example` 是公开 Vite 模板，`backend/.env.example` 是后端私有设置模板。真实 `.env`／`.env.local` 不提交、不直接覆盖；凭据不能放进 `VITE_` 变量。后端优先级为 **进程环境 > `backend/.env.local` > `backend/.env` > YAML > 默认值**。

本轮演示验收使用独立前端 5186／API 8012、PG 55433／Neo4j bolt 57687，与日常默认库分开。开发命令不是开机或登录自启配置；服务恢复见演示手册。

## 在原三页完成两个闭环

### 1. 运行与证据 · `/evidence`

保留原运行列表、case／observation 浏览与成品回放。Backend 点 **新建分析**，选择原图、52通道过程文件＋正常参考、晶圆网格，或上传原生EvidenceFrame；选择已启用的同场景工作图及推理器后提交真实任务。原 Evidence／records／image 仍可经“旧接口上传”使用。

成功后载入该次“已保存分析”。原候选、每Frame、分数和源路径保留；**下载本次 Evidence** 后可直接作为中间入口复算。新分析的旧Session导出不支持，原Run导出保持。之后改图不重算历史；无匹配、证据不足与同分候选均是有效结果，分数不是概率。

### 2. 根因与图谱 · `/graphs`

恢复原总图、局部子图、方向箭头、路径高亮和来源／反馈联动。Backend 工作图来自 `/api/kg/studio?graph_id=...` 的真实节点与边，不把共享节点复制成树枝。

总图读取当前登记图；历史局部路径与推理依据读取该次保存结果，两者不是同一份历史全图。D3改为项目内锁定依赖，不再依赖现场CDN。

完整工作图包支持导入、导出与保存。v2 知识在完整 JSON 中修改，保留未展示的绑定、有限值、语义角色、规则与来源，不从投影边重建。保存后点 **投入使用**，再点 **用这张图分析**，以确切图ID打开新建分析，不沿用历史结果或换成另一张图。独立候选条件向导仍以保留的后端API为准。

### 3. 素材与构图 · `/materials`

保留原素材库、文件／URL 登记和片段定位。勾选资料后在原 Build Recipe 点 **生成构图**，读取实际解析、LLM、校验和保存阶段。默认每次任务最多两个文本请求（首次＋一次修复）；失败停住，重试须明确点击。完成后点 **打开并编辑此图**，沿原图谱页保存并启用。制作成功不等于当前观测足以诊断。

## 保留的后端推理能力

- **统一约束推理** `unified_abduction`：三个场景共用类型、作用域、联合条件、冲突／缺失与 U/C/A/J 代价。
- **TEP RootKGD** `tep_rootkgd`：当前图的有向传播与完整 52 维残差贡献结构比较，复用原 RootKGD 传播、余弦／覆盖／熵评分及路径回溯，不使用 fault 标签或固定旧图记忆。当前 v2 投影按 host／稳定通道合并重复逻辑期待，避免重复条件制造传播票；真正新增通道或 effect 仍可改变结构。它不执行条件阈值／AND-OR／期待模式的惩罚。

原始 TEP 需要配套正常参考，窗口是一基闭区间。Wafer 接收 0 背景／1 正常／2 失效的原生网格，分类器不接收原生图案标签。图像使用对应对象的模型；缺模型或必要参考时明确失败。

分析 API 保存原始输入、Frame、图快照、候选与解释；每条路径可追到 observation、scope、来源和媒体／曲线。Frame 导出可从中间入口复算，纯标量 Frame 未附媒体时仍能推理。

“本次知识诊断”区分条件真／假／未知、排名资格、同签名候选组与成本先验；读取本次保存的知识，不用当前图重写历史。当前4个TEP×RootKGD v2已完成API／CLI精确复演，并验证d04原始输入→下载Frame→普通上传的三窗口结果及52曲线一致；原17项验证作为历史保留，其余13项统一引擎未重复运行。版本、实际正负结果与记录位置见演示手册。

## 当前边界与历史资产

Demo 成品快照、Session／runtime Replay 与原页面工作区已随原前端恢复；回放不执行新的推理。仍不支持从 nodes／edges／Evidence 在浏览器临时组装 runtime，也不执行本地构图或 RCA／what-if。Backend 保留旧接口与新双闭环接口各自的合同，不能用旧 run 外壳冒充重算的新结果。

U0–U5 的结果保留为历史：32 份同输入的独立平坦对照完全等价，TEP 首位有明确错误；当时前端 95 项／build 通过，后端 442 通过／5 项既有失败／1 跳过。统一架构不等于准确率提升。见 [U5 历史验收](backend/docs/unified-reasoning-u5.md)。M1–M6 的迁移、模型接入和旧回放走查见 [渐进重构历史](backend/docs/progressive-demo-2026-11-10.md)，其旧模式入口说明不覆盖当前产品。

本轮前端原生Vitest **28文件／147项通过**，类型与生产构建通过；保留Arco主chunk大小警告。后端原生pytest **575 passed／4 既有可选跳过**：3项隔离数据库 opt-in 和1项未安装的原 TEP_KG 对照。正式 `npm run backend:test` 使用现有后端 `.venv`，不会同步移除模型依赖。实跑见[原界面双闭环记录](src/doc/rootlens-restored-two-loops.md)；`f5e93aa` 的22文件／109项和 `8cf4d0b` 的18文件／97项按各自历史候选保留。

## 仓库与数据安全

```text
src/                         恢复原布局的 Vue 三页前端
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
- [原界面双闭环记录](src/doc/rootlens-restored-two-loops.md)与[实际操作验收](backend/docs/original-ui-loop-acceptance.md)：当前操作、真实运行和保留限制。
- [前端还原记录](src/doc/rootlens-original-frontend-restoration.md)与[独立实屏验收](backend/docs/frontend-restoration-acceptance.md)：原布局恢复阶段的兼容与检查。
- [双闭环历史独立验收](backend/docs/two-loop-acceptance.md)与[重构前端交付](src/doc/rootlens-two-loop-frontend.md)：还原前的界面验收、后端消费证据和保留限制。
- [来源项目与资产](src/doc/source-projects.md)、[迁移记录](backend/docs/rootlens-monorepo-migration.md)。

`module-1/2/3`、`frontend_handoff` 与旧 roadmap 是语义来源和历史背景，不覆盖当前边界。
