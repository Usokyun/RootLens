# MVTec Bottle：从一份新资料到同图 Evidence 复算

2026-11-11，在真实 RootLens 隔离栈执行，前端 `127.0.0.1:5186`、API `127.0.0.1:8012`。全程使用 Backend 三页，无 API 响应替身。入口与新部署步骤见 [演示手册](two-loop-demo.md)。

## 资料闭环：新材料生成的新图直接投入使用

1. **素材与构图**上传本仓[自著公开 Markdown](../data/demo/two_loop/mvtec/material.md)（1,800 字节），后端保留字节与原文件一致。`task_6a0191c386854e55b8230bf4cc3b84dc` 实际解析出一个片段 `su_ad521dbfdd4da79e`，第 1–21 行。未借用旧 PDF、图或已提取片段。
2. 只勾选该资料，发起 `task_5773d5820a55463eb4f9be35d5766c35`：`visual-region-v2`，最多一次修复，默认不启用。实测 **1 次文本调用**（`deepseek-flash`、5,899 tokens）、0 次修复。事件为解析 → LLM → 校验 → 编译 → 工作图落库 → 完成。
3. 从该任务点 **打开图谱**，得到确切新图 `graph_bc3893b9ae3d4a65bc3c75835ccc57a4`（18 节点、21 关系，初始待启用）。在画布选中实体，名称从 `bottle` 改为 `玻璃瓶 · Bottle`，增加别名 `玻璃容器`、`MVTec Bottle`。完整包和 Neo4j 回读均通过：只改该实体记录，边 ID 和其他知识不变。浏览器导出等于后端完整包；点击 **启用工作图 → 确认启用**。

编译结果保留源文中的两个同区域必需条件：掩码检测网格的面积占比 `≥ 0.10`、包围框长宽比 `≤ 2`。异常检测是前置门控，不能代替两条几何条件。两阈值来源为 `declared_demo_heuristic`；两个候选共享同一机理和现象，均是待区分的假设。现场没有修改阈值或添加外观等价绑定。

## 分析闭环：一次本地测量，原生 Frame 复算一致

在新图点 **用这张图分析**。普通原始上传[同一张公开 Bottle 006 图片](../data/demo/two_loop/mvtec/sample_006.png)（900×900 RGB，中性文件名），显式选择 `bottle` / `patchcore`、关闭外部 ROI 语义。后端输入与上传 PNG 逐字节一致，实际模型记录为本机 Anomalib Bottle PatchCore、CPU，异常门为真。数据集标签没有作为模型或解释器的输入。

| 保存分析 | 入口 | 真实处理 |
| --- | --- | --- |
| [原图 Run](http://127.0.0.1:5186/evidence/runs/e3092c7e-f2e4-43d8-9a72-40a402afb19e) · `task_7a7b338eddd74dab82fd0deb61331723` | 原始 PNG | 运行本地 PatchCore，保存原图、掩码、热图及原图像素 ROI；未调用 VLM。 |
| [Frame Run](http://127.0.0.1:5186/evidence/runs/140d1748-ef44-48fb-ac31-3b628e4705d8) · `task_739990f204c14baf917b0b8f0f061abc` | 从原图 Run 下载的 `evidence-frames.json`，普通上传 | 校验实际 Frame 后复算；没有模型阶段。原图沿用既有附件，未重新生成掩码或热图。 |

两次使用同一 `graph_id`、`unified_abduction` 和 `top_k=8`。实测下载的 `frames` 与原 Run 保存的 Frame 完整相同；再上传后 **canonical 图快照、全部 Frame 和完整 `cases[].results` 逐字段一致**，包含 outcome、候选、名次、分数、联合证明和源路径。任务／Run ID、上传文件名和附件归属可不同。

### 一条可点开的证据链

唯一 Frame 为 `mvtec_bottle_test_unknown_sample_006/query/1`，范围 `scope:1`、主体 `roi:1`。原图坐标 ROI `[98.4375, 73.828125, 734.765625, 643.359375]`（`xyxy`，像素）。图中 ROI 框取自保存范围，不是重新检测。

| 实测 | 保存值 | 本图条件 |
| --- | ---: | --- |
| `detection.anomaly_present` | true | 前置门成立 |
| `geometry.area_ratio` | 0.2284393310546875 | `≥ 0.10` 成立 |
| `geometry.aspect_ratio` | 1.117283950617284 | `≤ 2` 成立 |

原图 Run 的**推理**页中，点面积条件 **在图中高亮**，选择的真实边 ID 为 `signature:large_nonslender_local_anomaly:definition::gate::1::input::signature:large_nonslender_local_anomaly:condition:0`。边属于同一保存路径，并非从当前登记图临时推导。点 **定位同一观测**返回本次面积 `obs:mvtec_bottle_test_unknown_sample_006:region_1:geometry.area_ratio` 和上述原图 ROI。该路径引用的是本轮新材料；“路径附带来源”保持路径级，不写作单边独立来源。6 条保存路径共 40 个边步骤，逐一按原 Neo4j 源边和诊断反向标记核对，端点连续；画布显示的 11 个唯一源边 ID 与保存边集合相同。

结论为 `ambiguous`：**本工位取放接触扰动**与**进入工位前已有局部表面损伤**均排名 1，`U=0`、`C=0`、`A=1`、`J=0.25`、排序分 `−0.25`。这是同一几何对两种假设的相容性，不是概率、工位归因或瓶口判定；外观候选与外观缺陷判定未测。

## 本机证据与范围

- 原任务终态、完整包导出、原下载 JSON、核对结果和实屏在 `backend/runs/mvtec_public_full_chain/`（Git 忽略）。`verification.json` 记录实际请求和各阶段；`public-proof-summary.json` 保留精简的候选／路径标识。
- 可依次查看 `01-public-source-extracted.png`、`03b-completed-source-task-events.png`、`05-public-graph-node-alias-edit.png`、`07-raw-backbone-original-mask-heatmap-roi.png`、`08-raw-geometry-proof.png`、`09-raw-saved-source-path.png`、`10-raw-source-path-to-same-roi.png` 和 `12-frame-backbone-skipped.png`。
- 新图独立启用，旧配套图和旧保存分析未变。没有重启 API、重建库、额外构图、重跑原图或调用远程视觉。随仓 [`evidence.json`](../data/demo/two_loop/mvtec/evidence.json) 与本次浏览器下载逐字节相同，未重写媒体 URI；新实例可从「公开演示样本」绑定随包原图，普通上传依然可复算，但缺原运行时不保证有关联媒体。
