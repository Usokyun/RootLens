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

## 原版 UI 恢复（2026-11-11）

用户要求先恢复大幅重做前的界面。本轮在 `codex/restore-original-frontend` 以精确基准 `471e1aaa1dabd22fdb0dd7f00590e7e4cf08ab26` 的前端为主体恢复，不继续调整新工作台。后端、数据库、资料、模型、运行快照和新知识字段不回滚；根后端／Shell 安全启动脚本保留。

### 原来的页面与真实图网络已经回来

- 默认 `/` → `/evidence`，导航顺序为 **运行与证据 → 根因与图谱 → 素材与构图**。恢复 RL 顶栏、220／56px 折叠侧栏、小控件密度、浅灰蓝卡面、原字体和间距。
- 恢复原 `KnowledgeForceGraph`、`RunPathGraph` 的有向力导向网络、总图／局部子图、右侧候选和审阅／策展／来源详情；撤下替代主图的 `SemanticGraph` 层级卡片及相应新工作台组件。不是在新布局旁边增加旧皮肤。
- 原 App、全局样式、路由、main 和两个图组件与基准逐字节相同。直接读取基准源码核对共 56 个文件完全相同，没有基准前端文件缺失；必要薄改 16 处、额外 4 个桥接、声明及测试文件，详见 `.playwright-mcp/restore-original/baseline-source-comparison.json`。
- D3 渲染器仍使用原 API／布局／样式，只把 CDN 注入 loader 换成项目内锁定 `d3@7.9.0` 动态模块。既有依赖版本未随安装升级；不依赖演示现场外网，也没有树状 fallback。

### 原 API 与新保存结果的薄衔接

旧上传、素材、完整包及图谱入口继续走已有后端接口：`/api/dashboard/bootstrap`、`/api/runs`、`/api/kg/materials`、`/api/kg/studio?graph_id=...`。总图是该接口返回的真实 `graph_nodes/graph_edges` 网络，不拿树目录生成假边。

运行列表额外合并 `/api/analyses` 的新双闭环保存结果，标题以“已保存分析”区分。此类详情直接读取 `/api/analyses/{id}`，不先请求旧 Run 后 404，再回退 Demo。桥接只改展示结构，不测量、grounding、排序或重跑模型。

- 每个问题按 `case_id` 精确配对其 EvidenceFrame，分开保留窗口／ROI；原 case ID 另保留，不拿第一帧覆盖所有结果。缺少对应 Frame 时明确报错。
- 候选 rank、并列、score、cost 和 null confidence 原样保留。统一推理仍显示 `J`／`score = −J`；RootKGD 显示余弦、覆盖／熵惩罚和原结构分数，不转成概率，也不套用逻辑代价公式。
- 局部路径使用保存的连续节点与实际源边 ID／方向。Root 保存的源关系原样使用；Unified 仅存源边视图而没有关系文本时，如实标“源边（类型见原快照）”，不臆造关系。路径和原始 typed Frame 可在原“推理依据”抽屉读取。
- 原图与共享媒体保留；ROI 预览按保存的 scope／obs 关联，不把另一 ROI 图贴过来。各外层 case 的原始字段、完整 result 与原始 working graph snapshot 保留在展示数据中。
- **总图与历史局部图的范围不同**：原总图仍从当前登记工作图的 Studio 投影读取；历史局部路径／推理依据来自该次保存结果。Backend 原卡片分别标“当前登记知识图谱”和“本次保存推理路径”；点总图节点转邻域时改标“当前节点邻域”，不将当前邻域说成保存路径。本轮没有把 typed knowledge 快照重新编译成第二个浏览器总图。

原 Demo／Replay 只展示成品快照。恢复的服务层明确阻止在 Demo 中执行素材解析、LLM 制作、构图、校验／发布等处理，不恢复浏览器推理／构图／what-if。连接 Backend 出错时清除旧来源的运行／图谱／素材上下文，显示实际错误；迟到的前一来源响应不能把已返回的 Demo 选择覆盖。

v2 工作图仍用完整 GET 包 → 原 JSON 修改 → PUT，不根据旧 TS 类型或 Studio 投影重建子集。原策展页保留 v2 投影边保护，并引导完整 JSON；后端 owner 已用独立内存 registry 验证新 binding、semantic_role、有限值和 source locator 精确保留。本轮没有改写 live 图谱。

### 实屏、对照与最终验证

独立 Chrome／context，不使用用户 Chrome/profile、不清其 storage。渲染与检查文件位于 `/Users/hhm/code/RootLens/.playwright-mcp/restore-original/`：

- `01-baseline-evidence.png`：刚恢复精确基准、尚未加桥时的原页面。
- `03-restored-evidence.png`、`04-restored-force-network.png`：恢复候选原页与原网络。
- `05-original-edge-inspector.png`：实际局部源边选中与原策展 inspector。
- `06-{glass,root}-saved-analysis-network.png`、`07-root-preserved-score-semantics.png`：新保存结果在原网络／原抽屉里的显示；Root 实际分数 `0.5854474293642782` 未改变。
- `08-source-error-not-demo.png`：只读 503 注入后不残留 Demo 成功结果。
- `09-baseline-current-comparison.png`：同 viewport 的基准与当前主页面并排对照；已亲自查看恢复页面、真实网络及 Root 分数抽屉。

`restored-ui-check.json` 记录原 Demo 总图 **36 节点／29 边**、局部图、总图节点选中、实际 wheel zoom、node drag、候选 → 路径联动、局部边 → 原 inspector。所有外部网络被阻断，显式 jsdelivr 请求被拒绝，但本地 D3 网络与交互仍工作；没有 JS 错误。`final-readonly-check.json` 进一步记录来源错误清空、真实 Backend 响应延迟到返回 Demo 后也不覆盖、Root 保存分数及抽屉语义；无写请求。

复用入口为 `/private/tmp/rootlens-original-restored-check.mjs`、`/private/tmp/rootlens-original-final-readonly.mjs`，使用已安装 Playwright 和独立 Chrome。GET-only 与外网阻断在同一最后路由 handler 中执行，不把 mock 成功替换实际后端。页面仍为 `http://127.0.0.1:5186/{evidence,graphs,materials}`，API 为 `http://127.0.0.1:8012`；5186 保持运行。

- 最终原生 `npm test`：**22 文件／109 项通过**（11:42，包含最终来源标题）；基准原有 95 项保留，未加 skip／xfail。
- `npm run build` 类型与生产构建通过。原全量 Arco 主 chunk 约 796KB，仍有 >500KB 警告；本轮不为消除警告改变原布局或依赖体系。
- tracked 与恢复后 untracked 前端文件 whitespace 检查均通过。日志为 `final-vitest.log`、`final-build.log`；没有 stage／commit／push。
- 未重跑后端数学验收、模型或 LLM；本轮实屏为保存结果读取与输入故障注入。

### 本轮展示边界

第一阶段恢复熟悉的旧 UI，不把新工作台全部增强硬塞回来。新异步任务进度、候选专属条件向导／等价词表单、推荐样例配套图入口、全52通道曲线／晶圆网格区域联动等后端能力和数据仍保留，但本轮原页面未重新接入这些现代控件。新 analysis 的旧 Session 导出也明确提示当前只读展示范围，不伪称导出成功；原 legacy Run 的回放／导出保持。

Backend 总图采用当前登记图，历史局部路径和解释采用保存快照，不能把两者说成完全相同的历史全图展示。后续渐进改进应在这套原界面上单独授权，优先修基本逻辑，不再替换视觉语言或把网络图改成树。

## 在原三页接回真实双闭环（2026-11-11）

保留还原后的导航、Arco 卡片、总图／局部图和 Demo／成品 Replay。新操作接在原页面内，不另建工作台。
以下为原单层页面的接线验收；运行与证据的新入口见下一节。

### 运行与证据：新建、看进度、打开保存结果

在 **Backend → 运行与证据 → 新建分析** 打开紧凑弹窗。先选已启用的 v2 工作图，再选该场景兼容的推理器；TEP 提供统一条件溯因和 RootKGD，视觉／晶圆只提供适用引擎。

- **原始样本**：MVTec 选择原图、对象和异常定位模型，ROI 外观语义默认关闭；勾选才请求外部视觉模型。TEP 选择完整 52 通道序列、正常参考、一基闭区间窗口和采样间隔。Wafer 可直接选择原生 JSON／JSONL 网格。
- **中间 Evidence**：选择后端生成的 EvidenceFrame JSON，不再运行原始测量。打开保存分析后用 **下载本次 Evidence** 获取原生 `evidence-frames.json`，可从同一文件入口普通上传。保留同图、同引擎和保留候选数才能比较同一配置；弹窗从当前保存结果带入这些可用默认值。
- **公开样例**只填入真实输入，不自动提交。默认优先选择有保存测量的 Evidence；切到原始样本时显示是否按资料库调用 ROI 视觉模型。只有隐式选图才使用 `graph_ref` 精确匹配的已启用图；图页携入或用户手选的图保留，差异有提示和明确切换动作。配套图缺失／未启用不以同场景最新图代替。
- **开始分析**提交真实异步任务。弹窗显示实际阶段、单位计数、失败与阶段记录；无总量时只显示进行中。断连可重读任务，失败／中断须点击 **按原输入重试** 才创建新任务。提交未获确认不会自动再发。关闭弹窗后可在原 Run 卡片重新查看本页已提交任务。

完成后直接按 `source=analysis-v2` 的真实编号读 `/api/analyses/{id}`；进入图页及返回运行页继续携带同一 Frame `case_id`。已保存分析保留原分数和来源；旧接口上传和成品 Replay 保留原合同。工作图→新建分析携独立显式意图，先清旧运行上下文；晚到的目录或旧详情不会重置正在填写的文件、模式和工作图。

### 共用客户端与实屏证据

`src/api/two-loop.ts` 使用现有 API 地址解析和代理，`src/services/task-observer.ts` 按任务原服务读取增量事件，素材与分析各持一份观察实例；`src/components/tasks/TaskStatusPanel.vue` 共用阶段、断连和重试呈现。`src/services/analysis-entry.ts` 约定 `newAnalysisRoute(graphId)` 与 `savedAnalysisRoute(page, runId, frameId)`，不复制路由或结果适配。

分析线针对性原生测试 **6 文件／37 项通过**。独立 Chrome 实屏记录在 `/Users/hhm/code/RootLens/.playwright-mcp/original-two-loop/`：

- `01-new-analysis-native.png`、`02-demo-paired-graph.png`、`03-explicit-graph-preserved.png`：原版小弹窗、推荐 006 精确配套与指定严格图不被覆盖。
- `04-root-evidence-upload.png`：目录延迟响应期间选择真实 Frame 后，文件、图和 RootKGD 选择保持。
- `05-task-failure-explicit-retry.png`：使用受控任务响应验证失败和仅显式重试；此截图不代表新后端任务运行。
- `06-saved-analysis-native-evidence.png`：真实 `f0cca0c7-f7f7-4f1f-8e12-ec8f13296acf` 保存分析按准确 ID／源／`process_window_161_260/query/window` 打开；实际下载 `evidence-frames.json` 与原 Frame 逐字段一致，无旧 `/api/runs/{id}` 探测。

- `07-native-wafer-jsonl.png`：实际白名单下载的 `wafer-nearfull-248536.jsonl` 经中文文件选择进入原生晶圆模式。另核对 MVTec ROI 默认关闭、TEP 的正常参考、两引擎与 180 秒／1–100 默认；见 `analysis-file-chooser.json`。

证据索引 `analysis-dialog-check.json`，复用入口 `/private/tmp/rootlens-original-analysis-dialog-check.mjs`。此脚本只发送真实 GET；测试提交、失败、重试全部在隔离浏览器拦截。实际新任务链由串联验收另记，不把受控任务响应记为模型调用成功。

本机原 Vite 用既有 npm/mise 恢复，未占用其他服务。入口 `http://127.0.0.1:5186/evidence`，经同端口 `/api/health` 指向 8012 并返回 `ok`。如前端开发进程退出，从仓库根目录执行：

```sh
VITE_API_BASE_URL=http://127.0.0.1:8012 VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8012 npm run dev -- --host 127.0.0.1 --port 5186 --strictPort
```

最终三线源码的原生 `npm test` **28 文件／147 项通过**；`npm run build` 类型与生产构建通过，原全量 Arco 主 chunk 约 771KB 仍有体积警告。Tracked 及新增前端文件 whitespace 检查通过。实际日志为 `.playwright-mcp/original-two-loop/final-vitest.log`、`final-build.log`。未安装新工具或修改 D3、主题、根依赖。

同一候选的实际构图 → 编辑／启用 → 原始样本 → 下载 Evidence → 普通上传复算，及三场景的实屏边界，见 [原界面真实闭环验收](../../backend/docs/original-ui-loop-acceptance.md)。

## 运行与证据：列表与保存详情（2026-11-11）

在 [运行与证据](http://127.0.0.1:5186/evidence) 切到 **Backend**。列表用原 Arco 弹窗新建分析，上传走 `/api/tasks/inference`；选受管样例走同一任务族的 `/demo`。弹窗外显示实际阶段和计数，失败只在点击 **按原输入重试** 后重提。后端 `adapter` / `measurement` 归在同一测量与 Evidence 阶段，不估算百分比。

- **历史**分列显示执行状态和保存结论。结论只用 `/api/analyses` 的范围计数，正常门控单列，不从候选数推断；后端未返回结论时可打开查看。任务失败且未生成结果时只回到该任务，不打开其他历史结果。
- **详情**的正式地址是 `/evidence/runs/:runId`，用 `case_id`、`tab` 定位保存的 Frame 与视图。任务完成只用该任务返回的 `result.run_id`。详情左侧是四段执行索引，右侧有总览、输入、Backbone、Evidence、推理、图谱；图谱仍是本次保存源边的有向网络。Evidence 直入标注跳过提取；下载的是该次原生 Evidence。返回列表恢复同一后端地址下的搜索、场景、状态与滚动位置。
- **工作图**可携精确图 ID 新建，示例 `graph_ref` 不覆盖已明确选择的图。图谱页继续读取已有旧 Run 及其附件；新分析返回运行页时打开同一 Run／Frame。已存旧 Run 的回放下载 API 保留；旧上传工作台和 `/evidence?run_id…` 转发已删除，客户端不再按缓存猜运行来源。
- **回放**从当前列表的 **导入回放** 进入，可选完整 Session 或配套 runtime／graphs。回放和 Demo 都只读取成品；退出回放回到当前选择的数据源，不以成品替代失败的 Backend 请求。

### 同一工作树的真实合验

既有 [5186 前端](http://127.0.0.1:5186/evidence) 保持运行，应用默认 Backend 地址和代理目标均为 `http://127.0.0.1:8012`，同源 `/api/health` 实测 `ok`。已保存的自定义地址仍由顶部连接设置控制。

- 素材线实际上传并提取公开短摘，移出、恢复后原文件、提取片段与历史引用均不变。读取已完成的公开构图任务，从其精确登记图进入新建分析；该图本已启用。没有重跑构图。
- 唯一新增分析上传已有的 006 Evidence，完成为 [保存运行 2570f81d](http://127.0.0.1:5186/evidence/runs/2570f81d-7fee-406a-9eab-5132c2b2c223?case_id=mvtec_bottle_test_unknown_sample_006%2Fquery%2F1)。实际结果 8 个并列候选、24 条路径；页面展示 35 条去重源边，源边和观测联动，同一 Frame 下载精确，返回保留搜索。此次不重跑 Backbone 或 LLM。
- [实际请求、响应与截图索引](../../backend/runs/live_materials_inference_acceptance/verification.json)及同目录 `06-carried-graph-evidence-input.png`、`07-live-l2-same-source-edge.png`、`08-live-l2-same-observation.png`、`09-live-run-list-return.png`。
- 当前合并树原生 `npm test` **33 文件／180 项通过**，`npm run build` 类型与生产构建通过。既有 Arco 主 chunk 体积警告保留（约 797 KB）；前端差异检查通过。日志为 `.playwright-mcp/two-level-evidence/integration-final-vitest.log`、`integration-final-build.log`。

此前的归档实屏用于补足三场景和故障验证：[详情归档验收](../../backend/runs/two_level_evidence_detail_review/verification.json)记录 D3 缩放拖拽、d04 的 52 条已有曲线与正常窗口隔离，以及 38×38 晶圆网格。`.playwright-mcp/two-level-evidence/verification.json` 中的进行中、失败和重试为受控回执，不是实发任务；该目录旧脚本的过渡 URL 已退役。
