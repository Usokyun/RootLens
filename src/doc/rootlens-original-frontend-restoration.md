# 原前端恢复记录（2026-11-11）

> 历史版本记录。当前的工作台和演示以[集成边界](backend-integration-current.md)为准。

## 恢复原界面，不回滚后端或数据

用户要求先还原大幅重做前的界面，并明确知识图谱应是图而不是树。本轮从已推送的 `codex/demo-two-loops@8cf4d0b` 创建本地分支 `codex/restore-original-frontend`，不覆盖原分支，不推送本次还原。

精确界面基准为 `471e1aaa1dabd22fdb0dd7f00590e7e4cf08ab26`。Git历史核实：重大UI重构为 `3b3cf76`，其父 `8052e8b` 的前端源码（排除`src/doc`）、依赖和配置与该基准没有差异。

- 恢复范围：`src/`中的界面、样式、原服务／展示层与测试（不覆盖长期文档），以及对应前端package／lock和测试配置。
- 不整体恢复：`backend/`、根`scripts/`、README、`src/doc/`、数据库、运行输出、模型与素材。当前后端仍是增强后的双闭环服务。
- 原布局与交互：运行与证据、根因与图谱、素材与构图三页；Demo／Backend、成品Replay、总图／局部子图、路径／来源联动。
- 图组件恢复`KnowledgeForceGraph`和`RunPathGraph`，使用实际有向节点／边与共享节点，不改成层级树。
- App、全局style、router、main和两个图组件与基准内容相同。D3仅由CDN loader改为项目内锁定`d3@7.9.0`动态模块；既有依赖版本不升级。

## 当前API与原界面的衔接

原接口仍存在：`/api/dashboard/bootstrap`、`/api/runs`及detail／upload／artifacts、`/api/kg/studio`、`/api/kg/materials`和工作图完整包接口。已对现有8012做只读HTTP核对，未发写请求或模型调用。

图谱使用`GET /api/kg/studio?graph_id=...`：当前Bottle工作图实际返回57节点、80边。节点为`graph_nodes`（`node_id/label/node_type/scenario/aliases/description`），边为`graph_edges`（`edge_id/head/tail/relation/source/evidence/weight/confidence/...`）。`normalized_graph`不是后端字段，后端也没有`/api/pipeline`路由；浏览器只做展示结构映射。

新双闭环结果位于`/api/analyses`与`/api/analyses/{id}`，不是旧`/api/runs`。其case包含`results/evidence_frames`，不能未经映射就当成旧`RunDetail`。恢复版保留旧上传合同；完整新任务、RootKGD选择和原生Frame复算继续由[后端契约](rootlens-two-loop-backend-contract.md)定义。回放或展示映射不会重新执行推理，也不能改写原分数／候选／图快照。

`analysis-snapshot-view.ts`在运行列表与原详情中只读展示这些结果，标题以“已保存分析”区分；每个结果按case ID配对Frame，不把首帧复用到其他窗口／ROI。原rank、score、cost、null confidence、观测与连续源路径保留。RootKGD显示结构分数，不套用统一逻辑代价公式；完整原始字段与working graph snapshot保留，不筛成旧接口子集。

Backend总图仍使用当前登记工作图的Studio投影；历史局部路径／推理依据来自保存结果，不称为已恢复历史全图。新分析的旧Session导出明确提示不支持；legacy Run的导出／回放合同保留。

Demo模式默认读取成品；只有Backend连接真实服务。Session／runtime导入仍只接受成品回放，不从nodes／edges／Evidence临时构造runtime。

Demo中的素材处理／构图动作明确拒绝，不伪造执行成功；Backend连接错误时清除旧来源结果并显示错误，迟到的前一来源响应不能覆盖当前模式选择。

## 完整包保存不会丢掉新知识字段

原`savePackage`读取完整GET包、编辑原JSON并直接PUT，不按旧TypeScript接口筛字段。PUT是完整替换，不是部分合并；必须保留完整包，不能从studio投影或旧字段子集重建。

原策展入口已有v2保护：打开完整JSON并明确拒绝单独改写投影边，不假报保存成功。后端也拒绝typed图的投影edge upsert；简单实体PATCH只修改对应label／aliases。

新增核对使用FastAPI TestClient与独立内存registry／repository，没有连接数据库：

1. 构造含`value_bindings`、`semantic_role`、`allowed_values`和非空来源ID／定位字段的受控v2包。
2. 导入、GET完整包、只改一个label、PUT并重新读取；除该label外整包逐字段相同。
3. 确认所有绑定、feature metadata、期待／effect／pattern与source assertions保留。
4. 实体PATCH仅改变目标label／aliases；typed投影edge提交被拒绝且知识不变。

两次合法保存各产生一份临时备份；没有修改live默认图、分析、Frame或模型。证据为本机`/private/tmp/rootlens-restored-frontend-roundtrip.json`。无需后端修复或服务重载。

## 服务与既有验证

API仍为`http://127.0.0.1:8012`，专用launchd作业PID10919、health=ok；恢复前端`http://127.0.0.1:5186/graphs`返回HTTP200，Vite PID54921。最终轻量检查没有重载服务，独立测试数据库与原有数据保持原状态。

后端源码未修改，复用572 passed／4既有optional skipped：3项指定隔离数据库opt-in，1项未安装的原TEP_KG对照。没有新增skip／xfail，不为还原界面重跑模型或LLM。

后端日常入口、手动作业恢复、日志与停止方法见[后端运行记录](../../backend/docs/two-loop-backend.md)。不把开发服务设置成登录／开机自启。

## 本轮前端有效检查

- 原生`npm test`：22文件／109项通过，原基准95项保留；`npm run build`类型与生产构建通过。
- 原全量Arco主chunk约796KB的>500KB警告保留，不为消除它改动原视觉体系。
- 源码内容对照：56文件与基准相同、无基准文件缺失；16项必要薄改与4个新增桥接／loader文件。对照为直接内容比较，未使用哈希。
- 前端owner实际检查原三页、总图36节点／29边、局部图、节点选择／拖拽、wheel缩放、候选→路径→来源联动、Root保存分数`0.5854474293642782`及来源错误／迟到响应。外网和写请求阻断，项目内D3仍可渲染，未执行模型或LLM。
- 证据目录为`.playwright-mcp/restore-original/`：`baseline-source-comparison.json`、`restored-ui-check.json`、`final-readonly-check.json`、`final-vitest.log`、`final-build.log`与`09-baseline-current-comparison.png`。完整UI交付见[前端记录](rootlens-two-loop-frontend.md#原版-ui-恢复2026-11-11)。

[独立实屏验收](../../backend/docs/frontend-restoration-acceptance.md)已通过。原三页与220／56px侧栏、真实29条箭头边、拖拽／缩放、局部源边与候选联动均实际操作验证；阻断外网时图仍可用，受控503不残留Demo成功结果。保存RootKGD显示原结构分数及正确语义，并明确分开“当前登记知识图谱”和“本次保存推理路径”。fresh深链仍可能先探测一次旧Run接口，实测迟到的404不覆盖正确加载的保存分析。独立证据在`backend/runs/frontend_restoration_review/`（Git忽略），没有写请求或模型调用。
