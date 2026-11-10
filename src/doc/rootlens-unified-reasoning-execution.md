# 统一推理重构执行记录

## 目标与授权

落实 [统一方法与可复算规格](/Users/hhm/code/RootLens/src/doc/rootlens-unified-reasoning-method-plan-2026-11-10.md) 的 U0–U5。用户已授权设置持续 goal、新建分支、纳入现有未提交内容、分阶段 commit，以及必要下载、模型执行和实验。只在新分支本地提交；没有另行发布／推送要求。

- 分支：`codex/unified-industrial-reasoning`。
- 基线提交：`5777705`，完整保存先前渐进重构、前端改动和统一方法设计样例。
- 公共内核不得按 dataset 选择评分公式；不同场景只变观测适配、注册能力和知识。
- 前端保持三页，旧 Evidence／策略保持原合同；不覆盖既有数据库，不终止用户正在使用的服务。

## 阶段与完成证据

| 阶段 | 状态 | 交付与验收 | 提交 |
| --- | --- | --- | --- |
| 现有成果基线 | 完成 | 106 个现有修改／新增文件纳入新分支；公开模板核对，未纳入真实配置、权重和运行数据 | `5777705` |
| U0 契约 | 完成 | Evidence v2、公共知识 IR、类型／单位／引用／区域／正常参考校验；三个设计样例可实际解析、往返及生成 JSON Schema；初始 37 项合同测试通过 | `09322ec` |
| U1 公共内核＋MVTec | 完成；页面和回放已随 U5 验收 | 公开原图→PatchCore→ROI→公共内核→PG 运行快照，正例保留歧义、正常例无候选；视觉失败如实保留 | U1a `2081464`；U1b `950386a`；真实验收随 U2 |
| U2 LLM 构图与工作图 | 完成；过程／空间随 U3、U4 完成 | 原始厂家 PDF→LLM 领域蓝图→确定性编译→可加载知识；有界修复；持久编辑、完整交换、改图影响新推理；素材页仅加契约选择 | `591604b` |
| U3 TEP 同核 | 完成接入与真实反证；故障识别仍有明确负结果 | 实际正常参考、完整窗口／52 通道接入同一公共算法；3 个公开序列共 9 窗口，正常无候选；已知故障族进入候选但 top-1 不正确，保留首轮失败和修订 | `587c04d` |
| U4 Wafer 同核 | 完成适配与真实运行，内核未变 | 0/1/2 网格与独立 ResNet，8 个图案假设，18 个原网格实际同核运行；匹配、未匹配和原生类别分歧保留 | `aa1f556` |
| U5 评价与交付 | 完成 | 32 份同输入／知识平坦对照和去机制均等价；重复／缺失／删规则和权重消融；实屏及 22-case 回放；完整测试保留 5 项既有失败 | U5 阶段提交 |

## 已知基线与验证路径

先前基线：后端 345 passed / 7 failed / 1 skipped，前端 19 文件 / 89 项及 build 通过；详见 [前期验收](/Users/hhm/code/RootLens/backend/docs/progressive-demo-2026-11-10.md)。它是历史证据，不当成本轮测试结果。

后端使用 `backend/` 的 uv 环境；新检查先使用离线 `uv run --no-sync`，需新增依赖时按锁文件更新。真实库验证只用明确指定的隔离测试库。运行及实验输出进入被忽略的 `backend/runs/unified_reasoning/`，小型公共种子与测试入库。

Bits 测试工具的 bootstrap 会向第三方发送本机身份元数据并尝试安装全局工具，不是实现本项目所需操作；不执行该上传／全局安装，使用项目既有 pytest／Vitest 完成测试。项目凭据只通过现有配置读取路径供模型客户端使用，不输出到日志或提交。

## 当前交付

U0–U5 的约定实现与评价已完成。运行入口见 [统一推理使用说明](/Users/hhm/code/RootLens/backend/docs/unified-reasoning.md)，实际结果和失败见 [U5 验收](/Users/hhm/code/RootLens/backend/docs/unified-reasoning-u5.md)。现有 5186／8012 演示服务继续使用隔离库。下一研究重点是 TEP 知识／观测的区分能力；审核、正式版本治理和置信校准仍后置，未暗中纳入本轮实现。

## U1a：公共内核的实际证据

- 入口：`kgtracevis.core.unified_reasoner.UnifiedReasoner`；CLI 为 `/Users/hhm/code/RootLens/backend/scripts/run_unified_reasoning.py`。新模块未修改旧 pipeline 入口。
- 同一内核实际计算三份设计输入：MVTec 接触／磨损 J=0.25 并列、附着 J=1.916667 无支持；TEP 冷却 J=0.25、进料 J=1.916667；Wafer edge-ring J=0.25、nearfull J=1.916667。
- 实际运行输出：`/Users/hhm/code/RootLens/backend/runs/unified_reasoning/u1_core/manifest.json`，包含输入、知识、图视图与每个完整结果。仍是合成合同算例，不是 backbone／真实数据效果。
- 新合同＋内核测试 **63 passed**，新增／修改的统一推理文件 Ruff 通过。覆盖开放候选集、缺测与阴性、单位／正常参考错配、跨 ROI、重复／重排、完整反证、删边／改值／改别名、身份重命名、AND/OR/at_least、循环自支持、同分保留、搜索预算及 CLI 不覆盖旧输出。
- 当前一个 v2 Frame 表达一个聚焦问题；多个 ROI 由适配层生成多个 Frame，不将不同区域特征拼接。TEP 的一个 Frame 可联合多个主体变量，空间 Frame 可联合多个环带。

## U1b：工作图与现有产品合同

- 新 `rootlens-working-graph.v2` 保存完整 canonical knowledge。复用既有 PG 工作图登记、图锁、Neo4j 单事务投影、保存前备份和失败恢复；v1 包及旧策略保留。加载时拒绝与 canonical knowledge 不一致的投影。
- 原生 v2 入口 `POST /api/reasoning/{graph_id}/analyze`；现有原图／records 入口选择 v2 工作图时使用相同公共内核。图像 adapter 按 ROI 分 query，保留检测、几何和语义来源，不执行原生标签／任意 metadata，也不由标签缺席制造 foreign-material 阴性。
- 现有结果桥接使用真实 Neo4j 边 ID，保留 v2 源边、联合证明与完整 frames/results。独立 ROI 不进行隐蔽的跨 scope 分数混合。回放由保存的 canonical snapshot 重建显示投影，不读取当前图。
- 前端保持三页与现有 JSON 抽屉，选择 v2 图显示公共策略。v2 规则通过完整 JSON 修改，派生边不允许单独改写。服务支持删除整条 effect/expectation，影响后续分析；别名、绑定和条件均可往返持久保存。
- 合同／内核／服务接线／旧工作图／原 run payload 检查 **73 passed / 2 skipped**（真实 DB opt-in 尚未执行）；前端 **19 文件 / 89 项通过**、生产 build 通过。真实图像、实际 DB 重启和屏幕验收仍待执行，不能据此称 U1 全部完成。

## U2：原始资料构图与真实 MVTec

- 原始资料为 [Bucher Emhart Glass 2024 缺陷指南](https://www.emhartglass.com/sites/default/files/publications/2024-07/BEG_BR0060RevA-Defect_Guide-WEB.pdf) PDF 第 13／20 页，经现有 Docling parser 实际取得 **2 个定位片段、3008 字符**。未给构图模型任何测试图、测试值或原生标签。
- 直接生成完整 IR 的两轮实验均暴露方向／类型／悬空引用问题。改用小型 `KnowledgeBlueprint`：LLM 提领域签名和候选，编译器生成 ID、作用域、强制门控、共享机制、来源与边。同条件复用同一原子，显示文本改写不制造新候选。每次最多一次修复，失败原文保留。
- 最终蓝图有 **2 个观测签名、5 类竞争原因、4 个原子条件**，未臆造 source 未给的 break-size 阈值。48 节点／67 边公共种子（含显式 legacy 值别名）位于 `backend/data/kg/unified/bottle-working-graph.v2.json`。来源断言、执行知识、别名、绑定、完整 JSON 导入导出均可编辑保存。
- 素材／compiler API 可显式选 `target_contract=unified-v2`、`capability_id=visual-region-v2`，装载时显式使用相同契约；默认 legacy 入口不增加新前提。CLI 支持原始素材或既有片段，也可零模型调用重编译已保存蓝图。
- 真正 PG／Neo4j 测试已执行：此前整合 **14 passed**，另新增 v2 独立连接重载／删规则／重新导入／旧快照测试 **1 passed**。沙箱内 URL 测试的 bind 限制已通过授权复核，**1 passed**，不是代码失败。
- 实际模型：相同公开 bottle PatchCore、正常参考和配置的 ROI VLM；冻结知识分析 4 张异常测试图＋1 张正常图。2 张额外固定编号图返回 **4 个 rank=1、score=-0.25 的并列候选、12 条实际规则路径**；1 张异常被 VLM 判正常，另 1 张语义 uncertain，均无强配候选；正常图无候选。这是功能／失败走查，不是准确率评测。
- 初始图的 ROI 词汇只有空泛描述，现改为仅从图的观测断言提供有来源的外观释义，不向 VLM 发送原因候选。对首张失败图仅重做一次语义仍 uncertain，失败保留；未覆盖或改写成正例。
- 本轮实际产物目录 `backend/runs/unified_reasoning/u1_mvtec_actual/`：正例 run `3e83390c-8360-4f1e-a73e-ccb521e96d21`、`6136854b-0913-4f87-8917-703717d7db6f`；正常 run `038a083f-af8a-4b44-a81e-05e7a9a9fde0`。API 重启后继续使用同一库，原 run 与图保留。页面／回放最终验收仍待 U5。
- 构图失败记录、17 候选的过细蓝图、最终原始蓝图及公开 PDF 均保留在 `backend/runs/unified_reasoning/u2_bottle_*` 和 `public/`。最终包从实际模型原文重编译，未手填工业因果图；另声明的 legacy 符号映射是工程兼容绑定，trace 保留实际旧值与使用的绑定 ID。

## U3：完整过程数据进入同一公共内核

- `process-measurements.v1` 注册 adapter 生成一个 equipment／window Frame：53 个主体、**263 条观测**，包含全 52 通道的 mean-z、population std-z、OLS slope（单位 `1/sample`）、完整 PCA 平方残差贡献向量，以及实际原始序列资产；不消费顶层 top-channel 摘要或 fault 标签。
- 新 `.dat` producer 额外写入可直接读取的 `.npy` 窗口、闭合的正常参考资产清单和独立 fit ID；正常 CSV、均值／scale／PCA 文件明确绑定。缺少旧输入的参考资产时不猜参考，v2 返回不足／invalid；旧 CSV／Root-KGD／measured 入口合同未改变。
- 实测 slope 使用当前 producer 的 `np.polyfit` OLS，不误用另一份 legacy dynamic summary 的端点差。单元测试从实际数组与 scaler 复算，确认 52 通道、完整时间轴、参考错配拒绝、缺参考不伪造、改变 top-channel 摘要不改变 v2 结果。
- 构图原始输入为公开 `teprob.f` 变量／扰动说明和 `temain_mod.f` 控制程序，**3 个原始定位片段、22709 字符**。首轮中共享机制的模式冲突被拦截；错误现在同时列出所有冲突分组，避免修一处、遗漏另一处。
- 第一份可执行知识把两个冷却回路、level shift 与持续 slope 错设为同时发生，实际 d04 未召回冷却族。修订的是**通用知识制作约束**：替代症状用 OR／at_least，不因规则复杂而硬凑 AND；没有修改公共推理算法，没有把测试值或 fault ID 发给构图模型。
- 修订后的源知识为 **5 个候选、4 个签名、6 个原子条件、121 节点／106 边**，实际使用 mean-z、std-z、完整贡献中的图绑定通道及残差能量。完整向量在 Frame 中保留，未入图／未使用的统计明确列为 unused，不声称每个通道已对结果有贡献。
- 冻结该知识后，实跑 d04 及新增 d01／d05 的 1–100、161–260、261–360：3 个前故障窗口均无候选；6 个后故障窗口生成 3／4 个候选及 9／12 条实际路径。已知注入故障族在候选内，**三个序列的 top-1 故障族均不正确**；当前知识不能支撑故障识别准确率或优于旧算法的结论。两个后故障窗口来自同一序列，不当作独立运行重复数。
- API／PG／Neo4j 持久实跑：d04 run `0e04af33-6025-4095-8179-57b969638523`，d01 `54a7916a-c038-40c3-a7dd-6c4a63a08636`，d05 `535ce3b9-4ede-43a0-8aa5-d73f88877c5d`；全部选择同一 v2 图，不调用 process_graph_rbc／Root-KGD 排名。API 重启后 MVTec 原正例仍读取 4 个候选。
- 产物：`backend/runs/unified_reasoning/u3_tep_validation/` 保存 9 份 Frame、结果、真实数组、正常参考和完整 RunDetail；`u3_tep_actual/` 保留原图失败结果；小型公共知识包为 `backend/data/kg/unified/tep-working-graph.v2.json`。
- 统一合同／内核／适配及旧 measured 检查 **78 passed / 1 skipped**；修改的 Python 文件 Ruff 通过。U3 没有修改 `core/unified_reasoner.py`、`core/unified_grounding.py` 或候选编译算法。随后 Wafer 在该内核上增加空间观测与知识，最终界面及对照由 U5 验收。

## U4：冻结内核接入空间图案

- 新 adapter 只消费闭合的 `wafer-measurements.v1`，保留实际网格资产、shape、编码和同一 parent grid 下的 all_valid／center／middle／edge 作用域。内联网格会复算并核对测量；路径资产不由 adapter 任意加载。空网格／空区域的密度是 missing，不伪装成正常 0；0/1 正常 die 不当失效，bool/float 编码别名拒绝。
- density、八连通簇和线性程度来自数值计算；classifier.pattern 来自独立模型，不读 native_failure_pattern／annotation_state。分类任务声明 `pattern_family`，不把 nearfull 解释成颗粒污染等未观测制造原因。
- 资料为原始论文可取得的 PDF 第 3–4 页正文／caption 和模型作者卡，3 个片段、14348 字符。NIAR 的本地 PDF 下载经 curl／标准 Python TLS 均失败；已用 web PDF 提取结果保留原页码和获取方式，不声称本地 PDF／图表完整解析成功。
- 首个蓝图把相邻类别当作同一签名的替代原因，形成对称复制的候选，已保留为负例。现有 capability 可分别声明总候选／签名上限及每签名假设上限：分类签名单目标，竞争通过其他类别签名发生；机制诊断仍允许多原因。没有数据集专用评分或分类 rank 插件。
- 作者蓝图中的 scalar category membership 可由编译器明确降为 equality，并写入 normalization report；canonical IR 的错误类型仍拒绝，未放宽运行比较器。本次最终单目标源图没有该 normalization，也无需修复，生成 **8 签名／8 假设／20 原子，113 节点／143 边**。
- 同一 ResNet34 权重／作者预处理实际重跑 18 张公开原网格，随后冻结预测，只重分析知识。最终 7 张匹配：6 张与原生图案一致、1 张 Donut 被模型及规则解释为 Edge-Ring；11 张未匹配（含 2 张原生 none）。未按标签挑选成功样本，也未强配其余图案。
- 实际 run `5800defc-f490-48bd-9e9a-fd9d6fa33cae`，完整数据在 `backend/runs/unified_reasoning/u4_wafer_actual/` 与 `u4_wafer_validation/`；先前对称图的结果在前者保留，最终结果在后者。公共种子为 `backend/data/kg/unified/wafer-working-graph.v2.json`。
- 合同／三类 adapter／公共内核及旧 measured 检查 **82 passed / 1 skipped**；Ruff 通过。U4 没有修改公共 candidate compiler、grounding 或 reasoner；输入 schema 仅收紧固定 die 编码的 bool/float 别名。第三场景是架构迁移证据，不自动成为统计跨域泛化结论。

## U5：冻结比较、界面与交付

- 冻结 9 份真实 RunDetail 中的原始知识和 32 个 Frame：5 原图、9 TEP 窗口、18 Wafer 网格；没有替换成更新的种子、重跑 backbone 或再用 LLM 调图。
- 独立平坦参考复用原子 grounding／分支合同，独立展开和计算全候选损失与准入。**32／32 等价**；去掉中间机制但完整提升逻辑后果也 **32／32 等价**。未证明图存储本身改善准确率。
- 同知识单原子／路径参考在 MVTec 4／5、TEP 9／9、Wafer 18／18 有候选，完整联合支持分别为 2／5、6／9、7／18。移除冲突项改变 6 个 TEP 后故障窗口的分数／名次；统一权重 0／1／4 的完整结果保留，没有按场景调参。
- 32／32 重复同源观测、重排和改 dataset 保持代价／准入／路径节点不变；朴素重复行投票的平坦消融在 28／32 改变代价。有支持的 15 份输入，删除实际使用观测或 effect，各 15／15 计算／证明改变。ID 重命名／缺测对比阴性等性质由既有内核测试验证。
- 在相同 legacy observation 上复用旧图和三场景 reasoner／generic 作系统参照。旧 TEP cooling／feed 画像在 d04／d01 比新图贴近注入故障族，d05 未匹配；旧图／目标不同，不包装为受控准确率胜负。LLM 判断对照、训练与完整 benchmark 按冻结方案仍后置。
- 现有 Evidence／Graphs 仅补“推理依据”抽屉：全候选 U/C/A/J、实测／阈值、scope、反证／缺失、未使用观测、联合条件、源边和证明 DAG。实屏查看 MVTec 原图／ROI／mask／heatmap、TEP 52 通道和 Wafer 网格／空间统计；分数不是概率。修正跨页返回丢失窗口和构图按钮被窄列截断。
- 前端将原 bottle 工作图导入独立验收副本、修改别名并删 effect 后保存。独立 API 使用新别名分析得到 3 候选，原历史 run 保持 4。副本 ID `graph_ef3243718f7e44018164b5e4f3a468ab`，记录 `u5-ui-persistence.json`。
- `u5_replay/all-scenes-session.json` 经现有导入 UI 实际导入、刷新；3 Run／22 case、原图、完整时序、路径和代价保留在 IndexedDB，刷新期间无后端 `/api/` 请求。D3 仍有原有 CDN 依赖；不宣称全断网安装可用。
- 新增 5 份小型**真实测量** Frame 和期望结果入库，CLI 可直接读取 v2 工作图包，保留旧独立知识入口；无需 DB／模型可复算。完整 32 份便携摘要在 `backend/docs/unified-reasoning-u5-results.json`，详细结果／所有失败／权重敏感性在被忽略的 `backend/runs/unified_reasoning/u5_*`。
- 最终完整后端 **442 passed / 5 failed / 1 skipped**；5 个历史资产／默认模型断言失败在 U5 文档逐项列出。原 `env={}` 误读服务 Neo4j 配置的问题、单 case 上传保存前未补齐 cases 的旧 bug 均已修复；服务以新代码重启并实测旧入口持久化，原 run 保留。前端 **20 文件 / 95 项通过**、类型与生产 build 通过；修改的 Python 文件 Ruff 通过。完整套件不是全通过，未伪造旧资产清空失败。
- 新代码／小种子／样例／文档和阶段提交随分支保存，大权重／完整模型输出／数据库／凭据不入库。原数据／服务未重建，没有 push。
