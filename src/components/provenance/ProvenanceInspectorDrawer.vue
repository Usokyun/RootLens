<script setup lang="ts">
import { computed } from "vue";
import type { ProvenanceInspectorState } from "@/services/provenance-inspector";
import SourceTrail from "./SourceTrail.vue";
const props = defineProps<{
  visible: boolean;
  state: ProvenanceInspectorState | null;
}>();
const emit = defineEmits<{ "update:visible": [value: boolean] }>();
const visibleModel = computed({
  get: () => props.visible,
  set: (value: boolean) => emit("update:visible", value),
});
</script>
<template>
  <a-drawer
    v-model:visible="visibleModel"
    :width="480"
    title="来源核验"
    :footer="false"
    ><h3>
      {{
        state?.targetKind === "build"
          ? "构图来源记录"
          : state?.targetKind === "build_edge"
            ? "当前构图关系"
            : "当前解释依据"
      }}
    </h3>
    <SourceTrail :state="state"
  /></a-drawer>
</template>
