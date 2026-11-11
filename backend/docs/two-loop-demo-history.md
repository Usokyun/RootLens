# 双闭环研究验收：旧 PDF／ROI、TEP 与晶圆

这是此前双闭环的真实输入与结果记录，不是当前 MVTec 的启动手册。当前唯一 MVTec 样本使用自著 Markdown 和无 VLM 的几何 Evidence，见[现场手册](two-loop-demo.md)。旧 Run／图／媒体不随示例更新重算。旧 `bottle-rim-break` Frame 和旧适配图仍留作研究测试与严格 Finish 对照；五份已退役的重复导出可在历史提交 `2e98a28` 或 `runs/two_loop_demo/api-final/` 的完整保存结果中取回。保留旧数据中的不稳定观测和错误排名。

## TEP 的两引擎解释不同问题

- **统一条件溯因 `unified_abduction`**：执行图中联合条件、作用域与固定 U/C/A/J 代价。分数不是概率。
- **RootKGD 图传播 `tep_rootkgd`**：复用原有有向关系族衰减传播、全 52 维贡献余弦／覆盖／传播熵评分及路径回溯。使用当前工作图，不读固定旧图、fault ID、故障族调参或 anchor-memory。

当前 RootKGD 结果标记 `scoring_method=tep_rootkgd_propagation_v2`，`propagation.projection_version=rootkgd-host-channel.v2`。投影把同一 host→稳定通道的逻辑期待合并，并去除沿显式 effect 已由下游覆盖的上游同通道重复声明；来源仍以连续主路径／备选路径保留。重复写同通道统计条件或拆分等价 pattern 不再增加传播票／捷径，真正新增可达通道或 effect 仍可能改变分数。

RootKGD 不执行条件阈值、AND／OR 或期待模式的惩罚；需要这些判别时用统一约束引擎。同一候选新增条件后，不能把统一引擎的条件效果解释成 RootKGD 的条件执行。

原始 `.dat` 顺序为 XMEAS1–41、XMV1–11。窗口为一基闭区间 `[1,100]`、`[161,260]`、`[261,360]`，180 秒／样本。正常参考是独立 d00 的 500 行，保留 scaler/PCA 参数、完整 52 维贡献和原始窗口矩阵。正常数据横排的 52×500 输入会被 producer 明确转置。

推荐图在原始 LLM 蓝图基础上做了演示适配：反应器／冷凝器回路分开、明确通道关联、删除 Unknown 兜底，并用一致的 2 z 演示门槛。它仍没有每个通道的完整因果模型；稳定绑定不等于传播覆盖。原始蓝图、旧图、来源与差异详见 `data/demo/two_loop/knowledge/tep-demo-refinement.json`。

## 本轮真实输入与已复算结果

当时 manifest 的全部默认 Frame 来自**原双闭环验收版的原始输入实际运行**；本次方法增强保持它们不变，没有用旧词兼容绑定凑候选。旧 U5 Frame 在 `data/demo/two_loop/history/`，原始模型／LLM输出和失败在 `runs/two_loop_demo/`，不作为当前默认输入。

验收按方法版本分开保存：

- **原17项历史批次**：13个统一引擎组合＋4个 RootKGD v1 组合，API／CLI 的候选、名次、分数与 outcome 完全一致；媒体和来源检查通过。记录为 `runs/two_loop_demo/checks/current-final/summary.json`、`api-final/state.json` 与 `final-evidence-verification.json`。其中13个统一引擎组合未受本次投影改动影响，保留有效证据，不重复运行模型或矩阵。
- **当前4项 RootKGD v2**：d04、d01、d05、正常窗口分别通过正式 API／CLI 复演，完整候选、名次、分数、scoring_details 与 outcome 精确相等。每项52通道曲线可读、52评分输入未误列 unused；异常项各21条主路径连续且有真实来源／观测定位，默认图本身无备选路径。相对 v1，名次和 outcome 未变，分数最大差为 `1.11e−16`，原有错误排名仍保留。

该阶段完整记录为 `runs/two_loop_demo/rootkgd-v2-consumption-20261111/verification.json`。小型摘要 `data/demo/two_loop/verification-summary.json` 使用 v2 schema：当前4项与旧17项历史分区保存。13份冻结 Frame 和默认3图均未修改；这次不是17项全部在新方法下重跑，也不是准确率估计。

| 输入 | 默认适配图的实际结果（RootKGD为v2） |
| --- | --- |
| 推荐玻璃原图006 | 两次真实PatchCore／ROI均得到 `cracked_or_missing_glass`、defect=true；8个rank=1候选、score −0.25、24条路径。 |
| 正常玻璃图 | 定位模型判正常，无候选。 |
| `bottle-geometry-only` | 公开000图真实关闭ROI语义，仅保留定位／几何；insufficient_evidence。 |
| 玻璃001／002／003 | 本轮ROI均判正常，因而无匹配；与原生异常标注不一致。 |
| TEP d04 窗口161–260 | 两引擎首位均为反应器冷却入口温度／阀粘滞并列；统一score −0.25，RootKGD结构score 0.585447。 |
| TEP d01 窗口161–260 | 统一内核多族并列；RootKGD首位为进料温度，不是原生进料组成扰动。 |
| TEP d05 窗口161–260 | 统一内核无匹配；RootKGD首位进料供给，与原生冷凝器入口温度扰动不一致。 |
| TEP正常窗口 | 两引擎均无候选。 |
| 晶圆nearfull／native None | 近全片图案／无匹配；native None仍可含少量失败die。 |
| 晶圆31707 | 模型和推理输出Edge-Ring，原生Donut；保留真实分歧。 |

### RootKGD 原始输入与 Frame 入口一致

同一默认 TEP 图、`tep_rootkgd`、`top_k=8` 下，公开 d04 `.dat`＋独立正常参考实际运行得到 `48595ebd-a532-4c98-9464-5cb2730bac29`。直接下载**该次运行**的 Frame，再通过普通上传得到 `43311a86-a894-4bb9-b884-88ae7f8186b4`：三个窗口的候选、名次、分数、全部评分组件、outcome 和52条原始曲线逐项精确一致，并与 CLI 相等。正常窗无匹配，两个异常窗保留冷却入口温度／阀粘滞并列；没有新下载、LLM 调用或图谱改写。记录在上述目录的 `raw-frame-roundtrip.json`，原 v1 原始／中间复算记录仍保留为历史。

该阶段4个 Frame 运行依次为 d04 `d6d29421-a374-46e6-81bd-ec94a3812c91`、d01 `1bef2654-1513-4983-9288-91d1edca8ce8`、d05 `32b65e9a-dde1-4ef6-9653-230df8f95d07`、正常 `1ebc0f31-a092-4e52-820c-ea233ddfb501`。

### 用本次知识诊断决定下一条条件

结果中的“本次知识诊断”读取该 run 保存的快照，区分条件真／假／未知、是否具备排名资格、绑定观测与实际评分输入；相同期待条件组不代表已经被数据区分，成本先验单列。历史 run 没有诊断字段时显示未生成，不借当前图补算。

要验证编辑闭环，先导入图的副本，在目标候选下点“新增诊断条件”，选择真实特征／已绑定变量、typed 值和期待模式，保存后重传同一 Frame；再撤销这条独立条件并复算。该入口不修改共享机制，无来源时如实标人工演示启发式。阈值必须有业务依据才可解释为诊断知识；为验证操作能力添加的阈值不构成工业事实。已有独立实屏的新增／撤销与历史快照证据见[前端交付](../../src/doc/rootlens-two-loop-frontend.md)。

### 玻璃选样没有隐藏不稳定观测

公开原图000曾在相同PatchCore几何下，一次被ROI模型判缺损、一次被解释为包装／封口材料而判正常。两份完整分析分别是 `8f471853-0784-44bf-9e5d-907c526d5ec5` 和 `42753a06-ecfd-496e-b90b-d0e86a2b0109`。没有覆盖其布尔观测或临时增加几何因果规则。

随后肉眼检查4张额外公开图，选择结构缺失更明确的006。它的两次完整原始执行为 `bde29798-db9a-4eb6-aa6a-439125ac88d1` 与 `1d116c71-d461-4d9a-852f-eb7f243534c0`；默认Frame从第二次导出。两次均为面积比0.2284393、aspect ratio 1.117284、eccentricity 0.796951，语义与候选一致。两次一致用于选现场样本，不能推广为模型稳定率。

### 原验收版的真实资料制作与编辑

原验收版 API任务 `task_8217b6fb3f274fceb9d8519be95f2f38` 读取原厂PDF的2个定位片段／3008字符，真实调用文本模型2次（含一次有界修复，17141 tokens），得到8候选工作图 `graph_7718009df1d94a288f99d1e428487679`。中文实体别名已保存回读并启用；之后补充的部位未确认／演示迁移说明独立记录在 `data/demo/two_loop/knowledge/bottle-demo-refinement.json`。原始LLM包在 `runs/two_loop_demo/api-e2e-002/bottle.llm-original-package.json`，未覆盖。这项历史成功不替代后续 LLM prompt／有限域／binding 合同变更的验证。

之前的6候选上限曾使真实构图在validation失败，记录保留；改为明确的新任务后完成。TEP原程序蓝图超候选预算的原始失败、后续8候选演示适配及其差异也分别保留。后端没有用预存图冒充这些LLM调用。

### 当时的制作合同：保留真实失败，明确恢复后仍然不足

本次只新提交一次公开 PDF 制作任务 `task_2b5e770ad3114218bba64e58847b9cb5`：两页／3008字符解析成功，模型调用2次（含唯一修复，18899 tokens），候选20→17，均超过当时硬限16，任务在 validation 失败。原任务、两份响应和错误报告保留，没有追加模型抽样。

随后从**同一实际最终响应**离线恢复：视觉／过程的紧凑建议16与硬限32分开，17候选完整保留；同时发现两签名原写为 `fine_finish_cue OR defect_present=true`。编译器把已声明 presence gate 提为 ALL 前置，支持还需具体诊断原子，并记录两项 `presence_gates_lifted`、原 logic=any、`semantic_change=true`。这是明确的编译语义收紧，不是原样语义，也没有把原失败任务改成成功。最后这项门控提示词没有再调用模型抽样；恢复检查使用已有真实响应。

恢复包有17候选、2个pattern、26条定位来源，实际条件为 `broken_finish`／`chipped_finish`＋两个 presence 前置，词汇绑定为空；几何有限值目录随能力发送，但本次响应没有使用其 operand，不能把此例说成已现场覆盖全部有限类别或自动等价绑定。

正式 API 将恢复包导入／启用为独立图 `graph_538efc4369b64b46a879dd5a30652bc1`，再普通上传未改006 Frame：任务 `task_7898d4c1f0464b5287de779a7a47e7d3` 完成，Run `c846c64a-2388-4c3a-9827-25c4cb770496` 为 **insufficient_evidence／0个排名候选**，原图可读。异常／缺陷两门为真，但两个细 Finish 条件均为 unobserved：实际开放外观集合只有 `cracked_or_missing_glass`，既不补部位，也不把缺词当反证。恢复及上传均无新增 LLM／backbone／VLM 调用。

证据根目录为 `runs/two_loop_demo/rootkgd-v2-consumption-20261111/current-llm-contract/`：`captured-build-artifacts/` 保留真实输出；`offline-recovery-budget32-gate-aware/recovery-manifest.json` 明列预算与语义改动；`offline-recovery-api/` 保存正式导入、启用、任务及完整分析。默认3图另经只读有限证明核查，16个pattern／25个分支都还要求具体外观、通道统计或分类＋空间证据，没有仅 presence 就支持细候选的分支；没有改默认图或13份Frame。

无需本机历史库或再次付费也能重用这一对照：[完整源图包](../data/demo/two_loop/graphs/source-finish-recovered.json)（34,166字节）与[恢复来源说明](../data/demo/two_loop/graphs/source-finish-recovered.provenance.json)随仓库提供。图谱页“导入工作图包”会创建新副本，启用后上传现有 `data/demo/two_loop/evidence/bottle-rim-break.json`，选择统一引擎／top_k=8。该包用于展示**严格细条件与粗观测的不足**，不是就绪诊断图；不加入默认 manifest。包已按当前schema读回，正式导入／执行证据复用上述Run，导出时没有另建任务。它只含公共派生知识与定位，不含完整PDF、服务配置或原模型长日志。
