<script setup lang="ts">
import { IconUpload } from '@arco-design/web-vue/es/icon'
import { onBeforeUnmount, reactive, ref, watch } from 'vue'

import { createApiClient } from '@/api/client'
import type { KGMaterialRecord } from '@/api/contracts'
import { extractFilesFromDataTransfer, markDragEventHandled } from '@/services/file-drop'
import { materialError, materialScenarios, materialTypes } from '@/services/material-presentation'
import { uploadKGMaterialFiles } from '@/services/material-upload'

const props = defineProps<{ backendUrl: string | null }>()
const visible = defineModel<boolean>('visible', { required: true })
const emit = defineEmits<{ added: [materials: KGMaterialRecord[]] }>()

const tab = ref<'file' | 'url'>('file')
const fileInput = ref<HTMLInputElement>()
const fileButton = ref<{ $el: HTMLButtonElement }>()
const urlInput = ref<{ focus: () => void }>()
const files = ref<File[]>([])
const dragging = ref(0)
const busy = ref(false)
const errors = ref<string[]>([])
const form = reactive({
  title: '', scenario: 'shared', sourceType: '', notes: '', materialId: '', url: '',
})
let sourceRevision = 0

function reset() {
  tab.value = 'file'
  files.value = []
  dragging.value = 0
  errors.value = []
  Object.assign(form, { title: '', scenario: 'shared', sourceType: '', notes: '', materialId: '', url: '' })
}
watch(visible, (open) => { if (!open) reset() })
watch(() => props.backendUrl, () => {
  sourceRevision += 1
  busy.value = false
  reset()
}, { flush: 'sync' })
onBeforeUnmount(() => { sourceRevision += 1 })

function setFiles(next: File[]) {
  if (busy.value) return
  files.value = next
  errors.value = []
}
function onFileInput(event: Event) {
  const input = event.target as HTMLInputElement
  setFiles(Array.from(input.files ?? []))
  input.value = ''
}
function onDragEnter(event: DragEvent) {
  markDragEventHandled(event)
  dragging.value += 1
}
function onDragOver(event: DragEvent) {
  markDragEventHandled(event, { dropEffect: 'copy' })
}
function onDragLeave(event: DragEvent) {
  markDragEventHandled(event)
  dragging.value = Math.max(0, dragging.value - 1)
}
function onDrop(event: DragEvent) {
  markDragEventHandled(event, { dropEffect: 'copy' })
  dragging.value = 0
  setFiles(extractFilesFromDataTransfer(event.dataTransfer))
}

async function addMaterial() {
  const backendUrl = props.backendUrl
  if (!backendUrl || busy.value) return
  const revision = sourceRevision
  const client = createApiClient(backendUrl)
  const options = {
    title: form.title.trim() || undefined,
    scenario: form.scenario,
    notes: form.notes.trim() || undefined,
    material_id: form.materialId.trim() || undefined,
  }
  errors.value = []
  busy.value = true
  try {
    if (tab.value === 'file') {
      const batch = [...files.value]
      if (!batch.length) return
      const { uploaded, failed } = await uploadKGMaterialFiles(
        batch, { ...options, source_type: form.sourceType || undefined },
        (input) => {
          if (revision !== sourceRevision) throw new Error('数据源已切换。')
          return client.uploadKGMaterial(input)
        },
      )
      if (revision !== sourceRevision) return
      files.value = failed.map(({ file }) => file)
      errors.value = failed.map(({ file, error }) => file.name + '：' + error)
      // A failed tail from a batch is still using the batch's per-file defaults.
      if (batch.length > 1) Object.assign(form, { title: '', materialId: '', sourceType: '' })
      if (uploaded.length) emit('added', uploaded.map(({ material }) => material))
      if (!failed.length) visible.value = false
    } else {
      const url = form.url.trim()
      if (!/^https?:\/\//i.test(url) || !URL.canParse(url)) {
        errors.value = ['请输入完整的 HTTP 或 HTTPS 网址。']
        urlInput.value?.focus()
        return
      }
      const response = await client.registerKGMaterialUrl({
        ...options, url, source_type: form.sourceType || 'webpage',
      })
      if (revision !== sourceRevision) return
      emit('added', [response.material])
      visible.value = false
    }
  } catch (error) {
    if (revision === sourceRevision) errors.value = [materialError(error)]
  } finally {
    if (revision === sourceRevision) busy.value = false
  }
}

function switchTab(next: string | number) {
  if (busy.value || (next !== 'file' && next !== 'url')) return
  tab.value = next
  form.sourceType = ''
  errors.value = []
}
</script>

<template>
  <a-modal
    v-model:visible="visible"
    title="添加素材"
    width="min(520px, calc(100vw - 32px))"
    :mask-closable="false"
    :esc-to-close="!busy"
    :closable="!busy"
    :footer="false"
    @open="tab === 'file' ? fileButton?.$el.focus() : urlInput?.focus()"
  >
    <form class="material-import" @submit.prevent="addMaterial">
      <a-tabs :active-key="tab" @change="switchTab">
        <a-tab-pane key="file" title="上传文件" :disabled="busy && tab !== 'file'">
          <div
            class="rl-file-dropzone material-import__drop"
            :class="{ 'rl-file-dropzone--active': dragging > 0 && !busy }"
            @dragenter="onDragEnter"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @drop="onDrop"
          >
            <input ref="fileInput" type="file" multiple hidden :disabled="busy" @change="onFileInput">
            <strong>把文件拖到这里</strong>
            <p>可提取 TXT、Markdown、CSV、JSON、JSONL、HTML 和含文本层的 PDF</p>
            <a-button ref="fileButton" :disabled="busy" @click="fileInput?.click()">
              <template #icon><IconUpload /></template>
              选择文件
            </a-button>
          </div>
          <ul v-if="files.length" class="material-import__files" aria-label="待上传文件">
            <li v-for="(file, index) in files" :key="index">{{ file.name }}</li>
          </ul>
        </a-tab-pane>
        <a-tab-pane key="url" title="登记网址" :disabled="busy && tab !== 'url'">
          <div class="material-import__field">
            <label for="material-register-url">网址</label>
            <a-input
              ref="urlInput"
              v-model="form.url"
              :input-attrs="{ id: 'material-register-url', 'aria-label': '网址' }"
              :disabled="busy"
              placeholder="https://example.com/doc"
            />
            <p>登记后，提取时才会获取网页内容。</p>
          </div>
        </a-tab-pane>
      </a-tabs>

      <div class="material-import__fields">
        <div class="material-import__field">
          <label for="material-import-scenario-input">所属场景</label>
          <div id="material-import-scenario" v-control-label="'所属场景'">
            <a-select v-model="form.scenario" :disabled="busy">
              <a-option v-for="scenario in materialScenarios" :key="scenario.value" :value="scenario.value">
                {{ scenario.buildLabel }}
              </a-option>
            </a-select>
          </div>
        </div>
        <div class="material-import__field">
          <label for="material-import-title">名称（选填）</label>
          <a-input
            v-model="form.title"
            :input-attrs="{ id: 'material-import-title', 'aria-label': '名称（选填）' }"
            :disabled="busy || (tab === 'file' && files.length > 1)"
            :placeholder="tab === 'file' ? '默认使用文件名' : '默认使用网址'"
          />
        </div>
      </div>

      <details class="material-import__advanced">
        <summary>高级选项</summary>
        <div class="material-import__fields">
          <div class="material-import__field">
            <label for="material-import-source-type-input">类型</label>
            <div id="material-import-source-type" v-control-label="'素材类型'">
              <a-select v-model="form.sourceType" :disabled="busy || (tab === 'file' && files.length > 1)">
                <a-option value="">{{ tab === 'file' ? '按文件名识别' : '默认：网页' }}</a-option>
                <a-option v-for="type in materialTypes" :key="type.value" :value="type.value">{{ type.label }}</a-option>
              </a-select>
            </div>
          </div>
          <div class="material-import__field">
            <label for="material-import-id">素材 ID</label>
            <a-input
              v-model="form.materialId"
              :input-attrs="{ id: 'material-import-id', 'aria-label': '素材 ID' }"
              :disabled="busy || (tab === 'file' && files.length > 1)"
              placeholder="默认自动分配"
            />
          </div>
        </div>
        <div class="material-import__field">
          <label for="material-import-notes">备注</label>
          <a-textarea
            v-model="form.notes"
            :textarea-attrs="{ id: 'material-import-notes', 'aria-label': '备注' }"
            :disabled="busy"
            :auto-size="{ minRows: 2, maxRows: 4 }"
          />
        </div>
      </details>

      <a-alert v-if="errors.length" type="error">
        <div v-for="(error, index) in errors" :key="index">{{ error }}</div>
      </a-alert>

      <div class="material-import__actions">
        <a-button :disabled="busy" @click="visible = false">取消</a-button>
        <a-button
          type="primary" html-type="submit" :loading="busy"
          :disabled="tab === 'file' ? !files.length : !form.url.trim()"
        >
          {{ tab === 'file' ? '上传素材' : '登记网址' }}
        </a-button>
      </div>
    </form>
  </a-modal>
</template>

<style scoped>
.material-import { display: grid; gap: 14px; }
.material-import__drop {
  display: grid;
  justify-items: center;
  gap: 8px;
  min-height: 0;
  padding: 16px;
  text-align: center;
}
.material-import p { margin: 0; color: var(--color-text-2); font-size: 12px; line-height: 1.5; }
.material-import__files { margin: 8px 0 0; padding-inline-start: 22px; max-height: 112px; overflow: auto; overflow-wrap: anywhere; }
.material-import__fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.material-import__field { display: grid; gap: 5px; min-width: 0; }
.material-import__field > label, .material-import__advanced > summary { color: var(--color-text-2); font-size: 13px; }
.material-import__advanced > summary { cursor: pointer; }
.material-import__advanced > div { margin-top: 10px; }
.material-import__actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
