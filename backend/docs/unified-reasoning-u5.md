# U5：同输入评价与最终验收

2026-11-11。对象是已冻结的公开模型／数值输出与当时运行所用的知识快照，评价脚本不再调用模型或改图。目的：检验统一计算、设计项的作用和实际失败，而非从少量展示案例估计工业诊断准确率。

## 32 份实际输入，三个场景不换内核

| 输入单位 | 统一内核结果 | 需要保留的负结果 |
| --- | --- | --- |
| MVTec bottle：4 张异常＋1 张正常 | 2 ambiguous、2 no_match、1 insufficient；匹配例各 4 个 rank=1、score=−0.25，12 条路径 | 一张异常被 ROI VLM 判正常，一张 uncertain；无法用外观唯一识别制造原因 |
| TEP d04／d01／d05，各 3 窗口 | 3 个前故障窗口 no_match；6 个后故障窗口 supported，分别有 3／4 个候选 | 已知故障族在候选中，但三个序列的首位族都不正确；一序列的两窗口不算独立重复 |
| Wafer：18 张公开原网格 | 7 supported、11 no_match | 7 中 6 与原生图案相符，1 Donut→Edge-Ring；11 未匹配含 2 张原生 none |

同一固定策略 `λc=2、λa=0.25`；U3／U4 没有修改 common compiler、grounding、候选推理算法。第三场景接入支持架构迁移结论，不能直接推出统计跨域泛化。

### 公平的平坦对照完全等价

独立平坦参考复用原子 grounding／作用域合同和有限分支编译，但**独立展开根假设的可达期待、计算全候选损失／准入**，不调用公共 reasoner 的候选比较和排序实现。

- 32／32 份输入的全候选代价与准入一致（容差 1e−9）。
- 移除中间机制、把其全部逻辑后果直接提升到根假设，32／32 份结果一致。

因此当前没有“图存储本身带来准确率增益”的证据。现阶段的价值是共用合同、知识维护与迁移、共享机制表达和实际推导追溯；若论文主张更强推理能力，需要另有不能被等价平坦展开解释的贡献与实验。

### 更弱的路径与消融究竟丢失了什么

同知识的 single-atom/path 参考保留所有绑定观测及反向诊断 footprint，只要一个原子满足即可召回，去掉联合条件与冲突。它不是把旧 generic ranker 不兼容 v2 物理方向后的空结果当对照。

| 场景 | 完整联合支持的问题数 | 单原子／路径有候选的问题数 |
| --- | ---: | ---: |
| MVTec | 2／5 | 4／5 |
| TEP | 6／9 | 9／9 |
| Wafer | 7／18 | 18／18 |

路径连通不足以说明条件成立；特别是正常 gate 为 false 时，其他局部统计仍可能满足。多召回不能直接叫“错根因”，但其结果没有完整联合依据。

- 设 `λc=0` 后，6 个 TEP 后故障窗口的分数／名次输出改变，视觉和空间的支持排名输出不变。跨场景统一再取 1、4 的完整结果也保留；没有逐故障调权。
- 全 32 份输入重排、复制同源观测、改 `source_dataset` 名称，代价、准入与路径节点全保持一致。
- 故意按源行重复投票的平坦消融在其中 28 份产生不同代价。该消融演示重复计数问题，不构成真实数据上的准确率胜出。
- 对 15 份存在完整支持的输入，删除一个实际使用的观测，15／15 计算／证明改变；删除首位候选的一条实际使用 effect，15／15 改变。不要求每次首位翻转。
- 一致 ID 重命名、错单位／参考、跨 ROI、missing 对比显式阴性、同分截断、环自证明和搜索预算，由合同／内核测试另行验证。

### 原有 reasoner 保留为系统参照

在完全相同的 legacy observations 上，运行 M2–M6 的旧知识包和现有实现：视觉全部无匹配／不足；TEP 4 个后故障窗口匹配，旧 cooling／feed 画像在 d04／d01 上比新图更贴近已知故障族，d05 不匹配；Wafer 3 张匹配。

旧 generic 在 TEP 9／9、Wafer 11／18 有路径候选，MVTec 0／5。旧方法使用**不同知识、词汇和目标**，尤其旧 Wafer 输出的是机制假设、新 Wafer 是图案类别；这些结果作为工程参照，不与新方法直接比准确率或宣称胜负。没有移除旧策略，也没有隐去 TEP 旧画像更有辨识力的事实。

按冻结规划，同 Evidence＋知识的 LLM 判断对照、完整 benchmark 和训练不在本轮启动。U5 没有新增付费模型调用。

## 如何复算，输入和完整失败在哪

从 `backend/` 执行；输出必须用新目录：

```bash
# 从已有持久 RunDetail 的原始 snapshot 冻结，而不是替换成最新种子
uv run --no-sync python scripts/freeze_unified_runs.py \
  --run runs/unified_reasoning/u1_mvtec_actual/additional-001-run.json \
  --run runs/unified_reasoning/u3_tep_validation/run_04.json \
  --run runs/unified_reasoning/u4_wafer_validation/run.json \
  --output-dir runs/my-frozen

uv run --no-sync python scripts/evaluate_unified_reasoning.py \
  --manifest runs/my-frozen/manifest.json --output-dir runs/my-comparison
uv run --no-sync python scripts/perturb_unified_reasoning.py \
  --manifest runs/my-frozen/manifest.json --output-dir runs/my-perturbations
uv run --no-sync python scripts/evaluate_legacy_profiles.py \
  --manifest runs/my-frozen/manifest.json \
  --package runs/refactor_m2_m6/mvtec-package.json \
  --package runs/refactor_m2_m6/tep-package.json \
  --package runs/refactor_m2_m6/wafer-package.json \
  --output-dir runs/my-legacy-reference
```

本机完整 32 份 manifest 是 `runs/unified_reasoning/u5_frozen/manifest.json`：5 份原图 run、`run_04/01/05.json` 的 9 个窗口、Wafer 18 张。上面三个 `--run` 是复用入口示范；要复算全量使用该 manifest 或传全部 9 份 run。CLI 不下载资产、不运行感知、不修改原数据。

| 目录 | 保存内容 |
| --- | --- |
| `u5_frozen/` | 逐 run 的原始知识快照、32 份完整 Frame、manifest |
| `u5_comparisons/` | 全候选公共／平坦计算、去冲突消融、逐问题完整结果 |
| `u5_perturbations/` | 重复／重排／改 dataset、缺失观测／删规则、统一权重敏感性 |
| `u5_legacy_references/` | 旧三场景画像与原 generic 的结果，明确 different-knowledge 条件 |
| `u1_mvtec_actual/`、`u3_tep_validation/`、`u4_wafer_validation/` | 原始 RunDetail、frames、数值参考和模型／统计结果 |
| `u2_bottle_*`、`u3_tep_actual/`、`u3_tep_knowledge*`、`u4_wafer_actual/`、`u4_wafer_knowledge*` | 失败构图、过细候选、错误 AND、对称分类及其负结果 |
| `u5_replay/` | 3 单场景与 22-case 合并回放，原图和结果内嵌 |

上述目录均在 `runs/unified_reasoning/` 下，Git 忽略。小型实际 Frame、种子和 `unified-reasoning-u5-results.json` 已入库。前期权重和数据出处见 `809fb8d:backend/docs/progressive-demo-2026-11-10.md`；新增 d01/d05 来自同一 Braatz 仓库，bottle 补充图为 [DefectSpectrum DS-MVTec](https://huggingface.co/datasets/DefectSpectrum/Defect_Spectrum/tree/main/DS-MVTec/bottle/image/broken_large) 的 001–003，上传时使用中性文件名。

## 实际页面、持久化与回放验收

- 现有三页保留，只增加“推理依据”抽屉，显示全候选 U/C/A/J、实际值、scope、反证、缺失、未使用观测、联合证明和原始源边。分数不显示成概率。
- 实屏检查 bottle 的并列／不支持候选和 ROI／900×900 原图／mask／heatmap；TEP 的实际 161–260 窗口、52 行完整趋势、冲突候选；Wafer 实际 1139 有效／986 失效 die、径向密度和网格预览。截图 `u5-*.png`。
- UI 把原 bottle 图导入为验收副本 `graph_ef3243718f7e44018164b5e4f3a468ab`，保存新别名并删除 thermal effect。独立 API 读取确认保存成功，新别名 Frame 得到 3 候选，原历史 Run 仍是 4 候选。记录 `u5-ui-persistence.json`；原图没被覆盖。
- 真实隔离 PG／Neo4j 检查覆盖独立连接重载、改图、完整交换、备份恢复和历史 snapshot。已有数据未被重建。
- 合并 Session 经现有文件选择器实际导入，刷新页面后 3 Run／22 case 仍在 IndexedDB，实际路径／分数／图像和 52 通道仍显示。重载期间没有 `/api/` 请求，记录 `u5-replay-network.txt`；D3 仍沿用 CDN。
- 修正了 Graphs→Evidence 返回时错误回到第一个窗口的问题；现在保留所选 case 和 proof focus。Build Recipe 操作换行，窄列中“装载工作图”等按钮不再被截掉。

## 测试与验收结论

最终完整后端：**442 passed / 5 failed / 1 skipped**；日志 `runs/unified_reasoning/u5-full-pytest-delivery.log`。5 项均为已有失败：

1. `test_case_index_includes_checked_in_and_real_output_cases`：缺少历史 real-output case。
2. `test_case_detail_returns_analysis_for_real_outputs`：缺少 `wm811k_row_100402` 历史输入。
3. `test_upload_run_prepares_visual_evidence_artifacts`：旧 fixture 的图片／mask／heatmap 不在本机。
4. `test_image_upload_mode_defaults_to_unknown_label_when_unspecified`：旧 `crack/000.png` 不存在。
5. `test_mvtec_model_preset_route_reports_available_default`：固定 PatchCore 默认断言与现有 EfficientAD 配置不符。

已有 `env={}` 仍误读进程 Neo4j 设置的问题已修复。另查明旧单 case 上传先存库、后补 cases，导致持久化对象缺少 case；现改为保存完整 envelope，旧 user-study 测试及真实 API 重新打开均通过。上述缺失资产没有被伪造来“变绿”。v2 合同／内核／三适配／构图／编辑与实库检查通过。完整前端 **20 文件 / 95 项通过**，类型检查／生产 build 通过，保留既有大 chunk 警告。修改的 Python 文件 Ruff 通过。

### 证据如何使用

- 这是探索性工程验收：公开样本经过小范围取样，TEP 窗口同序列相关，知识曾因实际反例修订。没有确认性留出实验，也没有显著性检验或置信校准。
- 三场景只按各自任务报告，不能合并成“32 样本准确率”；原生外观／图案标签不能当制造根因真值。没有关于人群、幸存者、基率、回归均值、独立样本或因果干预的推断。
- 正常／失败、修订前配置与全部候选都保留，未只报告成功模型／图。平坦等价是强竞争解释；LLM 图上的原因关系是资料相容假设，路径追溯不等于因果验证。

**当前最优先的后续研究问题已经具体化：TEP 的候选知识对不同扰动的可区分性不足。** 应先查补能区分冷却入口变化、阀门行为和进料扰动的观测／响应关系，设置与强平坦基线公平的按原始序列分离实验，再判断是否需要时间机制或更强推理表达；不靠换大模型、按 fault 调权或增加固定演示案例解释现有错误。
