<script setup lang="ts">
import { IconFile, IconHistory } from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import type { ApiClient } from '@/api/client'
import type {
  KGMaterialChunkRecord,
  KGMaterialExtractionArtifactRecord,
  KGMaterialExtractionRunRecord,
  KGMaterialRecord,
} from '@/api/contracts'
import {
  formatMaterialDate, materialChunkLocator, materialError, materialLocation, materialStatuses,
  materialTypeLabel, scenarioLabel, type MaterialStatus,
} from '@/services/material-presentation'
import { formatClaimBoundaryCopy } from '@/services/ui-copy'

type MaterialReader = Pick<ApiClient,
  'getKGMaterial' | 'getKGMaterialChunks' | 'getKGMaterialExtractions'
  | 'getKGMaterialArtifacts'
>
type Tab = 'results' | 'info' | 'history'

const props = defineProps<{
  material: KGMaterialRecord
  reader: MaterialReader
  revision: number
  status: MaterialStatus
  canManage: boolean
  archived: boolean
  archiveBlocked: boolean
  mutationBusy: boolean
  taskBusy: boolean
}>()
const emit = defineEmits<{ parse: []; archive: []; restore: [] }>()

const tab = ref<Tab>('results')
const detail = ref<KGMaterialRecord>()
const chunks = ref<KGMaterialChunkRecord[] | null>(null)
const runs = ref<KGMaterialExtractionRunRecord[] | null>(null)
const expanded = ref<string[]>([])
const loading = ref(false)
const error = ref('')

const artifacts = ref<KGMaterialExtractionArtifactRecord[] | null>(null)
const technicalOpen = ref(false)
const technicalLoading = ref(false)
const technicalError = ref('')

let revision = 0
let paneRequest = 0
const current = computed(() => detail.value ?? props.material)
const original = computed(() => materialLocation(current.value))
const link = computed(() => /^https?:\/\//i.test(original.value) ? original.value : '')
const materialErrorText = computed(() => {
  const value = current.value.extraction?.error_message
  return typeof value === 'string' ? value : ''
})
const orderedChunks = computed(() => [...(chunks.value ?? [])].sort((a, b) => a.chunk_index - b.chunk_index))
const parseLabel = computed(() => ({
  ready: '重新提取', pending: '提取内容', failed: '重试提取', running: '提取中',
})[props.status])

async function readPane(force = false) {
  const id = props.material.material_id
  const request = ++paneRequest
  const currentRevision = revision
  const activeTab = tab.value
  const reader = props.reader
  error.value = ''
  loading.value = false
  if (!force && ((activeTab === 'results' && chunks.value !== null) || (activeTab === 'info' && detail.value)
    || (activeTab === 'history' && runs.value !== null))) return
  const stillCurrent = () => request === paneRequest && currentRevision === revision
  loading.value = true
  try {
    if (activeTab === 'results') {
      const result = await reader.getKGMaterialChunks(id)
      if (stillCurrent()) chunks.value = result.chunks
    } else if (activeTab === 'info') {
      const result = await reader.getKGMaterial(id)
      if (stillCurrent()) detail.value = result.material
    } else {
      const result = await reader.getKGMaterialExtractions(id)
      if (stillCurrent()) runs.value = result.runs
    }
  } catch (cause) {
    if (stillCurrent()) error.value = materialError(cause)
  } finally {
    if (stillCurrent()) loading.value = false
  }
}

async function readTechnical(force = false) {
  if (technicalLoading.value || (!force && artifacts.value !== null)) return
  const currentRevision = revision
  technicalLoading.value = true
  technicalError.value = ''
  try {
    const response = await props.reader.getKGMaterialArtifacts(props.material.material_id)
    if (currentRevision === revision) artifacts.value = response.artifacts
  } catch (cause) {
    if (currentRevision === revision) technicalError.value = materialError(cause)
  } finally {
    if (currentRevision === revision) technicalLoading.value = false
  }
}

function toggleTechnical(event: Event) {
  technicalOpen.value = (event.target as HTMLDetailsElement).open
  if (technicalOpen.value) void readTechnical()
}

function changeTab(next: string | number) {
  if (next === 'results' || next === 'info' || next === 'history') tab.value = next
}
function showMore(chunkId: string) {
  expanded.value = expanded.value.includes(chunkId) ? expanded.value.filter((id) => id !== chunkId) : [...expanded.value, chunkId]
}
function chunkText(chunk: KGMaterialChunkRecord) {
  const text = chunk.text_content
  return text.length > 168 && !expanded.value.includes(chunk.chunk_id) ? text.slice(0, 168).trimEnd() + '…' : text
}

function runStatus(status: string) {
  if (status === 'extracted' || status === 'completed') return { label: '已提取', color: 'green' }
  if (status === 'failed') return { label: '失败', color: 'red' }
  return { label: status, color: 'gray' }
}

watch(tab, () => { void readPane() })
watch([() => props.reader, () => props.revision], () => {
  revision += 1
  detail.value = undefined
  chunks.value = null
  runs.value = null
  artifacts.value = null
  technicalLoading.value = false
  void readPane()
  if (technicalOpen.value && tab.value === 'info') void readTechnical()
}, { immediate: true })

onBeforeUnmount(() => { revision += 1 })
</script>

<template>
  <div class="material-detail">
    <header class="material-detail__head">
      <p class="material-detail__label">素材详情</p>
      <div class="material-detail__heading">
        <h2>{{ material.title }}</h2>
        <a-tag v-if="archived">已移出</a-tag>
      </div>
      <p class="material-detail__meta">
        {{ materialTypeLabel(material.source_type) }} · {{ scenarioLabel(material.scenario) }}
        · 更新于 {{ formatMaterialDate(material.updated_at ?? material.created_at) }}
      </p>
    </header>

    <a-tabs class="material-detail__tabs" :active-key="tab" lazy-load @change="changeTab">
      <a-tab-pane key="results" title="提取结果">
        <div class="material-detail__body">
          <a-alert v-if="status === 'failed'" type="error">
            {{ materialErrorText || '未能提取内容。可重试或查看提取记录。' }}
          </a-alert>
          <a-alert v-if="error" type="error">
            {{ error }} <a-button size="mini" type="text" @click="readPane(true)">重新读取</a-button>
          </a-alert>
          <div v-else-if="loading" class="material-detail__state"><a-spin /> 正在读取提取结果…</div>
          <template v-else-if="orderedChunks.length">
            <p class="material-detail__label">{{ status === 'failed' ? '上次保留的 ' : '' }}{{ orderedChunks.length }} 个原文片段</p>
            <article v-for="chunk in orderedChunks" :key="chunk.chunk_id" class="material-fragment">
              <div class="material-fragment__heading">
                <strong>{{ materialChunkLocator(chunk) || '片段 ' + (chunk.chunk_index + 1) }}</strong>
                <a-button
                  v-if="chunk.text_content.length > 168"
                  size="mini"
                  type="text"
                  :aria-expanded="expanded.includes(chunk.chunk_id)"
                  @click="showMore(chunk.chunk_id)"
                >
                  {{ expanded.includes(chunk.chunk_id) ? '收起' : '展开全文' }}
                </a-button>
                <span v-else-if="materialChunkLocator(chunk)" class="material-detail__meta">片段 {{ chunk.chunk_index + 1 }}</span>
              </div>
              <p>{{ chunkText(chunk) }}</p>
            </article>
          </template>
          <div v-else-if="status !== 'failed'" class="material-detail__state">
            <IconFile />
            <div v-if="status === 'running'"><strong>正在提取内容</strong><p>完成后在这里查看原文片段。</p></div>
            <div v-else-if="status === 'ready'"><strong>没有可显示的原文片段</strong></div>
            <div v-else><strong>还未提取内容</strong><p>提取后可阅读原文片段和出处。</p></div>
          </div>
        </div>
      </a-tab-pane>

      <a-tab-pane key="info" title="素材信息">
        <div class="material-detail__body">
          <a-alert v-if="error" type="error">{{ error }} <a-button type="text" size="mini" @click="readPane(true)">重新读取</a-button></a-alert>
          <dl class="material-detail__facts">
            <dt>来源</dt>
            <dd><a v-if="link" :href="link" target="_blank" rel="noopener noreferrer">{{ link }}</a><template v-else>{{ original || '—' }}</template></dd>
            <dt v-if="material.original_filename">文件</dt>
            <dd v-if="material.original_filename">{{ material.original_filename }}</dd>
            <dt>场景</dt><dd>{{ scenarioLabel(material.scenario) }}</dd>
            <dt>状态</dt><dd>{{ materialStatuses[status].label }}</dd>
            <dt v-if="current.archived_at">移出时间</dt><dd v-if="current.archived_at">{{ formatMaterialDate(current.archived_at) }}</dd>
            <dt v-if="current.notes">备注</dt><dd v-if="current.notes">{{ current.notes }}</dd>
          </dl>
          <details class="material-detail__technical" @toggle="toggleTechnical">
            <summary>技术详情</summary>
            <div class="material-detail__technical-body">
              <p>{{ formatClaimBoundaryCopy(current.claim_boundary) }}</p>
              <pre class="rl-json-preview">{{ JSON.stringify(current, null, 2) }}</pre>
              <a-spin v-if="technicalLoading" />
              <a-alert v-if="technicalError" type="warning">
                {{ technicalError }} <a-button size="mini" type="text" @click="readTechnical(true)">重读详情</a-button>
              </a-alert>
              <details v-if="artifacts">
                <summary>提取产物（{{ artifacts.length }}）</summary>
                <pre class="rl-json-preview">{{ JSON.stringify(artifacts, null, 2) }}</pre>
              </details>
            </div>
          </details>
        </div>
      </a-tab-pane>

      <a-tab-pane key="history" title="提取记录">
        <div class="material-detail__body">
          <a-alert v-if="error" type="error">{{ error }} <a-button type="text" size="mini" @click="readPane(true)">重新读取</a-button></a-alert>
          <div v-else-if="loading" class="material-detail__state"><a-spin /> 正在读取提取记录…</div>
          <ul v-else-if="runs?.length" class="material-extraction-list">
            <li v-for="run in runs" :key="run.extraction_run_id">
              <div>
                <p>{{ formatMaterialDate(run.completed_at ?? run.started_at) }}</p>
                <p class="material-detail__meta">{{ run.error_message ?? (run.record_count == null ? '' : '取得 ' + run.record_count + ' 个片段') }}</p>
              </div>
              <a-tag :color="runStatus(run.status).color">{{ runStatus(run.status).label }}</a-tag>
            </li>
          </ul>
          <div v-else class="material-detail__state"><IconHistory /> 暂无提取记录</div>
        </div>
      </a-tab-pane>
    </a-tabs>

    <footer v-if="canManage" class="material-detail__footer">
      <template v-if="archived">
        <span class="material-detail__meta">保留原文件及提取记录</span>
        <a-button :loading="mutationBusy" @click="emit('restore')">恢复素材</a-button>
      </template>
      <template v-else>
        <div>
          <a-button type="text" status="normal" :disabled="archiveBlocked || mutationBusy" @click="emit('archive')">移出素材库</a-button>
          <span v-if="archiveBlocked" class="material-detail__meta">任务使用中</span>
        </div>
        <a-button :disabled="taskBusy || mutationBusy" @click="emit('parse')">
          <template #icon><IconFile /></template>{{ parseLabel }}
        </a-button>
      </template>
    </footer>
  </div>
</template>

<style scoped>
.material-detail { display: flex; flex: 1; flex-direction: column; min-width: 0; }
.material-detail p { margin: 0; }
.material-detail__head { padding: 14px 14px 5px; display: grid; gap: 4px; }
.material-detail__heading { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.material-detail h2 { margin: 0; font-size: 17px; line-height: 1.42; font-weight: 600; overflow-wrap: anywhere; }
.material-detail__label, .material-detail__meta { color: var(--color-text-2); font-size: 12px; line-height: 1.5; }
.material-detail__tabs { min-height: 0; flex: 1; }
.material-detail__tabs :deep(.arco-tabs-nav) { padding-inline: 14px; }
.material-detail__tabs :deep(.arco-tabs-content) { padding-top: 0; }
.material-detail__body { display: grid; align-content: start; gap: 8px; padding: 12px 14px; max-height: clamp(248px, 46vh, 430px); overflow: auto; }
.material-detail__state { display: flex; gap: 9px; align-items: flex-start; padding: 12px 0; color: var(--color-text-2); }
.material-detail__state strong { color: var(--color-text-1); }
.material-detail__state .arco-icon { margin-top: 3px; color: rgb(var(--primary-6)); }
.material-fragment { border: 1px solid var(--rl-border); border-radius: 3px; padding: 8px 9px; background: var(--color-bg-1); }
.material-fragment__heading { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 5px; }
.material-fragment__heading strong { color: rgb(var(--primary-6)); font-size: 12px; overflow-wrap: anywhere; }
.material-fragment p { margin-top: 4px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 1.55; }
.material-detail__facts { margin: 0; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px 12px; font-size: 13px; }
.material-detail__facts dt { color: var(--color-text-2); }
.material-detail__facts dd { margin: 0; overflow-wrap: anywhere; }
.material-detail__facts a { color: rgb(var(--primary-6)); }
.material-detail__technical { font-size: 12px; color: var(--color-text-2); }
.material-detail__technical summary { cursor: pointer; }
.material-detail__technical-body { display: grid; gap: 8px; padding-top: 8px; }
.material-detail__technical-body pre { max-height: 220px; }
.material-extraction-list { display: grid; padding: 0; margin: 0; list-style: none; }
.material-extraction-list li { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--rl-border); overflow-wrap: anywhere; }
.material-detail__footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px; border-top: 1px solid var(--rl-border); padding: 8px 14px; }
.material-detail__footer :deep(.arco-btn-text) { padding-inline: 0; color: var(--color-text-2); }
.material-detail__footer .material-detail__meta { margin-inline-start: 4px; }
</style>
