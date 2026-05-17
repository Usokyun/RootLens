# RootLens 当前集成边界（2026-05-17）

## 1. 当前定位

RootLens 当前是一个 **backend-first 的前端工作台**：

- 前端职责：上传、浏览、筛选、联动展示、反馈提交、素材与构图工作台 UI。
- 后端职责：真实的图谱构建、Evidence 处理、RCA 推理、运行记录持久化、反馈与构图相关接口。
- RootLens **不再**在浏览器端执行图谱构建、Evidence 临时组装或 RCA 本地推理。

## 2. 当前保留的三种数据来源

### 2.1 Backend 模式

- 真实数据与逻辑均来自后端 API。
- 这是当前默认的产品形态。

### 2.2 Mock / Demo 模式

- 保留为仓库内置的演示快照。
- 仅用于无后端时的 UI 展示与论文演示。
- 不代表前端仍然具备本地图谱构建或本地推理能力。

### 2.3 成品回放

当前仅支持两类回放输入：

1. `rootlens-runtime.json` + `unified-graphs.json`
2. `rootlens-session-export.v1`

说明：

- `workspace export` 仍可单独恢复 analyst workspace。
- 不再支持从 `nodes/edges/evidence` 在浏览器端临时组装 runtime。

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

## 4. 已下线能力

以下能力已经从 RootLens 前端仓库移除：

- 浏览器端从 `nodes.jsonl / edges.jsonl` 或 `nodes.csv / edges.csv` 建图
- 浏览器端从 `evidence*.json / case*.json` 组装 runtime case
- 浏览器端本地 RCA 推理 / what-if 重算
- 前端仓库内的 graph/evidence/runtime 生成脚本

## 5. 文档真值

当前优先阅读顺序：

1. 本文档 `backend-integration-current.md`
2. `source-projects.md`
3. 需要理解历史设计背景时，再看：
   - `module-1-graph-construction.md`
   - `module-2-unified-evidence.md`
   - `module-3-rca-engine.md`
   - `frontend_handoff.md`
   - 其他 roadmap / acceptance 文档

上述历史文档仅作为背景，不再代表当前前端实现边界。
