# [Automated Test Suite] [Business Line] / [Module Name]

> 💡 **Template Usage Instructions**:
> This template is designed to centrally manage **multiple** test cases under the same business module, supporting a hybrid orchestration of [Single API Tests] and [Scenario-based Tests].
> When writing your test cases, please delete the explanatory text starting with `> ` and retain only the actual test case content.

## 1. Suite Setup (Basic Info & Global Configuration)

### 1.1 Suite Meta
| Attribute | Content | Description |
| :--- | :--- | :--- |
| **Test Scope** | e.g., Core Search and Checkout Module in the Transaction Link | Brief description of the business module covered by this suite. |
| **Requirement Traceability** | [PRD / Technical Design Link](#) | Link to the relevant product or technical documentation. |
| **Maintainer** | @Name | Owner of this test suite. |

### 1.2 Global Pre-conditions
> 📝 **Instruction**: Specify the foundational prerequisites for running the entire test suite. This includes environments, accounts, and base data shared across **all** test cases.

* **Environment**: `zone=boei18n`, `env=prod`
* **Global Accounts**: `test_user_001`, `test_user_002`
* **Global Data Dependencies**: The product database must contain published items with `inventory > 0`.

### 1.3 Global Context Variables
> 📝 **Instruction**: Declare variables that flow across multiple test cases or are universally used throughout the suite. **Do not** put local variables (used only in a single test case) here. **CRITICAL: Do NOT arbitrarily add Authentication Tokens or Keys here unless the specific service's auth mechanism is strictly confirmed.**

| Variable Name | Initial Value | Source / Update Node | Business Purpose |
| :--- | :--- | :--- | :--- |
| `{{GLOBAL_TENANT_ID}}` | `null` | Global pre-condition script | Example: Global tenant ID used by all test cases. |

### 1.4 Assertion Field Registry
> 📝 **Instruction**: This section is the **central field registry** for all non-status/business assertions across this test suite. Before writing test case assertions, complete the three tables below based on the PRD / Technical Design. These tables serve as the **single source of truth** — test case assertions should **reference** them rather than independently defining field expectations.
>
> **Why this matters**: Decoupling field definitions from test cases ensures: (a) traceability from assertion → requirement, (b) consistency across cases, (c) easier maintenance when requirements change.

#### 1.4.1 Scheme Change Fields (方案改动点字段)
> 📝 **Definition**: Fields that are **newly added, renamed, type-changed, or structurally modified** in the current requirement/iteration. These fields are the **primary validation targets** for regression — if they break, the requirement is not correctly delivered.
>
> **How to identify**: Review the PRD's change log, technical design's "API Diff" section, or diff the IDL/API schema against the previous version. Focus on fields marked as `NEW`, `MODIFIED`, or `DEPRECATED`.

| Field Path | Change Type | Expected Behavior | Requirement Source |
| :--- | :--- | :--- | :--- |
| `$.data.items[0].sku_id` | NEW | Must be present and non-null for all items | [PRD §2.1](#) |
| `$.data.items[0].promotion_tag` | MODIFIED | Changed from `string` to `enum{HOT,NEW,SALE}`; must not return legacy free-text values | [Tech Design §3.2](#) |
| `$.data.items[0].legacy_score` | DEPRECATED | Must be absent from response; use `$.data.items[0].rating_score` instead | [API Diff v2→v3](#) |

#### 1.4.2 Business Key Fields (业务关键字段)
> 📝 **Definition**: Fields that are **critical for business correctness** — if they are wrong, null, or inconsistent, the core business flow will fail or produce incorrect results (e.g., financial loss, order failure, data corruption). These fields may not have changed in the current iteration, but they must always be asserted.
>
> **How to identify**: Ask "If this field is wrong, does the business break?" Fields involving money, identity, state transitions, quantity, and permissions are typical candidates.

| Field Path | Business Domain | Expected Behavior | Failure Impact |
| :--- | :--- | :--- | :--- |
| `$.data.items[0].price` | Pricing | Must be > 0 and consistent with SKU base price (±promotion delta) | Incorrect charge / revenue loss |
| `$.data.items[0].currency` | Pricing | Must match the seller's locale currency code | Cross-currency settlement failure |
| `$.data.order_id` | Order | Must be present and unique for created orders | Order cannot be tracked or fulfilled |
| `$.data.items[0].seller_id` | Identity | Must match the item's actual seller | Wrong seller attribution / revenue misallocation |

#### 1.4.3 High-Volatility Fields (高波动字段)
> 📝 **Definition**: Fields whose values **frequently change** between requests or across time (e.g., stock counts, real-time rankings, timestamps, TTL-based tokens). These fields cannot be asserted with exact values — instead, use **boundary, type, or state-machine assertions**.
>
> **How to identify**: If a field's expected value depends on **when** or **how often** you query, it's high-volatility. Typical examples: inventory counts, rankings, expiring URLs, cache-driven aggregations.

| Field Path | Volatility Reason | Assertion Strategy | Example Assertion |
| :--- | :--- | :--- | :--- |
| `$.data.items[0].stock` | Real-time inventory deduction | Boundary + type check | `$.data.items[0].stock >= 0` (int) |
| `$.data.items[0].ranking_score` | Recency-weighted real-time ranking | Relative ordering (if multiple items) | `$.data.items[0].ranking_score >= $.data.items[1].ranking_score` |
| `$.data.server_timestamp` | System clock | Reasonable range check | `abs($.data.server_timestamp - now) < 5000ms` |
| `$.data.items[0].cover_url` | CDN rotation / signed URL | Type + format check | `$.data.items[0].cover_url matches "^https?://"` |

---

## 2. Test Cases

> 💡 **Instruction**: If there are multiple test cases, copy the entire `### [TC-XXX]` block below and increment the ID accordingly.

### [TC-001] [Test Case Name] API Name / Core Scenario Name
**1. Test Case Information**
* **Test Type**: Single API / Scenario *(Choose one)*
* **Priority**: P0 / P1 / P2 *(P0 for core blockers, P2 for edge/exception cases)*
* **Data Dependencies & Local Variables**:
  > 📝 **Data Dependency Rules**: Provide the dependent data strictly following these priorities:
  >   **a. Priority 1 (Knowledge Base)**: If the knowledge base provides the exact data or method, write it directly.
  >   **b. Priority 2 (Auto Datagen)**: Write a requirement prompt tagged with `[tt-nova-datagen]` (e.g., `[tt-nova-datagen] Please generate an active SKU`). The AI agent will automatically invoke the datagen skill in a later step and replace this line with the real data.
  >   **c. Priority 3 (Manual Prompt)**: (Only used as a fallback if Priority 2 fails during automation) Tagged as `[Manual Prompt] <requirement>`.
  * *Data Dependency*: `[tt-nova-datagen] Please generate an active product SKU with stock > 0 for test_user_001.` *(This will be auto-processed and replaced by the agent)*
  
  > 📝 **Local Variable Rules**: Variables extracted and used strictly within this test case. **If a variable needs to be shared across multiple cases, do not use a local variable; assign it directly to a `Global Context Variable` defined in Section 1.3.** If no local variables are used or the case has only one step , leave this empty.
  * *Local Variables*: `{{LOCAL_SKU_ID}}` (Scoped only to TC-001).

**2. Test Steps & Assertions**

**Step 1: [Action Description] (HTTP Request Example)**
* **API Contract**: `tiktok.ecommerce.item` -> `GET /api/v1/item/search` [(View API)](#)
* **Protocal**: HTTP
* **Request Parameters**:
  * **Headers**:
    > 📝 **Header Rules**: ONLY include authentication/authorization headers if you are absolutely certain of this specific service's auth mechanism. **If the auth parameter cannot be confirmed from the current service context, DO NOT arbitrarily invent or write them.**
    * `X-Device-Type`: `iOS`
    * *(Include actual known auth headers here ONLY if confirmed, otherwise omit)*
  * **Query**: `keyword: "apple"`, `page_size: 20`
* **Assertions**:
  > 📝 **Assertion Writing Rules**:
  > Every step **MUST** include `[Status]` and `[Business]` assertions as the baseline.
  > For the other three categories, **selectively include** the fields relevant to this step based on the [Assertion Field Registry (§1.4)](#14-assertion-field-registry):
  > - **[Scheme Change]**: Include fields from §1.4.1 that are touched by this step's API. Use the Expected Behavior from the registry as the assertion value.
  > - **[Business Key]**: Include fields from §1.4.2 that are critical to this step's business logic. Use the Expected Behavior from the registry.
  > - **[High-Volatility]**: Include fields from §1.4.3 that appear in this step's response. Apply the Assertion Strategy from the registry — **never use exact-value assertions** on these fields.
  >
  > **Format**: `[Category] <field_path> <operator> <expected_value> // <reason or registry reference>`

  * [Status] `StatusCode == 200`
  * [Business] `$.data.items.length > 0` *(Validation: Can correctly retrieve existing items)*
  * [Scheme Change] `$.data.items[0].sku_id IS NOT NULL` *(§1.4.1: NEW field — must exist)*
  * [Scheme Change] `$.data.items[0].promotion_tag IN ["HOT","NEW","SALE"]` *(§1.4.1: MODIFIED — enum constraint)*
  * [Scheme Change] `$.data.items[0].legacy_score IS ABSENT` *(§1.4.1: DEPRECATED — must not appear)*
  * [Business Key] `$.data.items[0].price > 0` *(§1.4.2: Pricing — prevents zero/negative charge)*
  * [Business Key] `$.data.items[0].currency == "USD"` *(§1.4.2: Pricing — locale currency match)*
  * [High-Volatility] `$.data.items[0].stock >= 0` *(§1.4.3: Boundary — non-negative inventory)*
  * [High-Volatility] `$.data.items[0].cover_url matches "^https?://"` *(§1.4.3: Format — valid URL)*
* **Variable Extraction**: *(Ignore if no extraction is needed)*
  * Extract `$.data.items[0].sku_id` and assign it to the local variable `{{LOCAL_SKU_ID}}`.
  * Extract `$.data.order_id` and assign it directly to the global variable `{{GLOBAL_ORDER_ID}}`.

**Step 2: [Action Description] (RPC Request Example)**
* **API Contract**: `tiktok.ecommerce.trade` -> `TradeService.CreateOrder` [(View IDL)](#)
* **Protocal**: RPC
* **Request Parameters**:
  * **Context**: 
    > 📝 **Context Rules**: Like HTTP Headers, ONLY include RPC auth context if the mechanism is confirmed. Do not invent context variables.
    * *(Include actual known RPC context here ONLY if confirmed, otherwise omit)*
  * **Message**:
    ```json
    {
      "user_id": "test_user_001",
      "items": [{"sku_id": "{{LOCAL_SKU_ID}}", "quantity": 1}],
      "pay_type": "CREDIT_CARD"
    }
    ```
* **Assertions**:
  * [Status] `$.BaseResp.StatusCode == 0`
  * [Business] `$.OrderInfo.OrderID IS NOT NULL`
  * [Scheme Change] `$.OrderInfo.OrderID IS NOT NULL` *(§1.4.1: NEW field — order ID now returned in response)*
  * [Business Key] `$.OrderInfo.TotalAmount == $.OrderInfo.ItemAmount + $.OrderInfo.ShippingFee` *(§1.4.2: Pricing — amount consistency)*
  * [High-Volatility] `$.OrderInfo.ExpireAt - now > 0` *(§1.4.3: Boundary — order not expired at creation)*
* **Variable Extraction**:
  * None

---

### [TC-002] [Test Case Name] Search Boundary Value Exception Test
*(Copy the TC-001 block and modify it for this exception case. For single API tests, retain only Step 1.)*

---
