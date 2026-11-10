# 双闭环演示资产入口

2026-11-11。本文件是素材、原始样本与中间 Evidence 的导航；实际 API 见 [后端契约](rootlens-two-loop-backend-contract.md)，现场步骤与已验证结果见 [演示手册](../../backend/docs/two-loop-demo.md)。

## 一份 manifest，两个分析入口

真值清单是 `backend/data/demo/two_loop/manifest.json`。后端 `GET /api/demo-library` 读取同一文件，补充白名单资产的 `download_url`；前端不自行拼接本机路径。

- `demos[]`：场景、中文标题、构图能力、原始资料、工作图、模型、来源与许可。
- `samples[]`：稳定 `sample_id`、原始 `raw_input`、可直接上传的 `evidence`、原始入口 `raw_options`、可用 `reasoner_ids`。
- `supporting_assets[]`：冻结 Frame 引用的原图、网格、窗口矩阵、正常参考与 scaler/PCA；`frame_asset_id` 对应 Frame 内 ID。
- `storage_scope=repository` 的小型 Evidence／知识包随仓库提供；`local_runtime` 的原始数据、受版权约束资料和大权重不入库。每份资产带实际大小、公开出处与分发说明。
- `recommended=true` 标记主演示，不影响模型和推理。`expectation` 只用于演示对照说明，不进入 adapter、模型提示或最终排名。

`POST /api/tasks/inference/demo` 的 `input_variant=raw` 执行实际模型／测量，`input_variant=evidence` 从中间合同重新推理；后者不是读取预先写好的候选结果。

## 推荐的三套演示

| 场景 | 主样本 | 资料与测量 | 讲解重点 |
| --- | --- | --- | --- |
| 玻璃边缘 | `bottle-rim-break` | Emhart 原厂 PDF 13／20 页；公开 900×900 图像；Bottle PatchCore 与 ROI 视觉语义 | 多个制造原因可以共享可见缺损，保留并列，不伪造唯一答案。 |
| TEP | `tep-sequence-04` | 原过程／控制程序；52 通道原序列；独立正常 500 行拟合 scaler/PCA | 同一 Evidence 可选统一条件溯因或 RootKGD 图传播；路径与完整贡献向量共同可查。 |
| 晶圆 | `wafer-nearfull` | 作者模型卡；原生 0／1／2 网格；独立 ResNet34 与空间统计 | 输出是图案家族；分类与实际 die 统计各有来源。 |

其余样本保留正常、不足、语义漏检、模型／原生图案分歧及 TEP 错误排名对照，不把所有上传都强配到一条原因路径。

## 知识图的原始产物与演示适配分开保存

默认Bottle主图使用原双闭环验收版的真实原厂PDF LLM产物，默认Frame由两次一致的公开006原图第二次实际运行导出；原图拍摄部位未确认，Finish资料的外观迁移已明确写入来源。Wafer知识种子复用前期真实资料LLM产物，默认Frame同样是原验收版raw输出。TEP 原验收时重新向配置的文本 LLM 提交原始 `teprob.f` 与 `temain_mod.f`，原始输出及失败报告保留在 `backend/runs/two_loop_demo/knowledge/tep-source-llm-002/`。

13份默认Frame和默认3图本轮保持不变。原17项验证（13个统一引擎＋4个RootKGD v1）作为历史保留；其中13项统一引擎不受投影变更影响，没有重复运行。

当前另复演4个TEP×RootKGD v2组合：d04／d01／d05／正常，正式API与CLI的候选、名次、分数、完整评分组件和状态精确一致；52评分输入及曲线、连续真实源路径通过检查。结果标记 `tep_rootkgd_propagation_v2`／`rootkgd-host-channel.v2`，原错误排名未变。随仓库摘要 `backend/data/demo/two_loop/verification-summary.json` 将当前4项与旧17项分区，完整新记录在 `backend/runs/two_loop_demo/rootkgd-v2-consumption-20261111/verification.json`；摘要不参与计算。

当前d04原始Run `48595ebd-a532-4c98-9464-5cb2730bac29` 直接下载Frame并普通上传得到 `43311a86-a894-4bb9-b884-88ae7f8186b4`。同图／引擎／top_k=8下，三窗口候选、组件、结果和52曲线精确一致；不覆盖旧Run或默认冻结Frame。

TEP 工作图保留 8 个候选、分回路机制、14 个原子和全部 52 个稳定通道绑定。对原 LLM 产物的演示适配包括：移除无具体可诊断机理的 Unknown 兜底；使用原程序明确的进料组分测量；修正进料热边界的过强质量流量解释；统一声明 2 z 门槛。通道绑定不等于每个通道都有来源支持的传播路径。

可入库的原始蓝图、旧 U3 图与改动记录分别为：

- `backend/data/demo/two_loop/knowledge/tep-authoring-blueprint.original.json`
- `backend/data/demo/two_loop/knowledge/tep-working-graph.original-u3.v2.json`
- `backend/data/demo/two_loop/knowledge/tep-demo-refinement.json`

人工可以继续改图；新分析固定所选图快照。既有分析不因之后编辑而改变。

## 新源图验证与默认适配图分开

当前制作合同另用同一公开 Emhart PDF 实际调用一次任务（含唯一修复共2调用／18899 tokens）。原任务 `task_2b5e770ad3114218bba64e58847b9cb5` 因17候选超过当时硬16失败，记录未改写。保留最终响应后，按硬32／软建议16离线编译，并明确将原 ANY 中的泛缺陷布尔分支提升为 ALL 前置；报告标 `semantic_change=true`，没有再次调用模型。

独立恢复图 `graph_538efc4369b64b46a879dd5a30652bc1` 已通过正式导入／启用，006冻结Frame普通上传得到 `c846c64a-2388-4c3a-9827-25c4cb770496`：insufficient_evidence、0排名、媒体可读。细 `broken_finish/chipped_finish` 尚未观测，空词汇绑定不补成等价；这张17候选源图不替换默认已适配图。原始响应、编译归一化与实际API结果见 `backend/runs/two_loop_demo/rootkgd-v2-consumption-20261111/current-llm-contract/`，随仓库摘要保留任务／图／Run及明确恢复来源。

可跨机器导入的[完整源图包](../../backend/data/demo/two_loop/graphs/source-finish-recovered.json)与[恢复provenance](../../backend/data/demo/two_loop/graphs/source-finish-recovered.provenance.json)已入库，不依赖上述本机ID或重新调用LLM。它们不在默认manifest中；导入为新副本，启用后上传既有006 Frame即可复用这一不足对照。完整包34,166字节，已通过当前schema读回；原失败、2调用／0新增、预算和语义收紧在provenance明确区分。

## 准备和复算

从 `backend/` 执行：

```bash
uv run --offline --no-sync python scripts/prepare_two_loop_demo.py
uv run --offline --no-sync python scripts/prepare_two_loop_demo.py \
  --recompute-output runs/two_loop_demo/checks/my-new-check
```

第一条准备／检查资产，不调用外部LLM或视觉backbone、不连接数据库；缺失的TEP配套数值资产可从同一公开数据与正常参考重建并核对。缺失公开资产时才加 `--download`。第二条用小型冻结 Frame 重新执行内核；输出目录必须是新的。真实 API 闭环客户端是 `backend/scripts/prepare_two_loop_demo_api.py`，仅调用正式服务，不实现第二份 adapter 或推理算法。

仅复演受本次投影影响的四项时，复用现有已启用TEP图，不加 `--build-bottle`、不重新导图：

```bash
uv run --offline --no-sync python scripts/prepare_two_loop_demo_api.py \
  --output-dir runs/two_loop_demo/my-root-v2-check \
  --graph-id graph_c6d2a470450e41369de3fc7bdcaaf459 \
  --reasoner tep_rootkgd --variant evidence \
  --sample tep-sequence-04 --sample tep-sequence-01 \
  --sample tep-sequence-05 --sample tep-normal-window
```

上例图ID仅属于本机验收库；新库使用实际导入后返回的ID。当前Root投影按host／稳定通道去重逻辑期待，保留真实effect和来源；不执行条件阈值／AND-OR／mode，新增条件的业务含义与推理器选择见[现场手册](../../backend/docs/two-loop-demo.md)。
