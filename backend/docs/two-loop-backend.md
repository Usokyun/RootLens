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

API当前为 `http://127.0.0.1:8012`，由手动加载的会话作业 `com.rootlens.dev.two-loop-api` 管理，最后一次显式重载后的PID为 **82606**（实时值以status为准），不归属 agent exec session。只连接独立PG55433与Neo4j57687。task worker要求单API进程（两个线程），不支持多个Uvicorn worker同时接管同一任务表。

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
