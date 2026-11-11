# MVTec Bottle 006：偏心率进入联合形态条件

2026-11-11，在真实隔离栈（前端 `127.0.0.1:5186`、API `127.0.0.1:8012`）完成素材、图谱、运行三个页面的操作，无 API 响应替身。部署和入口见 [演示手册](two-loop-demo.md)；公开的实际输入和可机读验收在 [MVTec 演示包](../data/demo/two_loop/mvtec/README.md)。

## 资料闭环：编译三个同一区域的条件

1. 在「素材与构图」上传[本仓自著的 Markdown](../data/demo/two_loop/mvtec/material.md)（1,981 字节），回读与提交文件逐字节一致。新素材 `demo_mvtec_bottle_006_eccentricity_20261111` 经 `task_bd66d326fec04464808e439c3e402dec` 提取出 `su_c1df540751c17bbc`（第 1–17 行）。只选择这份材料。
2. 构图任务 `task_f2d0fc99637943558fd1826d538c3b4e` 采用 `visual-region-v2`，最多一次修复、默认不启用。实际 **1 次文本调用**（`deepseek-flash`，6,018 tokens），0 次修复。事件为解析 → LLM → 校验 → 编译 → 工作图落库 → 完成。新图 [`graph_94f38a08cc644cfabe075ebbabfff0f9`](http://127.0.0.1:5186/graphs?graph=graph_94f38a08cc644cfabe075ebbabfff0f9) 有 20 节点、23 条关系、6 条来源断言。
3. 从完成任务点「打开图谱」，在确切新图上把实体 `bottle` 改为「玻璃瓶 · Bottle（单区域）」，更新别名为「玻璃容器」和「MVTec Bottle（检测对象）」。完整包和 Neo4j 回读确认只改该实体行，源边 ID、条件和来源不变。浏览器导出内容与服务完整包相同，再明确确认启用。

可执行图以异常门控为前置，并在 `same_subject_same_scope` 中联合面积、包围框长短比、主轴离心率；三个阈值都标为 `declared_demo_heuristic`。近方形包围框也可以包住一条对角狭带，离心率补充了像素分布的主轴伸展信息。它是掩膜几何，不是工艺证据或瓶身部位。

## 分析闭环：本机模型一次，原生 Evidence 复算

从已启用的新图打开「用这张图分析」，普通上传[公开的 006 原图](../data/demo/two_loop/mvtec/sample_006.png)（900 × 900 RGB、中性文件名），选 `bottle` / `patchcore`、关闭 ROI 外观语义。上传和实际留存输入的 PNG 字节一致；本机模型记录为 Anomalib Bottle PatchCore、CPU。图像文件名和数据集目录标签不用于条件。

| 保存分析 | 输入和行为 |
| --- | --- |
| [原图 Run](http://127.0.0.1:5186/evidence/runs/f5cc2e9a-22eb-431a-9981-8502e176892d) · `task_69c71cdcd41e40f6ad2623e173d7f5ee` | 普通 PNG 上传；实际执行 PatchCore，保存原图、掩膜、热图和原图像素 ROI。VLM 关闭。 |
| [Frame Run](http://127.0.0.1:5186/evidence/runs/e465b4ff-89e3-4243-b9f6-6d71608c9961) · `task_b198553fbaab4a8d98be9ed8f72cf7cc` | 从该原图 Run 下载原生 Evidence 后普通上传；跳过 Backbone，不重新生成热图或掩膜。 |

两次使用同一图、`unified_abduction`、`top_k=8`。下载与原 Run 保存的 Frame 相同；重新上传后图快照、Frame 和完整 `cases[].results` **逐字段相同**，含候选、代价、条件和源路径。随仓图和 Evidence 分别为此次浏览器实际导出、下载的原字节，不重写本机相对媒体引用。新实例可以从受管公开演示入口关联原图。

### 同一区域的四项真值

唯一 Frame 为 `mvtec_bottle_test_unknown_sample_006/query/1`，范围 `scope:1`、主体 `roi:1`。原图像素框 `[98.4375, 73.828125, 734.765625, 643.359375]`（`xyxy`）取自该范围。

| 特征 | 实际保存值 | 参与方式 |
| --- | ---: | --- |
| `detection.anomaly_present` | true | 只作前置门 |
| `geometry.area_ratio` | 0.2284393310546875 | ≥ 0.10，成立 |
| `geometry.aspect_ratio` | 1.117283950617284 | ≤ 2，成立 |
| `geometry.eccentricity` | 0.7969506925604166 | ≤ 0.90，成立 |
| `geometry.component_count`、`geometry.morphology` | 1、`spot` | 不入条件。单连通 ROI 固定为 1；粗形态基于长短比和离心率，未重复使用。 |
| `geometry.location`、范围像素框 | `surface`、见上 | 定位图像证据。网格位置不是瓶口或其他解剖部位。 |
| `appearance.semantic_candidates`、`appearance.defect_present` | 缺测 | VLM 未运行，不补词、不作反证。 |

原图 Run 在「推理」点离心率条件的「在图中高亮」，准确命中保存源边 `signature:large_nonslender_local_anomaly:definition::gate::1::input::signature:large_nonslender_local_anomaly:condition:2`；再点「定位同一观测」返回 `obs:mvtec_bottle_test_unknown_sample_006:region_1:geometry.eccentricity` 和同一原图 ROI。保存的 8 条路径涉及 12 条不同源边；界面源边集合与该 Run 保存集合一致。路径级来源指向新 Markdown，不借用当前登记图。

结果为 `ambiguous`：「本工位取放接触扰动」与「进入工位前已有局部表面损伤」均为第 1 名，未解释 U = 0、冲突 C = 0、假设 A = 1、代价 J = 0.25，排序分 −0.25。没有观测能区分这两种工艺解释。

## 反事实：严格榜为空，仍可追溯部分支持

对原生 Frame 的**副本**只改 `/frames/0/observations/3/value/number`：`0.7969506925604166 → 0.94`。其余字段逐项相同；`0.94` 也低于本机单 ROI 粗形态分桶的 `0.95` 偏心门，不改 `spot` 标签。原生 Frame、规则阈值和实测 Run 不变。

| 同图同解释器 | 实测 Frame | 单值对照 |
| --- | --- | --- |
| 异常门／面积／长短比 | 成立 | 仍成立 |
| 离心率条件／联合形态 | 成立／成立 | 不成立／不成立 |
| 完整候选／保存支持路径 | 2 个并列／8 条 | 0 个入榜／0 条 |
| 待验证 | 无 | 2 个，每个 2 项诊断支持、1 项分支反证 |
| 结果 | `ambiguous` | `insufficient_evidence` |

早期严格对照的结果为 `no_match`；两候选的严格评估仍是 U = 1、C = 0.25、A = 1、J = 1.75。新引擎保留该评估和空主榜，独立记录有实测支持的**待验证分支**：同一区域的三个可判诊断量只计一次，面积、长短比符合，离心率是这条分支的反证，异常门控不计入诊断分母。唯一依赖组内 U = 1/3、C = 1/3、A = 1，待验证代价 **J = 1.25**。两种代价口径不同。离心率反证不等于推翻工艺原因，异常门仍为真。

隔离端口 8025 只提交一次明确标为「非实测」的副本（`task_e8b49532118348c688ea72361207fea2`，Run `8909ee8c-5f1c-49e4-aa76-e8ba42b5401d`）。浏览器显示完整榜 0 项、待验证 2 项，展开可看规则条件、可判分母、支持、反证和权重；点离心率反证定位到同一保存观测和既有原图 ROI。图谱无可绘制源边。没有模型调用。重放原值的完整结果与真实 raw Run 相同。

定向回归还用已冻结 Wafer Frame 做单值对照：最大失效连通占比改为 0.50，四项同父晶圆的观测符合、一项反证；完整榜为空，近全片失效只在待验证（J = 0.85）。将同父范围改成同一精确子范围后，分支不合法，待验证也消失。复验：

```bash
cd backend
uv run --offline --no-sync pytest -q tests/test_public_mvtec_geometry_demo.py tests/test_unified_tentative.py
```

## 实屏与历史

- 终态、图导出、原生下载、反事实记录与真实实屏保存在 `backend/runs/mvtec_eccentricity_full_chain/`（Git 忽略）。可依次查看 `01-public-source-extracted.png`、`03b-completed-source-task-events.png`、`05-public-graph-node-alias-edit.png`、`07-raw-backbone-original-mask-heatmap-roi.png`、`08-raw-geometry-proof.png`、`09-raw-saved-source-path.png`、`10-raw-source-path-to-same-roi.png` 和 `12-frame-backbone-skipped.png`。
- 待验证 API 回读和实屏在 `backend/runs/tentative_evidence_acceptance/`（Git 忽略）：`02-tentative-branch-calculation.png`、`03-tentative-observation-exact-id.png` 和 `verification.json`。公开摘要只保存数值和标识，不把合成 Frame 当作可发布实测。
- 旧的两条件配套图 `graph_bc3893b9ae3d4a65bc3c75835ccc57a4` 仍启用，旧 [原图 Run](http://127.0.0.1:5186/evidence/runs/e3092c7e-f2e4-43d8-9a72-40a402afb19e) 与历史图均逐字段回读未变；旧结果是两个并列候选、6 条路径。旧公开包和完整报告可从提交 `b691e2b` 读取，例如 `git show b691e2b:backend/docs/mvtec-public-demo-acceptance.md`。
