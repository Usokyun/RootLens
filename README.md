# RootLens

RootLens 是一个面向工业异常分析的前端工作台，当前以 **backend-first** 方式运行：

- 前端负责上传、浏览、筛选、联动展示、反馈与图谱工坊 UI
- 后端负责真实的图谱构建、Evidence 处理、RCA 推理与持久化

## 当前运行模式

- **Backend**：连接真实后端 API（推荐）
- **Demo**：使用仓库内置的演示快照
- **Replay**：导入成品回放资产

当前仅支持两类回放输入：

1. `rootlens-runtime.json` + `unified-graphs.json`
2. `rootlens-session-export.v1`

不再支持从 `nodes/edges/evidence` 在浏览器端临时组装 runtime。

## 开发

```bash
npm ci
npm run dev
```

构建：

```bash
npm run build
```

测试：

```bash
npm test
```

默认后端地址为 `http://127.0.0.1:8081`，可在页面顶部切换数据源模式并修改地址。

## 文档

优先阅读：

- `src/doc/backend-integration-current.md` — 当前有效的集成边界与运行模式
- `src/doc/source-projects.md` — 上游项目路径、资产索引与阅读顺序

历史背景文档：

- `src/doc/module-1-graph-construction.md`
- `src/doc/module-2-unified-evidence.md`
- `src/doc/module-3-rca-engine.md`
- `src/doc/frontend_handoff.md`
- 其余 roadmap / acceptance 文档

上述历史文档仅作背景参考，不代表当前前端实现边界。
