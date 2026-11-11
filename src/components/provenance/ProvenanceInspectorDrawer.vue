<script setup lang="ts">
import { computed } from "vue";

import type {
  ProvenanceInspectorState,
  ProvenanceRecord,
  ProvenanceSourceType,
  ProvenanceTargetKind,
} from "@/services/provenance-inspector";

const props = defineProps<{
  visible: boolean;
  state: ProvenanceInspectorState | null;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
}>();

const visibleModel = computed({
  get() {
    return props.visible;
  },
  set(value: boolean) {
    emit("update:visible", value);
  },
});

function formatTargetKind(value: ProvenanceTargetKind | null | undefined) {
  switch (value) {
    case "path":
      return "路径";
    case "edge":
      return "边";
    case "entity_link":
      return "实体链接";
    case "correction":
      return "修正建议";
    case "build":
      return "构图批次";
    case "build_edge":
      return "构图边";
    default:
      return "--";
  }
}

function formatSourceType(value: ProvenanceSourceType) {
  switch (value) {
    case "raw_evidence_ref":
      return "原始证据引用";
    case "visual_evidence":
      return "可视证据";
    case "edge_provenance":
      return "边来源";
    case "entity_link":
      return "实体链接";
    case "correction":
      return "修正建议";
    case "edge_metadata":
      return "边元数据";
    case "manifest":
      return "构图清单";
    case "summary":
      return "构图摘要";
    case "qa_report":
      return "质检报告";
    case "review_queue":
      return "审阅队列";
    case "source_material":
      return "来源素材";
    default:
      return value;
  }
}

function formatScore(value: number | null | undefined) {
  return typeof value === "number" ? value.toFixed(3) : "--";
}

function resolveTagColor(tag: string) {
  switch (tag) {
    case "projected":
      return "gold";
    case "generated":
      return "purple";
    case "source-grounded":
      return "green";
    default:
      return "arcoblue";
  }
}


function formatTagLabel(tag: string) {
  switch (tag) {
    case "projected":
      return "投影";
    case "generated":
      return "生成产物";
    case "source-grounded":
      return "来源锚定";
    default:
      return tag;
  }
}

function shouldShowVisual(record: ProvenanceRecord) {
  return !!record.previewUrl && record.sourceType === "visual_evidence";
}
</script>

<template>
  <a-drawer
    v-model:visible="visibleModel"
    width="460px"
    title="溯源检查器"
    :footer="false"
  >
    <div class="workspace-provenance-drawer">
      <div
        v-if="state"
        class="workspace-summary-list workspace-summary-list--two-col"
      >
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">目标</span>
          <strong>{{ state.summary }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">类型</span>
          <strong>{{ formatTargetKind(state.targetKind) }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">上下文</span>
          <strong>{{ state.contextLabel }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">审阅目标</span>
          <strong>{{ state.linkedReviewTarget ?? "--" }}</strong>
        </div>
      </div>

      <div
        v-if="state"
        class="workspace-claim-note workspace-claim-note--compact"
      >
        <span class="workspace-summary-label">断言边界</span>
        <strong>{{ state.claimBoundary }}</strong>
      </div>

      <div
        v-if="state?.semanticNotes.length"
        class="workspace-provenance-note-list"
      >
        <div
          v-for="note in state.semanticNotes"
          :key="note"
          class="workspace-claim-note workspace-claim-note--compact workspace-provenance-note"
        >
          <span class="workspace-summary-label">语义说明</span>
          <strong>{{ note }}</strong>
        </div>
      </div>

      <section v-if="state" class="workspace-feedback-pane__section">
        <div
          class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
        >
          <strong>溯源记录</strong>
          <span>{{ state.records.length }} 项</span>
        </div>

        <div
          v-if="state.records.length"
          class="workspace-provenance-record-list"
        >
          <article
            v-for="record in state.records"
            :key="record.recordId"
            class="workspace-provenance-record"
          >
            <div class="workspace-provenance-record__head">
              <strong>{{ record.sourceLabel }}</strong>
              <div class="workspace-provenance-record__tags">
                <a-tag size="small">{{
                  formatSourceType(record.sourceType)
                }}</a-tag>
                <a-tag
                  v-for="tag in record.tags"
                  :key="`${record.recordId}:${tag}`"
                  size="small"
                  :color="resolveTagColor(tag)"
                >
                  {{ formatTagLabel(tag) }}
                </a-tag>
              </div>
            </div>

            <div class="workspace-provenance-record__meta">
              <span>{{ record.sourcePathOrId }}</span>
              <span v-if="record.reviewTargetKey"
                >审阅 {{ record.reviewTargetKey }}</span
              >
              <span>置信度 {{ formatScore(record.confidence) }}</span>
            </div>

            <div
              v-if="shouldShowVisual(record)"
              class="workspace-provenance-record__visual"
            >
              <img :src="record.previewUrl ?? ''" :alt="record.sourceLabel" />
            </div>

            <pre
              v-if="record.snippetOrPreview && record.multiline"
              class="workspace-provenance-record__snippet workspace-provenance-record__snippet--pre"
              >{{ record.snippetOrPreview }}</pre
            >
            <p
              v-else-if="record.snippetOrPreview"
              class="workspace-provenance-record__snippet"
            >
              {{ record.snippetOrPreview }}
            </p>
          </article>
        </div>
        <a-empty
          v-else
          description="当前目标没有可展示的溯源记录。"
        />
      </section>
      <a-empty v-else description="当前未选择溯源目标。" />
    </div>
  </a-drawer>
</template>
