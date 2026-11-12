<script setup lang="ts">
import { computed, ref, onBeforeUnmount } from "vue";
import type { ProvenanceInspectorState } from "@/services/provenance-inspector";
import { readable, scoreText } from "@/services/presentation";
import type { KnowledgeSourceDetail } from "@/api/contracts";
import { getRootLensService } from "@/services/rootlens-service";
const props = defineProps<{ state: ProvenanceInspectorState | null }>();
function href(path: string) {
  return /^(https?:\/\/|\/demo-evidence\/)/.test(path) ? path : undefined;
}
const detailVisible = ref(false),
  busy = ref(false),
  error = ref(""),
  detail = ref<KnowledgeSourceDetail | null>(null);
let version = 0;
async function openSource(id: string) {
  const v = ++version;
  detailVisible.value = true;
  busy.value = true;
  error.value = "";
  detail.value = null;
  try {
    const result = await getRootLensService().getKnowledgeSource(id);
    if (v === version) detail.value = result;
  } catch (e) {
    if (v === version) error.value = e instanceof Error ? e.message : String(e);
  } finally {
    if (v === version) busy.value = false;
  }
}
onBeforeUnmount(() => {
  ++version;
});
const sourceTypes = new Set([
  "edge_provenance",
  "raw_evidence_ref",
  "source_material",
  "entity_link",
  "correction",
  "review_queue",
]);
const records = computed(() => {
  const seen = new Set<string>();
  return (props.state?.records ?? []).filter((r) => {
    if (!sourceTypes.has(r.sourceType)) return false;
    const key = `${r.sourcePathOrId}|${r.snippetOrPreview}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
});
const evidenceRecords = computed(() =>
  records.value.filter((r) =>
    ["raw_evidence_ref", "source_material"].includes(r.sourceType),
  ),
);
const knowledgeRecords = computed(() =>
  records.value.filter(
    (r) => !["raw_evidence_ref", "source_material"].includes(r.sourceType),
  ),
);
</script>
<template>
  <section class="source-trail">
    <div class="source-trail__group">
      <h4>
        <span class="trail-step">1</span
        >{{
          state?.targetKind.startsWith("build") ? "来源材料" : "观察从哪里来"
        }}
      </h4>
      <div
        v-for="record in evidenceRecords"
        :key="record.recordId"
        class="source-excerpt"
      >
        <strong>{{ readable(record.sourceLabel, "证据引用") }}</strong>
        <p
          v-if="
            record.snippetOrPreview &&
            !record.snippetOrPreview.startsWith('角色=')
          "
        >
          {{ record.snippetOrPreview }}
        </p>
        <a
          v-if="href(record.sourcePathOrId)"
          :href="href(record.sourcePathOrId)"
          target="_blank"
          rel="noopener noreferrer"
          class="source-link"
          >打开原始资源</a
        >
      </div>
      <p v-if="!evidenceRecords.length" class="source-missing">
        {{
          state?.targetKind.startsWith("build")
            ? "当前构图未绑定可定位的来源材料记录。"
            : "当前解释未提供可定位的原始观察引用。"
        }}
      </p>
    </div>
    <div class="source-trail__group">
      <h4><span class="trail-step">2</span>知识关系依据</h4>
      <div
        v-for="record in knowledgeRecords"
        :key="record.recordId"
        class="source-excerpt"
      >
        <strong>{{ readable(record.sourceLabel, "关系来源") }}</strong>
        <p v-if="record.snippetOrPreview">{{ record.snippetOrPreview }}</p>
        <p v-else class="source-missing">未提供支持片段</p>
        <div class="subtle break-anywhere">
          {{ readable(record.sourcePathOrId, "未记录出处") }}
        </div>
        <a-tag v-if="record.tags.includes('draft')" color="purple"
          >人工草稿 · 未发布</a-tag
        ><a-button
          v-if="
            ['edge_provenance', 'review_queue'].includes(record.sourceType) &&
            record.sourcePathOrId &&
            !record.tags.includes('draft')
          "
          type="text"
          size="small"
          @click="openSource(record.sourcePathOrId)"
          >查看原始出处</a-button
        >
        <div v-if="record.confidence !== null" class="subtle">
          关系置信度 {{ scoreText(record.confidence) }}
        </div>
      </div>
      <p v-if="!knowledgeRecords.length" class="source-missing">
        没有可核验的关系来源，仍需人工补充。
      </p>
    </div>
    <a-collapse v-if="state"
      ><a-collapse-item header="技术引用" item-key="raw"
        ><p class="subtle break-anywhere">目标 ID：{{ state.targetId }}</p>
        <div
          v-for="record in state.records"
          :key="record.recordId"
          class="source-technical"
        >
          <strong>{{ record.sourceType }}</strong>
          <p v-if="record.snippetOrPreview">{{ record.snippetOrPreview }}</p>
          <p class="break-anywhere">{{ record.sourcePathOrId }}</p>
        </div></a-collapse-item
      ></a-collapse
    >
    <a-modal
      v-model:visible="detailVisible"
      :title="detail?.title ?? '来源原文'"
      :footer="false"
      width="min(700px,94vw)"
      ><a-spin :loading="busy" class="block-spin"
        ><a-alert v-if="error" type="warning" :title="error" /><template
          v-if="detail"
          ><p class="subtle break-anywhere">
            {{ detail.location
            }}<span v-if="detail.line_start">
              · 第 {{ detail.line_start }}–{{ detail.line_end }} 行</span
            >
          </p>
          <blockquote v-if="detail.excerpt" class="source-document">
            {{ detail.excerpt }}
          </blockquote>
          <a-empty v-else description="未提供可读原文，仅保留来源登记" />
          <p class="subtle">{{ detail.notes }}</p></template
        ></a-spin
      ></a-modal
    >
  </section>
</template>
