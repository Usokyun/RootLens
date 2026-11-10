# 双闭环前端：交互与实际走查

2026-11-11。前端工作台以真实后端任务为主线，三个一级页面重新组织为：

1. **素材管理 `/materials`**：知识资料导入、真实解析、定位原文、多选资料与 LLM 制作任务。
2. **知识图谱 `/graphs`**：语义关系图、对象/候选/机制/联合现象/观测条件、持久表单修改与明确投入使用。
3. **推理分析 `/evidence`**：原始样本或 Evidence 输入、已启用工作图与两种推理器、真实进度、保存结果与观测—路径联动。

默认只消费 API；取消旧 Demo/Backend 开关、前端推理及虚假回退。成套示例通过后端的公开资产目录载入**输入**，点击开始分析后才产生新任务。已保存分析明确作为历史结果打开。

## 启动与接口

当前验收前端：<http://127.0.0.1:5186>，API：<http://127.0.0.1:8012>。前端已接管原有 Vite，未按端口关闭其他进程。

```sh
VITE_API_BASE_URL=http://127.0.0.1:8012 \
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8012 \
npm run dev -- --host 127.0.0.1 --port 5186 --strictPort
```

任务、启用、保存分析和演示资料接口见 [双闭环后端契约](rootlens-two-loop-backend-contract.md)。前端的 `src/api/workbench.ts` 直接消费它；不临时拼装新的诊断结果。

## 可操作主路径

### A：资料到可用知识

- “导入知识资料”支持文件与 URL；“公开资料”入口只真实登记并解析资料，不偷偷导入图包。
- 资料可多选；原文按解析片段查看。制作弹窗明确场景、名称、来源、最多两次模型调用（含一次自动修复）；高级设置可关闭修复。
- 制作阶段和错误来自后端 Task。LLM 阶段只显示等待，不伪造百分比；失败保留记录，明确点击才能重试。
- 完成后“查看并修改图谱”。语义视图默认不显示 SourceAssertion/reified rule 技术节点。
- 表单可改名称/实体别名、条件特征/阈值/主体/区域、嵌套 AND/OR/至少N项组合、影响和预期关系、主体与词汇绑定。
- “保存修改并生效”后才能“投入使用”；启用后“使用此图分析”承接当前工作图。
- “导入已准备图谱”是明确跳过制作的独立入口，始终导入为新副本，初始未启用。

### B：样本到可追溯解释

- 明确区分“从原始样本开始”和“从 Evidence 开始”，并选择场景。
- 加载示例时，隐式默认选择后端明确标识的样例配套就绪图；用户手选或“使用此图分析”的明确图谱意图保留，并提供切换配套图动作。缺配套图时提示导入 / 启用，不用最新同场景图代替。
- TEP 原生 DAT/CSV 必须提供配套正常参考与一基闭区间窗口；MVTec 显式 ROI 外观模型选项；Wafer 保留原生 0/1/2 编码。
- 只允许选择当前场景已启用的 v2 图谱。统一约束推理支持三场景；RootKGD 在非 TEP 场景禁用。
- 结果先展示实际图像/区域、窗口/变量或网格与观测，再比较候选、支持/冲突/缺测和实际路径。分数不作为置信率，也不跨引擎合并。
- 路径是联合证明的一部分，条件、实际值、来源断言和技术引用分别呈现；完整 JSON/ID/DAG 后置。
- “下载本次 Evidence”是结果主操作。上传同一 Frame、选择同一图/推理器/保留候选数，可复算；历史分析仍保留原知识快照。

## 独立浏览器与当前走查证据

共享 Playwright MCP profile 报占用，未删除锁、未关闭现有浏览器。使用已安装的 Playwright 与 Chrome 启动全新 browser/context：

```js
import { chromium } from '/Users/hhm/.npm/_npx/9833c18b2d85bc59/node_modules/playwright/index.mjs'
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true,
})
const context = await browser.newContext({ viewport: { width: 1512, height: 982 } })
const page = await context.newPage()
```

本轮临时自动化入口：`/private/tmp/rootlens-frontend-inspect.mjs`（三页只读截图）、`/private/tmp/rootlens-frontend-flow.mjs`（实际图谱副本编辑/启用、Evidence运行/下载、打开历史TEP结果）。脚本各自建立隔离 browser/context，不清用户 storage。

2026-11-11 02:33 的真实 UI 走查：

- 导入本轮 LLM 图为验收副本 `graph_a6f465b4da3a4dabafd61ea6c708ebaa`，保存“前端实屏验收别名”，投入使用并跳转分析。
- 上传本轮实际玻璃样本生成的 Frame，任务 `task_b37d3aa08c7e4e59be20b1e3b5645e38` 完成；显示 7 个首位并列及另一个获支持但未在 top-k 列名次的候选。
- 实际点击观测、第二候选与路径，下载后端 Evidence；打开保存的真实 TEP RootKGD 运行 `6fc02e0e-9455-4412-b4c3-1f6d4605db17`。
- 页面和控制台未出现 JS 错误。实屏发现的 TEP 统计缺显、初始焦点、MVTec 新语义词显示已修正，继续做针对性走查。

截图位于 Git 忽略目录 `/Users/hhm/code/RootLens/.playwright-mcp/two-loop/`：

- `01-materials-first.png`、`02-graphs-first.png`、`03-analysis-first.png`：第一轮布局（随后已提高字号与对比度）。
- `04-graph-edited-enabled.png`：真实修改并启用。
- `05-bottle-evidence-result.png`、`06-bottle-linked-proof.png`：真实 Frame 新运行与联动。
- `07-tep-rootkgd.png`：打开真实全通道 RootKGD 结果（统计缺显修正前的反例记录）。

独立审核者另验一次 GUI 真实资料制作，不重复付费启动相同检查。后端/资产的科学有效性、模型负结果和来源限制由其各自记录约束，本页只记录 UI 实际行为。

## 最终交付与补充验收（02:54）

- `npm test`：**8 个文件 / 40 项通过**。覆盖当前任务 API、显式失败重试、轮询/断连、保存与启用分离、知识表达展示、分数/窗口语义、真实媒体键、正常门控与采样间隔、一次性任务聚焦。
- `npm run build`：类型检查与生产构建通过。只注册实际使用的 Arco 组件后，主入口约 50 KB，无旧的大 chunk 提示。
- `git diff --check`：前端、本轮项目测试规则和包配置通过。
- 旧复杂页面实现已替换；旧 Mock 后端、本地 runtime/推理装配、Session/Replay 兼容、反馈混合页、D3 CDN loader 及配套旧测试已移除。`public/generated` 既有快照资产保留，但当前代码不再读取。

### 实际修改影响与失败恢复

- UI 将验收副本异常条件 true→false 后，同一实际 Frame 的新任务 `task_84c4a01d490b407582c75eb5dece50be` 返回未形成完整支持；随后通过 UI 恢复 true，API 读回确认。已有运行仍保存原知识快照。
- 真实无效输入任务 `task_0cdaece80021485ab0894203490ed7eb` 失败；明确点击重试后创建 `task_3b4df2cc309743ee84f40bbf06fafcc8`，`retry_of` 指向原任务。没有自动重复模型调用。
- 服务不可用时，右上状态切为未连接，显示可重试错误。隔离浏览器中模拟连接失败后，实际恢复 API 与资料库读取，记录 `frontend-readonly-final.json`；此项是网络故障模拟，不冒充重启后端的证据。
- 新提交/显式重试只聚焦一次任务面板，轮询不抢滚动。无 LLM 重解析任务 `task_a0bbd8740c014c83a15386aa5e7f4fb4` 从正文下方提交后，任务面板滚入可视位置（y≈112）；记录 `frontend-progress-visibility.json`。

### 三场景实屏

- 玻璃：先显示实际“裂纹或玻璃缺失”外观与拍摄部位未确认；原图、区域裁切、掩码、热力图按实际资产键切换。候选组保持并列，比较表折叠，默认能看到为何支持与尚缺条件。`13-glass-edge-firstscreen.png`、`14-glass-edge-roi.png`；本轮 Frame 新运行为 `21-final-glass-evidence.png`。
- TEP：完整 52 通道表直接读 Frame 统计，不在浏览器重新测量；点击变量更新完整窗口曲线，并与候选路径联动。`22-final-tep-rootkgd.png`。原生 Frame 正常窗口明确“未越过正常参考异常门/不启动候选排名”，保留 20.06 / 26.67 与每 180 秒采样；`20-native-frame-normal-window.png`、`frontend-normal-window.json`。
- Wafer：显示原始 0/1/2 网格与区域实际统计，选区域会联动显示范围；输出为图案类别。最终 near-full 为 `23-final-wafer-nearfull.png`；真实分歧仍保留在历史分析。原生上传接受 JSON 与 JSONL。
- 390 px 输入布局无横向溢出（clientWidth=scrollWidth=390）；`18-mobile-input.png`。全轮只读检查无 JS 错误。

### 独立审核的消费

独立审核者已通过 GUI 完成 PDF→真实制作 `task_6e68de18e2c74c30b51503b1c851ebe4`（首次校验失败→唯一一次修复成功）→`graph_3a24629ac3ce487097424b4983e05398`→修改候选名称/成本→保存/启用→分析承接。其 A 闭环截图在 `backend/runs/two_loop_demo/independent-review/`。

审核指出的进度不可见、正常门控误导、原生 Frame 采样间隔缺显、Wafer JSONL 选择器过滤均已修复。独立 B 闭环亦已完成，见 [最终独立验收](../../backend/docs/two-loop-acceptance.md)。Wafer 下载文件名已由后端修复，独立审核者已重新下载并通过原生 JSONL 入口普通上传。没有已知前端阻塞。

本机测试工具误执行的精确命令、输出与事件传输未知范围保存在 `.playwright-mcp/two-loop/tooling-incident.md`，不再执行安装/遥测。根 `AGENTS.md` 已按主 owner 授权加入窄的项目测试规则；事件事实由独立审核另存。

## Wafer 区域高亮与统计严格对齐（追加修复）

独立审核发现 SVG 高亮按“单元格数量的一半”取半径，比后端索引跨度多 0.5 个芯粒；中心/中圈/边缘实际高亮数量因此偏移。

- 当前显示使用后端 `measure_wafer_map` 同一公式：`rx=max((right-left)/2,1)`、`ry=max((bottom-top)/2,1)`。SVG 中心继续平移 0.5，对应实际芯粒中心坐标；边界保持中心 `r<=0.4`、中圈 `0.4<r<0.8`、边缘 `r>=0.8`。
- 新 `wafer-regions.ts` 只负责显示几何，不计算诊断或替换保存的测量。38×38 全有效合成网格回归固定为中心 172 / 中圈 516 / 边缘 756，并覆盖闭/开边界与最小半径。
- 只读打开现有真实 Run `33196a93-9a78-44e6-a4bd-b3b12023676f`，逐区点击后直接计数实际 SVG 高亮：中心 172 有效 / 156 失效，中圈 516 / 433，边缘 451 / 397。三个高亮失效率均与该 Run 保存的 Frame 精确一致；未重跑模型、任务或改图。
- 本轮 `npm test -- src/services/wafer-regions.spec.ts`：**3 项通过**；`npm run build` 通过。先前 40 项测试的有效证据保留。
- 实屏与计数：`.playwright-mcp/two-loop/24-wafer-center-aligned.png`、`wafer-zone-alignment-after.json`；独立脚本 `/private/tmp/rootlens-wafer-region-check.mjs`。

同时修正 `src/api/url.ts` 的 EOF 多余空行与 `src/api/workbench.ts` 的尾随空格。Git 由后端 owner 统一重暂存；前端未自行 stage/commit。

## 双闭环优化第一候选（2026-11-11 03:59）

### 跨页新分析意图修复

图谱页和侧栏的“使用此图分析”统一带显式 `intent=new-analysis&graph=…`，分析页优先消费这一意图，清除旧运行、旧任务观察器和输入上下文。处理完成后移除一次性参数；同页再次点击也可重新进入新分析。普通历史入口仍恢复已有结果，迟到的历史请求不会覆盖新的选择。“新建分析”优先当前工作图，不再用旧结果的图覆盖它。

真实隔离浏览器走查：旧 Wafer Run `33196a93-9a78-44e6-a4bd-b3b12023676f` → 图谱页选择玻璃图 `graph_3a24629ac3ce487097424b4983e05398` → 图谱和侧栏两入口均进入玻璃新分析表单，未重取旧结果。普通历史恢复与结果页“新建分析”亦已核对。

### 明确的词汇等价与共用特征目录

- “对象与等价词汇”支持从空列表添加映射，编辑外部词、标准词、模型范围和实际来源断言；删除后通过保存生效。没有相似度自动强配，不把粗玻璃缺损映射成已确认 Finish 部位。
- 观测条件读取 `/api/authoring/capabilities` 的真实特征类型、单位、定义和 `allowed_values`。有限值使用下拉 / 多选并即时校验；开放外观词汇明确提示语义等价边界。未修改的旧图条件不会仅因新目录而被浏览器静默改写。
- 真实副本 `graph_ffa07d51580e4cac87d4a1d4f7e17abf` 从空映射新增“裂纹或玻璃缺失 → cracked_or_missing_glass”，保存重开；只把既有 Frame 同义词替换成显式中文表示的合同测试，得到 Run `2a38c1a9-9f3d-427a-bc4a-a0ff4a882c97`，grounded facts 实际记录 `applied_value_binding_ids`。随后 GUI 删除并保存，GET 回读为空；该运行的原快照仍有映射。此项验收词汇适配，不作为新模型测量或准确率证据。
- 形态目录精确读取 `linear/spot/scattered/dense`，位置 `edge/surface`；散布 / 密集是既有 supplied_geometry 聚合适配能力，不声称单 ROI 算法新增这两类。

### 本次快照知识诊断

新结果读取已持久化的 `authoring_diagnostics`，区分保留观测、条件绑定观测、评分输入及实际条件事实真 / 假 / 未知；不把绑定数写成支持数。相同期待条件组与实际 Root 传播结构组分开呈现，成本先验单列，不当作观测已区分。Root 作者逻辑核对不参与阈值 / AND-OR 评分，完整结构比较输入数量不等于传播覆盖通道数。历史结果无字段时明确“本次未生成”，不借用当前图补算。

当前可修改已有 predicate、联合表达式和已有期待端点 / 模式；候选专属“新增 / 撤销诊断条件”已在最终增量完成，见下节。仍不提供任意节点、共享机制或通道绑定的泛型创建器。

### 验证与可复用入口

- 本候选 `npm test`：**14 文件 / 68 项通过**；`npm run build` 类型与生产构建通过。
- 第一候选实屏记录在 `/Users/hhm/code/RootLens/.playwright-mcp/two-loop-optimization/`：`01-selected-graph-new-analysis.png`、`02-sidebar-clears-old-analysis.png`、`03-binding-created-reopened.png`、`04-equivalent-word-used-in-analysis.png`、`05-finite-feature-directory.png`、`06-saved-knowledge-diagnostics.png`、`07-diagnostics-result-context.png`。
- 对应 `cross-route-check.json`、`binding-authoring-check.json`、`diagnostics-screen.json`；全轮无 JS 错误。
- 复用脚本 `/private/tmp/rootlens-cross-route-check.mjs`、`/private/tmp/rootlens-binding-finish.mjs`、`/private/tmp/rootlens-diagnostics-screen.mjs`；均使用前述已安装 Playwright 和独立 Chrome/context，不占用用户浏览器。绑定删除脚本属于写验收，请不要重复用于已删除状态。
- 页面仍是 `http://127.0.0.1:5186/{materials,graphs,evidence}`，API 为 `http://127.0.0.1:8012`。没有重复运行 backbone / VLM / LLM。


## 最终优化候选：候选专属条件与状态修复（2026-11-11 04:13）

### 给一个候选新增 / 撤销条件

图谱页选择“候选解释”中的目标，点击 **新增诊断条件**。向导从后端窄 operator 读取合法特征、算子、已绑定过程变量和晶圆区域，支持数值 signed/std/slope 等已有生产特征及有限类别；填写 typed 条件值、期待模式、说明和可选资料来源，保存时只连接当前候选。

后端创建独立 predicate / pattern / expectation，小束与本图已有异常门联合，不修改共享机制。没有来源时如实记录人工演示启发式；必要条件不满足 / 缺测按现有语义阻止支持排名，预期 / 可能模式不新增私有“冲突”规则。未知过程变量只能先核对已有绑定，不在向导猜测通道或制造观测。已有共享依赖时，后端返回不可撤销及原因，UI 禁用撤销。

本入口保存直接持久化；普通图谱草稿尚未保存时禁止进入，避免覆盖。向导可撤销本 operator 新建的独立小束，不能借此任意删除图谱。RootKGD 提示为按图传播与贡献结构评分、不执行条件阈值；新增 / 删除真实关系可能改变传播结构，不能把统一条件代价当 Root 分数。

独立审核真实使用未修改的玻璃 Frame 完成：

- 审核副本 `graph_ef7ee725081f4d2e95283ba18eadc729`，基线 Run `49bb6223-41c7-4954-a428-70fbdef9b01e` 的同签名组有 **7** 个候选。
- 只给“玻璃料温过低”添加人工能力对照“ROI 面积至少 0.2”，新 Run `e61fd3f3-21f3-4b7c-904e-093969567c94` 同组变为 **6**；实际面积 `0.2284393310546875`，新条件为真，并保留本条件、异常门及来源的完整联合路径。该人工阈值仅验证编辑能力，不作为已验证的工业区分规则。
- GUI 撤销后 Run `793a023f-f3e0-4717-a564-822d5f698f51` 同组回到 **7**；当前 knowledge 逐字段恢复。再次从 GUI 打开新增阶段的历史 Run，仍有原条件、实际值与路径，不使用当前图覆盖。

记录与截图：`/Users/hhm/code/RootLens/backend/runs/two_loop_demo/system-assessment/kg/incremental/operator-ui-check.json`，`06-candidate-condition-form.png`、`07-added-condition-diagnostic.png`、`08-historical-condition-after-delete.png`。续跑入口 `operator-ui-resume.mjs` 属于该已完成写验收的记录，不应无条件重放。前端另用只读向导填写 / 取消核对 52 个真实变量、`statistics.slope_z` 的 `1/sample` 单位及取消不修改图谱，见 `.playwright-mcp/two-loop-optimization/08-candidate-condition-wizard.png`、`candidate-wizard-readonly.json`。

### 初始化不再清除刚选择的输入

独立审核自然重现了“表单先可交互，迟到目录响应后再次消费新分析意图，清除 Evidence/file”的竞态。现在 metadata 与一次性意图未准备完前显示明确准备态，不挂可交互输入且禁用运行；准备完成后只消费一次。历史结果请求开始前解除入口锁，因此同路由新意图仍能中断迟到历史响应，不恢复旧错图。

导航回归共 9 项，覆盖延迟目录、准备期无可交互 setup、完成后 Evidence/file 保留、准备期侧栏意图、普通历史恢复与迟到结果防护。另在隔离浏览器实际延迟后端 GET、释放真实响应后立即选 Evidence/file，模式与文件保持且没有 POST；`09-entry-awaits-metadata.png`、`10-entry-preserves-evidence-input.png`、`entry-initialization-check.json`。独立审核在原副本两次快速选择 / 提交也通过。

### 正常 / 不足分组不是本次排名并列

组卡按保存的 `candidate_checks.eligible_for_ranking` 单独显示具备 / 不具备 / 未评估数量。正常或证据不足组全部无资格时明确“本组本次未获支持；以下为图谱条件的结构检查”，不称当前排名并列；搜索未完成和未评估保持未知状态。条件真 / 假 / 未知和输入计数仍独立展示。

独立审核提供的真实新 Run 已由前端只读实屏消费：正常 `6d354f30-a787-4be6-af92-80ade4b1377c`（14 事实全假、组资格 0/2），不足 `a4ff94e0-69e9-415c-96b0-fbd60e12b940`（组资格 0/7），Root `dde846a7-ad8d-427e-ae34-fcd6fcfc05fb`（14 作者条件事实，2 真 / 12 假；52 个结构评分输入）。截图 `11-{normal,insufficient,root}-knowledge-state.png` 与 `diagnostic-state-readonly.json`。这些记录不作为后端后续投影版本的重新验收；最终 Root 投影归一化由后端 owner 完成、独立审核消费，历史 Run 不回算。

### 当前验证与冻结交付

- 最终完整原生 `npm test`：**17 文件 / 84 项通过**（04:12）；`npm run build` 类型与生产构建通过，无大 chunk 警告。
- `git diff --check -- src package.json package-lock.json` 通过；新增前端文件另逐一执行 no-index whitespace check，未 stage / commit。
- 前端运行 URL 仍为 `http://127.0.0.1:5186`，三个页面和 API 地址未变。5186 保持运行；使用独立 browser/context，不占用或清除用户 Chrome。
- 本轮新增范围仅为分析入口状态、共用目录 / 等价词汇编辑、保存的知识诊断、候选专属条件向导与相应客户端 / 测试。未重跑模型或 LLM，不新增前端推理、知识自动强配或规则 IDE。
- 本阶段前端无已知阻塞。随后 Root v2 的真实 Run `f0cca0c7-f7f7-4f1f-8e12-ec8f13296acf` 已由独立审核验证：14 作者条件 / 52 结构输入、21 条连续主路径及 XMV(10) 曲线 / 贡献联动；见独立增量截图 `10-root-v2-diagnostics.png`、`11-root-v2-path-channel-linked.png`。历史 Run 不回算。


## 推荐样例的配套图与明确选择（追加 P1 修复）

新增严格源图启用后，fresh 浏览器的默认图会变成最新同场景图。旧 `loadDemo` 只切场景并保留默认，导致推荐 006 输入与图不配套。这是图选择合同缺失，不通过删除 / 停用合法严格源图解决。

- 工作空间持久区分 `graphSelection=implicit|explicit`：自动默认不变成用户选择；图谱页手选、分析页下拉和携图新分析意图为明确选择。已有只存 graphId 的旧设置保守保留为明确选择，不覆盖历史用户意图。
- 示例目录的 group / sample `graph_ref` 由后端按配套包实际内容解析；浏览器不按场景、标题、最新顺序或写死 UUID 猜配套图。
- fresh / 隐式默认加载任一场景样例时，只自动选 `state=ready && available` 且实际列表仍就绪启用的精确图。缺失、歧义、未启用和不可读状态不回退其他图，显示后端说明及下载 / 导入 / 启用入口；用户仍可明确选择其他工作图做对照。
- 明确指定的严格图加载样例后保持，提示与配套图不同、可能无匹配或证据不足，并提供一次明确切换动作。跨场景不适用时保留该意图但禁运行，直到用户换图。
- 配套状态重读会刷新实际目录与图列表，不清已载样例、输入类型或文件；迟到元数据不能覆盖后续明确选择。普通历史打开、同路由新分析和初始化准备态继续沿原合同。

### 追加修复的实际验证

- 后端 live `graph_ref` 部署后，独立 browser/context 在 GET-only guard 下实际验证：fresh 默认仍是合法严格源图 `graph_538efc4369b64b46a879dd5a30652bc1`；加载推荐 006 的 Evidence 后改选配套 `graph_7718009df1d94a288f99d1e428487679`。TEP 和 Wafer 亦分别采用目录精确指向的 `graph_c6d2a470450e41369de3fc7bdcaaf459`、`graph_5c3b30cbf4024ab1939c0435a1f676ec`，代码无 live UUID 表。
- route 和分析页下拉明确选择严格 538 时，加载同一个 006 仍保留 538、给出不同图提示；点击“切换到样例配套图”才切 7718，已载样例与 Evidence 模式不变。普通 Wafer 历史结果仍可恢复，随后新建分析仍保留明确选择，不由历史 run.graph_id 覆盖。
- 三场景隐式选择、明确选择 / 跨场景保留、缺配套禁运行、迟到目录恢复和输入保留由 24 项针对测试覆盖。本轮只填样例和读历史，不发新分析 / 模型 / LLM 请求，不修改、删除或停用严格源图。
- 实屏与请求记录：`/Users/hhm/code/RootLens/.playwright-mcp/two-loop-optimization/demo-graph-intent-check.json`、`12-recommended-demo-paired-graph.png`、`13-explicit-source-graph-preserved.png`；7 个检查场景均通过，无 JS 错误、无写请求。复用入口 `/private/tmp/rootlens-demo-graph-intent-check.mjs`，保持 GET-only guard。
- 最后源码候选完整 `npm test`：**18 文件 / 97 项通过**（04:58）；`npm run build` 类型 / 生产构建通过，tracked diff-check 和两个新增 helper / 测试的 whitespace check 通过。前端源码冻结交独立审核，5186 保持运行。

独立审核亦已在全新 context、GET-only guard 下复核 fresh 配对、真实下拉与图页携图两种明确意图、手动切换不丢输入、普通历史恢复；13 个 sample refs 均对应正确三图，错误与写请求为空。独立证据为 `backend/runs/two_loop_demo/system-assessment/kg/incremental/demo-graph-intent-after-check.json`、同名 `.mjs` 及 13/14/15 截图。当前前端无待修阻塞。
