---
name: adk-sdt-ff
description: "Use when the user wants to convert spec into test cases and has prepared `spec.md`, or explicitly states they want to enter the ff(fast forward) phase of the SDT workflow, use this feature. Do not use it for general implementation requests."
---

# ADK SDT FF (Fast Forward)

This skill is an SDT stage skill for generating text test cases. This skill is designed to rapidly push forward the preparation for the testing process upon completion of the SDD process, when the testing process is to be launched.

## Manual Trigger Constraints

- Use this skill only when the user explicitly mentions `sdt-ff`, `sdt fast forward`, `sdt:ff`, `sdt fast-forward`, or explicitly names this skill.
- If the user only says something general like "help me test this" or "help me find bug," do not switch to this skill automatically.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

If the given `$ARGUMENTS` contains a link, you need to read the content of the link. For lark/feishu doc URLs, export it
via lark-docs MCP (`mcp__lark-docs__export_lark_doc_markdown`), then read the exported markdown content as test data
source.

If `$ARGUMENTS` explicitly provides a `FEATURE_DIR` value, or clearly provides a feature-directory path, you **MUST**
treat it as the highest-priority target feature input. Reuse that exact value when invoking prerequisite scripts, and do
not ask the user to choose a different feature unless the provided path is invalid or ambiguous.

## Context

**Read context before Executing**:

1. Language Setting
    - Read `preferred_language` from `.ttadk/config.json` (default: 'en' if missing). **IMPORTANT** **Use the configured
      language for ALL outputs: 'en' → English, 'zh' → 中文. This applies to: generated documents (specs, plans, tasks),
      interactive prompts, confirmations, status messages, and error descriptions.**

## Skills (host compatibility)

Skills are installed **per host**, under the repo root:

| Host            | Skill directory        |
|-----------------|------------------------|
| **Claude Code** | `.claude/skills/`      |
| **Cursor**      | `.cursor/skills/`      |

Each skill is a folder named after the skill (e.g. `prd2case`, `webe2e`) containing `SKILL.md`.

**Resolve `SKILL.md` for a logical skill name `<name>`** (e.g. `prd2case`, `webe2e`) — try **in order** until a file exists:

1. `.claude/skills/<name>/SKILL.md` — **Claude Code** layout.
2. `.cursor/skills/<name>/SKILL.md` — **Cursor** layout.

If none of the paths exist for that skill, **STOP** and tell the user to sync or install skills so that `SKILL.md` appears under `.claude/skills/` or `.cursor/skills/`.

**Execution rule:**

- **Claude Code**: If the host exposes the skill as an **invocable** tool, you may invoke it by name; if not, **read** the resolved `SKILL.md` from step above and execute its workflow.
- **Cursor** (and whenever the skill is not invocable): **read** the resolved `SKILL.md` (typically from `.claude/skills/` and `.cursor/skills/`) and **execute** its workflow using your normal tools (read/write repo files, terminal, MCP). The file is the **source of truth**—do not skip because no skill tool appears in the tool list.

## User Interaction (host compatibility)

- **Claude Code**: References to `AskUserQuestion` mean the host's structured question tool.
- **Cursor**: Map `AskUserQuestion` to the `AskQuestion` tool for **structured multiple-choice interactions** (single-select or multi-select).
- **Cursor free-form input rule**: `AskQuestion` only supports predefined options. When you need arbitrary user input (for example `HOST`, `PSM`, `BRANCH`, `PPE_ENV_NAME`, `SITE`, or other unconstrained values), ask the user in a normal chat message instead of using `AskQuestion`.

Nested references inside those skills (e.g. to `AskUserQuestion`) must follow **User Interaction (host compatibility)**.

## Outline

Given the user input (optional test data source), generate GWT-format test cases from the feature specification.

### Step 1: Pre-check

1. Inspect `$ARGUMENTS` first:
   - If it explicitly contains `FEATURE_DIR`, or clearly contains a feature-directory path, store it as `EXPLICIT_FEATURE_DIR`.
   - Otherwise leave `EXPLICIT_FEATURE_DIR` empty.
2. Run `node .ttadk/plugins/ttadk/core/resources/scripts/check-prerequisites.js --json` from repo root.
   - If `EXPLICIT_FEATURE_DIR` is present, append `--feature-dir "<EXPLICIT_FEATURE_DIR>"`.
3. Parse the JSON output to get `FEATURE_DIR`.
4. If parsing fails, abort and instruct user to verify the feature directory environment.

### Step 2: Confirm Target Feature

1. If `EXPLICIT_FEATURE_DIR` was provided and Step 1 succeeded, use the returned `FEATURE_DIR` directly and skip interactive feature selection.
2. Otherwise, check if multiple feature directories exist under `specs/`.
3. **If multiple features exist, must use the host-compatible structured question tool per `User Interaction (host compatibility)` to let the user select the target feature**.
4. If only one feature exists, use it automatically.
5. Set `FEATURE_DIR` to the selected feature's absolute path.

### Step 3: Load Requirement Document

1. **REQUIRED**: Read `FEATURE_DIR/spec.md` — this is the primary input.
    - If `spec.md` does not exist, **STOP** and display error: "spec.md not found. Please run `/adk:specify` first to generate the requirement document."
2. **REQUIRED**: Use the `lark_docs` MCP to download all Feishu documents referenced in `spec.md`
   (like: `https://bytedance.larkoffice.com/wiki/1234567890abcdef`), and save the test-data-related portions to
   `FEATURE_DIR/test/test_data.md` as test data population source.
3. **OPTIONAL**: Read `FEATURE_DIR/plan.md` if exists (for technical context).
4. **OPTIONAL**: Read `FEATURE_DIR/data-model.md` if exists (for entity/field reference).

### Step 4: Infer Target Platform

**Do not** ask the user to choose. Infer a single target platform from context already loaded (and any reasonable repo signals), using the same semantic values as before:

| Value    | Meaning                                          |
|----------|--------------------------------------------------|
| Backend  | Server-side APIs, data processing, business logic |
| Frontend | Web frontend pages, components, interactions      |

**Inference signals** (use in order; stop when confident):

1. **Explicit scope in `spec.md` / `plan.md` / `data-model.md`**: phrases pointing to UI (页面、组件、路由、前端、浏览器、交互、SSR、React/Vue 等) → **Frontend**; phrases pointing to services (API、接口、RPC、服务、数据库、后端、消息队列 等) → **Backend**.
2. **Primary deliverable**: if user stories mainly describe user-visible screens and flows → **Frontend**; if they mainly describe contracts, data flows, or server behavior → **Backend**.
3. **Repository hints** (if visible without heavy scanning): typical frontend roots (`src/pages`, `apps/web`, `*.tsx` under feature area) vs backend (`cmd/`, `handler`, `proto`, `thrift`, `PSM`, `service` packages) near or under the feature’s code paths — align **Frontend** / **Backend** with where implementation likely lives.

**Resolution**: Prefer the stronger signal. If signals conflict, prefer **Frontend** when UI/UX dominates the spec, otherwise **Backend**. Briefly state the inferred value and one-sentence rationale in the run summary (Step 8).

Set **target platform** to exactly `Backend` or `Frontend` (these strings) for all following steps.

### Step 5: Generate Test Cases Using prd2case Skill

1. Run the **prd2case** workflow per **Skills (host compatibility)** (invoke by name in Claude Code when available **or** resolve `SKILL.md` for `prd2case` and follow it). Use `FEATURE_DIR/spec.md` as the primary input. Generate test cases according to the **inferred** target platform from Step 4.
    - If target platform is **Backend**, execute task type 1 to generate backend API test cases.
    - If target platform is **Frontend**, execute task type 2 to generate web e2e test cases.

### Step 6: Generate Test Execution Task File

**You must first copy the template file, then edit the copied file in place. Do not create task.md from scratch.**

1. Based on the target platform from Step 4, if it is **Backend**, read the template:
   `plugins/ttadk/core/resources/templates/sdt-backend-task-template.md`.
   If it is **Frontend**, read the template: `plugins/ttadk/core/resources/templates/sdt-frontend-task-template.md`.
2. Create `FEATURE_DIR/test/task.md` by copying the template file, if it doesn't exist.
3. If `FEATURE_DIR/test/task.md` already exists, use `AskUserQuestion` to confirm overwrite:
    - "test/task.md already exists. Overwrite?" → Yes / No (append to existing file)
4. fill `FEATURE_DIR/test/task.md` with:**Keep the original structure and the original text, only fill in the values, do not delete any content.**
    - Correct feature name from plan.md
    - Phase 1: Env Deploy
    - Phase 2: Tests
    - Phase 3: report
    - Numbered tasks (T001, T002...) in execution order
    - Clear file paths for each task

### Step 7: Fill in Required Parameters

1. Check whether the `Input` section in `FEATURE_DIR/test/task.md` is missing required parameters and their corresponding values, such as `HOST*`, `PSM`, `BRANCH`, `ENV_NAME`, `SITE`, etc. **When the target platform is Frontend**, obtain Platform and Env (and any platform-specific env keys) per the **webe2e** workflow in **Skills (host compatibility)**—invoke when available **or** resolve `SKILL.md` for `webe2e` (`.claude/skills/`, `.cursor/skills/`, or plugin fallback) and follow its platform list / platform-detail sections.
2. If any are missing:
   - Use the host-compatible structured question tool per `User Interaction (host compatibility)` when the missing information can be collected through predefined options.
   - Use a normal chat message when the missing information requires arbitrary user input.
3. Populate the missing parameters into `FEATURE_DIR/test/task.md`.
4. **Skip this when the target platform is Frontend**: Check whether test data (Test Data) exists in `FEATURE_DIR/test/case.md`. If it does not exist, prompt the user to input test data and populate it into `FEATURE_DIR/test/case.md`. case.md must follow the language configuration in Language Setting.
5. task.md must follow the language configuration in Language Setting.

### Step 8: Report Generation Results

Display a summary of the generation results:

```text
## Generation Complete

- **Total test cases**: N
- **Target platform** (inferred): Backend | Frontend
- **Output file**: test/case.md
...
```

## Error Handling

| Scenario                          | Handling                                                                                                                     |
|-----------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| spec.md does not exist            | Prompt user to run `/adk:specify` first                                                                                      |
| spec.md has no User Story         | Display error "Unable to extract test scenarios"                                                                             |
| Feishu document export fails      | Warn and fall back to AI inference mode                                                                                      |
| Skill `SKILL.md` missing          | Tell user to ensure skills exist under `.claude/skills/` or `.cursor/skills/`, or use plugin fallback paths in **Skills (host compatibility)** |
| Skill not invocable as a tool     | Read resolved `SKILL.md` per **Skills (host compatibility)** — do not abort                                                 |
| Explicit `FEATURE_DIR` is invalid | Stop and ask the user to verify the provided feature path                                                                    |
| Multiple feature directories      | Use the host-compatible structured question tool to let user select                                                          |
| test/case.md already exists       | Use the host-compatible structured question tool to confirm overwrite or append                                              |

## Next Step Guidance

After executing this command:

### Step 1 - Confirmation

Review the generated `test/case.md` to verify test cases are correct and comprehensive.

**If needs adjustment**: Run `/adk:sdt:clarify [feedback]` to review and modify specific test cases.

### Step 2 - Next Step Recommendation

Once test cases are confirmed:

**Review and Clarify**: Execute `/adk:sdt:clarify` to interactively review test cases against actual code
implementation.
**Execute Tests**: Execute `/adk:sdt:implement` to run tests using the appropriate testing Skill.
