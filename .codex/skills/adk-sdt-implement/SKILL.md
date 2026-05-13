---
name: adk-sdt-implement
description: "Use when the user wants to execute `tasks.md` and `case.md` in spec test directory, implement approved SDT test tasks in order, update task progress, and verify results; do not use for ordinary coding requests that are not task-list driven."
---

# ADK SDT Implement

This skill is an SDT stage skill for implementing test according to `case.md`. It is suitable for executing tests in `tasks.md` order, and completing validation.

## Manual Trigger Constraints

- Use this skill only when the user explicitly wants to implement work according to`tasks.md` and `case.md` in spec test directory, update task status, and perform completion validation.
- Do not automatically route ordinary coding and tests requests to `adk-sdt-implement`.

## User Input

```text
$ARGUMENTS
```
You **MUST** consider the user input before proceeding (if not empty).

If the given `$ARGUMENTS` contains a link, you need to read the content of the link. For lark/feishu doc URLs, export it via lark-docs MCP (`mcp__lark-docs__export_lark_doc_markdown`), then read the exported markdown content.

## Context
**Read context before Executing**:
1. Language Setting
   - Read `preferred_language` from `.ttadk/config.json` (default: 'en' if missing). **IMPORTANT** **Use the configured language for ALL outputs: 'en' → English, 'zh' → 中文. This applies to: generated documents (specs, plans, tasks), interactive prompts, confirmations, status messages, and error descriptions.**

## Outline

1. Run `node .ttadk/plugins/ttadk/core/resources/scripts/check-prerequisites.js --json --require-tasks --include-tasks` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute.

Goal: Act as a test execution dispatcher — select the appropriate Testing Skill based on user choice, execute tests against `test/case.md`

### 0: Git Status Check

1. Run `git status --porcelain` from repo root to check for uncommitted changes.
2. If the output is **non-empty** (there are uncommitted changes):
   - Display the list of changed files to the user.
   - Ask the user (using the host-compatible structured question tool): "There are uncommitted changes in the repository. Would you like to commit them before proceeding?"
     - **Yes**: Execute the `/adk:commit` skill to stage, commit, and push changes. After the commit completes, continue to the next step.
     - **No**: Skip committing and continue directly to the next step.
3. If the output is **empty** (no uncommitted changes), proceed directly to the next step.

### 1: Pre-check

1. Read `test/case.md` under FEATURE_DIR.
   - If `test/case.md` does not exist, **STOP** and display error: "test/case.md not found. Please run `/adk:sdt:ff` first to generate test cases."
2. Read `test/task.md` under FEATURE_DIR.
   - If `test/task.md` does not exist, **STOP** and display error: "test/task.md not found. Please run `/adk:sdt:ff` first to generate test tasks."

Parse the test case file:
- Count total test cases.
- Identify platforms distribution (Backend / Frontend / Client).
- Identify priority distribution (P0 / P1 / P2 / P3).
4. Display summary:
   ```
   Loaded test/case.md:
   - Total test cases: N
   - Backend test cases: X
   - Frontend test cases: Y
   - Client test cases: Z
   ```

### 2: Read test/task.md File
- **Task phases**: Env Deploy, Tests, Report
- **Task dependencies**: Sequential vs parallel execution rules
- **Task details**: ID, description, file paths, parallel markers [P]
- **Execution flow**: Order and dependency requirements


### 3: **⚠️ MANDATORY: Parallelization Analysis (MUST be done BEFORE any task execution)**

**You MUST NOT start executing any task until this analysis is complete.** Before running the first task, you are required to explicitly identify and plan all tasks that can be executed in parallel. Skipping this step is not allowed.

1. **Scan all pending tasks** (`- [ ]`) in `test/task.md` phase by phase.
2. **Identify parallel groups**:
   - Tasks explicitly marked with `[P]` within the same phase are candidates for parallel execution.
   - Verify no file-path conflict between candidates — tasks touching the same files MUST run sequentially, even if marked `[P]`.
   - Verify no implicit dependency (e.g., one task's output is another's input).
3. **Produce a Parallelization Plan** and present it to the user before execution. The plan MUST include:
   - Phase name
   - Parallel groups: `[Group-N] → [TaskID-A, TaskID-B, ...]`
   - Sequential tasks (tasks that must run alone): `[TaskID-X]`
   - Reasoning for why non-`[P]` or conflicting tasks cannot be parallelized
4. **Only after the plan is produced**, proceed to Step 4 to execute tasks according to the plan.

### 4: Execute Tasks Based on Dependencies in test/task.md
- **Follow the Parallelization Plan from Step 3**: Dispatch parallel groups concurrently, run sequential tasks one by one
- **Phase-by-phase execution**: Complete each phase before moving to the next
- **Never skip any task**: If a task is marked as `[ ]`, do not skip it.
- **Respect dependencies**: Run sequential tasks in order, parallel tasks [P] can run together
- **Follow TDD approach**: Execute test tasks before their corresponding implementation tasks
- **File-based coordination**: Tasks affecting the same files must run sequentially
- **Validation checkpoints**: Verify each phase completion before proceeding

### 5: Summary:
1. Read the report template: `plugins/ttadk/core/resources/templates/sdt-report-template.md`.
2. Fill in the template with execution results:
   - **Execution Overview**: execution time, skill name, scope, pass/fail/skip counts and rates.
   - **Result Details Table**: each test case's TC-ID, title, method, status, **Log ID** (extracted from each PSM's `test_report.md` — every case must have a Log ID, use N/A if unavailable), duration, failure reason.
   - **Failure Analysis**: for each failed case — error message, root cause, Argos log (backend), fix status.
3. Write the report to `test/report.md`.
4. Display the execution summary.


### 6: **⚠️ CRITICAL: Progress Tracking (MUST follow strictly)**

**Resume Rule**: If a task is already marked as `[X]` or `[x]`, skip it and move to the next uncompleted task. When re-entering this command, automatically continue from where you left off - do NOT start from the beginning unless the user explicitly requests to redo or fix a specific task.

**Immediate Update Rule**: As soon as a task is completed, you MUST immediately update its status in tasks.md from `- [ ]` to `- [x]` BEFORE moving to the next task. Do NOT batch updates. Do NOT wait until the end.

**Workflow**: Complete task → Verify completion → Update test_tasks.md (`- [ ]` → `- [x]`) → Move to next task

Other error handling:
- Report progress after each completed task
- Halt execution if any non-parallel task fails
- For parallel tasks [P], continue with successful tasks, report failed ones
- Provide clear error messages with context for debugging

### 7. Completion validation:
- Verify all required tasks are completed

### 8. Lark Export
   - Use `mcp__lark-docs__import_markdown_to_lark` to import the generated report into Lark
   - Parameter settings:
     - `filePath`: Absolute path of the generated `test/report.md`
     - `title`: **IMPORTANT** - Generate a concise descriptive title that summarizes the core purpose of the feature:
       - Use the language matching the `preferred_language` setting (zh → Chinese, en → English)
       - Keep it short (preferably no more than 30 characters)
       - Do not use the folder name directly — summarize the actual content
   - Obtain the Lark document URL
   - **Directly use the `open` command to open the Lark document link**:
     ```bash
     open "https://feishu.cn/docx/xxxxx"
     ```
   - provide
     ```markdown
      ## Report Generated
      **Lark Document**: [Link] (opened in browser)
      **Local File**: `test/report.md`
     ```

### 9. **Final Task Completion Check**:
- Re-read `test/tasks.md` and verify no `- [ ]` remains
- If incomplete tasks exist, complete them before proceeding



## Error Handling

| Scenario | Handling |
|----------|---------|
| test/case.md does not exist | Prompt user to run `/adk:sdt:ff` first |
| Skill not registered/does not exist | Display error "Testing Skill {name} not found" |
| Fix introduces new failures | Mark as "New failure introduced by fix" in report and alert |
| No test cases matching the platform | Display "No test cases found for {platform}" |
| Skill execution timeout | Mark test case as SKIP and continue to the next one |

## Next Step Guidance

After executing this command:

### Step 1 - Review Results
Review `test/report.md` to understand test results and any remaining failures.

### Step 2 - Next Step Recommendation
Once all tests pass or results are satisfactory:

**Commit Changes**: Execute `/adk:commit` to stage changes, generate commit message, and push to remote.
