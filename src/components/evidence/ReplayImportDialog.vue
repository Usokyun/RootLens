<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { buildLocalImportResult } from '@/services/browser-runtime'
import { saveImportedSession } from '@/services/rootlens-data'
import { restoreSessionImportFile } from '@/services/session-export'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [value: boolean]; imported: [message: string] }>()
const replayImportLoading = ref(false)
const errorMessage = ref('')
const formKey = ref(0)
const replayRuntimeInputRef = ref<HTMLInputElement | null>(null)
const replayGraphsInputRef = ref<HTMLInputElement | null>(null)
const replayWorkspaceInputRef = ref<HTMLInputElement | null>(null)
const replayImportForm = reactive({
  runtimeFile: null as File | null,
  graphsFile: null as File | null,
  workspaceFile: null as File | null,
})

watch(() => props.visible, visible => {
  if (!visible) return
  replayImportForm.runtimeFile = null
  replayImportForm.graphsFile = null
  replayImportForm.workspaceFile = null
  errorMessage.value = ''
  formKey.value += 1
})

function handleReplayFileChange(kind: keyof typeof replayImportForm, event: Event) {
  replayImportForm[kind] = (event.target as HTMLInputElement | null)?.files?.[0] ?? null
}
function openReplayFilePicker(kind: keyof typeof replayImportForm) {
  const input = { runtimeFile: replayRuntimeInputRef, graphsFile: replayGraphsInputRef, workspaceFile: replayWorkspaceInputRef }[kind]
  input.value?.click()
}

async function handleReplayImport() {
  if (replayImportLoading.value) return
  const assetFiles = [replayImportForm.runtimeFile, replayImportForm.graphsFile].filter(
    (file): file is File => Boolean(file),
  )
  const workspaceFile = replayImportForm.workspaceFile
  if (!assetFiles.length && !workspaceFile) {
    errorMessage.value = '请选择完整回放资产或工作区恢复文件。'
    return
  }

  replayImportLoading.value = true
  errorMessage.value = ''
  try {
    if (assetFiles.length && workspaceFile) {
      const payload: unknown = JSON.parse(await workspaceFile.text())
      if (payload && typeof payload === 'object' && 'schema_version' in payload
        && payload.schema_version === 'rootlens-session-export.v1') {
        throw new Error('完整 Session 请单独导入，不要同时选择 runtime 或 graphs。')
      }
    }
    const messages: string[] = [], warnings: string[] = []
    if (assetFiles.length) {
      const { graphs, runtime, summary } = await buildLocalImportResult(assetFiles)
      const note = `已导入回放：${summary.datasets.length} 个数据集、${summary.cases.length} 个案例。`
      await saveImportedSession({ graphs, runtime, summary: note, importSummary: summary })
      messages.push(note)
    }
    if (workspaceFile) {
      const restored = await restoreSessionImportFile(workspaceFile)
      messages.push(restored.summary)
      warnings.push(...restored.warnings)
    }
    emit('imported', [...messages, ...warnings].join(' '))
    emit('update:visible', false)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    replayImportLoading.value = false
  }
}
</script>

<template>
  <a-modal
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    title="导入回放资产"
    :footer="false"
    :mask-closable="!replayImportLoading"
    :esc-to-close="!replayImportLoading"
    :closable="!replayImportLoading"
    class="workspace-replay-modal"
  >
    <a-form
      id="evidence-replay-form"
      :key="formKey"
      :model="replayImportForm"
      layout="vertical"
      class="workspace-stack workspace-stack--tight workspace-form"
    >
      <a-form-item
        label="rootlens-runtime.json"
        tooltip="与 unified-graphs.json 一起导入。"
        label-component="span"
        class="workspace-replay-import-field"
      >
        <input
          ref="replayRuntimeInputRef"
          class="rl-file-input-native"
          type="file"
          accept=".json"
          @change="handleReplayFileChange('runtimeFile', $event)"
        />
        <a-button
          aria-label="选择 rootlens-runtime.json"
          size="small"
          @click="openReplayFilePicker('runtimeFile')"
        >
          {{ replayImportForm.runtimeFile?.name ?? '选择文件' }}
        </a-button>
      </a-form-item>

      <a-form-item
        label="unified-graphs.json"
        tooltip="与 rootlens-runtime.json 一起导入。"
        label-component="span"
        class="workspace-replay-import-field"
      >
        <input
          ref="replayGraphsInputRef"
          class="rl-file-input-native"
          type="file"
          accept=".json"
          @change="handleReplayFileChange('graphsFile', $event)"
        />
        <a-button
          aria-label="选择 unified-graphs.json"
          size="small"
          @click="openReplayFilePicker('graphsFile')"
        >
          {{ replayImportForm.graphsFile?.name ?? '选择文件' }}
        </a-button>
      </a-form-item>

      <a-form-item
        label="workspace export / session bundle"
        tooltip="可选工作区；完整 session bundle 请单独导入。"
        label-component="span"
        class="workspace-replay-import-field"
      >
        <input
          ref="replayWorkspaceInputRef"
          class="rl-file-input-native"
          type="file"
          accept=".json"
          @change="handleReplayFileChange('workspaceFile', $event)"
        />
        <a-button
          aria-label="选择 workspace export / session bundle"
          size="small"
          @click="openReplayFilePicker('workspaceFile')"
        >
          {{ replayImportForm.workspaceFile?.name ?? '选择文件' }}
        </a-button>
      </a-form-item>

      <a-alert
        type="info"
        :show-icon="false"
        title="回放只显示已保存结果，不会提交分析。完整 Session 可单独导入；分开的 runtime 和 graphs 文件须一并选择。"
      />

      <a-alert v-if="errorMessage" type="error">{{ errorMessage }}</a-alert>
      <div class="rl-form-actions rl-form-actions--dual">
        <a-button type="primary" :loading="replayImportLoading" @click="handleReplayImport">
          导入
        </a-button>
        <a-button :disabled="replayImportLoading" @click="emit('update:visible', false)">
          取消
        </a-button>
      </div>
    </a-form>
  </a-modal>
</template>
