# 双闭环 Demo 独立验收

2026-11-11，Asia/Singapore。审核者未参与本轮设计和实现，只写验收脚本、截图与本报告，不修改产品代码或 Git。

**结论：通过本轮双闭环 Demo 验收，建议交付。** 素材到新图的实际制作、人工修改启用、同图执行，以及原始样本 / Frame 到可追溯解释均已实屏贯通。发现的 6 个 P2 已由原 owner 修复，并独立消费确认；没有仍阻塞关键路径的问题。

## 1. 实际通过的路径

### A：公开资料 → 真实制作 → 修改启用 → 同图推理

独立 Chrome context，1440×900，访问前端 5186 / API 8012。未使用作者浏览器状态。

1. 素材页从公开资料入口实际登记 Emhart 原厂 PDF，解析任务完成；该 Demo 的制作范围是选定的第 13、20 页，不代表覆盖完整手册。
2. 在 GUI 提交唯一一次制作任务 `task_6e68de18e2c74c30b51503b1c851ebe4`。首次 LLM 输出 21 个候选，超出 16 个上限；任务真实记录校验失败，执行唯一一次自动修复后完成。共两次模型调用，没有另建付费重试任务。
3. LLM 阶段实际显示“等待当前阶段完成”，进度轨道为 `is-indeterminate`，没有定时百分比。
4. 新图 `graph_3a24629ac3ce487097424b4983e05398` 在知识图谱页显示中文候选、机制、联合现象及观测条件。用表单修改首候选名称，并将假设成本从 1 改为 1.2；保存请求 HTTP 200，重新读取完整包确认落盘，再“投入使用”。
5. “使用此图分析”承接同一图。普通上传当前玻璃 006 的实际 Frame，产生任务 `task_d7235617e2c14e14b924ed831b5ad1c0`、运行 `ab57734f-589c-4b0b-b978-a28de08ab609`。运行的图 ID 和知识快照均为这张新图，保留改名及成本 1.2。

这次新图推理得到 **证据不足**：原厂 LLM 图要求 `broken_finish` / `chipped_finish`，实际开放外观集合只有 `cracked_or_missing_glass`。页面逐条件展示未知与缺测，没有把新图自动替换成预制图，也没有将局部匹配包装成支持结果。**若要复用当前冻结的 006 Frame，这张新图仍需人工对齐 appearance 绑定或条件；修改别名不会自动完成词汇适配。** 推荐有依据候选的展示使用下文已明确适配的原厂来源图 `graph_7718…`。

证据目录：`backend/runs/two_loop_demo/independent-review/`。

- `03-material-import-parsed.png`、`04-build-confirmation.png`
- `06-llm-indeterminate-top.png`、`ui-build-latest.json`（真实阶段及修复事件）
- `07-fresh-llm-graph.png`、`08-edited-enabled.png`、`ui-edited-graph.json`
- `09-fresh-graph-carried-to-analysis.png`、`10-fresh-graph-analysis-result.png`
- `ui-fresh-graph-analysis.json`

### B：原始 TEP 上传 → RootKGD → 下载 Frame → 普通上传精确复算

GUI 普通上传公开 `sequence_04.dat` 和配套正常参考，选择 1–100、161–260、261–360 三个窗口、已启用 TEP 图和 RootKGD，保留候选数 8。

| 对象 | 实际标识 |
| --- | --- |
| 工作图 | `graph_c6d2a470450e41369de3fc7bdcaaf459` |
| 原始任务 / 运行 | `task_e8b20ed4464940a4b72d6aa8ca0ea4ed` / `8cc46e81-05f8-4273-b94b-cbeae348a31c` |
| Frame 重传任务 / 运行 | `task_43fa3a405bf64af28851fa738a448c37` / `abef6807-925c-4b6d-a68f-5923155c2d0f` |

实际点击“下载本次 Evidence”，将下载文件经普通上传入口重传，固定相同图、引擎及 top-k。三个窗口的完整结果、Frame、52 通道各 100 点曲线 **逐项精确相等**，不只比较首位名字。

实屏看到全部 52 个变量的中文名、均值 z、残差贡献及完整窗口曲线；切换候选后，默认曲线和支持观测随对应通道变化。正常窗口未排名，后两个窗口保留入口温度扰动 / 阀粘滞等并列结果。

独立计算与结构核对：

- 重新计算 16 个实际候选的余弦、覆盖贡献、熵和 `cosine - 0.12*covered_mass - 0.03*entropy`，与返回分数相符；`confidence=null`。
- 42 条解释路径逐边对照该运行知识快照的 canonical 投影，方向和相邻端点连续，来源断言与观测引用存在。
- 所有 52 个贡献输入均进入评分 trace；未展示路径不等于未参与向量比较。
- 只在 Python 内存副本删除当前首候选的出边，该候选随即变为不可评估；没有连接数据库或改写演示默认图。这证实当前图实际决定传播，不依赖固定旧图或 fault ID。

证据：`11-tep-raw-configuration.png`、`12-tep-rootkgd-result.png`、`13-tep-explanation.png`、`14-tep-candidate-linked.png`、`ui-tep-exported-frames.json`、`ui-tep-{raw,frame}-analysis.json`、`review_checks.py`、`independent-computation.json`。

### MVTec：实际原图、ROI、掩码、热图与联合证明

独立从 GUI 保存分析列表打开实际原始运行 `1d116c71-d461-4d9a-852f-eb7f243534c0`，图为 `graph_7718009df1d94a288f99d1e428487679`。本次没有再次发起付费视觉测量。

- 分别操作并实看原图、分割掩码、异常热图和区域裁切。原图 ROI 使用 Frame 的 900×900 坐标平面及相同 bbox，不拿 ROI 裁切坐标画到整图上。
- 页面显示“裂纹或玻璃缺失（开放候选集）”及“拍摄部位未确认”。八个原因保留首位并列，不宣称唯一已验证根因。
- 独立核对 24 条联合证明路径的实际源边连续、联合事实非空；路径来源包含明确的 `declared_demo_heuristic`，说明原厂 Finish 知识向可见玻璃边缘的演示迁移。
- 当前推荐 Frame 与该实际 raw run 的测量字段完全相同，仅受管资产 URI 重定位；没有改写模型观测制造正例。

证据：`16-mvtec-raw-original.png`、`17-mvtec-heatmap.png`、`18-mvtec-roi.png`、`19-mvtec-mask.png`、`consumed-mvtec-raw-analysis.json`、`visual_checks.py`、`visual-computation.json`。

### Wafer：实际下载 → 保留原名上传 → 独立分类与空间解释

从 GUI 推荐样本弹窗点击“原始样本”，发现并修复了下载文件名契约。修复后用全新独立 context 下载，浏览器真实文件名为 `wafer-nearfull-248536.jsonl`，未重命名，直接通过普通上传入口提交。

- 图：`graph_5c3b30cbf4024ab1939c0435a1f676ec`。
- 任务：`task_b0be7887223d474ba176daf9fad2f9ef`；运行：`33196a93-9a78-44e6-a4bd-b3b12023676f`。
- 实际执行 ResNet 与空间测量，得到 38×38 网格、1139 个有效 die / 986 个失效 die。近全片图案得到支持，页面明确它是图案类别，不是已验证制造原因。
- 实际点击中心、区域统计和条件。独立发现并修复区域高亮的半径公式差异；只读同一运行复验，实际 SVG 的全片 / 中心 / 中圈 / 边缘计数分别为 1139/986、172/156、516/433、451/397（有效 / 失效），与 Frame 的四区密度逐项相符，没有重新测量。
- 新任务提交后面板实际出现在视野内（y≈18px），已独立消费任务聚焦修复。

证据：`wafer-download-name.json`、实际同名下载文件、`ui-wafer-raw-task.json`、`ui-wafer-raw-analysis.json`、`20-wafer-task-visible.png`、`21-wafer-raw-grid.png`、`22-wafer-center-linked.png`（修前）、`24-wafer-center-aligned.png`（修后）、`wafer-zone-alignment-{before,after}.json`、`wafer_checks.py`、`wafer-computation.json`。三条实际联合证明路径也对照该图 canonical 源边核验连续。

## 2. 发现的问题与处理

| 严重性 | 复现与影响 | Owner / 状态 |
| --- | --- | --- |
| P2 | 制作按钮位于正文下，提交后仍停在页底，页顶真实阶段不可见。 | frontend，**已修并独立消费**：新任务聚焦面板，Wafer 真实上传时面板 y≈18px；轮询不抢滚动。原反例 `06-llm-indeterminate.png`，修后 `20-wafer-task-visible.png`。 |
| P2 | TEP 正常窗口因正常门控不排名，却提示“没有可评估候选，请检查主体绑定”等配置问题。 | frontend，**已修并独立消费**：同一 Frame 的正常窗口明确“不启动候选排名”；原反例 `15-tep-normal-gate.png`，修后 `23-tep-normal-corrected.png`。 |
| P2 | 原生 Frame 保留 `time_window.sampling_seconds=180`，重传页面却只读取旧统计字段而显示“按原始样本顺序”。 | frontend，**已修并独立消费**：同一保存分析显示“每 180 秒采样”，见 `23-tep-normal-corrected.png`。 |
| P2 | 推荐 Wafer 原始资产是 JSONL，原生上传 chooser 只接受 `.json`。 | frontend，**已修并独立消费**：accept 为 `.json,.jsonl`，普通上传实际成功。 |
| P2 | 推荐 Wafer 原始资产未发 `Content-Disposition`，浏览器实际下载为 `.ndjson`，原样重传会被后端拒绝。 | backend，**已修并独立消费**：以真实文件名发 attachment；新 context 原样下载和上传成功，未加无必要的 ndjson loader。 |
| P2 | 前端区域半径比后端统计多半格，中心高亮 180 个有效 die，但显示统计按 172 个 die 计算。 | frontend，**已修并独立消费**：加实际半径与 0.4 / 0.8 边界回归；审核者直接数同一运行 SVG，四区计数和密度全与 Frame 相符。 |

## 3. 检查范围与真实限制

- 两引擎代码为独立实现：统一引擎执行共同 grounding、联合条件和 U/C/A/J；RootKGD 使用有向衰减传播与完整向量结构比较。两种分数在 UI 中分别说明，不合并成置信概率。
- 旧前端 Mock、浏览器 runtime 和旧兼容入口已成套移除；路由只有素材管理、知识图谱、推理分析。仍在使用的后端算法、原始资产与数据库不是废代码。
- 普通 Frame 的媒体只从受管 registry 关联；源读与既有新 API 测试支持任意 URI 不被当作本机文件读取入口。本审核未读取凭据、未向任意 URL 发探测请求。
- 复用后端 owner 已有恢复、手动 retry、缺媒体与相关测试证据，不重复杀服务或跑完整矩阵。既有完整后端测试仍有 5 个历史资产 / 默认模型断言失败，不称全绿。
- 未独立重跑 MVTec backbone / VLM；这里实际打开并检查作者的原始 run，再独立核对其 Frame、媒体与源边。视觉正常、关闭语义不足、感知漏检和晶圆图案分歧继续作为真实对照，不要求这些输入产生候选。
- 不覆盖工业准确率、正式版本治理、置信校准或未配置对象模型；它们不是本轮 Demo 的承诺。
- 两个独立 Chrome context 的实际操作未产生 `pageerror`，最终记录在 `browser-events.json`。本次没有仍影响上述 Demo 验收的未执行检查。

## 4. 本机测试工具事件的离线核实

依据 `.playwright-mcp/two-loop/tooling-incident.md` 的已有命令输出与本地 `bootstrap.sh`，不重试任何网络事件，不读取实际身份值或凭据：

- 脚本后台启动 `gen_ut_bootstrap` HTTP 上报。可能字段包括 user 身份（JWT username，或 Git email 前缀 / USER 回退）、agent / model、执行与会话来源、临时目录和工作目录；事件 JSON 不含完整 JWT 字段。
- “failed to report”仅表示 curl 返回非零，**不能证明请求未发送或未到达对端**。原始错误与 HTTP 状态缺失，实际传输范围未知。
- 安装输出停在查询版本阶段，未见下载 / 安装成功，目标 `utree` 不存在；两个 span hook 文件当前不存在。现有证据不支持完整凭据或源码被上传的结论。

## 5. 复现入口

验收脚本和结果在 `backend/runs/two_loop_demo/independent-review/`（运行产物，Git 忽略）：

```sh
cd backend
UV_CACHE_DIR=/private/tmp/rootlens-review-uv-cache uv run --no-sync python runs/two_loop_demo/independent-review/review_checks.py
UV_CACHE_DIR=/private/tmp/rootlens-review-uv-cache uv run --no-sync python runs/two_loop_demo/independent-review/visual_checks.py
UV_CACHE_DIR=/private/tmp/rootlens-review-uv-cache uv run --no-sync python runs/two_loop_demo/independent-review/wafer_checks.py
```

`ui-session.mjs` 启动全新 Chrome context，`ui-actions.jsonl` 保留实际操作序列。界面截图以正常桌面尺寸拍摄并实际查看，不以页面能打开或 HTTP 200 代替视觉验收。
