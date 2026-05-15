---
name: prd2case-api
description: Generates text-based API test cases (case.md) from PRD and Spec documents. These cases serve as inputs for subsequent API automation testing.
user-invocable: true
---

## User Input

```text
$ARGUMENTS
```
**Instruction**: You **MUST** process the user input if it is not empty. If `$ARGUMENTS` contains a hyperlink, use the appropriate tool (e.g., `lark-docs` MCP for Lark documents) to read its content and replace the link with the extracted text before proceeding.


## Context

### Language Setting
Read `preferred_language` from `.ttadk/config.json` (default: `'en'`). If `.test_config.ini` `[prd2case]` section has a `language` value, it takes precedence.  
**All outputs** — documents, prompts, confirmations, status messages, errors — MUST use the resolved language (`en` → English, `zh` → 中文).

### Performance Rules (Mandatory)

| # | Rule | Anti-pattern |
|---|------|-------------|
| P1 | **Use `ls`/`test`/`cat` for known paths** — never Glob for deterministic paths like `idl/`, `.test_config.ini` | `Glob: specs/20260506-music-search-midpage/**/*` |
| P2 | **Strictly scoped IDL discovery** — Restrict IDL searches exclusively to the `idl/` (or `IDL/`) directory and its subfolders. API, protocol, and wrapper detection must complete in one consolidated search within this scope. | Repo-wide scanning for IDL files (must be avoided to prevent excessive folder permission prompts) |
| P3 | **Extract, don't read whole** — `grep -A <lines> "<pattern>" <file>` for large structured files (>500 lines) where only specific sections matter | Reading entire 1000+ line meta files |
| P4 | **Early feasibility check** — before invoking `tt-nova-datagen`, scan inventory; if unsupported → `[Manual Prompt]` immediately | "Try first, fail later" pattern |
| P5 | **Reuse generated data** — one `[tt-nova-datagen]` result applies to all matching scenarios; deduplicate before invocation | Generating the same dependency multiple times |
| P6 | **Defer optional reads** — skip PRD if spec.md already provides sufficient API-level context | Always reading PRD regardless |

---

## Workflow

### Phase 0: Bootstrap

Execute the following steps sequentially:

1. **Find repo root**: `REPO_ROOT="$(git rev-parse --show-toplevel)"`. On failure, abort with error.
2. **Read language config**: `cat "$REPO_ROOT/.ttadk/config.json"`. On failure, default to `en`.
3. **Read test config**: `test -f "$REPO_ROOT/.test_config.ini" && cat "$REPO_ROOT/.test_config.ini"`. If absent, skip (see below).
4. **Read spec.md**: Locate from `$ARGUMENTS` or `ls specs/`. On failure, abort — spec is mandatory.

**Config parsing** (`.test_config.ini`):
- If file exists and has `[prd2case]` section, extract: `language` (overrides `.ttadk`), `business_knowledge_path`.
- If `business_knowledge_path` is set: load it now (local file → `Read`, directory → `ls` + targeted reads, URL → appropriate fetch tool). Output: *"Querying business knowledge base from `{path}`..."*
- If file/section missing: output *"No `.test_config.ini` `[prd2case]` section found. Using defaults."* — continue without interruption.

> **Output**: Echo resolved config: *"Config: language={val}, business_knowledge_path={val|none}"*

---

### Phase 1: IDL Discovery & Confirmation

1. **IDL Path**: Check spec.md / plan.md / tasks.md for IDL path references. If not found:
    - **ONLY** check the `idl/` (or `IDL/`) directory listing from Phase 0 and its subdirectories.
    - **DO NOT** scan the entire repository for IDL files under any circumstances.
    - If no IDL is found strictly within the `idl/` folder, use the `bam-api` skill to get IDL or prompt the user directly.

2. **API Response Schema/Value**: Read spec.md and linked documents within it for API response schema or API response example value. Process linked documents: For each extracted link:
    - If it's a Lark document URL (contains larkoffice.com/docx/, larkoffice.com/wiki/, larkoffice.com/docs/): Use lark-docs-skill to read the document content.
    - If it's a local file path: Use Read tool to read the file.
    - **DO NOT** scan the entire repository for API response schema or value under any circumstances.

3. **Protocol Detection** (single pass): Analyze IDL files (within the restricted scope) and codebase to determine if the service uses **HTTP wrapping RPC**. For large meta files, use `grep -A <lines>` to extract only the relevant PSM section.

4. **User Confirmation** (single prompt, all questions combined):
   - If HTTP-wrapped RPC detected: ask *"HTTP or RPC interface for test cases?"*
   - Use `AskUserQuestion` tool to confirm IDL path and current Git branch
   - If `idl/` not found (and not resolved by `bam-api`): ask user to provide the exact path, branch, and interface type
   - **Proceed only after confirmation.**

---

### Phase 2: API Analysis & Test Design

#### 2A: Affected API Analysis
From collected documents and codebase, list for each affected API:
- **API Name**
- **PSM** (maintain `p.s.m` format; extract from spec or `grep` meta files)
- **Endpoint** (HTTP method + URI)
- **Logic Changes** (textual description)

#### 2B: User API Selection
After completing Phase 2A, present the list of affected APIs to the user for selection using the `AskUserQuestion` tool.

**Batch size limit**: `MAX_OPTIONS_PER_PROMPT = 5`. If the total number of APIs exceeds this limit, use **multi-round pagination** as described below.

**Single-round selection** (total APIs ≤ `MAX_OPTIONS_PER_PROMPT`):

1. **Build the options list**: Create one option per API from Phase 2A. Each option should display the API Name and Endpoint for clear identification (e.g., `SearchMusic - GET /api/v1/music/search`).
2. **Call `AskUserQuestion`** with:
   - **Question**: *"Which APIs do you want to generate test cases for? (Select all that apply)"* (or equivalent in the resolved language)
   - **Options**: The API list built above
   - **Allow multiple selections**: `true`
3. **Filter**: Only the APIs selected by the user will proceed to Phase 2C for test scenario design. All unselected APIs are excluded from further processing.
4. **If no APIs selected**: Abort with message *"No APIs selected. Test case generation cancelled."*
5. **If only one API affected**: Still prompt the user via `AskUserQuestion` for confirmation rather than skipping this step.

**Multi-round paginated selection** (total APIs > `MAX_OPTIONS_PER_PROMPT`):

When the API list exceeds the batch size limit, split APIs into sequential batches and conduct multiple rounds of `AskUserQuestion` calls. Follow the procedure:

1. **Initialize**: Set `remaining_apis` = full API list from Phase 2A. Set `selected_apis` = empty list. Set `batch_index` = 1.
2. **Loop** until `remaining_apis` is exhausted:
   a. **Extract batch**: Take the first `MAX_OPTIONS_PER_PROMPT` APIs from `remaining_apis` as the current batch.
   b. **Calculate pagination info**: `total_batches` = ceil(total_APIs / MAX_OPTIONS_PER_PROMPT), `current_batch` = batch_index.
   c. **Call `AskUserQuestion`** with:
      - **Question**: *"Which APIs do you want to generate test cases for? (Batch {current_batch}/{total_batches}, select all that apply)"* (or equivalent in the resolved language)
      - **Options**: The current batch's API list (one option per API, same format as single-round)
      - **Allow multiple selections**: `true`
   d. **Collect selections**: Append any user-selected APIs from this batch to `selected_apis`.
   e. **Advance**: Remove the current batch from `remaining_apis`. Increment `batch_index` by 1.
3. **After all batches complete**: Check `selected_apis`.
   - If `selected_apis` is empty → abort with *"No APIs selected. Test case generation cancelled."*
   - Otherwise → output *"Selected APIs for test case generation: {list of selected API names}"*
4. **Proceed** to Phase 2C with only `selected_apis`.

**Important constraints for multi-round selection**:
- **Do NOT skip batches**: Every batch must be presented to the user, even if they selected nothing in previous batches.
- **Preserve context**: In each batch's question, include the total batch count so the user knows progress (e.g., "Batch 2/3").
- **No deduplication across batches**: Each API appears in exactly one batch; selections are naturally disjoint.
- **If the user explicitly states** "select all remaining" or "skip remaining batches" during any round, honor that instruction: treat all APIs in remaining batches as selected or unselected accordingly, and terminate the loop early.

> **Output**: *"Selected APIs for test case generation: {list of selected API names}"*

#### 2C: Test Scenario Design
Design scenarios for **only the user-selected APIs** following these rules. **If Business Knowledge was loaded, strictly apply its domain rules, data constraints, and edge-case definitions.**

**Test Case Count (Spec-Referenced, Not Spec-Locked):**

1. **Primary reference**: If spec.md contains BE-XXX test points marked `API 自动化` for the selected API, use them as the primary reference. Each test point should inform at least one test case — but the model may add cases beyond the spec points when needed (e.g., for boundary values, error handling, or edge cases not explicitly listed in the spec).
2. **No spec test points**: If the spec has no API test points for the selected API, design test cases independently based on the API's parameters, logic changes from Phase 2A, and standard API testing patterns (positive + negative + boundary).
3. **Merge guideline**: If multiple test points share identical request parameters, they may be merged into one test case. List all covered BE-IDs in the header.
4. **Final count**: Determined by the model — spec test points are input, not a hard constraint. Default to covering all listed points plus reasonable negative/boundary cases.

**Coverage Rules:**

| Scenario Type | Rule |
|---------------|------|
| Positive | One test case per unique (API, parameter_combination) pair from spec test points. One sentence per scenario. |
| Negative | **Mandatory and fixed count**: For each selected API, generate exactly `N_required_params + 1` negative cases — one per missing required parameter + one for an invalid parameter value. Total negative cases per API = number of required parameters + 1. |
| Pagination APIs | MUST include positive + boundary scenarios for `limit`/`offset`; unconditional full-list queries alone are **prohibited** |
| Parameterless APIs | One basic positive scenario by default. Do NOT hallucinate contradictory assertions. If different data states needed → ask user first |

**Parameter Rules:**
- `GET` → Params/Query only (no Body, no `application/json`)
- `POST`/`PUT` → Body with appropriate headers
- JSON field names MUST match IDL exactly (respect `go.tag='json:"xxx"'`; no arbitrary case conversion)
- Values: extract from `specs/`; if unavailable, use explicit textual descriptions

**Assertion Rules (Two-Tier):**

| Tier | HTTP API | RPC API |
|------|----------|---------|
| Outer (Gateway) | `status_code == 200` | MUST NOT assert HTTP status codes |
| Inner (Business) | `jsonpath` assertion on business code | `jsonpath` assertion (e.g., `$.BaseResp.StatusCode == 0`) |

- Read `BaseResp` from `base.thrift` (or equivalent) to find status code field name and success value.
- `jsonpath` field names MUST match JSON serialization: use `go.tag='json:"xxx"'` value; if missing, Thrift retains original casing.
- Vague assertions like "matches expectations" are **prohibited**.

**Assertion Generation Principles:**

1. **Baseline assertions (Mandatory for all scenarios)**: Every test scenario MUST include:
   - `1` [Status] assertion (HTTP status code or RPC equivalent)
   - `1` [Business] assertion on the top-level business status field (e.g., `$.status_code == 0`)
   - These two are the only universally-applicable assertions.

2. **Conditional category coverage (Applicability-gated)**: For the three field categories (§1.4.1–§1.4.3), before writing assertions, determine whether each category is **applicable** to this scenario's test intent:
   - **Scheme Change Fields**: Applicable when the scenario tests a response that contains new/modified fields. Not applicable for negative scenarios (missing params, invalid values) where the response is an error.
   - **Business Key Fields**: Applicable for positive scenarios that return core business data. Not applicable for error-only responses where no business data is returned.
   - **High-Volatility Fields**: Applicable when the response includes optional/conditional fields (e.g., CDN URLs, real-time counters). Not applicable for minimal error responses.
   - For each category that IS applicable → generate at least `1` assertion from that category.
   - For each category that is NOT applicable → document the reason inline as a comment (e.g., `// 负面场景，无业务数据返回，Business Key 不适用`).

3. **No quantity cap** — beyond baseline + applicable categories, generate additional assertions for any fields that merit verification.

3. **Mandatory assertion coverage by field category**: For each scenario, assertions MUST be generated for the following three categories of fields. Identify these fields by cross-referencing the PRD/spec change descriptions, IDL definitions, and Business Knowledge (if loaded):

   | Field Category | Definition | Identification Method |
   |----------------|------------|----------------------|
   | **方案改动点字段** (Scheme Change Fields) | Fields directly affected or newly introduced by the current PRD/spec change. These are the primary targets of the test. | Cross-reference the "Logic Changes" from Phase 2A, spec.md change descriptions, and diff analysis. Any field that is newly added, modified in semantics, or has its value range/type changed belongs here. |
   | **业务关键字段** (Business Key Fields) | Fields that are critical to business correctness regardless of whether they are changed. Their correctness is fundamental to the API's purpose. | Fields used for core business logic, decision-making, or downstream consumption (e.g., IDs, status flags, calculation results, authorization results). Identified from IDL definitions, Business Knowledge, and the API's semantic role. |
   | **高波动字段** (High-Volatility Fields) | Optional fields that may or may not appear in every response. These fields are not mandatory in the response schema and their presence depends on specific conditions or data states. | Fields marked as optional in IDL (e.g., with `optional` keyword in Thrift/Protobuf), fields with conditional return logic, or fields only present when certain data conditions are met. |

4. **Assertion completeness check**: Before finalizing each scenario, verify that all three field categories are covered by at least one assertion. If a category has no representative assertion:
   - If the scenario truly cannot cover that category (e.g., a negative scenario may not meaningfully assert on scheme change fields), document the reason inline as a comment.
   - Otherwise, add the missing assertions immediately.

5. **Field Categorization Priority Rule (Mandatory — eliminates ambiguity)**:
   When a field matches multiple categories, apply this priority order:
   - **Priority 1**: If the field is NEW or MODIFIED in the current change → it is categorically a **Scheme Change Field**. Even if it is also business-critical.
   - **Priority 2**: If the field is critical for core business logic (ID, status, money, identity) → **Business Key Field**. Only if not already covered by Priority 1.
   - **Priority 3**: If the field is optional in the IDL or conditionally returned → **High-Volatility Field**.
   - A field can appear in the registry with **dual tags** (e.g., "Scheme Change + Business Key"), but in test case assertions, label it with its **highest-priority category** to avoid duplicate assertions for the same field.

6. **High-Volatility Fields Validation Rules**:
   - **Must-check fields** (Scheme Change Fields + Business Key Fields): MUST assert presence, type, and value for every response
   - **High-Volatility Fields**: 
     - **Conditional validation**: Only validate when the field is present in the response
     - If present → validate type and non-null value (do not validate specific value unless defined)
     - If absent → no assertion failure, continue silently
     - **Never** treat absence of high-volatility fields as an error

**Priority:**
- `P0`: Core/typical positive scenarios
- `P1`: Secondary scenarios / critical negative scenarios
- `P2`: General negative scenarios

---

### Phase 3: Generate case.md

1. **Copy template**: `cp resources/api_test_template.md <target_dir>/test/case.md`
2. **Populate** with Phase 2C results. **STRICT**: Maintain exact template structure — heading levels, bullet points, tables, assertion formats, `[tt-nova-datagen]` tags. No additions, deletions, or deviations.
3. **Self-check**: Validate format compliance before finalizing.

---

### Phase 4: Resolve Data Dependencies

1. **Parse** generated `case.md` for all `[tt-nova-datagen]` tags.
2. **Deduplicate** — group identical/shareable dependencies.
3. **Pre-check** — scan `tt-nova-datagen` inventory for each dependency type:
   - Supported → invoke `tt-nova-datagen` skill with prompt
   - Unsupported → replace tag with `[Manual Prompt]` immediately
4. **Update** `case.md`:
   - Success: replace `[tt-nova-datagen] ...` with actual generated data for **all** matching scenarios
   - Failure/unsupported: replace tag with `[Manual Prompt]`, keep prompt text

---

## Completion

Output: *"All tasks completed. Output: `<target_dir>/test/case.md`."*
