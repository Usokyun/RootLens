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

Bottle主图使用本轮真实原厂PDF LLM产物，默认Frame由两次一致的公开006原图第二次实际运行导出；原图拍摄部位未确认，Finish资料的外观迁移已明确写入来源。Wafer知识种子复用前期真实资料LLM产物，默认Frame同样是本轮raw输出。TEP 本轮重新向配置的文本 LLM 提交原始 `teprob.f` 与 `temain_mod.f`，原始输出及失败报告保留在 `backend/runs/two_loop_demo/knowledge/tep-source-llm-002/`。

最终13份默认Frame、17个样本／引擎组合的API与CLI候选、排名、分数和状态完全一致；每条实际路径有来源和观测定位，原始媒体／52通道曲线可读。随仓库的小型验证摘要是 `backend/data/demo/two_loop/verification-summary.json`；它只记录验收，不参与计算。

TEP 工作图保留 8 个候选、分回路机制、14 个原子和全部 52 个稳定通道绑定。对原 LLM 产物的演示适配包括：移除无具体可诊断机理的 Unknown 兜底；使用原程序明确的进料组分测量；修正进料热边界的过强质量流量解释；统一声明 2 z 门槛。通道绑定不等于每个通道都有来源支持的传播路径。

可入库的原始蓝图、旧 U3 图与改动记录分别为：

- `backend/data/demo/two_loop/knowledge/tep-authoring-blueprint.original.json`
- `backend/data/demo/two_loop/knowledge/tep-working-graph.original-u3.v2.json`
- `backend/data/demo/two_loop/knowledge/tep-demo-refinement.json`

人工可以继续改图；新分析固定所选图快照。既有分析不因之后编辑而改变。

## 准备和复算

从 `backend/` 执行：

```bash
uv run --offline --no-sync python scripts/prepare_two_loop_demo.py
uv run --offline --no-sync python scripts/prepare_two_loop_demo.py \
  --recompute-output runs/two_loop_demo/checks/my-new-check
```

第一条准备／检查资产，不调用外部LLM或视觉backbone、不连接数据库；缺失的TEP配套数值资产可从同一公开数据与正常参考重建并核对。缺失公开资产时才加 `--download`。第二条用小型冻结 Frame 重新执行内核；输出目录必须是新的。真实 API 闭环客户端是 `backend/scripts/prepare_two_loop_demo_api.py`，仅调用正式服务，不实现第二份 adapter 或推理算法。
