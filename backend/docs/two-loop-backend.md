# 双闭环后端执行记录

## 目标与所有权

本轮截止 2026-11-11 08:06:41 Asia/Singapore（00:06:41 UTC）。三个执行 owner 均为 GPT-6.1 Sol max：

- 后端：`backend/src`、`backend/tests`、`backend/scripts`（不含 demo 脚本）、本文件与 `src/doc/rootlens-two-loop-backend-contract.md`；唯一 Git 管理员。
- 前端：根 `src/`（`src/doc` 除外）、package.json/lock。
- Demo：`backend/data/demo`、`backend/runs/two_loop_demo`、`prepare_two_loop_demo.py` 与演示文档。

分支 `codex/demo-two-loops` 从干净的 `471e1aa` 创建。阶段 commit 只在主 owner 协调稳定点后逐路径暂存，不 push。

## 里程碑

- P1：冻结接口、持久任务骨架、正常／中断状态语义。
- P2：素材→可修改→启用；原样本／Evidence→双引擎→保存结果两闭环实库贯通。
- P3：独立 UX 审核、真实模型／RootKGD／API 重启验证。
- P4：清理确认废弃重复入口、相关检查、可运行交付。

## 当前决定

新任务与分析使用 PG 增量 JSONB 表，原运行／数据不重建。一个 API 进程有两个线程 worker；用户手动 retry 才创建新任务。任务重启恢复为 interrupted。LLM 未知长度阶段不生成进度百分比。

RootKGD 图传播复用 `simulate_propagation`、`trace_path`、完整向量余弦、贡献覆盖与传播熵结构评分；不复用固定旧图、故障标签、历史 memory 或按故障族 tie-break。同通道多谓词按稳定身份聚合，不把它们当独立变量。输入需完整正常参考、异常门控与 52 维贡献。

实际接口以 [前端契约](../../src/doc/rootlens-two-loop-backend-contract.md) 为准。

## 稳定后端交付（2026-11-11，Asia/Singapore）

### 已实现

- 新路由 `service/two_loop_api.py`、任务状态机 `two_loop_tasks.py`、PG存储 `two_loop_store.py`、双闭环执行 `two_loop_runtime.py` 与 `002_two_loop_tasks.sql`。
- 素材解析按实际资料数报告进度；真实LLM调用、自动校验、唯一一次有界修复、确定性编译与隔离图装载各有独立事件。默认最多两次模型调用，`max_repairs=0` 可关闭修复；失败任务不自动重新排队。
- 工作图 `enabled` 持久状态与可编辑 `ready` 分离。推理提交时固定完整知识快照，后续改图不改变已保存结果。
- 原图、52通道过程 `.dat/CSV + reference_file`、原始 0/1/2 晶圆网格、adapter records、原生 `rootlens-evidence.v2` Frame 均有明确入口。原生 Frame 不再受旧 Evidence 上传合同限制，完整保存在新分析表。
- RootKGD 独立传播引擎使用当前图，不使用旧固定图、fault标签、memory或fault族加分。全部52维真实贡献参与向量比较，同通道多原子不重复当变量；正常门控、图不可达贡献和每项评分分解可检查。
- 实际生成Frame可从 `/api/analyses/{id}/evidence` 下载并重传。媒体仅从受管demo manifest或原始分析实际生成的资产解析；普通JSON内任意本机URI不读取、远程URI不抓取。缺媒体仍执行可复算统计并明确标注。
- 演示材料导入是真实素材登记；预制图包下载与原始制作分开。配套数组/图像走白名单资产，不由前端猜本机路径。

### 实际证据

- 新单测覆盖任务状态/游标/真实计数、失败输入保留、手动retry、新进程中断恢复、完整52向量、正常门控、同通道去重、当前图改动、连续源边、普通Frame安全与raw→Frame精确复算。
- 相关集合 `test_two_loop* / test_rootkgd_working_graph / test_unified* / working_graph*`：**118 passed / 3 skipped**；producer/新功能/LLM制作相关集合：**62 passed**。最后的媒体／trace／正常零残差门控修正再跑关键集合 **25 passed**；修改Python与新增测试 Ruff、diff-check通过。
- 完整pytest在指定PG55433/Neo4j57687：**455 passed / 5 failed / 1 skipped**（执行时尚未加入后四项API与两项进度测试）。五项与本轮前基线相同：缺历史 real-output case、缺wm811k旧输入、缺旧图片/mask/heatmap、缺capsule crack/000.png、旧auto必须PatchCore断言。不是全部通过。日志 `/private/tmp/rootlens-two-loop-pytest-isolated.log`。
- 真实普通上传过程Frame→RootKGD→新PG Run：`fe74d822-7ace-4097-88cc-27673d883d8e`。首位为反应器冷却入口温度/阀粘滞并列，未宣称唯一已验证根因。完整任务/Run JSON在 `runs/two_loop_verification/native-rootkgd-{task,run}.json`。
- 真实非付费等待worker任务 `task_98a1dd3b70a3447682ede49554cf9440` 被终止后，API重启读取为 `interrupted/WorkerRestarted`；原Frame保留。显式POST retry创建 `task_1dd38ae0b4f442c983a2c1da51294031` 并完成，记录 `runs/two_loop_verification/restart-manual-retry.json`。
- 首次真实原厂PDF构图任务 `task_6f8bc887ec9e4bbb9ac8360dba1bcd1b` 实际LLM返回10候选，被旧6候选上限在validation阶段拒绝；原响应和失败事件保留。提升一致预算后的新明确构图已成功，见下方消费记录。

### 服务与消费方

API当前为 `http://127.0.0.1:8012`，由手动加载的会话作业 `com.rootlens.dev.two-loop-api` 管理，最后一次显式重载后的PID为 **7365**（实时值以status为准），不归属 agent exec session。只连接独立PG55433与Neo4j57687。task worker要求单API进程（两个线程），不支持多个Uvicorn worker同时接管同一任务表。

前端owner已收到契约、真实RootKGD Run和媒体字段。demo owner已冻结13样本／3工作图与准备复演脚本，17个“样本×引擎”的中间入口API结果与独立CLI完全一致；实际视觉正负结果都保留。Git按后端、冻结演示、最终前端／验收分阶段本地提交，不push。

### 实际消费追加

- demo owner 的 `runs/two_loop_demo/api-e2e-002/state.json` 已记录32个三场景分析任务与一次新原厂PDF制作全部completed，零服务失败；新源构图 `task_8217b6fb3f274fceb9d8519be95f2f38` → `graph_7718009df1d94a288f99d1e428487679`。构图成功不等于所有样本有候选，实际无匹配和语义不足均保留。
- 直接消费其原始TEP RootKGD Run `6fc02e0e-9455-4412-b4c3-1f6d4605db17`，下载实际3窗口Frame后，以同图、同reasoner和原top_k=8普通上传，得到 `c2528b72-3486-42a4-b0f8-d1a4a52f8f0a`：全部结果与52通道曲线逐项精确相等；没有backbone或LLM调用。记录 `runs/two_loop_verification/actual-raw-frame-roundtrip.json`。先前以默认top_k=5试传会少返回候选和路径，因此复算必须固定该展示选项。
- 多晶圆原始输入的每片网格已注册为独立受管资产；Frame重传保留正确网格，不重复拿第一片。最新关键集合25项通过，含新回归。
- RootKGD trace明确列出52个scoring_input_obs_ids；所有贡献都参与余弦，不因只展示8条路径而误列unused。
- 最终PID75700实例重新消费同一原始3窗口Frame，得到 `f6c8f922-ec11-45c4-9738-1fbebde4c191`：全部候选、分数、components和52曲线与原raw Run相同，52评分输入trace正确，无模型调用。记录 `runs/two_loop_verification/final-api-roundtrip.json`；正常门控也接受真正零残差/零贡献的正常窗口。
- 原manifest曾误把晶圆论文放进bottle.materials；demo owner已纠正清单。本轮刚登记的 `demo_bottle_wafer-original-paper-excerpt` 保留ID/原文件，已修正scenario=wafer与metadata并重解析，旧提取历史不删除。

## 02:39 断连恢复：进程归 launchd，不归临时执行会话

旧PID75700已不存在、8012无监听、exec session16711不可取回。旧启动没有持久退出日志或退出码，因此不能据此认定Python崩溃；已确认的问题是旧交付缺少独立于工具会话的进程所有权与退出证据。

新增 `scripts/development_api.py` 通过 launchd 手动加载项目专用会话作业。配置只放被Git忽略的 `runs/development_services/two-loop-api/`，不写 `~/Library/LaunchAgents` 或系统启动目录，不设置登录／开机自启。`KeepAlive=false`，进程退出不自动启动模型任务；用户明确重启后，旧未完成任务仍按 interrupted 处理。

从 `backend/` 运行以下命令。当前手动作业保存的连接是本轮测试库；后续start复用该配置，不退回普通库。首次创建新命名作业时，显式提供其数据库环境设置。应用API密钥仍由已有 `.env.local/.env` 读取，不复制到plist。

```bash
uv run --offline --no-sync python scripts/development_api.py status --name two-loop-api
uv run --offline --no-sync python scripts/development_api.py health --name two-loop-api

# 显式停止／启动这个命名作业；不按端口杀进程，不管理数据库。
uv run --offline --no-sync python scripts/development_api.py stop --name two-loop-api
uv run --offline --no-sync python scripts/development_api.py start --name two-loop-api --port 8012

# 独立检查历史任务、Run、实际Frame与所有可用媒体附件。
uv run --offline --no-sync python scripts/development_api.py health --name two-loop-api \
  --task-id task_8217b6fb3f274fceb9d8519be95f2f38 \
  --run-id e1794575-3526-41b2-8cf7-ac650336b1b7
```

- PID／启动记录：`runs/development_services/two-loop-api/service.json`；实时退出状态由 `status` 读取launchd，不打印连接凭据。
- 持久stdout/stderr：`runs/development_services/two-loop-api/api.log`。
- 最新独立健康记录：`runs/development_services/two-loop-api/last-health.json`。
- 实跑恢复证据：启动命令已退出后，后续独立exec仍读取到PID77728/PPID1；运行超过一分钟后health为ok，历史构图任务completed、历史Run与Frame可读，四个媒体附件均HTTP可读。launcher相关6项测试、Ruff通过。
- 交接后存活已由demo owner在本owner结束turn后独立GET确认，实际时间／HTTP状态见 `runs/two_loop_demo/handoff-consumption.json`：2026-11-11 02:42:20 Asia/Singapore，health、历史完整分析及其中原图均HTTP 200。此消费证据不依赖原启动命令的返回值。

## 下载原名与手动重载收口

独立GUI审核发现：只返回 `application/x-ndjson` 时，Chrome会把晶圆素材命名为 `.ndjson`，而原始loader按实际 `.jsonl` 入口读取。现资产响应显式设置 `Content-Disposition` 的真实安全文件名，不扩大后缀兼容范围。实际GET已确认 `wafer-nearfull-248536.jsonl`、`sequence_04.dat`、`sample_006.png`；Wafer下载后不改名直接交既有loader可读。3个HTTP文件名契约用例通过。

该次受控重载还暴露launchd卸载的异步状态：旧job仍在SIGTERMed时立即bootstrap会返回EIO5。持久日志显示旧API正常shutdown，随后job确实卸载；管理脚本现等命名job实际卸载再启动，不按端口杀进程、不提权绕过。launcher/API针对集合13项通过；真实下载头记录为 `runs/two_loop_verification/download-filenames.json`。GUI下载→原名上传由独立reviewer另行消费验收。

## 默认测试隔离与历史失败清零

2026-11-11后续阶段从已推送的 `a5faf68` 重现默认命令：

```bash
cd backend
UV_CACHE_DIR=/private/tmp/rootlens-plan-uv-cache uv run --offline --no-sync pytest -q -ra
```

首次实际结果为 **23 failed / 450 passed / 4 skipped**，不是只有先前已记录的5项：旧adapter／实验／service单元测试遗漏KG依赖注入，默认尝试Neo4j7687；URL测试还要求绑定本地HTTP服务。未为本次清理读取／修改数据库，也未启动模型下载或付费调用。

五项原失败均保留有效覆盖，没有删除测试、降低断言或新增skip/xfail：

| 原测试 | 原因 | 处置与保留覆盖 |
| --- | --- | --- |
| case index包含固定real-output ID | 断言本机忽略目录中一定存在旧实验结果。 | 使用checked-in样例与临时生成的完整Evidence目录，检验合并发现、generated来源标记，以及缺少可选目录时的正常行为。 |
| 固定`wm811k_row_100402` detail | 依赖未入库的旧输出JSON。 | 临时完整wafer Evidence＋显式seed KG，仍实际执行详情分析，断言候选路径、workflow与claim边界。 |
| records媒体预览 | 引用缺失的旧图片／mask／heatmap。 | 生成16×16 PNG与2×2 mask/heatmap，在临时受信根目录下验证image/mask/heatmap/wafer_map四种预览、角色标签、浏览器URL和PNG响应；不放宽生产路径检查。 |
| 未标注图片上传 | 依赖capsule旧原图和本机checkpoint。 | 小型PNG、显式checkpoint存在性fixture与注入predictor，保留真实producer→adapter→KG链，仍断言unknown标签与无臆造形态。 |
| auto模型必须PatchCore | 把机器有无权重误当固定默认行为。实际优先级本就按可用性选择。 | 控制三个checkpoint路径的存在性，覆盖PatchCore优先、仅EfficientAD/STFPM可用、仅STFPM、均不可用四种组合；不修改正确的生产优先级。 |

其余网络依赖通过明确的checked-in `seed_graph`／真实 `seed_pipeline` fixture注入；子进程CLI使用既有 `--kg-node-path` 显式入口。原生产默认仍连运行时Neo4j，新增测试直接验证连接、按dataset缓存、关闭，以及失败时不偷偷回退seed。

URL测试在实际`urlopen`边界注入404和随后成功的响应流，继续走真实fetch、定位解析、失败记录、明确重试和compiler交接；不需要外网或本机监听端口。真正数据库集成测试仍需独立数据库显式opt-in，真正模型有效性仍由已有原始模型／独立演示验收承担，单元fixture不冒称模型复现。

当前四项skip均为既有可选外部验证：3项要求`ROOTLENS_TEST_DATABASES=1`与指定隔离PG／Neo4j，1项比较原TEP_KG checkout但本机未安装。未新增skip。

同一默认离线命令最终为 **478 passed / 4 skipped，8.76s**；修改过的测试文件Ruff通过。全部有效断言保留，原来依赖机器状态的断言改为控制输入／依赖后验证真实行为。日志保存在本机临时目录 `/private/tmp/rootlens-test-cleanup-{before,after,final}.log`，不入库；本轮没有重跑backbone、LLM或数据库集成矩阵。

## 两小时增强：制作词汇与显式等价绑定

用户后续授权先推送验收基线，再按闭环增强；本阶段为2026-11-10 19:35:49–21:35:49 UTC。`a5faf68`已按正常非force流程推到`origin/codex/demo-two-loops`，本阶段后续commit只留本地。测试清零为`7c5e838`。

- `schema/feature_catalog.py`集中维护kind、unit、定义、参考需求和有限类别；掩膜producer使用其中同一组常量，capability与LLM实际prompt复制同一目录，公开`GET /api/authoring/capabilities`供编辑器消费。定义使用中文、机器ID与词值不翻译。
- 修正旧声明与真实输出漂移：morphology不再声称`irregular/compact`，位置不再声称`upper/lower/...`。有限类别未知operand和绑定canonical目标明确报错，可触发现有唯一修复。开放appearance不设伪枚举，不从粗外观补解剖信息。
- Blueprint新增来源明确的`equivalent`词汇绑定，确定性降低到既有ValueBinding。实际source/unit/locator随映射保留；`llm_proposed`不能声称词汇等价。人工图编辑仍走完整PUT，不另造规则系统。
- KnowledgeProgram按feature与procedure model建立绑定索引；条件比较使用映射，保留原观测和实际binding IDs。模型专用映射在同义全局映射上优先记录，但不允许重叠映射给出不同canonical值。
- 新回归实际走完整图API：导入副本→无绑定不匹配→PUT绑定→回读→新pipeline匹配且原值不变→删除→下次不匹配；已有pipeline快照不变。均为受控内存store／repository，不改演示图或真实数据库。

服务重载前与前端协调空窗，并只读确认79个已存任务均无queued/running；专用作业重载后PID96453、health=ok，新目录HTTP实际可读。前端随后消费该接口，不重复调用模型。

## 同次快照的可分辨性诊断

独立方法owner实现纯模块`core/candidate_discriminability.py`；后端只在`two_loop_runtime.infer`的解释完成后调用并将`result.authoring_diagnostics`随run持久化。模块不读数据库、不调用模型、不重新运行推理，要求知识graph ID与Frame case ID对应本次结果。

统一引擎按可达条件／期待模式签名显示数据无法区分的候选组，cost先验分开。RootKGD按真实52维传播／观测向量及结构评分项分组，作者条件检查不参与其评分。未生成完整结构输入时明确unavailable；诊断展开预算不足明确incomplete，不推翻已有推理。覆盖统计将条件grounding与实际评分输入区分，正常门控标记未排名。

独立模块22项单测加运行时集成覆盖同签名不同成本、方向／std／slope条件、正常门控、缺向量、搜索不足、快照／Frame错配。原始过程→Frame导出→原生重传的结果（含新诊断）仍精确相等，RootKGD实际评分输入数为52。历史run GET保持原JSON，不用当前图补诊断，另有直接回归。

诊断整合阶段的默认完整离线pytest为 **512 passed / 4 skipped，10.95s**，四项仍为上述既有外部opt-in验证。日志`/private/tmp/rootlens-two-hour-final-pytest.log`；修改代码及新测试Ruff、diff-check通过。依照当前AGENTS，仅用项目原生pytest/Ruff，跳过skill附带的bootstrap、telemetry、全局安装及flush，不执行或重试外部上报。未使用新增skip/xfail、付费模型或真实数据库测试来获得此结果。

## 候选局部条件：从诊断到补条件再撤销

后续同预算内补`service/candidate_conditions.py`及`working_graph_editor.update_working_knowledge`：GET给合法目录／已绑定通道／现有zone；POST在已有锁内创建一个诊断predicate、独立pattern、目标hypothesis直连expectation和明确作者assertion；DELETE只撤销这组独立内容。不是把新条件接到共享机制，使原本同组的所有候选一起得到该期待。

复用已有异常gate与新predicate做ALL，不复制相同测量票数；直接回归证明其余数值为真但显式anomaly=false时仍不能获支持。缺gate、未知变量／来源／单位／范围在写入前具体报错，不改变原分析入口。无来源标记人工`declared_demo_heuristic`；已有实际来源按ID保留。撤销先检查其他规则、模式与作者来源引用，拒绝误删共享内容；独立束完整删除，原gate不删。

19项新测试覆盖三场景、四种signed/std/slope条件、三个现有mode、正常前置、来源和范围错误、依赖保护、完整API保存→同Frame异步推理→拆目标签名→撤销→结果精确恢复，以及历史run快照不变。与既有API/editor集合共 **35 passed / 2既有DB skipped**，不调模型／真实数据库。

此operator交付时的RootKGD v1暴露表示耦合反例：固定结构只改阈值或mode不改变分数，但新增独立pattern路径会改变传播。冻结d04、同一冷却入口温度候选向已有xmeas_9新增路径，结构分数从0.5854474293642781变为0.38634032056418194，即使std阈值1e6为假。该阶段保留反例，下一节单独修复表示问题，不将逻辑C惩罚混入RootKGD。

前端与reviewer交出无任务窗口后，只读确认80项任务无queued/running，专用作业重载为PID99986、health=ok。实际GET默认TEP目录返回52已绑定通道、中文定义与合法算子；此GET未改默认图。前端／reviewer随后只对副本进行无模型Frame消费。

本operator阶段最终默认全pytest为 **531 passed / 4 skipped，11.00s**；Ruff与diff-check通过，日志`/private/tmp/rootlens-candidate-operator-final-pytest.log`。上述同通道新增路径改变Root评分是保留的表示耦合反例，后续投影归一化作为独立可恢复阶段处理，不把此阶段称为已修复该缺陷。

## RootKGD v2：逻辑改写不再变成物理传播票

独立投影模块`core/rootkgd_projection.py`规范化expectation管线，不改变`simulate_propagation`、有向衰减、完整52维向量、cosine／coverage／entropy或结构评分公式：

1. 保留可达的每条显式effect关系，不将源图因果边消除成逻辑简写，也不只选一棵首次推导树。
2. 同host／稳定通道的所有expectation、pattern和统计谓词映射为一条集合边，合并实际来源。等价AND拆分、重复pattern或同通道多统计谓词不新增传播票或额外衰减层。
3. 若上游host的同通道期待已由显式effect严格可达的下游host覆盖，上游声明只作为备选provenance，不生成shortcut；循环host不任意排序或全部消除。不同真实作用关系仍需明确的mechanism／effect表达。
4. 主路径与备选源路径分开，每条均使用实际连续源边；共享机制上其他候选的上游声明不会冒充当前候选的完整路径。没有按人工／LLM来源类别排除条件，没有使用故障标签选方案。

结果标记`scoring_method=tep_rootkgd_propagation_v2`与`propagation.projection_version=rootkgd-host-channel.v2`；历史run不改写。新7项回归覆盖重复pattern、AND拆分、同通道std谓词、上游冗余期待、未达新通道、显式effect敏感性、循环保留以及主／备选路径连续性。

冻结d04的旧反例在v2中：基线和新增同通道假阈值条件后，全部候选分数／向量／分解**精确一致**，该候选前后均0.5854474293642782。四Frame离线新旧对照保持首位次序：d04冷却入口温度／阀粘滞并列，d01进料温度，d05进料供给损失；正常仍不排名。部分分数有浮点末位变化，不宣称准确率提升。

完整脱敏对照与22条实际连续主／备路径核对记录在`runs/two_loop_demo/rootkgd-representation-v2/projection-checks.json`，各case的v1/v2结果与冗余声明结果同目录；全程无模型调用、数据库写入。旧演示17/17是v1历史证据；受影响的四个TEP×RootKGD组合由演示owner在v2 API恢复后单独更新，不重做13个统一引擎组合或原始模型。

最终投影候选完整默认命令为 **538 passed / 4 skipped，11.01s**；四项外部opt-in skip不变，新代码／测试Ruff与diff-check通过。日志`/private/tmp/rootlens-projection-v2-final-pytest.log`。前端、演示及审核owner均停止提交的窗口内，确认86个已存任务无进行中后，8012手动作业重载为PID3195且health=ok；随后分别交演示／独立审核实际消费，交付与消费证据分开记录。

演示owner随后已完成四Frame的正式API／CLI消费：全部候选、名次、分数、scoring_details与outcome精确一致，保留52评分输入与曲线，默认图没有备选路径时保持0而不强造。d04原始Run `48595ebd-a532-4c98-9464-5cb2730bac29` 下载实际Frame后普通上传为 `43311a86-a894-4bb9-b884-88ae7f8186b4`：3窗口、52曲线、分数／分解和CLI逐项精确一致。消费证据`runs/two_loop_demo/rootkgd-v2-consumption-20261111/verification.json`，未改默认图或输入Frame。

### 正式测试入口与依赖保留

已读实际调用链：`npm run backend:test -- -q -ra` → `scripts/backend.mjs`直接使用`backend/.venv/bin/python` → `scripts/dev.py test`以同一`sys.executable -m pytest -q -ra`在`backend/`运行。test分支在`configure_environment()`之前返回，不注入应用数据库默认值。链上没有uv同步／安装，和本轮`uv run --offline --no-sync pytest`使用同一环境与pytest配置；不为确认这条未变链重复跑完整矩阵或模型。

`backend/AGENTS.md`原日常验证示例可能让uv自动同步而移除未声明extras，现仅把验证示例改为`--offline --no-sync`，与首次显式安装分开。正式npm入口本身无需修改，ML／LLM环境与锁文件不变。

## 最后一次源构图检查：分开预算与语义安全

唯一新合同LLM任务`task_2b5e770ad3114218bba64e58847b9cb5`真实解析公开PDF后调用两次（18899 tokens），返回20候选／修复后17候选，因旧硬16在validation失败。任务、两份原响应和定位SourceUnits完整保留；没有图被伪启用，也没有继续付费调用。

16原本是紧凑作者建议，不是引擎安全边界。现在视觉／过程建议≤16，默认硬32，可由`candidate_limit`明确配置1–64，仍低于推理默认128候选预算；签名／证明分支／组合／状态限制仍执行，不保证任意复杂查询一定完成。wafer的8类是任务语义，不扩成工厂原因。17/20/32以及显式64候选完整编译、33/65越界、canonical绕过和查询预算耗尽均有直接测试，绝不截断或自动合并。报告与真实validation事件分别记录建议、硬限和完整保留警示。演示脚本两处旧TEP hard8同步改为软recommended8，不重跑构图。

进一步检查发现最终响应的两个ANY签名都是“具体broken_finish/chipped_finish OR appearance.defect_present=true”，仅放宽预算会让粗缺陷布尔分支伪装成细部位支持。因此共用目录新增`semantic_role`：仅已知通用检测／缺陷存在为presence_gate，参考量／原始附件等为context，其他具体测量为diagnostic；不是把所有boolean当门控。source lowerer把presence/context lift为ALL前置，只对具体诊断项应用原any/all/at_least，纯gate或canonical退化分支明确报错。ALL为代数等价重组；ANY/at_least收紧明确记录`presence_gates_lifted / semantic_change=true`及原logic、gate特征、剩余诊断项数，计数不可能时拒绝而不猜。事件展示收紧过程；存量蓝图离线编译不再伪报LLM阶段。

窄candidate operator的GET／POST亦排除／拒绝presence或背景作为单独充分条件，保留原编辑器修改已有gate。默认三图由演示owner只读核查：16 pattern／25 proof无generic-only分支；默认图与种子除graph身份外一致，因此没有改冻结图或重复无影响模型验证。

原最终`proposal-1.txt`以新预算与明确门控归一化离线编译，17候选、原文／source／locator完整保留，额外LLM调用为0。包位于`runs/two_loop_demo/rootkgd-v2-consumption-20261111/current-llm-contract/offline-recovery-budget32-gate-aware/working-graph.v2.json`，`build_id`明确标原failed task、proposal-1、budget32与presence-gates-v1；`recovery-manifest.json`保留原失败事实、两次调用和semantic_change。**这不是原样语义恢复，也不是把原task改成功。**原始响应另存`original-proposal-1.txt`。

离线使用未改006 Frame实际得到`insufficient_evidence`、0排名：通用缺陷为真，但fine Finish cue仍未知；没有加coarse→Finish映射或制造部位证据。正式新副本导入／启用／普通上传由演示owner在最后schema加载后消费，原failed task和默认图不改。

最后完整候选（含演示caller的6项新回归）为 **566 passed / 4既有optional skipped，11.37s**；命令仍为`UV_CACHE_DIR=/private/tmp/rootlens-plan-uv-cache uv run --offline --no-sync pytest -q -ra`，日志`/private/tmp/rootlens-final-all-callers-pytest.log`。全部改变的Python／新测试Ruff、diff-check通过；未新增skip/xfail、未删有效断言，未同步／重装环境。

确认94项任务均无queued/running后，仅手动重载专用作业为PID7365，health=ok；实际GET已确认推荐16／硬32／每签名32、两个presence角色及operator过滤。演示owner随后正式导入并启用恢复图`graph_538efc4369b64b46a879dd5a30652bc1`，任务`task_7898d4c1f0464b5287de779a7a47e7d3`→Run `c846c64a-2388-4c3a-9827-25c4cb770496`：`insufficient_evidence`、0排名，fine两项unobserved、presence两真、媒体可用、value_bindings为空。零新增模型／LLM调用，原构图task仍failed；消费证据`current-llm-contract/offline-recovery-api/`。这验证了资料恢复到可编辑／启用和真实否定推理，而不是用泛存在条件凑出Finish支持。
