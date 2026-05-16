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
      return "Path";
    case "edge":
      return "Edge";
    case "entity_link":
      return "Entity Link";
    case "build":
      return "Build";
    case "build_edge":
      return "Build Edge";
    default:
      return "--";
  }
}

function formatSourceType(value: ProvenanceSourceType) {
  switch (value) {
    case "raw_evidence_ref":
      return "Raw ref";
    case "visual_evidence":
      return "Visual evidence";
    case "edge_provenance":
      return "Edge provenance";
    case "entity_link":
      return "Entity link";
    case "edge_metadata":
      return "Edge metadata";
    case "manifest":
      return "Manifest";
    case "summary":
      return "Summary";
    case "qa_report":
      return "QA report";
    case "review_queue":
      return "Review queue";
    case "source_material":
      return "Source material";
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

function shouldShowVisual(record: ProvenanceRecord) {
  return !!record.previewUrl && record.sourceType === "visual_evidence";
}
</script>

<template>
  <a-drawer
    v-model:visible="visibleModel"
    width="460px"
    title="Provenance Inspector"
    :footer="false"
  >
    <div class="workspace-provenance-drawer">
      <div
        v-if="state"
        class="workspace-summary-list workspace-summary-list--two-col"
      >
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">Target</span>
          <strong>{{ state.summary }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">Type</span>
          <strong>{{ formatTargetKind(state.targetKind) }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">Context</span>
          <strong>{{ state.contextLabel }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">Review target</span>
          <strong>{{ state.linkedReviewTarget ?? "--" }}</strong>
        </div>
      </div>

      <div
        v-if="state"
        class="workspace-claim-note workspace-claim-note--compact"
      >
        <span class="workspace-summary-label">Claim boundary</span>
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
          <span class="workspace-summary-label">Semantic note</span>
          <strong>{{ note }}</strong>
        </div>
      </div>

      <section v-if="state" class="workspace-feedback-pane__section">
        <div
          class="workspace-feedback-pane__section-head workspace-feedback-pane__section-head--compact"
        >
          <strong>Provenance records</strong>
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
                  {{ tag }}
                </a-tag>
              </div>
            </div>

            <div class="workspace-provenance-record__meta">
              <span>{{ record.sourcePathOrId }}</span>
              <span v-if="record.reviewTargetKey"
                >review {{ record.reviewTargetKey }}</span
              >
              <span>confidence {{ formatScore(record.confidence) }}</span>
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
          description="当前 target 没有可展示的 provenance records。"
        />
      </section>
      <a-empty v-else description="当前未选择 provenance target。" />
    </div>
  </a-drawer>
</template>
