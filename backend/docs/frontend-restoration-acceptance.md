# 原界面与节点—关系图恢复验收

2026-11-11。**恢复验收通过：原工作台与真实 D3 节点—关系图已恢复，不是换色的树视图。**独立实屏为 `http://127.0.0.1:5186`，Backend 读取 `http://127.0.0.1:8012`。

## 本次恢复的精确基准

- 分支：`codex/restore-original-frontend`，从现有后端完整保留的 `8cf4d0b` 开始。
- 原 UI 基准：`471e1aaa1dabd22fdb0dd7f00590e7e4cf08ab26`。本次不是重新设计三页，不以之前双闭环新外观作为恢复目标。
- 恢复前端组件、路由、布局、主题和交互；允许运行必要的接口薄适配。不回退 backend、数据、模型、工作图或分析快照。
- Demo / Replay 可显示成品快照，但必须与 Backend 在线模式区分。浏览器不恢复本地构图、RCA、what-if 或将 mock 结果冒充在线结果。

## 原壳、原布局和实际网络交互均通过

| 项目 | 原基准的实际形态 | 冻结候选的独立实屏结果 |
| --- | --- | --- |
| 导航与页面框架 | `/` 跳 `/evidence`；页名和顺序为“运行与证据 → 根因与图谱 → 素材与构图”。原 RL/RootLens 顶栏、Arco 左侧导航，侧栏可折叠。 | 1440×1100 独立 context 三页均实际显示；默认入口、顺序和真实折叠/展开一致。 |
| 主题与密度 | `a-config-provider size="small"`；顶栏基准高 50px；侧栏宽 220px、折叠 56px；浅灰蓝背景、白色卡片、紧凑表格/表单。 | 顶栏实测 51px（含 1px 边框），侧栏 220→56→220px；运行/Case/Evidence 四卡和素材表格/右编辑区可辨。 |
| 根因页布局 | 总图谱在主区上方；下方为局部子图、审阅与策展卡；右侧是运行/案例和候选列表。 | 全图、局部图、策展卡和右候选同屏；没有用分层树替代主图。 |
| 真正节点—关系图 | `KnowledgeForceGraph.vue` 使用 D3 `forceSimulation` / `forceLink`、SVG 节点和边；有向边带 `marker-end`。总图、局部图均消费节点/边集合。 | Demo 总图实际 SVG 36 节点、29 关系边，29 边有箭头；局部图 4 节点、3 边。阻断外网仍实际渲染。 |
| 图交互 | 节点和透明边 hit-area 都发出选择事件；节点可拖拽；画布缩放范围 0.36–3.2。 | 点总图 `BottleObject` 触发节点选择；滚轮后实际缩放为 1.283；拖拽中节点 SVG 坐标从 (506.11,335.73) 变为 (527.93,351.31)。 |
| 原 detail/path 联动与数据边界 | `RunPathGraph.vue` 复用同一网络 renderer；候选、路径和节点/边选择联动，原策展卡及推理依据可查看。 | 点击第二候选 Handling damage 更新 path，局部图实点 `ScratchDefect → HAS_PLAUSIBLE_CAUSE → MechanicalContact` 进入边策展详情；后端保存 Root 结果和受控来源故障见下。 |

原总图默认 `show-labels=false`、局部图为 true；不把“主图所有节点常驻标签”额外加成恢复要求。交互细节应按原版工作，不为本轮加入新的设计偏好。

## 基准源码与必要薄适配

均为 `git show 471e1aa:<path>` 的只读核查，不依赖正在改动的工作树：

- `src/App.vue`：原导航、Demo/Backend 切换、后端地址设置、上下文顶栏、220/56 侧栏和 small 控件。
- `src/router/index.ts`：三路由及默认入口 `/evidence`。
- `src/style.css`：原页面、卡片、表格和网格样式；根 `--ocean-header-height:50px`。
- `src/views/GraphExploreView.vue:2275–2398`：原总图/局部图/审阅卡结构；右侧候选区域在 `3327` 行以后。
- `src/components/graphs/KnowledgeForceGraph.vue:692–885`：SVG、箭头 marker、边 hit-area、节点选择、force 模拟、drag 和 zoom。
- `src/components/graphs/RunPathGraph.vue`：局部图直接复用 `KnowledgeForceGraph`，不是另一种树图。
- `src/views/EvidenceManageView.vue:900`、`src/views/MaterialsManageView.vue:840` 起：原运行/证据及素材页模板。
- `src/services/browser-runtime.ts`：基准已仅导入完整 `rootlens-runtime.json` + `unified-graphs.json` 成品回放，并拒绝从 nodes/edges/evidence 临时组装 runtime。

独立直接对照文件内容：`App.vue`、`router/index.ts`、`style.css`、`SectionCardTitle.vue`、`KnowledgeForceGraph.vue`、`RunPathGraph.vue` 六个关键文件均与基准字节相同，记录 `baseline-source-identity.json`。实施 owner 的完整范围记录为 56 文件相同、无原基准文件缺失；原主壳与两个网络图组件不是新写的近似替代。

必要差异仅作用于运行与数据合同：

- 原 D3 v7 CDN loader 改为项目锁定 `d3@7.9.0` 的动态本地模块。原布局、样式和力模拟组件未改，外网阻断条件下实屏验证通过，没有树形 fallback。
- 原视图读取新 `/api/analyses` 保存结果的只读桥，使用“已保存分析”区分 legacy Run；保留当前真实候选、条件和分数语义，不从浏览器计算。该新分析不冒充旧 Session 可导出结果；旧 Replay 仍只导入成品。
- Backend 总图显示“当前登记知识图谱”，局部路径显示“本次保存推理路径”。当前 Studio 图与历史保存路径是不同来源；本次没有把完整历史 knowledge 另投影为总图。
- 当前双闭环 API、模型和数据保留。恢复原界面的范围内，没有把后来的新条件向导或现代曲线/晶圆联动布局塞进旧工作台；新增后端能力仍以其 API 合同为准。

对照读取了 owner 提供的基准渲染 `01-baseline-evidence.png`、`02-baseline-force-graph.png`（`.playwright-mcp/restore-original/`）；后者还在布局启动期，只用于面板布局参照。实际通过依据是原源码和本轮稳定后的实屏、数据与交互，不把后来大改截图当作原版或要求力布局逐像素一致。

## 保存结果与来源切换边界已实测

- 实际打开已保存 RootKGD v2 分析 `f0cca0c7-f7f7-4f1f-8e12-ec8f13296acf`。请求回读 `/api/analyses/{id}`，主图区分当前登记图（实屏 74 节点、80 边）与保存路径（实际 72 个局部 SVG 节点）；侧栏是“已保存分析”。推理依据显示窗口 161–260、两个并列结构分数 0.585447、作者条件核对不参与结构评分，不套用 U/C/A/J 或概率。
- fresh 深链初始化实际有一次旧 `/api/runs/{id}` 探测，最终由真实 `/api/analyses/{id}` 加载。将该旧探测的 404 受控延迟至正确候选出现后返回，未显示旧错误或覆盖正确结果。记录 `saved-deeplink-race-check.json`。
- Demo 图已显示时切 Backend，并仅在独立浏览器将其 API GET 受控响应为 HTTP 503：界面显示后端错误、0 节点/0 边、无候选，未把 Demo 当作在线结果。真实服务没有停机。实施 owner 的迟到跨来源响应检查另已通过。
- 源码消费边界：Demo 的素材解析、构图与模型处理明确拒绝本地执行并引导 Backend；Replay 导入只消费成品，不从 raw nodes/edges/Evidence 组装 runtime。未提交反馈或工作图修改。

只使用现有服务和独立 Chrome/context，阻断外网与所有 API 写请求；独立检查零 JS 错误、零写请求、零模型/LLM 调用，浏览器均已关闭。

## 证据与验证范围

- [原总图、局部图和右侧候选同屏实景](/Users/hhm/code/RootLens/backend/runs/frontend_restoration_review/02-restored-network-layout.png)。同目录有运行与证据 `01-original-evidence.png`、边选择 `03-edge-path-inspector.png`、素材 `04-original-materials.png`、来源错误 `05-backend-unavailable-not-demo.png`、Backend 保存 Root `06-backend-saved-root-network.png`。
- 独立 `actual-ui-check.json` 记录实际 DOM、选择、图几何、请求和推理依据，脚本 `actual-ui-check.mjs`、`actual-ui-resume.mjs`、`actual-ui-root-consume.mjs` 与 `saved-deeplink-race-check.mjs`。证据仅在忽略目录 `backend/runs/frontend_restoration_review/`。
- 实施 owner 对同一冻结候选实际运行原生 Vitest **22 文件 / 109 项通过**及类型/生产构建通过，复用 `.playwright-mcp/restore-original/final-vitest.log`、`final-build.log`。约 796KB 的原 Arco 主 chunk 警告保留。未重复全量前后端矩阵。
- 对照 `8cf4d0b`，后端树差异只有文档；保留后端 **572 passed / 4 既有 optional skips** 的有效证据，不把本次界面恢复写成后端/模型重新验收。

## 已消费的后端非重叠证据

原后端 owner 通过 TestClient 与独立内存 registry 验证了导入、改 label、完整包 PUT/回读、实体 PATCH 与投影边 guard；未连接数据库、未调用模型。完整对象 PUT 保留 value_bindings、feature_registry（含 semantic_role / allowed_values）、patterns、effects、expectations、来源与定位；实体 PATCH 只变目标 label/aliases；v2 派生投影边的单独改写被拒绝且知识未变。备份计数为 2。

原记录为 `/private/tmp/rootlens-restored-frontend-roundtrip.json`，审核已直接读取并保存副本至 `backend/runs/frontend_restoration_review/backend-roundtrip-producer.json`。这是后端 owner 的受控内存测试，不是审核者对 live 图的写入验收；不再重复写默认 KG。完整包保存不是 merge，前端必要薄适配必须保留 GET 的完整对象，不能按旧 TypeScript 子集重建后 PUT。
