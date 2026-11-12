<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import type {
  KGConstructionBuildRecord,
  KGConstructionGraphPayload,
} from "@/api/contracts";
import type { UnifiedGraphEdge, UnifiedGraphNode } from "@/types/graph";
import KnowledgeForceGraph from "@/components/graphs/KnowledgeForceGraph.vue";
import { useAppPreferences } from "@/services/app-preferences";
import { getLocalSessionMeta } from "@/services/rootlens-data";
import { getRootLensService } from "@/services/rootlens-service";
import {
  buildConstructionGraphDataset,
  constructionGraphLocation,
} from "@/services/construction-graph";

const props = defineProps<{ buildId: string }>();
const router = useRouter();
const { preferences } = useAppPreferences();
const payload = ref<KGConstructionGraphPayload | null>(null);
const builds = ref<KGConstructionBuildRecord[]>([]);
const loading = ref(false);
const error = ref("");
const renderMessage = ref("正在准备构图快照…");
const showLabels = ref(false);
const search = ref("");
const selection = ref<
  | { type: "node"; item: UnifiedGraphNode }
  | { type: "edge"; item: UnifiedGraphEdge }
  | null
>(null);
const dataset = computed(() =>
  payload.value ? buildConstructionGraphDataset(payload.value) : null,
);
const buildName = computed(() => {
  const index = builds.value.findIndex((b) => b.run_id === props.buildId);
  return index >= 0
    ? `知识图谱 ${String(index + 1).padStart(2, "0")}`
    : "所选知识图谱";
});
const canReadBackend = computed(
  () =>
    preferences.value.dataSourceMode === "backend" &&
    getLocalSessionMeta()?.source !== "import",
);
let requestVersion = 0;

async function loadGraph() {
  const version = ++requestVersion;
  payload.value = null;
  selection.value = null;
  error.value = "";
  builds.value = [];
  loading.value = false;
  if (!canReadBackend.value) {
    error.value =
      "构图快照需要 Backend 模式。请先退出回放并切换到 Backend；不会用 Demo 或其他图谱替代。";
    return;
  }
  loading.value = true;
  try {
    const service = getRootLensService();
    const [graphResult, listResult] = await Promise.allSettled([
      service.getKGConstructionGraph(props.buildId),
      service.listKGConstructionBuilds(),
    ]);
    if (version !== requestVersion) return;
    if (graphResult.status === "rejected") throw graphResult.reason;
    payload.value = graphResult.value;
    if (listResult.status === "fulfilled")
      builds.value = listResult.value.builds;
  } catch (reason) {
    if (version === requestVersion)
      error.value = reason instanceof Error ? reason.message : String(reason);
  } finally {
    if (version === requestVersion) loading.value = false;
  }
}

function selectBuild(value: string) {
  void router.push(constructionGraphLocation(value));
}

onBeforeUnmount(() => {
  ++requestVersion;
});
watch(
  [
    () => props.buildId,
    () => preferences.value.dataSourceMode,
    () => preferences.value.apiBaseUrl,
  ],
  loadGraph,
  { immediate: true },
);
</script>

<template>
  <div class="rl-page rl-screen workspace-stack">
    <a-alert type="info" title="正在浏览构图快照（只读）">
      不发布到运行库、不触发分析。候选原因实体不是已验证根因。
    </a-alert>
    <a-alert v-if="error" type="error" :title="error" />
    <article class="rl-section-card">
      <header class="rl-section-card__header">
        <div>
          <h3 class="rl-section-card__title">{{ buildName }}</h3>
          <span class="workspace-subtle">只读构图快照</span>
        </div>
        <div class="rl-panel-actions">
          <a-tag color="green">{{ payload?.node_count ?? 0 }} 节点</a-tag>
          <a-tag color="gold">{{ payload?.edge_count ?? 0 }} 边</a-tag>
          <a-button :loading="loading" @click="loadGraph">刷新快照</a-button>
          <a-button @click="router.push({ name: 'materials' })"
            >返回知识维护</a-button
          >
          <a-button @click="router.push({ name: 'graphs' })"
            >返回运行图谱</a-button
          >
        </div>
      </header>
      <div class="rl-section-card__body workspace-stack">
        <div class="snapshot-controls">
          <label for="construction-graph-select">选择已生成图谱</label>
          <a-select
            id="construction-graph-select"
            aria-label="选择已生成图谱"
            :model-value="buildId"
            :disabled="loading || !canReadBackend"
            :options="
              builds.map((build, index) => ({
                value: build.run_id,
                label: `知识图谱 ${String(index + 1).padStart(2, '0')}`,
              }))
            "
            @change="selectBuild"
          />
          <a-input
            v-model="search"
            aria-label="搜索快照节点"
            placeholder="搜索节点名称"
            allow-clear
          />
          <a-checkbox v-model="showLabels">显示节点名称</a-checkbox>
        </div>
        <a-alert
          v-if="payload?.truncated"
          type="warning"
          :title="`图谱较大，当前展示 ${dataset?.nodes.length ?? 0} 个节点、${dataset?.edges.length ?? 0} 条边；顶部为完整规模。`"
        />
        <div class="snapshot-graph-stage" :aria-busy="loading">
          <KnowledgeForceGraph
            v-if="dataset"
            :key="dataset.id"
            :dataset="dataset"
            :show-labels="showLabels"
            :search-term="search"
            :selected-node-id="
              selection?.type === 'node' ? selection.item.id : null
            "
            :selected-edge-id="
              selection?.type === 'edge' ? selection.item.id : null
            "
            @select="selection = $event"
            @render-state="renderMessage = $event.message"
          />
          <a-empty v-else>{{
            loading ? "正在读取图谱快照…" : "暂无可展示的图谱快照"
          }}</a-empty>
        </div>
      </div>
      <footer class="rl-section-card__footer">
        <span class="workspace-subtle">{{
          payload ? renderMessage : "未加载快照；不会自动替换为运行图谱。"
        }}</span>
      </footer>
    </article>
    <article class="rl-section-card">
      <header class="rl-section-card__header">
        <h3 class="rl-section-card__title">节点 / 关系详情</h3>
        <a-tag>只读 · 保留来源与审阅状态</a-tag>
      </header>
      <div class="rl-section-card__body">
        <template v-if="selection?.type === 'node'">
          <h4>{{ selection.item.name }}</h4>
          <p>
            类型：{{ selection.item.kind }} · 场景：{{
              selection.item.category
            }}
          </p>
          <p>{{ selection.item.description || "暂无节点说明" }}</p>
        </template>
        <template v-else-if="selection?.type === 'edge'">
          <h4>
            {{ selection.item.source }} → {{ selection.item.relation }} →
            {{ selection.item.target }}
          </h4>
          <p>
            来源：{{ selection.item.attributes.source }} · 置信度：{{
              selection.item.confidence
            }}
            · 审阅状态：{{ selection.item.attributes.review_status }}
          </p>
          <p>{{ selection.item.attributes.evidence || "暂无关系证据说明" }}</p>
          <p class="workspace-subtle">稳定关系 ID：{{ selection.item.id }}</p>
        </template>
        <p v-else class="workspace-subtle">
          点击图中的节点或关系，查看实体说明、来源、证据与置信度。
        </p>
      </div>
    </article>
  </div>
</template>

<style scoped>
.snapshot-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.snapshot-controls :deep(.arco-select) {
  width: min(100%, 340px);
}
.snapshot-controls :deep(.arco-input-wrapper) {
  width: min(100%, 220px);
}
.snapshot-graph-stage {
  height: clamp(520px, 62vh, 720px);
  min-width: 0;
}
</style>
