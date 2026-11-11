# 原界面双闭环：实际操作验收

2026-11-11，在 `codex/restore-original-frontend`、隔离服务 `5186 → 8012` 上验证。原素材库、运行页和有向 D3 总图／局部网络仍在原位置。进入 **Backend** 模式后，可直接打开下列本机结果。

## 从公开资料制作并启用一张新图

1. 在「素材与构图」只勾选已登记、已解析的 **Emhart 原厂缺陷指南 PDF**（`demo_bottle_bottle-manufacturer-pdf`）。复用 PDF 第 13、20 页的两个真实片段（3,008 字符），并非本轮重新上传这份 PDF。
2. 一次真实「生成构图」提交 `enable_when_ready=false`、`max_repairs=1`。任务 `task_d31016f07e86436aa98c20959b722be2` 保存了 8 条解析、模型、校验、编译、图就绪及完成事件；实际 **1 次文本 LLM、8,543 tokens、0 次修复**。完整保留 21 个候选（软建议 16、硬上限 32），编译出 112 节点、164 边，初始未启用。
3. 在完成卡点「打开并编辑此图」，进入[该工作图](http://127.0.0.1:5186/graphs?graph=graph_fb6f04b8867c4cdb96ed92fc465bf28b)。在原完整包抽屉，仅给 `bottle` 对象加入别名 `玻璃容器（原页验收别名）`；保存后回读的完整包仅此一处变化。未保存时不能启用；点「投入使用」后，「用这张图分析」将同一图 ID 明确带入原运行页弹窗，不选另一张图或旧运行。

原上传入口另验一次：通过「上传 / 注册素材」登记 272 字节的公开 PDF 第 13 页短摘（`audit_restored_20261111_emhart_short_excerpt`），「解析资料」任务 `task_6d507c9cd83247e5920da0e594d509f1` 完成，在 Chunks 页读回 1 个实际片段。该短摘未勾入构图，不覆盖旧资料，不调用模型。

## 原图和下载的 Evidence 得到同一结果

在该来源图上普通上传公开瓶图 `sample_006.png`，选择 PatchCore、关闭 ROI 外观语义（实际请求 `semantic_mode=disabled`）、统一条件溯因、`top_k=8`。后端本地测量检测到异常并生成原图／遮罩／热图及区域几何。`spot` 满足形态条件，但未测得 `broken_finish` 或 `chipped_finish` 所需的细外观语义；两个联合现象仍未知，正确保存 **证据不足、0 排名、无推理路径**。

从运行页进入图谱页，再返回原分析与同一 Frame；点「下载本次 Evidence」，普通上传实际下载文件，用同一图、推理器和 `top_k` 复算。原生 Frame 内容与首次保存一致，两个运行的完整 `cases[].results` 逐项精确相同。复算不跑模型；能关联原图，遮罩和热图留在首次原图运行的附件中。

| 原页入口 | 实际保存结果 |
| --- | --- |
| 原图 → 本地测量 | [运行与证据](http://127.0.0.1:5186/evidence?run_id=3d2bd6d2-af6e-4804-a4a8-8c37e99f9271&source=analysis-v2&case_id=mvtec_bottle_test_unknown_sample_006%2Fquery%2F1) · `task_7473d79efd03499381159dbf47986bf8` |
| 下载 Frame → 普通上传 | [复算结果](http://127.0.0.1:5186/evidence?run_id=f4e24f5e-47d6-48c0-bef3-10751bb467cf&source=analysis-v2&case_id=mvtec_bottle_test_unknown_sample_006%2Fquery%2F1) · `task_d4f9aef8850e4c69a48da8d7ebf727b1` |

## 有候选时，从保存路径定位证据

- **玻璃边缘缺损**：导入并启用单独的[就绪适配图副本](http://127.0.0.1:5186/graphs?graph=graph_3b5aeb37986542d7abaf4db5feb3b125)，普通上传既有真实 006 外观 Frame，不重跑视觉模型。新[保存路径](http://127.0.0.1:5186/graphs?run_id=c78600aa-80fc-48b9-b108-74a195d98882&source=analysis-v2&case_id=mvtec_bottle_test_unknown_sample_006%2Fquery%2F1)有 8 个并列候选，`J=0.25`、排序分 `-0.25`；局部 D3 的 35 条去重源边与响应逐 ID 相同。另用已保存的同样本分析实查候选、源边、原图／热图／ROI 对应、PDF 第 13 页来源；可拖拽、滚轮缩放，点击当前边看邻域，点击保存边定位本次观测。未由图片确认瓶口部位或任何一个机械成因。
- **TEP d04**：普通上传同一冻结 Frame，窗口 161–260（一基闭区间，180 秒采样），同一登记图、`top_k=8`。两次任务均保存 52 条变量曲线；反应器冷却水入口温度扰动与阀粘滞并列首位。[统一条件溯因](http://127.0.0.1:5186/graphs?run_id=69337ddb-063b-4f76-a643-10a1e11ca9d7&source=analysis-v2&case_id=process_window_161_260%2Fquery%2Fwindow)显示 `J=0.25`、排序分 `-0.25`；[RootKGD](http://127.0.0.1:5186/graphs?run_id=d2a015cd-c7f8-4831-9a8a-092f31ba9938&source=analysis-v2&case_id=process_window_161_260%2Fquery%2Fwindow)使用 `rootkgd-host-channel.v2` 的全 52 项贡献输入，结构分 `0.5854474293642782`。两者分值均非概率。本轮未重跑 TEP 原始模型。
- **历史不随当前图或窗口改写**：受控只读切换当前登记图的节点名，保存路径仍保留原标签。既有 d04 原始分析从 161–260 切至 1–100，正常门控显示 0 排名，不借用另一个窗口的候选或路径。

## 证据与验证范围

本机记录在 `backend/runs/original_ui_loop_review/`（Git 忽略）：`live-material/verification.json`、`terminal-task.json` 及 `import-verification.json` 保存真实制作、阶段及独立上传解析；`live-inference/verification.json`、各 `.analysis.json`／`.task.json`、`actual-downloaded-006-frame.json` 保存实际原图、复算、正例及两引擎检查；`read-only/graph-check.json` 与 `interaction-check.json` 保存源边、定位、拖拽缩放和历史隔离检查。各目录附实屏截图，原 D3 与保存边定位见 `read-only/05-d3-selected-real-edge.png`。

原生 Vitest **28 文件／147 项**、类型检查和生产构建通过（仍有 Arco 主 chunk 大小提示）；后端 **575 通过／4 既有可选跳过**。其它受控失败与显式重试、Wafer `.jsonl` 文件入口检查见[原界面接线记录](../../src/doc/rootlens-restored-two-loops.md)；本轮不重跑 Wafer 推理矩阵，也未做第二次文本制作、任何新 VLM 调用或 GPU 任务。
