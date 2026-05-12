# 接口测试详情 (API Test Details)

## HTTP 接口示例

### 接口 1: [API 名称，例如：更新用户资料]
- **PSM**: `p.s.m`
- **Endpoint**: `[METHOD] /path/to/endpoint`
- **请求类型**: HTTP
- **变更点分析**: [简述此处代码/文档逻辑的改动点]

| 用例 ID | 测试场景 | 输入参数 (Request Headers/Body/Params) | 断言/预期结果 (Status & Response Assertions) | 优先级 |
| :--- | :--- | :--- | :--- | :--- |
| TC-G01-01 | [正向场景] | Headers: `{...}` / Body: `{...}` | 1. Status: `200`; 2. Biz Code: `response.code` == 0; 3. Check: `response.data.id` 存在; 4. Check: 数据库中字段 `x` 已更新 | P0 |
| TC-G01-02 | [异常场景] | Params: `id=-1` | 1. Status: `400`; 2. Biz Code: `response.code` == 对应错误码; 3. Check: `error_msg` 等于 "Invalid ID" | P1 |

---

## RPC 接口示例

> **注意**：RPC 接口无 HTTP 状态码概念，**禁止**使用 `status_code == 200` 断言。业务状态码必须通过 `jsonpath` 直接断言响应体中的字段（如 `$.BaseResp.StatusCode`）。

### 接口 2: [API 名称，例如：批量更新门店信息]
- **PSM**: `p.s.m`
- **Endpoint**: `[METHOD] /rpc/method`
- **请求类型**: RPC
- **变更点分析**: [简述此处代码/文档逻辑的改动点]

| 用例 ID | 测试场景 | 输入参数 (Request Headers/Body/Params) | 断言/预期结果 (Status & Response Assertions) | 优先级 |
| :--- | :--- | :--- | :--- | :--- |
| TC-G02-01 | [正向场景] | Body: `{...}` | 1. Biz Code: `jsonpath('$.BaseResp.StatusCode')` == 0; 2. Check: `jsonpath('$.data.id')` 存在 | P0 |
| TC-G02-02 | [异常场景] | Body: `{...}` | 1. Biz Code: `jsonpath('$.BaseResp.StatusCode')` == 对应错误码; 2. Check: `jsonpath('$.BaseResp.StatusMessage')` 包含错误描述 | P1 |
