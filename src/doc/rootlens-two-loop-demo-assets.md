# 双闭环演示资产索引

运行步骤见[现场手册](../../backend/docs/two-loop-demo.md)，接口见[后端契约](rootlens-two-loop-backend-contract.md)。

## 受管清单：每个场景只指向当前完整链

`backend/data/demo/two_loop/manifest.json` 是 `/api/demo-library` 的唯一清单。服务检查白名单资产可用性、按完整知识内容解析 `graph_ref`；前端不猜本机路径或最新图。`expectation` 和 `recommended` 只用于说明，不输入推理。

- **MVTec**：`bottle-rim-break` 对应[原图 006](../../backend/data/demo/two_loop/mvtec/README.md)，同 ROI 使用面积、长短比、离心率。样本为未改像素的 MVTec AD CC BY-NC-SA 4.0 PNG；原始模式为 `bottle`／PatchCore／`semantic_mode=disabled`，不需要 VLM 或正常参考。权重按固定上游版本另行本机取得。
- **TEP**：`tep-sequence-04` 对应[d04 冷却回路](../../backend/data/demo/two_loop/tep/README.md)，正常参考 d00，保存三个实际 52 通道窗口，支持统一约束与 RootKGD。初始严格判别的未匹配结果与人工串级控制修订分开保留。原始和参考 DAT 按固定 Braatz 来源准备；可选窗口附件按 `frame_case_id` 与 `case_asset_id` 精确对应。
- **WM811K**：`wafer-nearfull` 对应[公开表原始行 248536](../../backend/data/demo/two_loop/wafer/README.md)，保留分类器独立输出、区域密度和连通占比。原生标签不进入模型。原始 0/1/2 网格和模型权重不入库；固定版下载后限读取数据构造器并裁样。发布 Frame 是派生观测与资源引用，不包含原始网格。

三个包均有自著 `material.md`、实际保存的 v2 图包和原始运行导出的原生 `{frames:[…]}`。直接上传或选择公开 Evidence 样例会重新推理，不重跑 Backbone。公开入口只绑定存在的受管媒体；缺少原始文件、网格或过程曲线不阻止对已有标量观测推理。普通上传不会按 Frame URI 任意读本机文件。

`uv run --offline --no-sync python scripts/prepare_two_loop_demo.py`（在 `backend/`）核对发布输入，分别报告缺失发布资产和可选本机文件。`--dataset mvtec|tep|wafer --download` 只取选中场景固定的原始输入或权重；不改清单、图、Frame 或数据库。过程附件从同一输入重建时，先和每窗保存的观测核对，再绑定；不覆盖既有分析结果。

## 历史与研究对照

[旧 PDF／ROI、TEP 和晶圆研究验收](../../backend/docs/two-loop-demo-history.md)保留原图、真实失败和对照结论。`backend/data/demo/two_loop/verification-summary.json` 是前期验收摘要，不代表三个当前包的结果。

旧 VLM 版 006 Frame 与旧适配图、[严格 Finish 恢复包](../../backend/data/demo/two_loop/graphs/source-finish-recovered.json)、旧 TEP 和晶圆对照仍供研究回归；不经当前清单分发。当前同 ID 的三条路线各读取当前包，不能混用历史图或帧。用户资料、登记图、历史 Run、媒体和数据库不随目录更新清理。
