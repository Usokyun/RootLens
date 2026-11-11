# RootLens 双闭环 API

所有创建操作走 Python 后端。目录读取不会隐式安装工作图、重算历史或调用模型。请求和状态使用下面的当前合同；旧运行、旧图包、旧 Evidence 和旧 Replay 路由不提供转换。

## 资料到工作图

- `/api/kg/materials` 列活动素材，`?archived=true` 列已移出；`/upload` 接收文件，`/register-url` 登记网址。详情、提取片段、提取历史和产物按素材 ID 读取。`POST /api/kg/materials/{material_id}/archive` 或 `/restore` 只改选材状态；正在使用的素材不允许移出（409）。
- `POST /api/tasks/material-parse`：`{"material_ids":["id"],"force":false}`。提取阶段实际读取并保留原文位置。
- `GET /api/authoring/capabilities` 返回三个场景的能力目录。`features[]` 包含 `feature_id/value_kind/unit/definition/requires_reference/allowed_values/semantic_role`；`allowed_values=null` 不是空枚举。`diagnostic` 是诊断量，`presence_gate`、`context` 不能代替具体证据。图像位置是图像网格，不是物体部位。
- `POST /api/tasks/material-build`：`{"material_ids":["id"],"dataset":"tep","title":"过程知识","capability_id":"process-window-v2","max_repairs":1}`。另两能力 ID 为 `visual-region-v2`、`spatial-grid-v2`。一次只选同场景及共享素材，文本模型最多生成加一次修复；实际调用和校验问题进入事件。可显式设 `candidate_limit`（视觉／过程上限 64，晶圆限声明的图案词汇）。默认新图未启用。

LLM 生成实体、作用、可观测条件与来源，不设置评分曲线或预算。后端为新图生成确定性的初始观测预算；通过完整包编辑 `observable_definitions[].grade`、`knowledge.graded_policy` 或 `value_bindings`。别名仅在匹配的特征和可选模型内归一，不修改原 Evidence 值；等价来源、单位、范围和所有引用由编译器校验。预设条件和假设可能仍需按资料调整。

## 工作图

- `GET /api/kg/working-graphs` 返回登记图；`GET /api/kg/studio?graph_id=…` 读取指定工作图的真实有向投影。
- `POST /api/kg/working-graphs/import` 接受 `rootlens-working-graph.v2` 完整包，创建新的待启用图。
- `GET`／`PUT /api/kg/working-graphs/{graph_id}/package` 交换该图的完整包。保存前备份；包的图 ID 不得指向另一张图。条件、绑定和预算随包一起保存，不从视图字段反构造。
- `POST /api/kg/working-graphs/{graph_id}/enable`：`{"enabled":true}` 启用，或传 `false` 停用。只使用已启用的就绪图创建任务。
- `GET /api/reasoners`：`{reasoners:[{reasoner_id,title,datasets,description,requires_graded_policy?}]}`。`graded_abduction` 是默认的三场景引擎，要求图有比较预算；`tep_rootkgd` 仅 TEP 可选。不自动换引擎。

## 原始输入到保存分析

`POST /api/tasks/inference` 接收 multipart：`file`、`graph_id`、`input_mode`、可选 `reasoner_id`、`dataset`、`title`、`top_k`。按所选模式补充：

| `input_mode` | 输入与配置 |
| --- | --- |
| `evidence` | 原生 `rootlens-evidence.v2` 单帧、数组或 `{frames:[…]}`。保留类型、单位、范围、正常参考与原始引用。 |
| `image` | 原图，按 `object_name` 和可选 `model_preset` 选择对应模型；`semantic_mode=disabled` 为默认。 |
| `process` | 52 通道序列和同序 `reference_file`，`windows` 如 `[[1,100],[161,260]]`（一基闭区间），`sampling_seconds` 默认 180。 |
| `wafer` | 0 背景／1 正常／2 失效的网格，单对象或 JSONL 批；原生类别不传分类器。 |

`GET /api/tasks?limit=50` 查看近况，`GET /api/tasks/{task_id}?after_sequence=0` 增量读取实际事件。状态为 `queued/running/completed/failed/interrupted`；未知比例时 `progress.indeterminate` 为真。任务完成返回 `material_ids`、`graph_id/build_id` 或 `run_id`。失败保留阶段和错误；仅在 `failed/interrupted` 可用 `POST /api/tasks/{task_id}/retry` 明确重提，不自动重放付费步骤。API 重启不会把未完成任务标成成功。

`GET /api/analyses` 返回摘要，`GET /api/analyses/{run_id}` 返回完整保存分析。`cases[]` 带 `evidence_frames`、同帧 `results`、`observation_locations` 与媒体状态，另保存 `working_graph_snapshot`。`GET /api/analyses/{run_id}/evidence` 下载该次 `{frames:[…]}`；`GET /api/analyses/{run_id}/artifacts/{name}` 读取受管附件。不访问 Frame 里的任意本地路径或 URL，未附媒体不阻止数值推理。

### 分级结果与实际贡献

`graded_joint_abduction_v1` 返回固定比较预算 `graded_comparison`、有支持／待核验的 `graded_candidates[]` 和实际选择的联合分支。每项 `graded_conditions[]` 保存实测值、`obs_id`、权重、支持／反证与带符号贡献。`scoring_details` 用 `support/conflict/score/coverage` 保存 P/C/S/V；`path_kind=graded_contribution` 附真实 `source_edges`、反向视图、正／反证观测和定位。`joint_proof_id` 为空，不从软证据合成布尔证明。仅有支持组进入 `ranked_root_causes`。

`graded_policy.groups[]` 为 `{group_id,weight,slots:[{slot_id,weight,predicate_ids}]}`，`anchor_predicate_ids[]` 引用判别条件。仅适用知识决定固定预算，缺测不改分母；同一实际测量或 `dependency_group` 不得跨两个预算重复使用。必要反证排除分支，`expected` 的实测不符扣分，`possible` 不出现不算反证。数值曲线声明 `direction`、阈值、正的 `support_width/conflict_width`、可选中性宽度、单位、依据和来源引用；方向和单位需与运算一致。每个合法分支用 `S = Σ w·p − Σ w·c`，另报覆盖，分组内同分保留。

`tep_rootkgd_propagation_v2` 使用完整 52 维残差贡献、实际图传播、余弦／贡献覆盖／传播熵；按 host 和通道合并重复逻辑期待，主／备选路径各自保留真实源边。RootKGD 与分级分数不能直接比较。`authoring_diagnostics` 来自本次图快照和实际评分输入，不拿后来编辑的图补历史。

## 唯一公开演示目录

- `GET /api/demo-library` 从 `backend/data/demo/graded_rca/manifest.json` 读取三组和样例。`sample_id` 为唯一键；`graph_ref` 只按完整知识匹配，返回就绪、待启用、未安装、歧义或不可用，不按日期和场景猜图。
- `GET /api/demo-library/assets/{asset_id}` 只下载白名单资产。可用性取决于实际文件；没有原料或模型时仍可用发布 Frame 复算。
- `POST /api/demo-library/{demo_id}/working-graph` 由用户显式发起。未安装则导入并启用，已匹配则启用或复用，返回就绪 `graph_id` 和动作。歧义明确拒绝，不改已有知识；目录读取本身不写入。
- `POST /api/demo-library/{demo_id}/materials` 登记该组公开来源资料，重复登记复用同一素材；不执行提取、构图或安装图。
- `POST /api/tasks/inference/demo`：`{"sample_id":"tep-d04-graded","graph_id":"...","reasoner_id":"graded_abduction","input_variant":"evidence","top_k":8}`。选中工作图须与样本同场景；默认 `evidence`，重新计算保存 Frame；显式 `raw` 用相同清单的原始样本及配套文件。需要附件的场景按精确 Frame ID 关联，缺失不从其它窗口／网格借用。

[演示手册](../../backend/docs/graded-rca-demo.md)提供三个可直接操作的场景与来源。Postgres 存素材、图登记和完整分析；Neo4j 存图投影。旧持久化数据没有被批量迁移、清空或重算。
