# Demo 重构验收 · 2026-11-11

分支：`codex/demo-narrative-redesign`。依据论文 §4–5 与 `backend-integration-current.md`，
将入口收敛为证据浏览、关联分析、知识维护；不是浏览器推理系统或运行图自动发布工具。

## 已交付

- Arco Design Vue 统一壳层、可读名称、按需详情、响应式布局。
- 原图/区域/响应/叠加/放大与严格资源绑定；没有资源时明确提示。
- 候选对应路径、观察联动、关系来源文本与定位、对象明确的审阅和历史。
- 节点/关系新增、修改、停用，来源/理由必填、修改对比、撤销、保存/恢复、离开保护。
- Demo、Replay 与不同 Backend 地址/场景的草稿隔离；Replay 不误用同名 Demo 的图片或出处。
- 来源素材阅读和单对象关系策展；保留已有独立构图快照入口与请求过期保护。
- 本地打包 D3，不再要求访问外部 CDN 才能显示图谱。

## 实际执行的验证

| 项目 | 结果及范围 |
| --- | --- |
| 前端构建 | `npm run build` 通过，包含 TypeScript 检查。 |
| 前端单测 | **28 文件 / 140 项通过**；覆盖展示语义、绑定、编辑验证/恢复、并发上下文、回放隔离。 |
| 后端重点测试 | `test_demo_workspace.py`、`test_kg_studio_runtime.py`、`test_kg_construction_graph.py`：**33 passed**。 |
| 完整后端 pytest | **317 passed / 6 failed / 3 skipped**；失败 node IDs 与既有基线一致，不是全通过。 |
| 变更后端 lint | 对本次涉及的服务、脚本及测试执行 ruff：通过。 |
| 浏览器 | 独立浏览器上下文检查三页；原有浏览器页及 8000 API 不重启、不清数据。 |
| 响应式 | 1440 / 1200 / 768 / 390px 检查；修复窄屏侧栏和内容裁切，无页面横向溢出。 |
| 编辑闭环 | Demo 新增/修改/停用、预览/撤销/保存、刷新恢复、失败重试、离开保护；Replay 与 Demo 草稿分离。 |
| 重置 | 确认/取消均检查；重置 Demo 保留 Replay 草稿，不调用 Backend 写接口。 |
| 既有 Backend | 临时 8002 服务执行 GET：5 个运行、210 节点 / 602 关系、注册来源原文、草稿列表均 200；草稿总数仍为 0。 |
| 持久化写路径 | 隔离 JSONL 与模拟 PG 连接验证追加/回读；**没有为验收向既有 PG 保存图谱草稿**。 |

本机日志及截图在 Git 忽略的 `.rootlens-cache/demo-redesign/`，不随 clone 提供。

### 既有后端失败

```text
tests/test_service_api.py::test_case_index_includes_checked_in_and_real_output_cases
tests/test_service_api.py::test_case_detail_returns_analysis_for_real_outputs
tests/test_service_api.py::test_upload_run_prepares_visual_evidence_artifacts
tests/test_service_api.py::test_image_upload_mode_defaults_to_unknown_label_when_unspecified
tests/test_service_api.py::test_mvtec_model_preset_route_reports_available_default
tests/test_wafer_user_study_workflow.py::test_prepare_wafer_user_study_can_persist_a_wafer_run_with_testing_store
```

涉及已有真实产物/模型资产与用户研究测试存储路径假设，不在本次界面重构中改写测试以掩盖失败。

## 限制与安全

- 瓶体图是固定 seed 的合成资产；响应来自实际像素差分与平滑，不是训练模型输出。
  原始代码与 manifest 可核验；运行 `backend/.venv/bin/python backend/scripts/generate_demo_visuals.py` 可复现。
- 晶圆图片及原始过程序列未补造。Replay 当前不打包视觉资产和来源全文，缺失时不替用 Demo 内容。
- 来源查看只解析注册项与 `backend/docs/sources/` 内允许的文本；不代理任意 URL 或读取任意本地文件。
- Backend 当前来源与历史 run 的 KG 可能不同；界面说明历史分析未重算。运行图预览最多 2000 条边。
- 保存知识草稿不是发布。未验收真实工厂因果准确率、所有模型、真实构图发布或 Docker 栈。
- 构建仍有约 780kB 的 Arco 入口 chunk 警告；`npm audit` 报告现有依赖 **3 moderate / 7 high**，
  未在此任务中强制升级 Vue/Vite/Vitest 等依赖，新增 D3 不在该告警列表。
- 切分支前已有改动已保留，未提交/推送；未初始化、重建、清理既有数据库或来源备份。

## 本次新增 / 维护的前端测试

下表包含每个文件的完整用例数，不代表全部为新增用例。

| 测试文件 | 通过 / 总计 |
| --- | --- |
| `src/services/demo-reset.spec.ts` | 2 / 2 |
| `src/services/evidence-observation.spec.ts` | 9 / 9 |
| `src/services/graph-editor.spec.ts` | 8 / 8 |
| `src/services/graph-workspace.spec.ts` | 5 / 5 |
| `src/services/mock-backend.spec.ts` | 6 / 6 |
| `src/services/presentation.spec.ts` | 2 / 2 |
| `src/services/provenance-inspector.spec.ts` | 6 / 6 |
| `src/views/EvidenceManageView.spec.ts` | 10 / 10 |
| `src/views/GraphExploreView.spec.ts` | 4 / 4 |
| `src/components/graphs/ConstructionGraphPreview.spec.ts` | 5 / 5 |
| `src/components/knowledge/GraphEditor.spec.ts` | 3 / 3 |

完整逐文件记录位于本机 `.rootlens-cache/demo-redesign/test-generation-summary.json`。
