# 双闭环演示资产索引

运行步骤见[现场手册](../../backend/docs/two-loop-demo.md)，接口见[后端契约](rootlens-two-loop-backend-contract.md)。

## 受管清单：只从发布资产读取

`backend/data/demo/two_loop/manifest.json` 是 `/api/demo-library` 的唯一清单。服务按实际文件可用性补白名单 `download_url`，以完整知识内容解析 `graph_ref`；前端不猜本机路径或最新工作图。`expectation`、`recommended` 仅用于选样和解释，不输入模型或排名。

- MVTec `bottle` 组只含 `bottle-rim-break`（原图 006）。[公开包](../../backend/data/demo/two_loop/mvtec/README.md)含自著短 Markdown、未改像素的原图、实际制作后保存的 v2 工作图包和同图原始运行导出的原生 `{frames:[…]}`。原图与派生测量按 MVTec AD CC BY-NC-SA 4.0 分发。
- 原始模式使用 `bottle`／PatchCore／`semantic_mode=disabled`，不需要视觉服务或正常参考。权重固定上游版本，只留本机忽略目录，准备方法和限制见[原图入口](../../backend/docs/two-loop-demo.md#走原图先准备固定的-bottle-patchcore)。模型说明不是应用下载资产。
- `input_variant=evidence` 从实际观测重新推理，不读预制候选、不调用 Backbone；白名单样例可以绑定受管原图。普通上传只处理原生 Frame，不从旧 URI 任意读取机器文件。热图、掩膜随各次原始运行保存，不复制另一份到仓库。
- TEP 仍以 `tep-sequence-04` 为推荐，保留正常与扰动对照、52 通道和双引擎。晶圆仍以 `wafer-nearfull` 为推荐，保留正常和分类分歧；原生标签不送进分类器。两组清单与既有 Frame 保持原样。来源许可与可用模式见各资产字段。

`uv run --offline --no-sync python scripts/prepare_two_loop_demo.py --dataset mvtec`（在 `backend/`）只核对已发布资产，不接数据库、不调用模型。`--download` 是可选本机模型准备，不改清单或导出 Frame。针对 TEP／晶圆的同一入口只恢复所需本地配套文件；TEP 恢复窗口和正常模型时先核对已保存观测，不覆写它们。

## 历史与研究对照

[旧 PDF／ROI、TEP 和晶圆研究验收](../../backend/docs/two-loop-demo-history.md)保留旧运行、真实失败和对照结果。`data/demo/two_loop/verification-summary.json` 仍是前期验收摘要，不是当前 MVTec 的复算结果。

- 旧 006 VLM Frame `data/demo/two_loop/evidence/bottle-rim-break.json`、对应旧图、原始来源和适配记录保留给研究回归；不在受管清单。它与当前同 ID 样例的 `mvtec/evidence.json` 是两次独立采集，不能互换。
- [严格 Finish 恢复包](../../backend/data/demo/two_loop/graphs/source-finish-recovered.json)与[原始失败、离线语义收紧、正式执行的来源记录](../../backend/data/demo/two_loop/graphs/source-finish-recovered.provenance.json)仍用于展示真实证据不足，不替换当前配套图。
- 旧 U5 Frame、旧测试图和 TEP 原蓝图都保留。五个不再被清单、运行或研究使用的旧 MVTec 重复导出已退出工作树；精确副本可由 `2e98a28` 取得，历史完整分析仍在本地归档。用户资料、登记图、历史 Run、媒体和数据库未被清理。
