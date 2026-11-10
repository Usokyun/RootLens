# 两个闭环还缺哪一段

2026-11-11。基于实际新图负例、独立 UI 复现，以及保存的三场景 Frame 方法核查。下文区分**改进前诊断**与**本轮已验证增量**；新图意图、目录、绑定/诊断、候选条件新增/撤销、RootKGD 投影 v2，以及真实 LLM 响应的显式门控归一化恢复已完成独立消费。原收费任务的失败与恢复链分开保留。

## 判断：最弱的是 KG 可区分知识与实际可观测特征的接缝

目前两条路径都能走通，但**图谱制作闭环更弱**：产物已从资料变为可加载、可执行的图，却还不能稳定地变为“适用于当前 Evidence、且能区分候选的知识”。解析、LLM、编译、保存和启用是真实的；ready 只说明结构可执行，不说明所选测量能表达这些概念。

推理闭环的上传、测量、保存、固定 Frame 复算和路径生成已经可复用；主要上限仍来自知识：多个候选引用同一证据签名，再换 backbone 或调整成本先验，也不能凭空补出区分它们的观测。本轮已接通目录、等价词汇、分组诊断和候选专属条件的可修复短链；还未解决的是让资料编译主动区分共享现象、候选差异与当前根本测不到的概念，而不是等人看完一次“证据不足”后自行补齐。

近期应先补这段可修复闭环，而不是加入审核流程、正式版本治理或置信校准。

### 当前实际方法：先测量，再比较图中已有的候选

统一推理的主链是：

**原始样本 → adapter 生成带类型/单位和位置范围的观测 → grounding 执行主体/词汇绑定 → 展开当前 KG 已列出的候选及其期待 → 检查联合条件并比较解释成本 → 按实际图边生成路径。**直接上传 Frame 从观测这一步开始，不重跑测量。候选基本来自选定图的 hypotheses，不是运行时凭空发现新的制造原因；开放 metadata 也不会自动变成可执行 Evidence。

同一 Frame 下，修改合法绑定、条件、作用范围或候选期待，可以改变支持/冲突/缺测与结论；只换候选名字不会改变证据，调整假设成本只是更改先验偏好。多个候选最终期待相同，所以当前常会并列。要分开它们，应补有来源的方向、波动、时间或空间区分条件，而不是先换更大 backbone。

**RootKGD 走另一条数值路径：当前 KG 的有向关系与通道足迹 → 衰减传播向量 → 与完整实测残差贡献比较 → 结构分数和真实传播路径。**它不是同一逻辑条件 score：仅改既有阈值可改变条件核对，却不改变结构排名。真实新增通道作用或显式因果边可以改变结构，重复同一通道知识的逻辑写法则不应被当作新增物理作用；本轮 host-channel v2 已修复这种表示依赖，核心传播与评分算法不改。两类分数分别解释，不能合成置信概率。

## 1. 改进前的 P1：明确“使用此图”仍会回到另一张历史图

只读实际复现：打开 Wafer 历史运行 `33196a93-9a78-44e6-a4bd-b3b12023676f`，到图谱页选择新玻璃图 `graph_3a24629ac3ce487097424b4983e05398`，点击“使用此图分析”。页面仍显示旧 Wafer 结果、输入区隐藏，侧栏却写新玻璃图。再点击“新建分析”，实际选择又被改回 Wafer 图 `graph_5c3b30cbf4024ab1939c0435a1f676ec`。

原因是“使用此图”只改变全局 graphId 并跳转普通 `/evidence`；页面挂载按 analysisId 恢复历史，随后 newAnalysis 又从旧 run 恢复图和场景。这不是合理的历史快照行为，而是两个明确用户意图互相覆盖。以下旧实现行号均以改进前提交 `7c5e838` 为准，不指本轮修复后的行号。

- 入口：`/Users/hhm/code/RootLens/src/views/GraphExploreView.vue:132–133`，侧栏也跳普通 `/evidence`。
- 历史恢复与再次覆盖：`/Users/hhm/code/RootLens/src/views/EvidenceManageView.vue:91–110`。
- 选择状态：`/Users/hhm/code/RootLens/src/services/workspace.ts:25–31`。
- 实屏和完整复现：`backend/runs/two_loop_demo/system-assessment/kg/context-check.json`、`context-after-use.png`、`context-after-new.png`；脚本 `context-check.mjs` 用 GET guard 拦所有写请求，实际无写请求。

**本轮修复：**“使用此图分析”传递明确的新建分析及 graph 意图，挂载时优先消费；普通导航仍可恢复历史，历史解释使用当次图快照，没有通过全局清除历史绕过冲突。

**验收：**先打开另一场景历史，再选新图并使用，必须进入该图的输入区；后续提交的 graph_id 与用户选择一致，历史结果仍能单独打开。

## 2. 概念不匹配要分三类，不能都叫“缺测”或都做别名替换

真实负例是新制作任务 `task_6e68de18e2c74c30b51503b1c851ebe4` 的图 `graph_3a24629…`，在运行 `ab57734f-589c-4b0b-b978-a28de08ab609` 中得到证据不足。

实际原始字符串是 **`broken finish` / `chipped finish`（带空格）**；当前 Frame 是 `cracked_or_missing_glass` 的开放候选集，且拍摄部位未确认。实体别名只负责主体身份，不能将这些外观值自动变成同一个概念。

1. **真实信息不足：**“可见玻璃开裂/缺失”不能推出“已确认瓶口 Finish”，更不能推出某个制造原因。保留未知是正确的，不能为了得到阳性强加等价映射。
2. **本可对齐的词汇差异：**同一已定义外观的不同写法，可以用有来源的特征值等价映射解决；当前 grounding 已支持，不需要重新调用模型。
3. **适用范围/形态抽象变化：**把原厂 Finish 知识迁移到“部位未确认的可见玻璃边缘”是知识适配，需要修改适用条件并声明依据，不是偷偷加一个字符串别名。推荐演示图已有这种明确适配，应保留这种透明性。

改进前的根因不止这一个负例：

- 特征注册只有 ID、类型、单位、定义，没有有限取值域：改进前 `7c5e838` 的 `/Users/hhm/code/RootLens/backend/src/kgtracevis/schema/unified_knowledge.py:52–64`。
- 编译提示要求严格复制 feature/单位，但 appearance 允许临时生成短外观词：`/Users/hhm/code/RootLens/backend/src/kgtracevis/source_kg_compiler/unified.py:49–105`。
- 原图 VLM 的候选词由当前图条件动态抽出：`/Users/hhm/code/RootLens/backend/src/kgtracevis/kg/unified_semantics.py:6–23`；因此同一原图换图后，测量词表也可能变，而冻结 Frame 不会跟着变。
- 有限 geometry 声明存在确切漂移：改进前 `7c5e838` 的 `adapters/unified_capabilities.py:68–77` 声称 morphology 为 linear/irregular/compact、location 为 upper/lower/left/right/center；实际原图 producer 输出 linear/spot，location 为 edge/surface（`mask/visual_regions.py:77–82`、`mask/mask_feature_extractor.py:59–97`）。Frame 实际是 spot/surface，adapter 原样写入（`adapters/unified.py:111–121`）。

**本轮修复：**有限类别由 producer 与 capability 共用一份可执行目录，校验条件 operand 是否属于真实取值域；开放外观保留不确定性，显式维护等价映射及适用范围，不用模糊字符串匹配把窄概念与宽观测硬合并。

**验收：**producer 输出值必须全部被声明覆盖；有限类别的未知值在制作/编辑校验中明确报错；同义映射可使同一 Frame 正确绑定，宽泛玻璃外观仍不能自动满足“已确认 Finish”的条件。

## 3. 编辑器确实能改知识，但改进前缺“从零新增修复”

现有表单不是只改标签：能改数值/类别条件、主体、范围、嵌套 AND/OR/至少 N 项、影响/预期关系和现有绑定；完整包保存会重建 canonical 投影并做备份。它们都应保留。

改进前的卡点是：LLM blueprint 不生成 value_bindings，默认新图往往是空列表；UI 只遍历已有条目，没有新增映射按钮。实际新图的“观测绑定”只有一条 bottle 主体绑定。高级区只是 JSON 只读预览，用户只能导出、外部改包再导入新图，无法完成一次最常见的词汇修复。本轮 blueprint 已增加可选等价绑定草稿，并仅允许有定位来源的明确同义关系；资料没有这种关系时保持空列表是正确行为，不能强迫 LLM 补映射。

另一个已补的末端缺口是：**能改既有条件，不等于能补一条新的区分知识。**改进前没有创建新 predicate、pattern、expectation 的普通入口。因此即使新增诊断指出两候选拥有同一签名，用户仍无法在界面中给其中一个候选补一条专属诊断条件；只在 AND/OR 中引用已有项不能替代这个动作。

- 改进前 `7c5e838` 的 blueprint 输出没有 value_bindings：`/Users/hhm/code/RootLens/backend/src/kgtracevis/source_kg_compiler/unified_blueprint.py:311–326`。
- 改进前 UI 只列已有行：`/Users/hhm/code/RootLens/src/services/knowledge.ts:40–56`；表单只编辑 selectedRow：`src/views/GraphExploreView.vue:140–153`。
- 现成内核按 feature/model 精确映射，且保存应用的 binding IDs：`/Users/hhm/code/RootLens/backend/src/kgtracevis/core/unified_grounding.py:176–200`。
- 完整包保存、投影替换和回滚：`/Users/hhm/code/RootLens/backend/src/kgtracevis/service/working_graph_editor.py:92–104,173–220`。

**本轮修复：**增加/删除特征值映射的普通表单，选择特征、外部值、标准值、可选模型限定，给映射保存明确依据；冲突在原表单中解释。继续复用现有 ValueBinding 与 grounding，没有新增第二套匹配逻辑；候选专属条件的窄入口见 §5。

**验收：**从 value_bindings=[] 开始，用表单新增等价映射、保存、回读，并让同一冻结 Frame 的 grounding trace 显示实际应用该 binding；冲突映射被拒绝，删除后能恢复原未知状态。实体别名不被误当作特征值别名。

## 4. 推理方法真正的上限：信息已测到，但知识没有区分它

以下来自同一冻结输入与 checked-in 演示知识的离线核查。完整记录为 `backend/runs/two_loop_demo/system-assessment/reasoning/HANDOFF.md`、`method-checks.json` 与 `diagnostic-examples.json`，本次没有重复其数学矩阵。

### 4.1 同分有时是正确答案，有时暴露知识还没写到位

- Bottle 当前 8 个候选中有 **7 个拥有相同两条可达期待**。它们虽然经过不同中间机制名称，最终检查的是同一组外观条件；当前知识不能用观测将这 7 个分开。另一个候选未落入该同签名组，也可能在这个具体样本上同分，二者不是同一个判断。
- TEP 的反应器入口温度扰动 / 阀粘滞共享一条回路期待；冷凝器两候选也如此。两个同签名组各含 2 个候选。
- Wafer 当前没有这种同签名组；这不等于每个输入都能正确分类。真实 31707 仍随模型得到 Edge-Ring，与外部 Donut 标注分歧。

感知层也保留着真实负例：公开玻璃 001/002/003 的 ROI 语义漏检，000 同图曾正常/异常摇摆，006 的两次一致只支持这个演示样本。KG 不能靠绑定词替换把漏检变成新观测；完整 Frame 复算保证的是固定输入下可复现，不是 backbone 稳定率或未见样本准确率。

统一引擎按候选可达期待展开（`/Users/hhm/code/RootLens/backend/src/kgtracevis/kg/unified_compiler.py:82–108`）。所以要改善原因区分，必须补有来源的区分条件；仅改中间节点名字不产生新证据，改 assumption_cost 只会改变先验成本。

### 4.2 不是 signed/std/slope 算子缺失，而是当前 TEP 图没引用它们

| 场景 | Frame 保留观测 | 条件实际绑定的不同输入观测 | 当前主要条件 |
| --- | ---: | ---: | --- |
| Bottle | 9 | 3 | detector 与两项视觉语义 |
| TEP | 263 | 14 | 异常门控及 13 个 `abs(mean_z) >= 2` 条件 |
| Wafer | 12 | 9 | 分类、失效率、连通簇、线性度等空间统计 |

这里的 14 不是“14 条条件成立”：d04 实际有 14 个条件事实，**2 真、12 假**，假条件照样被执行并参与冲突/排除；绑定到的不同输入观测也是 14 条。`condition_feature_ids` 表示知识引用的特征类型，`condition_grounded_observation_count` 表示实际绑定到的不同观测，`score_input_observation_count` 表示本引擎数值比较的实际输入，三者不可混用。未用信息由报告中的 `unreferenced_features/not_scored_features` 确认，而不是用“263−真条件数”推断。

`gte/lte/abs_gte`、std、slope 已可执行；已有四项反事实验证真值随阈值正确翻转（`unified_grounding.py:217–241` 及 `existing_signed_std_slope_execution` 记录）。下一步应利用已有算子表达有来源的方向、波动或趋势知识，而不是再造同名算子。

完整曲线和网格目前还主要是解释附件。单 Frame 聚焦一个对象/ROI，统一引擎明确拒绝多个 focus（`unified_reasoner.py:40–48`）；保存多个窗口不等于已经执行跨窗口先后、滞后或跨 ROI 关系推理。更强时空组合应在区分条件可靠后另定义输入和执行语义。

### 4.3 RootKGD 的结构支持不是“联合条件已经成立”

RootKGD 从当前图提取通道足迹，执行有向衰减传播，将全 52 维残差贡献与传播向量做结构比较。阈值、符号和 AND/OR 不是这套排名的数值依据。

实际反事实：把 d04 图全部 2 z 条件改成 1e6，统一引擎变为 no_match；RootKGD 的候选、评分分解及名次完全不变。这说明**仅修改既有阈值不改变结构评分**。随后候选专属条件操作又暴露了一个表示依赖：为已有通道重复新增独立 pattern/expectation，会新增投影路径或捷径，仍指向同一物理通道也能改变分数。这不是“增加了新的物理知识”的充分理由，应修投影层的重复表示，而不是只补提示。

本轮最小修法为 `rootkgd-host-channel.v2`：将同 host→通道足迹规范化、同 host/channel 去重；仅当显式 effect 下游已经覆盖该通道时去掉上游重复期待，保留真实新通道与显式 effect 的结构作用。这里将 expectation 定义为测量足迹，而不是一条额外物理传播路线；真实独立机制应通过显式 effect 表达。主路径与备选来源分列，不能把不同来源片段拼成虚假的连续路径。核心衰减模拟和评分不改；验收按表示等价对照，不按哪个标签排名更好选择实现。

后端的实际冻结输入对照已落在 `backend/runs/two_loop_demo/rootkgd-representation-v2/projection-checks.json`：原实现给已达 xmeas_9 新增阈值 1e6 的 std 条件，首候选分数从 **0.5854474293642781 变为 0.38634032056418194**；v2 在同一冗余声明前后为 **0.5854474293642782**，全部候选数值逐项相同。三异常窗口的首位次序保留、仅浮点末位变化，正常窗口仍无排名；该冗余条件作为单独备选来源保留，22 条主/备源路径均连续。独立审核已读实现和有效对照，没有重跑这套离线数学矩阵。

**进入结构比较时完整 52 维都参与，不等于图有 52 通道的作用知识；正常门关闭时不启动排名。**当前图有路径的通道为 13/52，另外通道在传播向量中为零，但对应实测贡献仍留在余弦计算。d01、d04、d05 的全图不可达残差质量分别为 **79.28%、32.42%、74.82%**。d01 的结构首位只覆盖 5.33% 的贡献，d05 首位只覆盖 6.45%。这些结果仍会排名，不能被解释为完整制造原因支持；也不能仅凭三个示例拍一个覆盖阈值来改排名。

## 5. 本轮选定的务实增量

| 次序 | 改什么 | 当前状态与验收重点 |
| --- | --- | --- |
| 1 | 新图分析意图优先于历史恢复 | 独立实屏通过：旧 Wafer 历史 → 新玻璃图立即进入该图的新输入区；普通刷新仍恢复原历史。 |
| 2 | 有限类别共用目录，制作/编辑校验真实取值域 | 已读取实际 API 并实屏确认：形态为 linear/spot/scattered/dense，位置为 edge/surface；开放 appearance 单独提示，不伪装成封闭部位本体。 |
| 3 | 空图可新增/删除有依据的特征值等价映射 | 作者已走表单新增/保存/运行/删除；独立消费确认当前副本为空，旧运行仍保留已应用绑定及原图快照。映射仅支持 category/candidate_set，后端拒绝数值特征。 |
| 4 | 候选可分辨性与未引用观测诊断 | 新运行持久化、正例/正常/不足与 RootKGD 实屏已通过：静态同签名组与本次支持状态分开，RootKGD 分开作者条件和完整结构输入；旧运行明确没有诊断，不补算当前图。 |
| 5 | 窄候选级诊断条件新增/撤销 | 独立真实 GUI 通过：审核副本新增 → 同一冻结 Frame 的同签名组 7→6 → 撤销后知识逐字段恢复、下一运行组恢复 7 → 重开旧运行仍保留原条件、观测和路径。无资料依据时明确标人工 heuristic，不生成虚假来源定位。 |
| 6 | RootKGD 逻辑投影的表示等价 | v2 对照和最终 API/实屏已通过：重复已有通道不改分，新通道/effect 仍有作用；主/备源路径独立连续，完整 52 维输入与 13 通道知识覆盖分开。 |
| 7 | 来源编译预算与诊断门控约束 | 推荐 16 与硬上界 32 分开；泛 presence 不得单独证明细诊断，必要的逻辑收紧明确记录。真实失败响应恢复为 17 候选图，正式启用并执行 006 得到正确缺细外观的不足结果，原失败任务不改写。 |

诊断应回答“为什么这些候选目前无法区分、哪些已测信息尚未被知识引用”，不能把“没有发现同签名组”写成“已经证明可辨”。RootKGD 的“未被逻辑条件引用”与“未进入结构评分”必须分别显示：52 个 residual.contribution 都参与其向量比较，即使不属于逻辑谓词。

候选级新增沿用三个真实期待模式：expected 失败按现有冲突代价处理，necessary 失败阻止准入，possible 表示弱兼容；不增加第四个“冲突模式”。独立复核使用实际冻结 Frame 和标为人工能力对照的审核副本，检查新增后条件/分组变化、撤销后恢复，以及撤销后重开历史运行仍消费当次条件和路径快照，不把功能对照当作工业区分准确率。

**管理编辑的实际边界：**本轮新向导只为现有候选、当前对象或已绑定变量新增/撤销诊断条件小束；它不是任意候选、机制、主体绑定或新领域概念的完整 GUI 图编辑器。既有条件、表达式和关系可编辑，但新建这类结构仍需重新制作，或在外部维护完整包后导入。超出当前 typed 特征目录的新观测还需要 adapter/schema 支持，不能靠开放 metadata 或新名称直接执行。

### 第一批稳定候选的实际消费证据

独立 Chrome 使用 1440×900 新 context，全部 API 写请求被拦截，实际未产生写请求或 JS 错误：

- **新图意图：**从旧 Wafer 运行 `33196a93-9a78-44e6-a4bd-b3b12023676f` 到图页选 `graph_3a24629ac3ce487097424b4983e05398`，点“使用此图分析”，工作图为该新图、analysisId 为空、旧结果不再显示。另一次独立页面刷新正常恢复 `2a38c1a9-9f3d-427a-bc4a-a0ff4a882c97`，没有为修新建而取消历史恢复。
- **绑定真实消费：**审核副本 `graph_ffa07d51580e4cac87d4a1d4f7e17abf` 当前 `value_bindings=[]`；上述新运行的快照仍保留 `binding:b42ad8b1-c727-49f3-bedc-958037aca5f6`。独立 GET 的两项 grounded_facts 记录了 applied_value_binding_ids，一项为真、一项仍未知；该绑定只将“裂纹或玻璃缺失”改写为同一外观词，不增加部位信息。表单操作证据为 `.playwright-mcp/two-loop-optimization/binding-authoring-check.json`，独立回读为 `incremental/binding-run-consume.json`。
- **类型与值域：**表单只列类别/候选集合特征；`KnowledgePackage` 在 `unified_knowledge.py:299–305` 同样拒绝数值特征映射，并验证有限目录的标准值。对数值均值/std 的语义标签替换不是这项能力。
- **诊断与目录：**实际保存诊断 basis 为 reachable_expectation_conditions，1 组包含 7 候选；4 项条件事实是 3 真、1 未知，而不是“3 个已证实原因”。旧 Wafer 结果明确显示“本次未生成，不使用当前图谱补算”。实屏有限下拉与开放输入使用同一能力 API。

独立脚本、HTTP 回读与截图集中于 `backend/runs/two_loop_demo/system-assessment/kg/incremental/`：`first-batch-check.mjs/.json`、`catalog-history-check.mjs/.json`、`binding-run-consume.json`、`01-new-graph-intent.png`、`02-saved-diagnostics.png`、`03-finite-catalog-ui.png`、`04-open-vocabulary-ui.png`。

### 增量走查发现并修复的两项实际状态缺陷

1. **新建输入被异步初始化清空。**从图页进入分析时，输入区曾先可交互，立即选择 Evidence 和文件后，尚在等待刷新请求的挂载流程再次消费新建意图，把输入切回 raw、清掉文件，未提交推理请求。独立走查在导入后和新增后各遇到一次。前端已改为目录与一次性入口意图 settle 前显示准备状态、不挂可交互输入；原副本两次快速选择 Frame 和提交已通过。修复前记录为 `incremental/operator-ui-check-before-navigation-fix.json`、`operator-error-before-navigation-fix.png`，修复后是下述完整短链。
2. **静态同签名组暗示本次已支持并列。**正常窗口新运行 `6d354f30-a787-4be6-af92-80ade4b1377c` 没有排名，14 项条件全假；几何不足新运行 `a4ff94e0-69e9-415c-96b0-fbd60e12b940` 也没有支持候选。组卡曾写“并列不是运行错误”，没有标本组均未获支持。前端已按 candidate_checks 分开作者诊断与实际支持；同一运行独立实屏回读显示“本组本次未获支持……不是本次排名并列”，正常组为 0/2、缺测组为 0/7 具备资格，没有改分组或排名。RootKGD 运行 `dde846a7-ad8d-427e-ae34-fcd6fcfc05fb` 已正确分开 14 项作者条件与 52 维结构输入，条件为 2 真、12 假。三状态实际 API、修复前后屏幕为 `incremental/state-diagnostic-runs.json`、`state-diagnostic-ui.json`、`state-diagnostic-ui-after.json`、`05-*-diagnostic.png`、`09-*-diagnostic-after.png`。

### 一条真实“发现同组 → 补条件 → 固定输入检验 → 撤销”短链

仅操作独立导入并启用的审核副本 `graph_ef7ee725081f4d2e95283ba18eadc729`，使用未改动的公开玻璃 006 冻结 Frame：

| 状态 | 实际任务与运行 | 可检查的变化 |
| --- | --- | --- |
| 原图基线 | task_b5beef6239be4aefbd164c5435697697 → 49bb6223-41c7-4954-a428-70fbdef9b01e | 7 个候选同签名。 |
| GUI 新增并分析 | task_c8265666e5b945e980cdaaf0d0270336 → e61fd3f3-21f3-4b7c-904e-093969567c94 | 只给“玻璃料温过低”候选新增必要条件，原组变为 6；新条件绑定真实面积观测 0.2284393310546875，满足 >=0.2，支持路径引用新条件和原观测。 |
| GUI 撤销再分析 | task_75a6a467673a4db8952318fa35cca258 → 793a023f-f3e0-4717-a564-822d5f698f51 | 当前知识与保存基线逐字段相同，组恢复 7。 |

条件 `candidate-condition:c840df04b11f420e911b8f24b33e74dd` 明确标为人工能力对照：只测试候选专属条件、分组和快照，不声称 ROI 面积能识别玻璃料温，也没有补充 Finish 部位信息。来源为空时生成的声明为 declared_demo_heuristic，没有伪造材料定位。

撤销后通过“已保存分析”重开 `e61fd3f3…`，实际界面仍显示原必要条件、面积 0.2284、联合门控和该次源边路径；API 的原图快照保持不变，没有拿当前已删条件的图替换历史解释。审核副本当前已恢复，不改默认演示图。脚本为 `incremental/operator-ui-check.mjs` 与 `operator-ui-resume.mjs`，回读为 `operator-ui-check.json`、`operator-*-run.json`；关键实屏为 `06-candidate-condition-form.png`、`07-added-condition-diagnostic.png`、`08-historical-condition-after-delete.png`。没有模型调用或 JS 错误。

### RootKGD v2 最终服务的独立消费

固定原生 TEP d04 Frame → `task_2b54af461fc74938a1052dd253e54bdb` → `f0cca0c7-f7f7-4f1f-8e12-ec8f13296acf`，实际使用图 `graph_c6d2a470450e41369de3fc7bdcaaf459`。保存结果为 `tep_rootkgd_propagation_v2` / `rootkgd-host-channel.v2`，含 15 条 host-channel 足迹、8 条 effect；仍是 13 个不同通道知识覆盖，不把足迹边数当通道数。

独立仅检查这次服务产物：21 条主路径全部引用该运行保存 canonical 图的真实连续边，support_obs_ids 均存在；默认图本次没有备选路径，冗余表示的 1 条备选采用上面的有效对照。实屏将 14 项作者条件与 52 个评分输入分开；点击 xmv_10 路径，左侧切到 XMV(10) 的完整 161–260 窗口曲线、均值 z=7.17、贡献 0.4609，与该路径相符。没有调用模型或改工作图。

记录在 `incremental/root-v2-api-run.json`、`root-v2-api-check.json`、`root-v2-path-check.json`、`root-v2-ui-check.json`；脚本 `root-v2-consume.mjs`、`root_v2_path_check.py`、`root-v2-ui-check.mjs`。实屏为 `10-root-v2-diagnostics.png`、`11-root-v2-path-channel-linked.png`。

资料 owner 另完成本次投影变化影响的 4 组 Root API↔CLI 回归，以及当前原始 d04 三窗口运行 `48595ebd-a532-4c98-9464-5cb2730bac29` → 直接下载 Frame 普通上传 `43311a86-a894-4bb9-b884-88ae7f8186b4`。其保存记录显示候选、组件、状态与 52×100 曲线逐项精确相同；正常窗口保留完整观测但无排名，两个异常窗口保留冷却候选并列。与 v1 的次序和状态不变，分数末位差最大 1.11e-16。本审核直接读取有效记录 `backend/runs/two_loop_demo/rootkgd-v2-consumption-20261111/verification.json`，没有重复这些生产者回归；它们与上面的独立路径/实屏检查分别提供证据。

### 新制作合同暴露两层问题，预算修复不能掩盖语义退化

资料 owner 用相同公开 Emhart PDF 的第 13、20 页，按新的 finite 值域与可选绑定合同实际提交 `task_2b5e770ad3114218bba64e58847b9cb5`。任务初次生成 20 候选，唯一一次修复仍为 17，均超过当时的 16 上限，因此停在 validation failed。实际只调用两次、保留原响应和失败任务，没有无限修复或假报成功。

第一层是**可执行编译的工程预算断点**，不能混成“资料没提供知识”或“当前样本确实缺部位”。16 是当时 capability 的制作预算，推理器默认候选搜索预算为 128，并非只能执行 16 候选；本轮选择分开 prompt 的紧凑建议与明确可配置的编译硬边界，拒绝真正超界包但不截断候选或来源。

第二层更本质：**泛缺陷存在被误写成细外观的充分条件。**独立读取两个真实 proposal，两个签名都为 `ANY(外观包含 broken_finish/chipped_finish, appearance.defect_present=true)`。仅放宽数量预算可以通过类型验证，却会让“看到了某种缺陷”单独支持细 Finish 签名；当前 006 没有确认部位，不能因此获得这种支持。这是知识编译语义退化，不是同义词映射问题，也不是 reasoner 的 false/unknown 运算错误。

后端已补最小 gate-aware 编译约束：只有 `detection.anomaly_present` 与 `appearance.defect_present` 这两项已知 presence gate 被前置，不把所有布尔特征一概当门；ANY/at_least 保留具体诊断原子的选择逻辑，剥离门后 at_least 已不可能则拒绝，不猜计数。每条可达 canonical proof 都必须有具体诊断 cue，纯 gate 分支不能绕过。ALL 的等价重组不改义，ANY/at_least 的收紧明确记录原逻辑及 **semantic_change=true**。推理内核和 RootKGD 不改。这次修复只约束已知退化形式，不证明开放外观词已具备完整部位层级或工业区分语义。

最后 API 的实际目录已确认为 `recommended_max_candidates=16`、`max_candidates=32`，硬上界可配置至 64，推理器默认搜索预算仍为 128；候选和来源不截断。窄条件 operator 的目录及 POST 也不接受仅泛 presence/context 的“诊断条件”。独立回读见 `incremental/final-authoring-contract.json`。

这一反例没有被扩大成“默认三图也都退化”：资料 owner 只读展开默认 live/seed 三图，共 16 个 pattern、25 条有限证明分支，generic-only 分支为 0，live 与种子除导入标识外相同，未改知识。审核直接读取 `rootkgd-v2-consumption-20261111/default-gate-audit.json`；这项针对检查复用既有演示证据，不重跑原始模型。

**最终恢复链已实际执行：**资料 owner 将 `proposal-1` 经新 compiler 离线编译，不删 17 个候选、2 个 pattern、26 项来源；两项 `presence_gates_lifted` 均记录原 `authored_logic=any` 与 `semantic_change=true`。完整包正式导入并启用 `graph_538efc4369b64b46a879dd5a30652bc1`，build_id 显式为 `offline-recovery:task_2b5e770ad3114218bba64e58847b9cb5:proposal-1:budget32:presence-gates-v1`。普通上传未改 006 Frame，任务 `task_7898d4c1f0464b5287de779a7a47e7d3` 完成，运行 `c846c64a-2388-4c3a-9827-25c4cb770496` 为 insufficient_evidence、0 排名。

独立直接回读 API 核实：输入 Frame 与原公开冻结文件逐字段相同；两 presence 事实为真，`broken_finish/chipped_finish` 两细 cue 均为 unknown，原因是开放候选集没有反驳或确认它们；实际值仍为非穷举的 `cracked_or_missing_glass`，没有应用任何 ValueBinding。原响应与保留副本内容完全相同，原 task 仍为 failed，新增 LLM 调用为 0。

因此当前有效证据是**真实响应 → 记录在案的逻辑收紧 → 正式导入启用 → 当前 Evidence 的合理负结果**；不是最终配置下又得到一次新的 LLM 成功任务，也不是自动完成 Finish 层级适配。使用这张细 Finish 图仍需相应细部位观测，或有明确依据的适用范围调整；推荐的演示适配图与它应分开选择。

实际请求、任务阶段、能力目录、两个原 proposal 与报告保存在 `backend/runs/two_loop_demo/rootkgd-v2-consumption-20261111/current-llm-contract/`；`offline-recovery-budget32-gate-aware/recovery-manifest.json` 明示恢复与语义变化，`offline-recovery-api/` 保存正式导入、启用及运行。独立只读消费为 `incremental/source-recovery-consume.mjs/.json` 与 `source-recovery-api-run.json`，没有重跑 Frame 或模型。

## 6. 下一层优先级：先补有来源的区分知识，再增强组合推理

1. **按观测能力编译知识，而非强制候选各有独特签名。**当前提示已经要求共享不可区分现象、禁止伪造差异；下一步应把产物中的“多个原因共享的现象条件”“有来源的候选差异条件”和不可观测缺口变成可检查的编译报告与修正入口。优先增加有来源的方向、波动、时间和空间条件，用固定 Frame 检查哪个候选应被支持、反驳或保留未知；资料没有差异依据，或当前没有这种观测，就继续保留同组竞争解释，不补任意阈值或修改成本制造首选。等价词汇只处理同义表达，不能越过“玻璃缺损≠已确认 Finish”的概念粒度与部位层级。
2. **补制作范围与覆盖摘要。**材料片段选择、unsupported claims、已用/未用测量等应成为用户能采取行动的界面，而不是只留本机报告。
3. **再定义跨主体/跨窗口组合。**明确关系、单位、时间对齐和证据来源后，扩展通用组合推理；不能把“已保存数组”当作已经支持动态因果。

制作能力中仍待后续处理的具体缺口：

- **材料范围不可自助控制。**制作请求只收 material_ids；103 页 PDF 虽可预览片段，却不能勾选页/片段。超过 100000 字符时 compiler 提示“select located material chunks”，产品却没有这个选择入口。Demo 的 13/20 页是后端 metadata 特例，不是普通资料可用的操作。参见 `two_loop_runtime.py:79–105`、`unified.py:210–213`、`MaterialsManageView.vue:106–114`。
- **制作成功报告没有成为修正入口。**compiler 记录 unsupported_claims、已用/未用 features、来源范围和修复事件，但主要留在本机 build 报告，UI 成功后只引导看图。用户不知道缺哪类测量、哪些来源没有进入图。应把必要覆盖摘要接到结果，而不是添加人工审核门。
- **可观察与可区分不是一回事。**多种原因共享破损表现时保留并列是正确的；不能靠加任意阈值/几何或修改假设成本制造唯一根因。下一步是告诉用户需要哪种区分性观测，而不是把材料中的所有工艺原因都称为当前已证实原因。

## 7. 已有基础值得保留，测试基线也已修复

真实任务阶段及有界修复、缺测/阴性/冲突区分、严格类型/单位/范围绑定、完整 Frame 与图快照、可执行规则表单、持久保存及备份、完整图包交换都已经有用。**当前通用性主要在 typed Evidence、可执行条件、图快照与解释器插件**，不是已解决跨时空关系或真正原因可区分性。上轮 TEP 原始↔Frame 精确复算、MVTec 与 Wafer 源边/媒体证据继续有效；本轮已另外完成 RootKGD v2 的同 Frame、实际路径及原始↔Frame 消费，没有拿旧数值替代。近期应沿这些能力接通“发现不适配 → 定位 → 修改 → 用同一 Evidence 检验”的短路径，建立观测约束下的知识编译与对照验收，而不是推翻三页、先换更大 backbone 或另造推理平台。

测试按阶段区分：`7c5e838` 清零原有实际 23 项失败时为 **478 passed / 4 既有 optional skips**；加入目录、诊断和候选条件后 `13d8d4f` 为 531/4；投影修复 `153eea3` 为 **538 passed / 4 skipped**。最后加入来源预算、presence 安全和 6 项 demo 调用方测试，原 backend owner 全量原生 pytest 为 **566 passed / 4 既有 skips（11.37 秒）**，Ruff 与 whitespace 检查通过。没有删有效测试或新增 skip/xfail；这与较早验收的历史失败不是同一候选。最终前端 `6854ad7` 的原生 Vitest 为 **17 文件 / 84 项通过**，类型与生产构建通过，记录见 `src/doc/rootlens-two-loop-frontend.md`。独立审核复用了这些有效测试结果，只补上述实际 GUI、保存产物、源边和状态消费，没有重复全矩阵。
