---
name: webe2e
description: 从 case.md 生成 Web E2E 执行计划，支持 TTAT 远程执行或基于 Playwright MCP 的本地执行，并在同一技能内支持平台查询、按 task_id 查询状态和显式分析失败报告。
user-invocable: true
---

# Web E2E

## 适用场景

- 用户已经准备好 `case.md`，希望直接跑 Web E2E 自动化
- 用户说"根据这个 case.md 跑自动化测试""帮我创建并执行 Web E2E 用例"
- 用户希望一条链路完成：`case.md` -> TTAT 任务 或 Playwright 本地执行 -> `test_report.md`
- 用户想查询 Web E2E 当前可用的平台列表
- 用户想查看某个 Web E2E 平台的详情，以及该平台对应需要补充的环境变量

## 输入

1. 必须提供 `case.md`
2. 可选提供：`title`、`creator`
3. 如用户需要，可按需查询 Web E2E 可用平台列表或某个平台详情；这两个能力是对外提供的独立查询能力，不要求在主流程中主动调用
4. 环境参数通过 `.env` 文件配置；其中 `EXECUTION_MODE` 控制执行分支；本地模式固定使用 `LOCAL_RUNNER=playwright`
5. 本地模式可通过 `LOCAL_CASE_CONCURRENCY` 控制 case 级并发度；默认 `10`
6. `.env` 初始化时，会优先尝试从同任务目录的 `task.md` 提取 `RUN_ENV`、`SWIMLANE`、`TEST_IDC` 默认值；提取不到也可以，后续仍由用户确认

## 执行规则

### ⚠️ 强制确认流程

**必须严格按照以下顺序执行，不得跳过用户确认步骤：**

1. **init-env** - 初始化环境配置文件
2. **show-env** - 展示环境配置给用户
3. **确认执行模式** - 执行前必须确认 `EXECUTION_MODE`；若为 `local`，还必须确认 `LOCAL_RUNNER=playwright` 和 `LOCAL_CASE_CONCURRENCY`
4. **等待用户确认** - 用户必须明确回复"确认"、"继续"、"OK"等
5. **按执行模式进入对应执行分支** - 用户确认后才可执行

进入执行命令时，必须显式带上 `--confirmed-env`，表示当前 `.env` 已经展示给用户且用户已确认。

**禁止行为**：
- ❌ 展示配置后直接执行 run 命令
- ❌ 未确认 `EXECUTION_MODE` 就直接开始执行任务
- ❌ `EXECUTION_MODE=local` 时未确认 `LOCAL_RUNNER` 就直接调用本地 MCP
- ❌ 未拿到用户确认就带着默认值直接执行，或省略 `--confirmed-env` 强行执行
- ❌ 假设用户已确认而跳过等待
- ❌ 在用户修改配置后未重新展示就执行

### 其他规则

- 已有 `case.md` 时，不要再走 PRD/Bits 用例生成流程
- 创建用例组和任务时无需逐个 curl 向用户确认接口调用
- 只要进入执行阶段，无论用户说"执行"、"开始跑"、"run"还是"run-local"，都必须先确认执行模式；不能自行假定默认值
- `test_report.md` 默认写到 `case.md` 同目录，文件名固定为 `test_report.md`
- 写 `test_report.md` 时要参考 `prd2case` 的产物放置习惯：结果文件放在当前测试任务目录内，通常与 `case.md` 同级
- 本地模式与 TTAT 远程模式的 `test_report.md` 顶层格式必须保持一致，至少统一使用 `执行概览` 与 `任务状态` 两个主章节；本地不存在的远程字段使用 `-` 占位
- `EXECUTION_MODE=ttat` 时，创建任务成功后，必须立即把任务信息和报告文件路径写入 `test_report.md`
- `EXECUTION_MODE=local` 时，不创建 TTAT `case_group_id` / `task_id`，而是先生成本地执行计划，再通过 Playwright MCP 实际执行，并把结果写回 `test_report.md`
- 所有接口调用细节统一收敛在 `scripts/case2webe2e.py` 中，技能文档只描述流程与约束，不再展开每个接口请求体
- 技能本身不自动轮询 TTAT 任务状态，也不自动分析报告
- 如何查询任务状态、什么代表任务完成、以及如何显式进入报告分析阶段，统一写在 `SKILL.md` 中，不写入 `test_report.md`
- 任务完成后，如需分析报告，应继续使用当前 `webe2e` 技能的分析子命令，并把当前 `task_id` 作为输入；不要在 `run` 完成后自动触发
- `analyze-task` 以终端返回和可选文件落地为主；如调用方未明确要求，不需要额外生成 Excel 汇总文件
- 当用户询问"Web E2E 有哪些平台可选"时，可按需调用 `list-platforms` 能力，并向用户列出 `nameZh`、`platform`、`domain`、`poc`
- 当用户询问"某个平台的详情"时，可按需调用 `platform-detail` 能力，并向用户解释该平台需要补充哪些环境变量、哪些值可沿用默认值

## 本地执行模式

当 `EXECUTION_MODE=local` 时，执行流程改为本地 MCP 驱动，不创建 TTAT 任务。

- 本地模式固定使用插件内置的 `playwright` MCP 执行
- `.env` 中的 `LOCAL_RUNNER` 必须保持为 `playwright`
- `.env` 中可通过 `LOCAL_CASE_CONCURRENCY` 配置 case 级并发度；默认值为 `10`
- Playwright 本地模式不需要查询平台详情，也不依赖平台变量来补齐执行前置
- 本地模式仍然先调用 `markdown2midscene` 解析 `case.md`，再把解析结果写到 `local_execution_plan.json`
- AI 必须基于 `local_execution_plan.json` 执行；允许按 case 级并发调度，但单个 case 内的 flow 顺序不能重排，不能跳步骤
- Playwright 本地模式应以 case 为单位并发执行；每个 case 必须使用独立的 browser context，避免共享登录态和页面状态互相污染
- 必须将 Playwright 产生的截图、trace、录像、控制台日志等过程产物统一整理到当前任务目录的 `test_result/`
- 每个 case 的 Playwright 过程产物应优先落在 `test_result/<case目录>/` 下，不要散落到其他临时目录后只给终端输出
- 执行完单个 case 后，必须立即把该 case 的截图、trace、录像、控制台日志落到对应的 `test_result/<case目录>/`
- 如果某种执行方式无法把产物稳定归属到单个 case 目录，则该执行方式不允许使用；不能先做一轮批量 `browser_run_code` 再让用户补充 case 范围
- `run-local` 初始化阶段只预留每个 case 的产物目录，不要预填截图、trace、录像、控制台日志等具体文件路径
- 若 `SWIMLANE` 非空，Playwright 浏览器默认请求头中必须添加 `x-tt-env: ${SWIMLANE}`
- 若 `RUN_ENV=ppe`，Playwright 浏览器默认请求头中必须添加 `x-use-ppe: 1`
- 若 `RUN_ENV=boe`，Playwright 浏览器默认请求头中必须添加 `x-use-boe: 1`
- 执行完成后，必须把每个 case 的执行结果、关键证据和本地产物路径回写到同一份 `test_report.md`
- `test_report.md` 顶层结构必须继续沿用远程模式的 `执行概览` / `任务状态`；本地模式不存在的远程字段仍使用 `-` 占位

插件已内置的本地 MCP 配置：

- `plugins/ttadk/frontend-test/mcps/playwright.json`

## 平台查询能力

### 1. 查询当前 Web E2E 可用平台列表

当用户明确要求"查看 Web E2E 当前支持哪些平台"时，可按需调用：

```bash
python3 $SKILL_DIR/scripts/case2webe2e.py list-platforms
```

- 接口返回的是平台列表
- 面向用户展示时，保留 `nameZh`、`platform`、`domain`、`poc`
- 推荐以表格形式返回，便于用户直接选择平台值写入 `.env`
- 如果同一个 `platform` 在不同 `domain` 下重复出现，应提醒用户后续查询详情时尽量同时带上 `domain`
- 如果返回中还有 `description` 等字段，可内部参考，但默认不主动展开给用户

推荐展示格式：

| 平台名称 | platform | domain | poc |
|------|------|------|------|
| TSOP MM | tsop-mm | growth | liqiang.leo |
| Live Campaign | live-campaign | ads | - |

### 2. 按平台查询平台详情

当用户已经指定 `platform`，并要求"查看这个平台详情"或"看看这个平台需要补哪些环境变量"时，可按需调用：

```bash
python3 $SKILL_DIR/scripts/case2webe2e.py platform-detail --platform <platform> [--domain <domain>]
```

- 返回结果是该平台详情中的环境变量配置项列表
- 如果接口返回了 `domain`，或用户已从平台列表中拿到 `domain`，应一并展示给用户，避免同名平台歧义
- 关键字段说明：
  - `key`：环境变量名
  - `value`：默认值；为空时通常表示需要用户补充
  - `useDefault`：是否可直接使用默认值
  - `description`：该变量的获取方式或填写说明
- 面向用户展示时，应明确区分：
  - 哪些变量已经有默认值，可直接保留
  - 哪些变量没有默认值，需要用户从浏览器 `Cookies`、`Local Storage` 或接口响应里补充
- 如果该接口返回 `platform` 本身也作为配置项，仍应保留并提示用户 `.env` 中应填写对应的平台值

推荐展示格式：

| 参数 | 默认值 | 是否可直接使用 | 说明 |
|------|--------|----------------|------|
| platform | tsop-mm | 是 | 固定使用 tsop-mm |
| X_MPSSO_TOKEN | - | 否 | 从 Local Storage 获取 |

## 完整流程

### 步骤 1：检查并创建环境配置文件

检查 `case.md` 同目录下是否存在 `.env` 文件：

- 若不存在，使用脚本自动创建默认配置文件
- 若同任务目录存在 `task.md`，优先从中提取 `RUN_ENV`、`SWIMLANE`、`TEST_IDC` 作为 `.env` 初始值
- 默认配置如下：
  ```
  EXECUTION_MODE=ttat
  LOCAL_RUNNER=playwright
  LOCAL_CASE_CONCURRENCY=10
  platform=live-campaign
  RUN_ENV=ppe
  TEST_IDC=sg
  SWIMLANE=
  TASK_TIMEOUT=10
  ```

### 步骤 2：读取并展示环境配置

读取 `.env` 文件内容，以表格形式展示给用户：

| 参数 | 当前值 | 说明 |
|------|--------|------|
| creator | your_name | 创建者邮箱前缀（必填） |
| EXECUTION_MODE | ttat | 执行模式（`ttat` / `local`） |
| LOCAL_RUNNER | playwright | 本地模式 runner（固定为 `playwright`） |
| LOCAL_CASE_CONCURRENCY | 10 | 本地模式 case 级并发度 |
| platform | live-campaign | 测试平台 |
| RUN_ENV | ppe | 运行环境 (boe/ppe/online) |
| TEST_IDC | sg | 测试机房 |
| SWIMLANE | - | 泳道标识 |
| TASK_TIMEOUT | 10 | 任务超时时间（分钟） |

**注意**：`creator` 优先级为 `命令行参数 > 环境文件 > git user.email`

**补充**：

- `RUN_ENV`、`SWIMLANE`、`TEST_IDC` 在初始化 `.env` 时会优先参考 `task.md`，但最终仍以用户确认后的 `.env` 内容为准
- `EXECUTION_MODE=ttat` 走 TTAT 远程执行链路
- `EXECUTION_MODE=local` 走本地 MCP 执行链路，此时必须再确认 `LOCAL_RUNNER`
- `EXECUTION_MODE=local` 时，不需要查询平台详情或补平台变量；但若 `SWIMLANE` / `RUN_ENV` 已配置，必须据此生成 Playwright 默认请求头
- `EXECUTION_MODE=local` 时，还必须明确看到 `LOCAL_CASE_CONCURRENCY`，用于后续 case 级并发执行

### 步骤 3：等待用户确认（必须）

**AI 必须在此步骤暂停，先确认执行模式，再等待用户明确确认后才能继续。**

确认要求：

- 必须明确看到 `EXECUTION_MODE`
- 若 `EXECUTION_MODE=local`，必须明确看到 `LOCAL_RUNNER` 和 `LOCAL_CASE_CONCURRENCY`
- 若用户只说"执行"但未明确模式，或 `.env` 中模式值不清楚，必须先让用户确认，不能直接运行 `run` / `run-local`

向用户展示确认提示：

```
当前环境配置：

| 参数 | 值 |
|------|-----|
| creator | xxx |
| EXECUTION_MODE | xxx |
| LOCAL_RUNNER | xxx |
| LOCAL_CASE_CONCURRENCY | xxx |
| local_browser_headers | xxx |
| platform | xxx |
| RUN_ENV | xxx |
| TEST_IDC | xxx |
| ... | ... |

请确认以上执行环境配置是否正确。你可以：
1. **直接确认** - 回复"确认"或"继续"
2. **修改文件** - 编辑 `.env` 后回复"继续"
3. **逐项修改** - 告诉我需要修改的参数，如"RUN_ENV 改为 boe"
```

**用户确认后才可执行步骤 4**。如果用户修改了配置，或执行模式从 `ttat` 改成 `local`，需重新展示配置并再次确认。

### 步骤 4：执行自动化链路并初始化测试报告

用户确认后，必须先读取 `.env` 中的 `EXECUTION_MODE`，确认本次执行到底走 `ttat` 还是 `local`，再进入对应分支：

#### 分支 A：`EXECUTION_MODE=ttat`

1. 读取 `case.md`
2. 由 `scripts/case2webe2e.py` 统一调用 `markdown2midscene` 并生成 Midscene 内容
3. 解析返回内容并拼装 TTAT `create_case_group` 请求体
4. 读取环境配置并写入 `extras.execEnv`
5. 创建 Web E2E 用例组，拿到 `case_group_id`
6. 获取动态 `X-Custom-Token`
7. 调用 TTAT OpenAPI 创建自动化任务，拿到 `task_id`
8. 立即创建/覆盖 `test_report.md`，至少写入以下内容：
   - `case_group_name`、`case_group_id`、`task_name`、`task_id`、`task_url`
   - 当前环境文件路径
9. 返回任务链接，供用户查看执行结果

#### 分支 B：`EXECUTION_MODE=local`

1. 运行：
   ```bash
   python3 $SKILL_DIR/scripts/case2webe2e.py run-local \
     --case-md test/case.md \
     --confirmed-env \
     --plan-out out/local_execution_plan.json
   ```
2. 脚本会统一调用 `markdown2midscene`，并将解析结果写入 `local_execution_plan.json`
3. 使用 `playwright` MCP 按 case 级并发执行 `local_execution_plan.json` 中的用例；并发上限由 `LOCAL_CASE_CONCURRENCY` 或 `--local-case-concurrency` 决定
4. 每个 case 必须使用独立 browser context；单个 case 内的 flow 仍需保持顺序，不得跳步骤
5. 执行前必须读取 `browser_headers`：
   - `SWIMLANE` 非空时添加 `x-tt-env: ${SWIMLANE}`
   - `RUN_ENV=ppe` 时添加 `x-use-ppe: 1`
   - `RUN_ENV=boe` 时添加 `x-use-boe: 1`
6. 执行阶段必须持续把截图、trace、录像、控制台日志等产物整理到 `test_result/`
7. 每个 case 执行完成后，必须立刻把该 case 的截图、trace、录像、控制台日志落到对应的 `test_result/<case目录>/`；不能等所有 case 跑完后再按记忆补归档
8. 若当前执行方式无法将产物一一映射到 `local_execution_plan.json` 中的 case 目录，则必须停止该方式，改为按 case 执行；不能使用无法归档到 case 目录的批量 `browser_run_code`
9. 执行完成后，立即更新/覆盖 `test_report.md`，并保持与 TTAT 模式一致的主结构，至少写入：
   - `case.md`、`report_file`、`env_file`、`creator`、`case_group_name`、`case_group_id`、`case_count`、`task_name`、`task_id`、`task_url`
   - 其中本地模式不存在的 `case_group_id`、`task_id` 使用 `-` 占位；`task_url` 改为本地执行目录路径（默认 `test_result/`），作为远程任务链接的本地对应物
   - `execution_mode`、`local_runner`、`case_concurrency`、`case_isolation`、`plan_file`、`browser_headers`
   - 初始化阶段只写每个 case 的本地产物目录；截图、trace、录像、控制台日志等具体路径必须等执行完成后再补充
   - 每个 case 的执行结果（通过 / 失败 / 阻塞）
   - 失败 case 的关键证据、失败现象、建议处理方式
   - 截图、trace、日志等本地产物路径（若有）
8. 本地模式不返回 `task_id`，也不进入 TTAT 查询 / 分析子流程

### 步骤 5：告知任务状态查询方式（仅 TTAT 模式）

创建任务成功后，使用本技能时必须按下面这个请求方式查询任务状态：

```bash
python3 $SKILL_DIR/scripts/case2webe2e.py query-task --task-id <task_id>
```

```bash
curl 'https://ttat-openapi-sg.tiktok-row.net/ui/task/query_task_execution' \
  -H 'Accept: application/json, text/plain, */*' \
  -H 'Accept-Language: zh-CN,zh;q=0.9' \
  -H 'Cache-Control: no-cache' \
  -H 'Connection: keep-alive' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://ttat-us.byteintl.net' \
  -H 'Pragma: no-cache' \
  -H 'Referer: https://ttat-us.byteintl.net/' \
  -H 'Sec-Fetch-Dest: empty' \
  -H 'Sec-Fetch-Mode: cors' \
  -H 'Sec-Fetch-Site: cross-site' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36' \
  -H 'X-Custom-Token: <your_x_custom_token>' \
  -H 'sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  --data-raw '{"page_request":{"page_size":1,"cur_page":1,"sort_key":"","sort_descending":true},"task_id":<task_id>}'
```

- 查询接口：`https://ttat-openapi-sg.tiktok-row.net/ui/task/query_task_execution`
- 请求方式：`POST`
- 请求头中必须带 `X-Custom-Token`
- 请求体中必须带 `task_id`
- `query_task_execution` 返回顶层 `status_code=0` 只代表查询接口调用成功，不代表任务本身已执行完成
- 只有同时满足以下条件，才代表任务执行完成：
  - 顶层 `status_code=0`
  - `tasks[0].execute_status=10`
- 若 `status_code=0` 但 `tasks[0].execute_status` 仍不是 `10`，则任务仍在执行中

### 步骤 6：任务完成后的后续处理（仅 TTAT 模式）

当任务状态查询接口同时满足 `status_code=0` 且 `tasks[0].execute_status=10` 后，说明任务执行完成。此时如需继续做失败 case 收集或报告分析，应显式执行当前 `webe2e` 的分析子命令，而不是在 `run` 阶段自动执行。

- 推荐触发方式：`python3 $SKILL_DIR/scripts/case2webe2e.py analyze-task --task-id <当前task_id> --case-md test/case.md`
- 默认第一轮只写 Overview 到 `test_report.md`，并给出"是否继续下钻详细分析"的确认提示与预计耗时
- AI 在 Overview 写完后必须暂停，等待用户明确确认，再继续详细分析
- 只有在用户明确确认后，才继续执行详细分析：`python3 $SKILL_DIR/scripts/case2webe2e.py analyze-task --task-id <当前task_id> --case-md test/case.md --detail`
- 详细分析阶段按失败 case 逐条增量写回 `test_report.md`；如果命令因超时或中断未完成，必须明确告诉用户"当前只完成了部分 case 的详细分析"
- 重新执行同一条 `--detail` 命令时，脚本会自动跳过已完成 case，只继续剩余 case
- 执行 `analyze-task --detail` 时，外层 `Bash timeout` 应设置为 `>= 900000ms`（15 分钟）；否则可能先于脚本内部超时被调用方中断
- 整个流程仍然是显式人工触发，不自动串行到分析阶段

#### 下钻确认前的预计耗时

在用户进入详细分析前，必须先根据当前任务的失败 case 数量给出预计耗时，并让研发确认是否继续。

- `<= 10` 个失败 case：约 `1-3 分钟`
- `20-30` 个失败 case：约 `3-6 分钟`
- `50-60` 个失败 case：约 `6-12 分钟`
- `100` 个失败 case左右：约 `12-25 分钟`

也可以用粗略公式表达：

```text
基础约 1 分钟 + 每 10 个失败 case 约 1-2 分钟
```

确认提示必须至少包含：

1. 当前失败 case 总数
2. 预计详细分析耗时
3. 接下来会逐个拉取节点执行信息和 HTML 报告
4. 明确等待研发确认是否继续下钻

推荐确认话术：

```text
当前任务共有 59 个失败 case。
按历史分析耗时估算，完整下钻分析预计需要 6-12 分钟。
我会逐个拉取失败 case 的节点执行信息和 HTML 报告做根因分析。
请确认是否继续详细分析。
```

## 脚本

```bash
# 按需查看当前所有已注册平台
python3 $SKILL_DIR/scripts/case2webe2e.py list-platforms

# 按需查看某个平台需要补充的环境变量
python3 $SKILL_DIR/scripts/case2webe2e.py platform-detail --platform tsop-mm --domain growth

# 步骤 1：初始化环境配置文件（在 case.md 同目录创建）
python3 $SKILL_DIR/scripts/case2webe2e.py init-env --case-md test/case.md

# 步骤 2：读取并展示当前环境配置
python3 $SKILL_DIR/scripts/case2webe2e.py show-env --case-md test/case.md

# 步骤 3：用户确认后执行，并写入 test_report.md
python3 $SKILL_DIR/scripts/case2webe2e.py run \
  --case-md test/case.md \
  --confirmed-env \
  --payload-out out/case_group_payload.json

# 本地模式：生成本地执行计划并初始化 test_report.md
python3 $SKILL_DIR/scripts/case2webe2e.py run-local \
  --case-md test/case.md \
  --confirmed-env \
  --plan-out out/local_execution_plan.json

# 步骤 4：按 task_id 查询任务状态
python3 $SKILL_DIR/scripts/case2webe2e.py query-task --task-id <task_id>

# 步骤 5：任务完成后，先写 Overview 到 test_report.md
python3 $SKILL_DIR/scripts/case2webe2e.py analyze-task --task-id <task_id> --case-md test/case.md

# 步骤 6：用户确认后，再继续详细分析
python3 $SKILL_DIR/scripts/case2webe2e.py analyze-task --task-id <task_id> --case-md test/case.md --detail
```

## 子命令说明

### 1. `init-env`

- 在 `case.md` 同目录下创建默认 `.env` 文件
- 若存在 `task.md`，优先用其中的 `RUN_ENV`、`SWIMLANE`、`TEST_IDC` 预填 `.env`
- 若文件已存在，则跳过创建
- 输出文件路径

### 2. `show-env`

- 读取并输出当前环境配置，便于展示给用户确认
- 输出格式为 JSON，包含 `env_file` 和 `config` 字段

### `list-platforms`

- 按需查询当前所有可用的 Web E2E 平台
- 底层调用 `https://po3gp9uh.fn.bytedance.net/getWebE2EPlatform?withMeta=true`
- 输出 JSON，包含 `count` 和 `platforms`
- `platforms` 里默认保留 `nameZh`、`platform`、`domain`、`poc`

### `platform-detail`

- 按 `platform` 查询某个 Web E2E 平台详情
- 如已知 `domain`，建议一并透传，避免同名平台冲突
- 底层调用 `https://po3gp9uh.fn.bytedance.net/getWebE2EPlatformDetail?platform=<platform>&withMeta=true[&domain=<domain>]`
- 输出 JSON，包含 `platform`、`domain`、`variables`、`default_keys`、`required_keys`
- `variables` 中会标记哪些字段可直接使用默认值，哪些字段仍需用户手动补充

### 3. `prepare`

- 只做解析和 payload 拼装
- 用于调试 `markdown2midscene` 返回结果和 `create_case_group` 请求体

### 4. `create-group`

- 创建用例组但不触发执行
- 输出 `case_group_name`、`case_count`、`case_group_id`

### 5. `run`

- `EXECUTION_MODE=ttat` 时：执行完整链路，创建用例组并直接触发 TTAT 自动化任务
- `EXECUTION_MODE=local` 时：等价转到 `run-local`
- 默认在 `case.md` 同目录写入 `test_report.md`
- 创建任务后会立即把任务基础信息写入 `test_report.md`
- 输出 `case_group_id`、`task_id`、`task_url`、`report_file`

### 6. `run-local`

- 生成 `local_execution_plan.json`，并初始化本地模式的 `test_report.md`
- 统一调用 `markdown2midscene` 解析 `case.md`
- 后续执行阶段必须由 AI 使用 `playwright` MCP 按 case 级并发执行，并把截图、trace、录像、控制台日志等过程产物整理到 `test_result/`
- 不允许采用无法把产物稳定归档到 `test_result/<case目录>/` 的批量执行方式；若使用 `browser_run_code`，也必须保证产物在 case 完成后立即落到对应目录
- 会把 `LOCAL_CASE_CONCURRENCY` 解析为 `case_concurrency` 写入本地执行计划；若未配置则默认 `10`
- 会把基于 `RUN_ENV` / `SWIMLANE` 生成的 `browser_headers` 写入本地执行计划，供 Playwright MCP 启动浏览器时直接使用
- 输出 `execution_mode`、`local_runner`、`mcp_server`、`runner_mode`、`case_concurrency`、`case_count`、`plan_file`、`report_file`
- 不创建 TTAT `case_group_id` / `task_id`

### 7. `query-task`

- 按 `task_id` 查询 TTAT 任务状态
- 输出 JSON，包含 `task_id`、`task_name`、`execute_status`、`task_counts`、`status_line`、`done` 和原始响应

### 8. `analyze-task`

- 按 `task_id` 显式进入报告分析流程
- 仅当任务状态同时满足 `status_code=0` 且 `execute_status=10` 时才会真正进入分析；否则只返回当前状态，不自动等待
- 默认模式只收集失败 case 概览，并把 Overview 写入 `test_report.md`
- 默认模式必须给出"是否继续下钻详细分析"的确认提示，以及基于失败 case 数量推算的预计耗时
- 默认模式必须把"失败 case 数量 -> 预计耗时"的推算结果明确展示给研发，不能只说"耗时较久"这类模糊描述
- 只有显式带 `--detail` 时，才继续读取节点执行信息、HTML 报告 `reasoning_content` 和截图线索，生成详细分析
- `--detail` 会逐 case 增量落盘到 `test_report.md`，每完成一个 case 就立即更新进度
- 如果 `--detail` 过程中因超时或中断没有跑完，报告里必须明确标注"详细分析未完成"，并提示重新执行同一条命令继续
- 再次执行 `--detail` 时，必须自动跳过已完成 case，避免重复分析
- 调用 `--detail` 时，建议外层命令超时不少于 `900000ms`（15 分钟）
- 为避免重复，Overview 保留失败 case 清单；详细分析阶段只保留"根因汇总 + 逐 case 下钻"，不再重复输出原始失败清单
- 默认输出 Markdown；可用 `--format json` 输出结构化结果
- `--report-out` 可改写分析结果落地路径；未传时优先写 `--case-md` 同目录下的 `test_report.md`

## analyze-task 分析规范

### 批量分析流程

执行 `analyze-task --task-id <task_id>` 时，必须按以下顺序处理：

1. 查询任务状态，确认任务已完成
2. 查询失败 case 列表
3. 根据失败 case 数量估算详细分析耗时
4. 先将 Overview 写入 `test_report.md`，内容只包含任务概览、失败 case 列表、下一步确认提示和预计详细分析耗时
5. AI 必须在终端明确提示：当前失败 case 数、预计耗时、分析范围，并在此处暂停等待确认
6. 只有用户明确确认后，才继续执行带 `--detail` 的详细分析
7. 详细分析阶段再对每个失败 case 查询 `query_task_case_node_execution`
8. 详细分析阶段再拉取对应 HTML 报告：`https://tosv-sg.tiktok-row.org/obj/tiktok-ttat-uimost-sg/webui/{task_id}_{case_execution_id}.html`
9. 每分析完 1 个 case，就立即把最新进度和已完成 case 的详细结果写回 `test_report.md`
10. 如果命令因超时或中断结束，必须在报告和终端中明确说明"当前仅完成部分 case 详细分析"，并提示重新执行同一条 `--detail` 命令
11. 重新执行 `--detail` 时，自动跳过已完成 case，只继续剩余 case
12. 如调用方明确要求，再额外生成 Excel 或其他汇总产物

### 首步截图优先检查

详细分析任何失败 case 前，必须先做首步页面校验。这一条优先级高于单个错误摘要，也高于后续步骤里的业务细节。

1. 先取第一个 execution 的第一张有效截图，确认首步是否真的进入了目标页面
2. 必须优先识别以下首步异常：`404` / `Page not found` / 登录页 / 权限页 / 白屏 / 启动页
3. 如果首步已经异常，后续 case 的失败大概率是连锁反应；此时仍要记录各 case 的局部现象，但汇总时必须收敛到共享上游原因
4. 不要因为首步 `waitFor` 返回成功，就默认认为页面正确；页面有内容 ≠ 已进入正确业务页
5. 如果首步截图与首个节点 instruction 指向的 URL / 页面不一致，优先把问题定位在 URL、登录态、权限或环境前置条件

### 单 case 必须包含的信息

每个失败 case 的分析结果必须至少包含：

- 失败步骤序号
- 失败步骤原始 instruction（来自节点执行接口的 `step_name`）
- 若 instruction 为空，必须明确标注"当前节点没有拿到可执行步骤文本"
- AI 推理过程中的 `reasoning_content` 关键片段
- 失败截图与首步截图的验证结论
- 失败现象
- 关键证据（至少 2 条，优先来自 instruction / 节点错误 / reasoning / 截图）
- 排除判断（为什么不是更常见的相似类）
- 直接原因
- 根本原因
- 归因类别（见下方归因分类体系）
- 归因子分类
- 置信度（高 / 中 / 低）
- 修复建议

额外约束：

- 每个 case 都必须做 **原始 instruction + reasoning_content + 截图** 三方交叉验证；不能只读错误摘要就下结论
- 如果 `reasoning_content` 与截图结论冲突，以截图体现的页面状态为准，并把这种冲突写进分析结果
- 如果首步截图已经显示 404 / 登录页 / 权限页 / 白屏，则后续 case 默认按连锁失败思路继续分析，除非有更强证据证明失败发生在独立步骤
- 如果 instruction 为空，但 `error_message`、截图、页面状态或 HTML 报告已经给出更强证据，则必须优先采用这些更强证据归因
- 如果没有足够证据，结论只能写"当前证据不足以确定根因"，不能直接写"instruction 为空"
- `instruction 为空` 只能作为现象或证据，不能自动等于最终根因；只有原始报错明确指出空 instruction 时，才允许归为 `Bits2Midscene-解析步骤`
- 如果没有 `关键证据`、`排除判断` 或 `置信度`，则视为分析不完整

### 截图与推理的强制校验

分析时不能只看错误摘要，必须同时核对 `reasoning_content`、原始 instruction 与截图线索：

1. 先看第一步是否已经进入正确页面
2. 第一优先级是核对首步页面是否为 `404`、`Page not found`、登录页、权限页、白屏/启动页；若首步已异常，后续失败大多属于连锁反应
3. 第二优先级是核对失败步骤的原始 instruction、模型 `reasoning_content` 与失败截图是否相互印证
4. 如果 `reasoning_content` 与截图线索不一致，以截图体现的页面状态为准；分析结果里必须写清楚 AI 误判在什么地方
5. 不能只写"AI 操作失败""断言失败""页面加载问题"这类泛化结论，必须说清楚失败发生在什么页面、哪一步、哪里不一致
6. `failed to locate element`、`Replanned 100 times`、`instruction incomplete` 都只是现象，不能直接跳到模型或 `Bits2Midscene`
7. 如果 HTML 报告没有明确 `failed task`，必须继续检查 `executions -> tasks` 是否存在长时间循环
8. 判断循环时，**优先看多步 `Planning` prompt 是否高度重复、`Action Space` 是否反复穿插、执行是否长期没有前进**；不要依赖 `BOE`、`TikTok Test` 这类业务关键词做结论
9. 循环摘要应写成抽象结论，例如"重复 prompt 模式累计出现 24 次，执行未进入稳定的后续步骤"，而不是抄具体业务词当根因

### 归因分类体系（v2 - 对齐人工标准）

> **重要变更**：归因输出不再使用旧的"改动方"单一字段，改为输出 **归因类别 + 归因子分类** 双层结构。以下分类体系与业务 QA 人工归因标准完全对齐。

#### 一级归因类别

| 归因类别 | 定义 | 典型场景 |
|---------|------|---------|
| **Case 测试数据问题** | 测试数据不满足前置条件 | 页面数据为空、搜索无结果、账号不存在、测试数据被占用、预期数据已过期 |
| **Case 描述 - 业务QA** | 用例步骤/断言本身的描述有问题 | 步骤描述不清晰、断言文案与页面不一致、URL 填写错误、预期与实际页面结构不匹配 |
| **Bits2Midscene-解析步骤** | markdown2midscene 转换阶段产生的问题 | 空步骤（instruction 为空）、URL 解析错误、节点文本丢失、步骤拆分异常 |
| **工具问题 - 模型** | 模型本身的执行或规划能力问题 | 模型 429、LLM 返回空、JSON 解析失败、Replanned 100 次、明确的元素定位失败（排除数据/描述问题后）、规划路径不合理 |
| **Midscene** | Midscene 框架层面的问题 | 首步 waitFor timeout、白屏启动页、页面未稳定、浏览器内部截图错误 |
| **环境问题** | 运行环境相关的非业务问题 | 登录凭证失效、Google 登录页弹出、session 过期、网络连接错误、CDN 超时 |
| **Bug** | 被测产品的实际 Bug | 页面功能异常，操作和断言均正确但产品行为不符合 PRD |

#### 二级归因子分类

| 一级类别 | 子分类 | 典型证据 |
|---------|--------|---------|
| Case 测试数据问题 | **空数据** | 页面/表格显示 No result、No tasks found、空列表 |
| Case 测试数据问题 | **断言描述** | 断言中的预期文案/顺序/结构与页面实际不一致（如侧边栏新增了 Shop 条目） |
| Case 描述 - 业务QA | **步骤描述** | 步骤指令模糊（如"点击右上角按钮"但存在多个按钮）、操作路径不正确 |
| Case 描述 - 业务QA | **步骤清晰度** | 步骤可执行但歧义导致模型选错目标 |
| Case 描述 - 业务QA | **断言描述** | 断言条件本身写错或不可验证 |
| Case 描述 - 业务QA | **URL** | Case 中配置的 URL 不正确或缺少必要参数 |
| Bits2Midscene-解析步骤 | **空步骤** | markdown2midscene 转换后 instruction 字段为空 |
| Bits2Midscene-解析步骤 | **URL** | 转换后 URL 丢失或拼接错误 |
| 工具问题 - 模型 | **规划能力** | 模型规划路径不合理、错误地跳过关键步骤 |
| 工具问题 - 模型 | **执行边界** | 模型无法处理复杂交互（如拖拽、多级下拉） |
| 工具问题 - 模型 | **断言太快** | 操作执行后未等待页面稳定就发起断言 |
| Midscene | **启动失败** | 首步 timeout、白屏 |
| Midscene | **截图异常** | Protocol error (Page.captureScreenshot) |
| 环境问题 | **网络错误** | 请求超时、DNS 解析失败、CDN 错误 |
| 环境问题 | **登录态** | 登录弹窗、凭证失效、Google 登录跳转 |
| Bug | **功能异常** | 产品行为与 PRD 不一致 |

#### ⚠️ 不再使用的旧分类

以下旧标签已废弃，**禁止在输出中使用**：
- ❌ `改动方: 模型` → 改用 `归因类别: 工具问题 - 模型`
- ❌ `改动方: PRD2Case` → 改用 `归因类别: Bits2Midscene-解析步骤`（确认是转换阶段问题）或 `归因类别: Case 描述 - 业务QA`（确认是用例描述问题）
- ❌ `改动方: 业务QA` → 改用 `归因类别: Case 测试数据问题` 或 `归因类别: Case 描述 - 业务QA`（必须区分数据问题 vs 描述问题）
- ❌ `改动方: 业务QA（待确认）` → 已废弃，如证据不足直接标注置信度为"低"并给出最可能的归因方向
- ❌ `改动方: 待确认` → 已废弃，同上

#### 与旧 report-analysis 口径的映射

为兼容历史分析习惯，阅读旧报告时可按下面方式映射到当前 `webe2e` 的 v2 归因体系：

| 旧口径 | 当前归因类别 | 常见落点 |
|------|------|------|
| `改动方: 业务QA` | `Case 测试数据问题` 或 `Case 描述 - 业务QA` | 空数据、前置条件未满足、步骤描述不清、断言文案不符 |
| `改动方: PRD2Case` | `Bits2Midscene-解析步骤` | 空步骤、URL 丢失、节点拆分异常 |
| `改动方: 模型` | `工具问题 - 模型` | 规划能力、执行边界、断言太快 |
| `改动方: Midscene` | `Midscene` | 启动失败、截图异常、页面未稳定 |
| `改动方: Bug` | `Bug` | 功能异常 |
| `改动方: 环境问题` | `环境问题` | 登录态、网络错误、权限页、环境不可达 |

如果旧报告里只有 `改动方`，没有进一步细分，迁移时必须继续补全到当前格式：`归因类别 + 归因子分类 + 根因摘要`，不能只保留旧标签。

### 强制分层归因决策树

> **重要变更**：原规则写了"分层排除不能跳步"但执行中经常跳步。现改为强制决策树，每个 case 必须在输出中逐层展示排除过程。

每个 case 必须严格按以下顺序逐层排除，**每一层的判断结果必须在输出中显式写出**（即使结论是"排除"）：

```text
┌─ Layer 1: 证据充分性检查
│  Q: 是否同时具备节点执行信息 + HTML 报告 + 截图/reasoning？
│  → 否：置信度强制降为"低"，在归因结论前标注"⚠️ 证据不足"
│  → 是：继续 Layer 2
│
├─ Layer 2: 测试数据检查
│  Q: 页面是否显示空数据/No result/空列表？搜索/筛选后无匹配结果？
│  Q: 账号/前置数据是否不满足条件？
│  → 命中：→ Case 测试数据问题 / 空数据
│  → 不命中，继续 Layer 3
│
├─ Layer 3: 断言一致性检查
│  Q: 断言预期的文案/结构/顺序是否与页面实际不一致？（如页面新增/移除了元素）
│  → 命中：→ Case 测试数据问题 / 断言描述
│  → 不命中，继续 Layer 4
│
├─ Layer 4: 步骤/instruction 检查
│  Q: instruction 是否为空？
│  → 空：→ Bits2Midscene-解析步骤 / 空步骤
│  Q: 步骤描述是否清晰可执行？是否有歧义/错误？
│  → 不清晰/有错：→ Case 描述 - 业务QA / 步骤描述 或 步骤清晰度
│  Q: URL 是否正确？
│  → URL 错误：→ Case 描述 - 业务QA / URL 或 Bits2Midscene-解析步骤 / URL
│  → 全部通过，继续 Layer 5
│
├─ Layer 5: 时序检查（断言太快）
│  Q: 失败步骤中是否同时包含「操作」和「断言」？
│  Q: 操作刚执行后是否立即进行了断言（无等待）？
│  Q: 截图是否显示页面处于加载态/动画进行中/搜索结果未返回？
│  → 全部命中：→ 工具问题 - 模型 / 断言太快
│  → 不命中，继续 Layer 6
│
├─ Layer 6: 环境检查
│  Q: 首步页面是否为 404、登录页、权限页、白屏？
│  Q: 是否出现登录弹窗、session 过期、网络错误？
│  Q: HTML 报告是否出现前置步骤长循环，同时伴随 Request Error / RPC error / service error？
│  → 命中：→ 环境问题 / 对应子分类，或 Midscene / 启动失败
│  → 不命中，继续 Layer 7
│
├─ Layer 7: 产品 Bug 检查
│  Q: 操作步骤和断言本身都正确，但产品行为不符合预期？
│  → 命中：→ Bug / 功能异常
│  → 不命中，继续 Layer 8
│
└─ Layer 8: 模型能力问题（兜底层）
   只有以上所有层级都排除后，才归为模型问题：
   Q: 模型是否返回 429 / empty content / JSON 解析失败？
   → 是：→ 工具问题 - 模型 / 执行边界
   Q: 模型是否 Replanned 100 次 / 规划路径明显不合理？
   → 是：→ 工具问题 - 模型 / 规划能力
   Q: HTML 报告是否显示多步 `Planning` prompt 高度重复、`Action Space` 反复穿插，但没有更强的环境错误信号？
   → 是：→ 工具问题 - 模型 / 规划能力
   Q: 模型是否在步骤清晰、数据存在的情况下仍定位失败？
   → 是：→ 工具问题 - 模型 / 执行边界
```

**强制输出格式**：每个 case 的分析中必须包含一个"归因决策路径"段落，格式如下：

```text
归因决策路径：
- Layer 1 证据充分性：✅ 具备节点信息 + HTML 报告 + 截图
- Layer 2 测试数据：✅ 排除（页面有数据展示）
- Layer 3 断言一致性：❌ 命中 → 侧边栏新增 Shop 条目，预期顺序为 For You → Explore，实际为 For You → Shop → Explore
- 归因结论：Case 测试数据问题 / 断言描述
```

### 根因摘要格式约束

> **重要变更**：禁止使用泛化现象描述作为根因摘要。

根因摘要必须包含三要素：**[失败环节] + [具体现象] + [责任判定]**

**禁止的根因摘要示例**（现象描述，不是根因分析）：
- ❌ "指令不完整"
- ❌ "登录问题"
- ❌ "Follow 按钮问题"
- ❌ "Explore 页面问题"
- ❌ "内部错误"
- ❌ "需进一步分析"

**正确的根因摘要示例**：
- ✅ "第 2 步 instruction 为空，markdown2midscene 转换时丢失了操作步骤文本（Bits2Midscene-解析步骤）"
- ✅ "首步跳转到 Google 登录页，case 中配置的 URL 未包含登录态参数（Case 描述 - 业务QA / URL）"
- ✅ "Explore 页面无视频封面展示，网络请求返回错误，非 case 问题（环境问题 / 网络错误）"
- ✅ "第 3 步断言侧边栏顺序为 For You → Explore，但页面实际显示 For You → Shop → Explore，新增了 Shop 入口（Case 测试数据问题 / 断言描述）"
- ✅ "第 4 步点击 Close 后模型返回 empty content from AI，模型服务异常（工具问题 - 模型 / 执行边界）"
- ✅ "第 2 步搜索后立即断言表格有数据，但截图显示搜索结果尚在加载（工具问题 - 模型 / 断言太快）"

### 连锁失败收敛

详细分析时，不能把明显共享上游原因的 case 机械拆成多个独立根因。至少要检查是否存在以下模式：

- 首步 URL / 登录态异常，导致后续所有断言一起失败
- 某个核心动作提交失败，后续 toast、状态更新、列表持久化全部跟着失败
- 同一类数据缺失导致多个 case 同时出现 `No tasks found`、`No result`、空列表
- 同一 UI 变更（如侧边栏新增条目）导致多个 case 断言失败

如果命中这类模式：

- 单 case 里仍要写各自失败现象
- 但汇总里必须把它们收敛为共享上游原因，避免"11 个 case，11 个不同根因"的假象
- 单 case 分析中增加字段：`收敛标记: "与 Case-XXX 共享上游原因：[原因简述]"`

### 常见归因规则（更新版）

#### `Bits2Midscene-解析步骤`（原 PRD2Case 部分场景）

- 真实报错明确指出 instruction 为空、`No specific instruction was provided`
- URL 在 markdown2midscene 转换后丢失或拼接错误
- 节点文本在转换阶段丢失，导致模型拿不到操作目标
- **⚠️ 判定标准**：必须确认问题出在 markdown → midscene 转换环节；如果 case.md 原始步骤本身就不清晰，应归为 `Case 描述 - 业务QA`
- **⚠️ 与模型的区分**：如果 instruction 不完整但模型仍然可以合理推断操作（只是执行失败），应归为 `工具问题 - 模型`

#### `工具问题 - 模型`

- 模型服务 `429`
- `empty content from AI model`
- `failed to parse LLM response into JSON`
- `Replanned 100 times`
- HTML 报告里多步 `Planning` prompt 高度重复，`Action Space` 反复出现，但没有更强的环境错误信号时，可归为 `规划能力`
- **断言太快**：操作执行后未等待页面稳定即断言，截图显示加载态
- **⚠️ 前置排除**：归为模型问题前，必须已排除 Layer 2-6 的所有可能；如果步骤描述不清晰导致定位失败，根因在 Case 描述而非模型

#### `Midscene`

- 首步 `waitFor timeout`
- 截图显示 TikTok logo 白底启动页、白屏、长时间 loading
- `Protocol error (Page.captureScreenshot): Internal error`（Midscene 框架的截图异常）
- 任务失败点主要发生在页面尚未稳定时

#### `Case 测试数据问题`

- 账号不存在
- 前置数据不满足，例如没有可用收藏视频、测试数据已被占用
- 页面/表格显示 `No result`、`No tasks found`、空列表
- 断言中的预期文案/结构/顺序与页面实际不一致（**UI 更新导致断言过期**）

#### `Case 描述 - 业务QA`

- 步骤描述不清晰或有歧义，导致模型无法准确执行
- 步骤路径本身不正确（如元素不存在、导航路径错误）
- 断言条件写错或不可验证
- Case 中配置的 URL 不正确

#### `环境问题`

- 登录凭证失效、Google 登录页弹出
- Session 过期
- 网络连接错误、CDN 超时
- HTML 报告显示执行长时间卡在同一前置步骤循环，同时伴随 `Request Error`、`RPC error`、未处理服务错误提示
- **⚠️ 与 Case 描述的区分**：如果 URL 本身就配错了（写的就不对），归 Case 描述；如果 URL 正确但环境不可达，归环境问题

### HTML 报告循环判定

当节点执行接口没有给出明确失败步骤，或 HTML 报告里没有明确 `failed task` 时，必须进一步检查 `executions -> tasks`：

- 重点看 `Planning` 是否连续高频出现，且中间反复穿插 `Action Space`
- 重点看多个 `Planning` 的 prompt 是否属于同一类语义，经过归一化后仍高度重复
- 如果重复 prompt 模式持续出现，且执行没有进入新的稳定步骤，可视为"卡在同一阶段循环"
- 如果循环同时伴随 `Request Error` / `RPC error` / service error，优先归为 `环境问题 / 网络错误`
- 如果循环存在，但没有更强的环境或服务异常信号，再考虑归为 `工具问题 - 模型 / 规划能力`
- 输出时必须总结成抽象模式，例如：
  - `重复 prompt 模式累计出现 24 次，执行未进入稳定的后续步骤`
  - `Planning / Action Space 在同一前置阶段反复切换，但没有形成有效前进`
- 禁止把页面里的业务实体词直接当作根因；业务词最多只能作为辅助证据，不能代替循环判定本身

#### `Bug`

- 页面功能异常，操作步骤和断言本身都正确，但产品行为不符合预期
- 需要截图或 HTML 报告中有充分证据证明是产品问题

### 禁止的通用归因

以下表述不能直接作为最终结论：

- "任务执行失败"
- "AI 操作失败"
- "断言不通过"
- "页面加载问题"
- "元素定位失败"
- "全部都是 PRD2Case"
- "没有证据，但先归因为 instruction 为空"
- "指令不完整"
- "登录问题"
- "XXX 按钮问题"
- "XXX 页面问题"
- "内部错误"
- "需进一步分析"
- "待确认"

必须替换成带上下文的结论，例如：

- "第 5 步点击视频封面后实际跳转到 `@haniawooga` 的视频详情页，与预期 `@testhmuhdwstmh` 不一致"
- "第 2 步首屏仍停留在 TikTok logo 白底启动页，`waitFor` 多次判断页面处于加载态，未进入目标 profile 页面"
- "第 2 步 instruction 为空，模型没有可执行动作，因此直接返回 `No specific instruction was provided`"
- "当前只有节点元数据缺失，尚无足够证据判断是步骤生成缺陷还是业务态异常，需要继续结合错误信息或页面状态确认"

### 建议输出骨架

每个失败 case 的文字分析建议固定按下面结构输出：

- `失败步骤信息`：步骤序号、原始 instruction、节点/执行名称
- `AI 推理过程`：引用 `reasoning_content` 关键片段，说明模型认为页面状态是什么、计划做什么
- `截图验证`：首步截图与失败截图各自显示了什么；若与 reasoning 不一致，必须明确写出差异
- `失败现象`：页面 / 日志里实际发生了什么
- `关键证据`：至少 2 条
- `归因决策路径`：逐层排除记录（见上方强制格式）
- `排除判断`：为什么不是其他高相似类
- `直接原因`：具体错误现象，禁止泛化描述
- `根本原因`：为什么会发生，必须落到前置条件、步骤描述、转换链路、模型能力、环境或产品行为
- `最终归因`：`归因类别 / 归因子分类 / 根因摘要`
- `归因理由`：为什么责任落在这里
- `置信度`：高 / 中 / 低
- `收敛标记`：如有共享上游原因，标注关联 case
- `修复建议`：具体到用例、步骤或链路

### 可选汇总产物

- 默认先更新 `test_report.md` 中的 Overview，再由用户决定是否继续详细分析
- 详细分析阶段的"根因汇总"建议至少包含 `Case 名称`、`执行节点`、`归因类别`、`归因子分类`、`根因摘要`、`置信度`、`详情页`、`HTML 报告`
- 只有当用户明确要求导出 Excel、表格化汇总、或需要二次分发材料时，才额外生成 Excel
- 如果需要生成 Excel，建议包含：`Case 名称`、`执行节点`、`归因类别`、`归因子分类`、`根因摘要`、`置信度`、`失败步骤`、`失败现象`、`关键证据`、`排除判断`、`直接原因`、`根本原因`、`修复建议`、`详情链接`、`HTML 报告链接`

## 参数说明

### list-platforms 命令

- 无额外参数

### platform-detail 命令

- `--platform`: 平台标识，必填
- `--domain`: 平台域，可选；当平台列表里存在同名 `platform` 时建议一并传入

### init-env 命令
- `--case-md`: `case.md` 路径，必填

### show-env 命令
- `--case-md`: `case.md` 路径，必填
- `--env-file`: 环境变量文件，可选

### prepare / create-group / run / run-local 命令

- `--case-md`: `case.md` 路径，必填
- `--title`: 用例组标题，可选；默认优先取 `case.md` 一级标题
- `--creator`: 创建者，可选；默认从 `git user.email` 推导
- `--env-file`: 环境变量文件，可选；默认读取 `case.md` 同目录的 `.env`
- `--execution-mode`: 可选；覆盖 `.env` 里的 `EXECUTION_MODE`
- `--local-runner`: 可选；覆盖 `.env` 里的 `LOCAL_RUNNER`
- `--payload-out`: 仅 `prepare` / `create-group` / `run` 常用；将 TTAT payload 写到本地，便于排查
- `--plan-out`: 仅本地模式使用；将 `local_execution_plan.json` 写到指定路径
- `--task-name`: 仅 `run` 使用；指定任务名，默认沿用 `case_group_name`
- `--token-name`: 仅 `run` 使用；获取动态 token 时的 name，默认使用 `creator`
- `--report-out`: `run` / `run-local` 使用；指定 `test_report.md` 输出路径，默认写到 `case.md` 同目录
- `--confirmed-env`: `run` / `run-local` 必填语义参数；只有在 `show-env` 展示完成且用户明确确认后才能传

### query-task 命令

- `--task-id`: TTAT 任务 ID，必填

### analyze-task 命令

- `--task-id`: TTAT 任务 ID，必填
- `--case-md`: 可选；用于把 Overview / 详细分析默认回写到 `case.md` 同目录的 `test_report.md`
- `--detail`: 可选；只有用户确认后才使用，开启失败 case 详细下钻分析
- `--format`: 输出格式，可选 `markdown` / `json`，默认 `markdown`
- `--report-out`: 自定义分析结果写入路径；不传时默认写 `test_report.md`

### 超时恢复说明

- `analyze-task --detail` 的脚本内部 HTTP 超时是 15 分钟，因此外层 `Bash timeout` 也应至少设置为 `900000ms`
- 若 `--detail` 执行过程中被外层 `cc` 或其他执行器超时中断，`test_report.md` 中仍会保留已经完成的 case 详细分析
- 报告中的"分析进度"会明确展示已完成数、剩余数，以及"可能因超时或中断未完成"的提示
- 重新执行同一条 `--detail` 命令即可继续，脚本会自动跳过已完成 case

## 环境文件 `.env`

### 模板文件
模板文件位于 `resources/.env`，当执行 `init-env` 命令时会复制到 `case.md` 同目录下。

### 文件位置
执行时默认读取 `case.md` 同目录下的 `.env` 文件。

### 支持的参数
| 参数 | 说明 | 示例值 | 是否必需 |
|------|------|--------|----------|
| creator | 创建者邮箱前缀（必填） | yourname | 是 |
| EXECUTION_MODE | 执行模式 | ttat, local | 是 |
| LOCAL_RUNNER | 本地模式 runner，固定为 playwright | playwright | 是 |
| LOCAL_CASE_CONCURRENCY | 本地模式 case 级并发度 | 10 | 否 |
| platform | 测试平台；仅 TTAT 远程链路使用，本地 Playwright 模式忽略 | live-campaign | 否 |
| RUN_ENV | 运行环境；TTAT 远程链路使用，本地 Playwright 模式仅用于生成 header | boe, ppe, online | 否 |
| TEST_IDC | 测试机房 | sg, boe, ppe | 否 |
| SWIMLANE | 泳道标识；本地 Playwright 模式用于生成 `x-tt-env` header | your_swimlane | 否 |
| TASK_TIMEOUT | 任务超时时间（分钟） | 10 | 否 |
| *自定义变量* | 任意自定义参数，会一并传入 TTAT | any_key=any_value | 否 |

### 默认模板（resources/.env）
```text
# Web E2E 执行环境配置
# 创建者邮箱前缀（必填，用于 TTAT 用例和任务创建）
creator=
# 执行模式: ttat, local
EXECUTION_MODE=ttat
# 本地执行 runner: playwright
LOCAL_RUNNER=playwright
# 本地 case 级并发度
LOCAL_CASE_CONCURRENCY=10
# 测试平台，如 live-campaign, your-platform
platform=live-campaign
# 运行环境: boe, ppe, online
RUN_ENV=ppe
# 测试机房: sg, boe, ppe 等
TEST_IDC=sg
# 泳道标识（可选）
SWIMLANE=
# 任务超时时间（分钟）
TASK_TIMEOUT=10
```

### `task.md` 预填规则

- 搜索路径：从 `case.md` 所在目录开始，逐级向上查找 `task.md`
- 预填变量：`RUN_ENV`、`SWIMLANE`、`TEST_IDC`
- 支持格式示例：

```md
- RUN_ENV: ppe
- TEST_IDC: sg
- SWIMLANE: ppe_xxx
```

```md
| RUN_ENV | ppe |
| TEST_IDC | sg |
| SWIMLANE | ppe_xxx |
```

- 如果 `task.md` 中没有这些值，也不会报错，用户仍可在环境确认阶段手动修正

## 推荐用法

### TTAT 模式（推荐）

```bash
# 1. 初始化环境配置文件
python3 $SKILL_DIR/scripts/case2webe2e.py init-env --case-md test/case.md

# 2. 展示当前环境配置（供用户确认）
python3 $SKILL_DIR/scripts/case2webe2e.py show-env --case-md test/case.md

# 3. 用户确认后执行完整链路
python3 $SKILL_DIR/scripts/case2webe2e.py run \
  --case-md test/case.md \
  --confirmed-env \
  --payload-out out/case_group_payload.json

# 4. 显式查询任务状态
python3 $SKILL_DIR/scripts/case2webe2e.py query-task --task-id <task_id>

# 5. 任务完成后，先把 Overview 写入 test_report.md
python3 $SKILL_DIR/scripts/case2webe2e.py analyze-task --task-id <task_id> --case-md test/case.md

# 6. 用户确认后，再继续详细下钻
python3 $SKILL_DIR/scripts/case2webe2e.py analyze-task --task-id <task_id> --case-md test/case.md --detail
```

### 本地模式（Playwright MCP）

```bash
# 1. 初始化环境配置文件
python3 $SKILL_DIR/scripts/case2webe2e.py init-env --case-md test/case.md

# 2. 展示当前环境配置（确认 EXECUTION_MODE=local，LOCAL_RUNNER 已设置）
python3 $SKILL_DIR/scripts/case2webe2e.py show-env --case-md test/case.md

# 3. 用户确认后，生成本地执行计划并初始化报告
python3 $SKILL_DIR/scripts/case2webe2e.py run-local \
  --case-md test/case.md \
  --confirmed-env \
  --local-case-concurrency 10 \
  --plan-out out/local_execution_plan.json

# 4. AI 根据 local_execution_plan.json 使用 Playwright MCP 做 case 级并发执行
#    启动浏览器时必须带上 plan 中的 browser_headers
#    必须将截图、trace、录像、控制台日志等产物整理到 test_result/

# 5. 执行完成后，将结果补充回 test_report.md
```

## 测试报告 test_report.md

### 默认位置

- 默认写到 `case.md` 同目录，例如 `test/test_report.md`
- 如需改路径，使用 `--report-out`

### 必须写入的内容

1. TTAT 模式：用例组和任务基础信息、本次环境文件路径、当前任务状态说明
2. 本地模式：沿用远程模式相同的 `执行概览` / `任务状态` 主结构；其中 `task_url` 写为本地执行目录路径（默认 `test_result/`），并补充 `execution_mode`、`local_runner`、`plan_file`、`browser_headers`、每个 case 的本地产物目录；Playwright 的截图、trace、录像、控制台日志必须在执行后统一落在 `test_result/`，再把这些实际产物路径和执行结果、关键证据回写到报告
3. `analyze-task` 仅适用于 TTAT 模式，且默认先回写 Overview 到 `test_report.md`
4. 只有用户确认后执行 `--detail`，才继续把详细下钻结果写回 `test_report.md`

### 仅创建用例组

```bash
python3 $SKILL_DIR/scripts/case2webe2e.py create-group \
  --case-md test/case.md \
  --payload-out out/case_group_payload.json
```

## 输出

TTAT 模式执行成功后，脚本会输出：

- `case_group_name`
- `case_count`
- `case_group_id`
- `task_name`
- `task_id`
- `task_url`
- `report_file`

本地模式执行计划生成成功后，脚本会输出：

- `execution_mode`
- `local_runner`
- `task_url`
- `artifacts_root`
- `mcp_server`
- `runner_mode`
- `case_count`
- `plan_file`
- `report_file`

## 失败处理

- `case.md` 不存在：直接报错并停止
- `markdown2midscene` 无法解析：保留 `prepare` 能力方便排查返回内容
- 创建用例组失败：输出接口响应并停止
- 创建任务失败：输出接口响应并停止
- 本地模式下 `EXECUTION_MODE` / `LOCAL_RUNNER` 非法：直接报错并停止
- 本地模式下 MCP 未安装或 Midscene 模型环境变量未配置：停止执行，并提示先修正 MCP 配置
