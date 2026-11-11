<script setup lang="ts">
import { Modal } from '@arco-design/web-vue'
import { IconDownload, IconUpload } from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import type { WorkingGraphPackage } from '@/api/contracts'
import { editableWorkingGraphNode, parseWorkingGraphDraft, updateWorkingGraphNode } from '@/services/working-graph-edit'

const props = defineProps<{
  mode: 'node' | 'package' | 'import' | null
  graphPackage: WorkingGraphPackage | null
  nodeId: string | null
  busy: boolean
  error: string
}>()
const emit = defineEmits<{
  submit: [value: { kind: 'save' | 'import'; package: WorkingGraphPackage }]
  close: []
  'dirty-change': [dirty: boolean]
}>()

const initialPackage = shallowRef<WorkingGraphPackage | null>(null)
const initialNode = computed(() => editableWorkingGraphNode(initialPackage.value, props.nodeId))
const initialJson = computed(() => initialPackage.value ? JSON.stringify(initialPackage.value, null, 2) : '')
const initialAliases = computed(() => initialNode.value?.aliases?.join('\n') ?? '')
const draftName = ref('')
const draftAliases = ref('')
const draftJson = ref('')
const localError = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const filename = ref('')
const reading = ref(false)
let readRevision = 0

const kindNames = { entity: '实体', hypothesis: '候选原因', mechanism: '机理', pattern: '现象' }
const legacy = computed(() => initialPackage.value?.schema_version === 'rootlens-working-graph.v1')
const title = computed(() => props.mode === 'node' ? '编辑节点' : props.mode === 'import' ? '导入工作图' : '工作图包')
const dirty = computed(() => {
  if (props.mode === 'node') return !!initialNode.value && (
    draftName.value !== initialNode.value.name || draftAliases.value !== initialAliases.value
  )
  if (props.mode === 'package') return !legacy.value && draftJson.value !== initialJson.value
  return props.mode === 'import' && !!draftJson.value.trim()
})
const canSubmit = computed(() => !props.busy && !reading.value && dirty.value && (
  props.mode === 'node' ? !!initialNode.value && !!draftName.value.trim()
    : props.mode === 'package' ? !!initialPackage.value && !legacy.value && !!draftJson.value.trim()
      : props.mode === 'import'
))

function startDraft() {
  readRevision += 1
  reading.value = false
  filename.value = ''
  localError.value = ''
  initialPackage.value = props.graphPackage
  draftName.value = initialNode.value?.name ?? ''
  draftAliases.value = initialAliases.value
  draftJson.value = props.mode === 'package' ? initialJson.value : ''
}

watch([() => props.mode, () => props.nodeId], startDraft, { immediate: true })
watch(() => props.graphPackage, () => { if (!dirty.value) startDraft() })
watch(dirty, value => emit('dirty-change', value))
watch([draftName, draftAliases, draftJson], () => { localError.value = '' })
onBeforeUnmount(() => { readRevision += 1 })

function close() {
  if (props.busy) return
  const dismiss = () => {
    emit('dirty-change', false)
    emit('close')
  }
  if (!dirty.value) return dismiss()
  Modal.confirm({
    title: '放弃未保存的内容？',
    content: '这次编辑不会写入工作图。',
    okText: '放弃',
    cancelText: '继续编辑',
    onOk: dismiss,
  })
}

async function openFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || props.busy) return
  const revision = ++readRevision
  reading.value = true
  const replace = async () => {
    try {
      const text = await file.text()
      if (revision !== readRevision) return
      draftJson.value = text
      filename.value = file.name
    } catch {
      if (revision === readRevision) localError.value = '无法读取所选文件。'
    } finally {
      if (revision === readRevision) reading.value = false
    }
  }
  if (!dirty.value) return replace()
  Modal.confirm({
    title: '替换当前导入内容？',
    content: '选择的 JSON 文件会替换当前导入草稿。',
    okText: '读取文件',
    cancelText: '保留草稿',
    onOk: replace,
    onCancel: () => { if (revision === readRevision) reading.value = false },
  })
}

function downloadPackage() {
  const graph = initialPackage.value
  if (!graph) return
  const blob = new Blob([initialJson.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'rootlens-working-graph.json'
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}

function submit() {
  if (!canSubmit.value) return
  localError.value = ''
  try {
    if (props.mode === 'import') {
      emit('submit', { kind: 'import', package: parseWorkingGraphDraft(draftJson.value) })
      return
    }
    const graph = initialPackage.value
    if (!graph || graph !== props.graphPackage) {
      throw new Error('工作图已重新加载。请复制保留草稿后重新打开编辑。')
    }
    if (props.mode === 'node' && initialNode.value) {
      emit('submit', { kind: 'save', package: updateWorkingGraphNode(graph, initialNode.value.id, {
        name: draftName.value,
        ...(initialNode.value.aliases !== null && draftAliases.value !== initialAliases.value
          ? { aliases: draftAliases.value.split('\n') } : {}),
      }) })
    } else if (props.mode === 'package') {
      emit('submit', { kind: 'save', package: parseWorkingGraphDraft(draftJson.value, graph) })
    }
  } catch (error) {
    localError.value = error instanceof Error ? error.message : String(error)
  }
}
</script>

<template>
  <a-modal
    :visible="mode !== null"
    :title="title"
    :width="mode === 'node' ? 'min(480px, calc(100vw - 24px))' : 'min(720px, calc(100vw - 24px))'"
    :footer="false"
    :closable="!busy"
    :mask-closable="!busy"
    :esc-to-close="!busy"
    @cancel="close"
  >
    <form class="working-graph-editor" @submit.prevent="submit">
      <template v-if="mode === 'node' && initialNode">
        <div><a-tag size="small" color="arcoblue">{{ kindNames[initialNode.kind] }}</a-tag></div>
        <label class="working-graph-editor__field">
          <span>节点名称</span>
          <input v-model="draftName" class="working-graph-editor__input" required :disabled="busy" />
        </label>
        <label v-if="initialNode.aliases !== null" class="working-graph-editor__field">
          <span>别名</span>
          <textarea v-model="draftAliases" class="working-graph-editor__input" rows="3" placeholder="一行一个别名" :disabled="busy" />
        </label>
      </template>
      <a-alert v-else-if="mode === 'node'" type="warning">此节点没有可编辑的规范名称。</a-alert>

      <template v-else-if="mode === 'import'">
        <p class="working-graph-editor__hint">选择或粘贴完整的 v2 工作图 JSON。导入会新建一张待启用的图，不覆盖已有图。</p>
        <div class="working-graph-editor__toolbar">
          <input ref="fileInput" type="file" accept=".json,application/json" hidden @change="openFile" />
          <a-button html-type="button" :loading="reading" :disabled="busy" @click="fileInput?.click()">
            <template #icon><IconUpload /></template>选择 JSON 文件
          </a-button>
          <span v-if="filename" class="working-graph-editor__hint">{{ filename }}</span>
        </div>
        <label class="working-graph-editor__field">
          <span>工作图 JSON</span>
          <textarea v-model="draftJson" class="working-graph-editor__input working-graph-editor__json" rows="12"
            :disabled="busy || reading" spellcheck="false" placeholder="在此粘贴完整工作图 JSON" />
        </label>
      </template>

      <template v-else-if="mode === 'package' && initialPackage">
        <div class="working-graph-editor__toolbar working-graph-editor__toolbar--package">
          <p class="working-graph-editor__hint">
            {{ legacy ? '旧版工作图只读，可以导出已保存的完整包。' : '高级编辑：保存完整包。条件、引用与来源由后端校验。' }}
          </p>
          <a-button html-type="button" :disabled="busy" @click="downloadPackage">
            <template #icon><IconDownload /></template>导出 JSON
          </a-button>
        </div>
        <label class="working-graph-editor__field">
          <span>工作图 JSON</span>
          <textarea v-model="draftJson" class="working-graph-editor__input working-graph-editor__json" rows="14"
            :readonly="legacy" :disabled="busy" spellcheck="false" />
        </label>
      </template>
      <a-alert v-else-if="mode === 'package'" type="warning">当前没有可读取的工作图包。</a-alert>

      <details v-if="(mode === 'node' && initialNode) || (mode === 'package' && initialPackage)" class="working-graph-editor__technical">
        <summary>技术详情</summary>
        <dl v-if="mode === 'node' && initialNode">
          <dt>节点标识</dt><dd><code>{{ initialNode.id }}</code></dd>
        </dl>
        <dl v-else-if="initialPackage">
          <dt>工作图标识</dt><dd><code>{{ initialPackage.graph_id ?? '未分配' }}</code></dd>
          <dt>包版本</dt><dd><code>{{ initialPackage.schema_version }}</code></dd>
          <dt>构图来源</dt><dd><code>{{ initialPackage.build_id }}</code></dd>
        </dl>
      </details>
      <a-alert v-if="localError || error" type="error" role="alert">{{ localError || error }}</a-alert>
      <div class="working-graph-editor__actions">
        <a-button html-type="button" :disabled="busy" @click="close">{{ legacy && mode === 'package' ? '关闭' : '取消' }}</a-button>
        <a-button v-if="mode === 'import' || (mode === 'node' && initialNode) || (mode === 'package' && initialPackage && !legacy)"
          html-type="submit" type="primary" :disabled="!canSubmit" :loading="busy">
          {{ mode === 'import' ? '导入为新图' : '保存' }}
        </a-button>
      </div>
    </form>
  </a-modal>
</template>

<style scoped>
.working-graph-editor {
  display: grid;
  gap: 14px;
}
.working-graph-editor__hint { margin: 0; color: var(--color-text-2); overflow-wrap: anywhere; }
.working-graph-editor__field { display: grid; gap: 6px; min-width: 0; font-weight: 500; }
.working-graph-editor__input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  padding: 8px 10px;
  font: inherit;
  font-weight: 400;
  color: var(--color-text-1);
  background: var(--color-fill-1);
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
}
.working-graph-editor__input:focus-visible { outline: 2px solid rgb(var(--primary-6)); outline-offset: 1px; }
.working-graph-editor textarea { resize: vertical; }
.working-graph-editor__json {
  min-height: 120px;
  max-height: 46vh;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  line-height: 1.55;
  tab-size: 2;
}
.working-graph-editor__toolbar,
.working-graph-editor__actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.working-graph-editor__toolbar--package { justify-content: space-between; }
.working-graph-editor__actions { justify-content: flex-end; padding-top: 4px; }
.working-graph-editor__technical { color: var(--color-text-2); font-size: 13px; }
.working-graph-editor__technical summary { cursor: pointer; }
.working-graph-editor__technical dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; margin: 6px 0 0; }
.working-graph-editor__technical dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
</style>
