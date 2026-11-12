<script setup lang="ts">
import { Modal } from "@arco-design/web-vue";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import type {
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from "@/types/graph";
import type { KGDraftRecord } from "@/api/contracts";
import { getRootLensService } from "@/services/rootlens-service";
import { useAppPreferences } from "@/services/app-preferences";
import { getLocalSessionMeta } from "@/services/rootlens-data";
import {
  applyGraphPatch,
  emptyGraphPatch,
  graphPatchRequest,
  latestGraphPatch,
  stageGraphEdit,
  validateGraphEdit,
  type GraphEdit,
  type GraphPatch,
} from "@/services/graph-editor";
import { readable, shortDate } from "@/services/presentation";

const props = defineProps<{
  dataset: UnifiedGraphDataset;
  selectedNodeId?: string | null;
  selectedEdgeId?: string | null;
}>();
const emit = defineEmits<{
  patch: [value: GraphPatch];
  dirty: [value: boolean];
}>();
const { preferences } = useAppPreferences();
const scope = computed(
  () =>
    `${getLocalSessionMeta()?.source === "import" ? `replay:${getLocalSessionMeta()?.updatedAt}` : preferences.value.dataSourceMode === "mock" ? "demo" : `backend:${preferences.value.apiBaseUrl}`}|${props.dataset.id}`,
);
const patch = ref<GraphPatch>(emptyGraphPatch(scope.value));
const saved = ref("");
const history = ref<GraphPatch[]>([]);
const records = ref<KGDraftRecord[]>([]);
const busy = ref(false);
const error = ref("");
const notice = ref("");
const loaded = ref(false);
let version = 0;
const visibleGraph = computed(() =>
  applyGraphPatch(props.dataset, patch.value),
);
const selectedNode = computed(() =>
  visibleGraph.value.nodes.find((n) => n.id === props.selectedNodeId),
);
const selectedEdge = computed(() =>
  visibleGraph.value.edges.find((e) => e.id === props.selectedEdgeId),
);
const form = reactive({
  kind: "node" as "node" | "edge",
  id: "",
  name: "",
  type: "Concept",
  description: "",
  aliases: "",
  head: "",
  tail: "",
  relation: "RELATED_TO",
  confidence: 0.5,
  source: "",
  evidence: "",
  note: "",
});
const formBaseline = ref(JSON.stringify(form));
const formDirty = computed(() => JSON.stringify(form) !== formBaseline.value);
const patchDirty = computed(
  () => loaded.value && JSON.stringify(patch.value) !== saved.value,
);
const dirty = computed(() => patchDirty.value || formDirty.value);
async function confirmFormChange(): Promise<boolean> {
  if (!formDirty.value) return true;
  return new Promise((resolve) =>
    Modal.confirm({
      title: "放弃表单修改？",
      content: "当前表单尚未预览，切换对象将放弃这些输入。已预览变更不受影响。",
      okText: "放弃输入",
      cancelText: "继续编辑",
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    }),
  );
}
const isReplay = computed(() => getLocalSessionMeta()?.source === "import");
const isBackend = computed(
  () =>
    preferences.value.dataSourceMode === "backend" &&
    getLocalSessionMeta()?.source !== "import",
);

function fillSelection() {
  const node = selectedNode.value,
    edge = selectedEdge.value;
  notice.value = "";
  error.value = "";
  Object.assign(form, {
    kind: "node",
    id: "",
    name: "",
    type: "Concept",
    description: "",
    aliases: "",
    head: "",
    tail: "",
    relation: "RELATED_TO",
    confidence: 0.5,
    source: "",
    evidence: "",
    note: "",
  });
  if (edge)
    Object.assign(form, {
      kind: "edge",
      id: edge.id,
      head: edge.source,
      tail: edge.target,
      relation: edge.relation,
      confidence: edge.confidence ?? 0.5,
      source: String(edge.attributes.source ?? ""),
      evidence: String(edge.attributes.evidence ?? ""),
      note: "",
    });
  else if (node)
    Object.assign(form, {
      kind: "node",
      id: node.id,
      name: node.name,
      type: node.kind,
      description: node.description,
      aliases: node.aliases.join(", "),
      source: String(node.attributes.draft_source ?? ""),
      evidence: String(node.attributes.draft_evidence ?? ""),
      note: "",
    });
  formBaseline.value = JSON.stringify(form);
}
async function create(kind: "node" | "edge") {
  if (!(await confirmFormChange())) return;
  Object.assign(form, {
    kind,
    id: "",
    name: "",
    type: "Concept",
    description: "",
    aliases: "",
    head: visibleGraph.value.nodes[0]?.id ?? "",
    tail: visibleGraph.value.nodes[1]?.id ?? "",
    relation: "RELATED_TO",
    confidence: 0.5,
    source: "",
    evidence: "",
    note: "",
  });
  error.value = "";
  notice.value = "";
  formBaseline.value = JSON.stringify(form);
}
function stage(operation: "upsert" | "disable" = "upsert") {
  try {
    if (!loaded.value) throw new Error("请先成功读取已有草稿。");
    const id = form.id || `draft:${form.kind}:${crypto.randomUUID()}`;
    const existing =
      (form.kind === "node"
        ? visibleGraph.value.nodes
        : visibleGraph.value.edges
      ).find((i) => i.id === id) ?? null;
    const origin = existing?.origin ?? {
      projectId: props.dataset.id,
      projectLabel: "人工草稿",
      filePath: form.source,
      layer: "draft",
      rowNumber: 0,
    };
    const after =
      operation === "disable"
        ? null
        : form.kind === "node"
          ? ({
              id,
              name: form.name.trim(),
              category: "draft",
              kind: form.type.trim(),
              description: form.description,
              aliases: form.aliases
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
              degree: 0,
              inDegree: 0,
              outDegree: 0,
              attributes: { ...existing?.attributes },
              origin,
            } as UnifiedGraphNode)
          : ({
              id,
              source: form.head,
              target: form.tail,
              relation: form.relation.trim(),
              label: form.relation.trim(),
              category: "draft",
              confidence: form.confidence,
              weight: 1 - form.confidence,
              directed: true,
              attributes: {
                ...existing?.attributes,
                source: form.source,
                evidence: form.evidence,
              },
              origin,
            } as UnifiedGraphEdge);
    const edit: GraphEdit = {
      kind: form.kind,
      operation,
      id,
      before: existing,
      after,
      source: form.source,
      evidence: form.evidence,
      note: form.note,
    };
    validateGraphEdit(edit, visibleGraph.value);
    history.value.push(JSON.parse(JSON.stringify(patch.value)));
    patch.value = stageGraphEdit(patch.value, edit);
    emit("patch", patch.value);
    form.id = id;
    formBaseline.value = JSON.stringify(form);
    notice.value = "已更新草稿预览，尚未保存。";
    error.value = "";
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
}
function undo() {
  const last = history.value.pop();
  if (last) {
    patch.value = last;
    emit("patch", last);
    notice.value = "已撤销上一步。";
  }
}
async function load() {
  const v = ++version;
  formBaseline.value = JSON.stringify(form);
  records.value = [];
  loaded.value = false;
  busy.value = true;
  error.value = "";
  history.value = [];
  patch.value = emptyGraphPatch(scope.value);
  emit("patch", patch.value);
  try {
    const result = await getRootLensService().listKGDrafts({
      target_type: "graph_workspace",
      target_key: `editor:${scope.value}`,
      source: "rootlens-editor",
      limit: 500,
    });
    if (v !== version) return;
    records.value = result.records;
    patch.value = latestGraphPatch(result.records, scope.value);
    saved.value = JSON.stringify(patch.value);
    loaded.value = true;
    emit("patch", patch.value);
    fillSelection();
  } catch (e) {
    if (v === version)
      error.value = `草稿读取失败：${e instanceof Error ? e.message : String(e)}`;
  } finally {
    if (v === version) busy.value = false;
  }
}
async function save() {
  if (busy.value || !loaded.value || !patchDirty.value || formDirty.value)
    return;
  const v = version;
  const snapshot = JSON.parse(JSON.stringify(patch.value)) as GraphPatch;
  busy.value = true;
  error.value = "";
  try {
    await getRootLensService().submitKGDraft(
      graphPatchRequest(props.dataset, snapshot),
    );
    if (v !== version) return;
    saved.value = JSON.stringify(snapshot);
    history.value = [];
    notice.value = isBackend.value
      ? "已保存后端草稿；未修改运行图谱。"
      : isReplay.value
        ? "已保存回放草稿；未写入后端。"
        : "已保存演示草稿；未执行推理。";
    const result = await getRootLensService().listKGDrafts({
      target_type: "graph_workspace",
      target_key: `editor:${scope.value}`,
      source: "rootlens-editor",
      limit: 500,
    });
    if (v === version) records.value = result.records;
  } catch (e) {
    if (v === version) error.value = e instanceof Error ? e.message : String(e);
  } finally {
    if (v === version) busy.value = false;
  }
}
function discard() {
  patch.value = JSON.parse(
    saved.value || JSON.stringify(emptyGraphPatch(scope.value)),
  ) as GraphPatch;
  history.value = [];
  emit("patch", patch.value);
  fillSelection();
  formBaseline.value = JSON.stringify(form);
  notice.value = "已恢复到已保存版本。";
}
function changedFields(change: GraphEdit) {
  const keys =
    change.kind === "node"
      ? ["name", "kind", "description", "aliases"]
      : ["source", "relation", "target", "confidence"];
  const before = change.before as unknown as Record<string, unknown> | null;
  const after = change.after as unknown as Record<string, unknown> | null;
  return keys
    .filter((k) => JSON.stringify(before?.[k]) !== JSON.stringify(after?.[k]))
    .map((k) => ({
      key: (
        {
          name: "名称",
          kind: "类型",
          description: "说明",
          aliases: "别名",
          source: "起点",
          relation: "关系",
          target: "终点",
          confidence: "置信度",
        } as Record<string, string>
      )[k],
      before: String(before?.[k] ?? "—"),
      after: String(after?.[k] ?? "—"),
    }));
}
function label(change: GraphEdit, after: boolean) {
  const item = after ? change.after : change.before;
  return item
    ? readable("name" in item ? item.name : item.relation)
    : after
      ? "停用"
      : "新增";
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault();
    event.returnValue = "";
  }
}
defineExpose({ discard, confirmFormChange });
watch(dirty, (value) => emit("dirty", value), { immediate: true });
watch(scope, load, { immediate: true });
watch([() => props.selectedNodeId, () => props.selectedEdgeId], fillSelection);
window.addEventListener("beforeunload", beforeUnload);
window.addEventListener(
  "rootlens:before-workspace-change",
  beforeUnload as EventListener,
);
onBeforeUnmount(() => {
  ++version;
  window.removeEventListener("beforeunload", beforeUnload);
  window.removeEventListener(
    "rootlens:before-workspace-change",
    beforeUnload as EventListener,
  );
});
</script>
<template>
  <div class="graph-editor">
    <div class="editor-context">
      <a-tag color="purple">草稿工作区</a-tag
      ><span class="subtle"
        >{{
          isBackend ? "后端保存" : isReplay ? "回放本地保存" : "浏览器演示保存"
        }}
        · 不发布运行图谱</span
      >
    </div>
    <a-alert v-if="error" type="error" :title="error" class="page-alert"
      ><template v-if="!loaded" #action
        ><a-button @click="load">重试</a-button></template
      ></a-alert
    >
    <a-alert v-if="notice" type="success" :title="notice" class="page-alert" />
    <a-space class="editor-create"
      ><a-button :disabled="busy" @click="create('node')">新增节点</a-button
      ><a-button :disabled="busy" @click="create('edge')"
        >新增关系</a-button
      ></a-space
    >
    <a-form :model="form" layout="vertical" :disabled="busy || !loaded">
      <h4>
        {{ form.id ? "编辑" : "新增"
        }}{{ form.kind === "node" ? "节点" : "关系" }}
      </h4>
      <template v-if="form.kind === 'node'">
        <a-form-item label="名称" required
          ><a-input
            v-model="form.name"
            v-control-label="'节点名称'"
            aria-label="节点名称"
        /></a-form-item>
        <a-form-item label="实体类型" required
          ><a-input
            v-model="form.type"
            v-control-label="'实体类型'"
            aria-label="实体类型"
        /></a-form-item>
        <a-form-item label="别名"
          ><a-input
            v-model="form.aliases"
            v-control-label="'节点别名'"
            aria-label="节点别名"
            placeholder="多个别名以英文逗号分隔"
        /></a-form-item>
        <a-form-item label="说明"
          ><a-textarea
            v-model="form.description"
            v-control-label="'节点说明'"
            aria-label="节点说明"
            :auto-size="{ minRows: 2, maxRows: 4 }"
        /></a-form-item>
      </template>
      <template v-else>
        <a-form-item label="起点" required
          ><div v-control-label="'关系起点'" class="labeled-control">
            <a-select v-model="form.head" aria-label="关系起点" show-search
              ><a-option
                v-for="node in visibleGraph.nodes"
                :key="node.id"
                :value="node.id"
                :label="readable(node.name)"
            /></a-select></div
        ></a-form-item>
        <a-form-item label="关系" required
          ><a-input
            v-model="form.relation"
            v-control-label="'关系类型'"
            aria-label="关系类型"
            placeholder="例如 RELATED_TO"
        /></a-form-item>
        <a-form-item label="终点" required
          ><div v-control-label="'关系终点'" class="labeled-control">
            <a-select v-model="form.tail" aria-label="关系终点" show-search
              ><a-option
                v-for="node in visibleGraph.nodes"
                :key="node.id"
                :value="node.id"
                :label="readable(node.name)"
            /></a-select></div
        ></a-form-item>
        <a-form-item label="置信度" required
          ><a-input-number
            v-model="form.confidence"
            v-control-label="'关系置信度'"
            aria-label="关系置信度"
            :min="0"
            :max="1"
            :step="0.05"
        /></a-form-item>
      </template>
      <a-divider />
      <a-form-item label="来源定位" required
        ><a-input
          v-model="form.source"
          v-control-label="'编辑来源'"
          aria-label="编辑来源"
          placeholder="文档名及页码、记录位置或人工观察编号"
      /></a-form-item>
      <a-form-item label="支持内容" required
        ><a-textarea
          v-model="form.evidence"
          v-control-label="'支持内容'"
          aria-label="支持内容"
          placeholder="原文片段或人工观察；不把猜测写成已验证事实"
      /></a-form-item>
      <a-form-item label="修改理由" required
        ><a-textarea
          v-model="form.note"
          v-control-label="'修改理由'"
          aria-label="修改理由"
      /></a-form-item>
      <a-space
        ><a-button type="primary" @click="stage('upsert')">预览修改</a-button
        ><a-popconfirm
          v-if="form.id"
          content="仅在草稿中停用；节点关联关系将一并隐藏。"
          @ok="stage('disable')"
          ><a-button status="danger">停用</a-button></a-popconfirm
        ></a-space
      >
    </a-form>
    <a-divider />
    <div class="surface-heading editor-changes-heading">
      <h3>变更对比</h3>
      <a-tag>{{ patch.changes.length }}</a-tag>
    </div>
    <div
      v-for="change in patch.changes"
      :key="`${change.kind}:${change.id}`"
      class="change-row"
    >
      <strong>{{ label(change, false) }} → {{ label(change, true) }}</strong>
      <p
        v-for="field in changedFields(change)"
        :key="field.key"
        class="change-field"
      >
        <span>{{ field.key }}</span
        ><del>{{ readable(field.before) }}</del
        ><span>→</span><ins>{{ readable(field.after) }}</ins>
      </p>
      <p>{{ change.note }}</p>
      <span class="subtle">来源：{{ change.source }}</span>
    </div>
    <p v-if="!patch.changes.length" class="subtle">
      暂无变更。选择图中的节点或关系，或新增知识。
    </p>
    <p v-if="formDirty" class="subtle">表单已修改，请先预览，再保存草稿。</p>
    <div class="editor-save">
      <a-button
        type="primary"
        :disabled="!patchDirty || formDirty || !loaded"
        :loading="busy"
        @click="save"
        >保存草稿</a-button
      ><a-button :disabled="!history.length || busy" @click="undo"
        >撤销一步</a-button
      ><a-button :disabled="!dirty || busy" @click="discard"
        >放弃未保存</a-button
      >
    </div>
    <a-collapse
      ><a-collapse-item
        :header="`已保存版本（${records.length}）`"
        item-key="history"
        ><div v-for="r in records" :key="r.draft_id" class="change-row">
          <strong>{{ shortDate(r.recorded_at ?? r.created_at) }}</strong>
          <p class="subtle">
            {{
              (r.metadata.editor_patch as GraphPatch | undefined)?.changes
                .length ?? 0
            }}
            项草稿变更 · 未发布
          </p>
        </div></a-collapse-item
      ></a-collapse
    >
  </div>
</template>
