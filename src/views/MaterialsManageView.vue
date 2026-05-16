<script setup lang="ts">
import {
  IconBulb,
  IconInfoCircle,
  IconRefresh,
  IconRelation,
  IconStorage,
  IconUpload,
} from '@arco-design/web-vue/es/icon'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import type {
  KGConstructionBuildDetail,
  KGConstructionBuildListResponse,
  KGConstructionSourceFormat,
  KGConstructionSourceInput,
  KGConstructionSourceListResponse,
  KGConstructionSourceType,
  KGStudioPayload,
} from '@/api/contracts'
import WorkbenchHero from '@/components/layout/WorkbenchHero.vue'
import { useAppPreferences } from '@/services/app-preferences'
import { getRootLensService } from '@/services/rootlens-service'
import { downloadJsonFile } from '@/services/session-export'
import { useWorkbenchState } from '@/services/workbench-state'

interface MaterialRecord {
  id: string
  title: string
  type: string
  role: string
  dataset: string
  status: string
  updatedAt: string
  note: string
  path: string
  sourceType: KGConstructionSourceType
  sourceFormat: KGConstructionSourceFormat
  buildSource: KGConstructionSourceInput
}

interface RootLensKGBuildExportV1 {
  schema_version: 'rootlens-kg-build-export.v1'
  exported_at: string
  source_mode: 'mock' | 'backend'
  build: KGConstructionBuildDetail['build']
  summary: KGConstructionBuildDetail['summary']
  manifest: KGConstructionBuildDetail['manifest']
  claim_boundary: string
}

const { preferences } = useAppPreferences()
const { state: workbenchState, updateState } = useWorkbenchState()

const loading = ref(false)
const errorMessage = ref('')
const actionMessage = ref('')

const kgStudio = ref<KGStudioPayload | null>(null)
const builds = ref<KGConstructionBuildListResponse | null>(null)
const buildDetail = ref<KGConstructionBuildDetail | null>(null)
const sourceList = ref<KGConstructionSourceListResponse | null>(null)
const sourceUploadInputRef = ref<HTMLInputElement | null>(null)
const sourceUploadDragActive = ref(false)
const sourceUploadDragDepth = ref(0)

const selectedMaterialId = ref<string | null>(null)
const selectedMaterialIds = ref<string[]>([])
const hiddenMaterialIds = ref<string[]>([])
const materialOverrides = ref<Record<string, Partial<MaterialRecord>>>({})

const filters = reactive({
  search: '',
  dataset: 'all',
  type: 'all',
  status: 'all',
  sortField: 'updatedAt' as 'updatedAt' | 'title' | 'type',
  sortOrder: 'desc' as 'asc' | 'desc',
})

const sourceUpload = reactive({
  file: null as File | null,
  source_id: 'uploaded_source',
  source_type: 'manual_table' as KGConstructionSourceType,
  scenario: 'shared',
  source_format: 'csv' as KGConstructionSourceFormat,
})

const materialEditor = reactive({
  title: '',
  dataset: '',
  role: '',
  note: '',
})

const buildForm = reactive({
  output_name: 'workspace-build',
  scenario: 'shared',
})

const selectedBuildRunId = computed(() => workbenchState.value.selectedConstructionRunId)
const sourceUploadAccept = '.csv,.json,.jsonl'
const canExportBuild = computed(() => !!buildDetail.value)

const heroMetrics = computed(() => [
  {
    label: '素材数',
    value: materials.value.length,
    hint: '筛选前可管理的素材总数',
    tone: 'blue' as const,
  },
  {
    label: '选中素材',
    value: selectedMaterials.value.length,
    hint: '构图配方当前选中的素材数',
    tone: 'teal' as const,
  },
  {
    label: '构图记录',
    value: builds.value?.builds.length ?? 0,
    hint: '已生成的图谱构建批次',
    tone: 'amber' as const,
  },
])

function formatDateTime(value: string | undefined | null) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', { hour12: false })
}

function inferSourceFormat(path: string): KGConstructionSourceFormat {
  if (path.endsWith('.jsonl')) {
    return 'jsonl'
  }
  if (path.endsWith('.json')) {
    return 'json'
  }
  return 'csv'
}

function normalizeSourceType(value: string): KGConstructionSourceType {
  if (value === 'manual_table' || value === 'structured_records' || value === 'tep_semantic_lift' || value === 'tep_variable_mapping') {
    return value
  }

  return 'structured_records'
}

const materials = computed<MaterialRecord[]>(() => {
  const seeded: MaterialRecord[] = (kgStudio.value?.sources ?? []).map((source) => {
    const sourceType = normalizeSourceType(source.source_type)
    const sourceFormat = inferSourceFormat(source.path_or_url)
    return {
      id: `seed:${source.source_id}`,
      title: source.title,
      type: source.source_type,
      role: source.used_for,
      dataset: 'shared',
      status: '内置',
      updatedAt: '',
      note: source.notes,
      path: source.path_or_url,
      sourceType,
      sourceFormat,
      buildSource: {
        source_id: source.source_id,
        source_type: sourceType,
        scenario: 'shared',
        path: source.path_or_url,
        source_format: sourceFormat,
      },
    }
  })

  const uploaded: MaterialRecord[] = (sourceList.value?.sources ?? []).map((source) => ({
    id: `uploaded:${source.source_id}`,
    title: source.filename,
    type: source.source_type,
    role: source.source_id,
    dataset: source.scenario,
    status: '已上传',
    updatedAt: source.uploaded_at,
    note: source.path,
    path: source.path,
    sourceType: source.source_type,
    sourceFormat: source.source_format,
    buildSource: source.build_source,
  }))

  const merged = [...seeded, ...uploaded]
    .filter((item) => !hiddenMaterialIds.value.includes(item.id))
    .map((item) => ({
      ...item,
      ...materialOverrides.value[item.id],
    }))

  return merged
})

const filteredMaterials = computed(() => {
  const keyword = filters.search.trim().toLowerCase()
  const list = materials.value.filter((item) => {
    if (filters.dataset !== 'all' && item.dataset !== filters.dataset) {
      return false
    }
    if (filters.type !== 'all' && item.type !== filters.type) {
      return false
    }
    if (filters.status !== 'all' && item.status !== filters.status) {
      return false
    }
    if (!keyword) {
      return true
    }

    return [item.title, item.role, item.note, item.path].join(' ').toLowerCase().includes(keyword)
  })

  return list.sort((left, right) => {
    const direction = filters.sortOrder === 'asc' ? 1 : -1

    if (filters.sortField === 'updatedAt') {
      const leftTime = left.updatedAt ? new Date(left.updatedAt).getTime() : 0
      const rightTime = right.updatedAt ? new Date(right.updatedAt).getTime() : 0
      return (leftTime - rightTime) * direction
    }

    if (filters.sortField === 'title') {
      return left.title.localeCompare(right.title) * direction
    }

    return left.type.localeCompare(right.type) * direction
  })
})

const selectedMaterial = computed(() => {
  return filteredMaterials.value.find((item) => item.id === selectedMaterialId.value) ?? filteredMaterials.value[0] ?? null
})

const selectedMaterials = computed(() => {
  return materials.value.filter((item) => selectedMaterialIds.value.includes(item.id))
})

function syncEditorFromSelectedMaterial() {
  materialEditor.title = selectedMaterial.value?.title ?? ''
  materialEditor.dataset = selectedMaterial.value?.dataset ?? ''
  materialEditor.role = selectedMaterial.value?.role ?? ''
  materialEditor.note = selectedMaterial.value?.note ?? ''
}

function setSourceUploadFile(file: File | null) {
  sourceUpload.file = file
}

function handleSourceUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null
  setSourceUploadFile(input?.files?.[0] ?? null)
}

function openSourceUploadPicker() {
  sourceUploadInputRef.value?.click()
}

function resetSourceUploadDragState() {
  sourceUploadDragDepth.value = 0
  sourceUploadDragActive.value = false
}

function handleSourceUploadDragEnter(event: DragEvent) {
  event.preventDefault()
  sourceUploadDragDepth.value += 1
  sourceUploadDragActive.value = true
}

function handleSourceUploadDragOver(event: DragEvent) {
  event.preventDefault()
  sourceUploadDragActive.value = true
}

function handleSourceUploadDragLeave(event: DragEvent) {
  event.preventDefault()
  sourceUploadDragDepth.value = Math.max(0, sourceUploadDragDepth.value - 1)
  if (sourceUploadDragDepth.value === 0) {
    sourceUploadDragActive.value = false
  }
}

function handleSourceUploadDrop(event: DragEvent) {
  event.preventDefault()
  const [file] = event.dataTransfer?.files ?? []
  setSourceUploadFile(file ?? null)
  resetSourceUploadDragState()
}

function toggleMaterialSelection(materialId: string, checked: boolean) {
  if (checked) {
    selectedMaterialIds.value = [...new Set([...selectedMaterialIds.value, materialId])]
    return
  }

  selectedMaterialIds.value = selectedMaterialIds.value.filter((item) => item !== materialId)
}

function applyMaterialEdit() {
  if (!selectedMaterial.value) {
    return
  }

  materialOverrides.value = {
    ...materialOverrides.value,
    [selectedMaterial.value.id]: {
      title: materialEditor.title,
      dataset: materialEditor.dataset,
      role: materialEditor.role,
      note: materialEditor.note,
    },
  }
  actionMessage.value = `已更新素材展示信息：${materialEditor.title || selectedMaterial.value.title}`
}

function deleteMaterialFromView() {
  if (!selectedMaterial.value) {
    return
  }

  hiddenMaterialIds.value = [...new Set([...hiddenMaterialIds.value, selectedMaterial.value.id])]
  selectedMaterialIds.value = selectedMaterialIds.value.filter((item) => item !== selectedMaterial.value?.id)
  selectedMaterialId.value = null
  actionMessage.value = '素材已从当前视图移除。'
}

async function loadBuildDetail(runId: string) {
  try {
    buildDetail.value = await getRootLensService().getKGConstructionBuild(runId)
    updateState({ selectedConstructionRunId: runId })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

async function refreshWorkspace() {
  loading.value = true
  errorMessage.value = ''

  try {
    const [kgStudioPayload, buildList, sources] = await Promise.all([
      getRootLensService().kgStudio(),
      getRootLensService().listKGConstructionBuilds(),
      getRootLensService().listKGConstructionSources(),
    ])

    kgStudio.value = kgStudioPayload
    builds.value = buildList
    sourceList.value = sources

    const nextBuildId =
      buildList.builds.find((item) => item.run_id === selectedBuildRunId.value)?.run_id ?? buildList.builds[0]?.run_id ?? null

    if (nextBuildId) {
      await loadBuildDetail(nextBuildId)
    } else {
      buildDetail.value = null
    }

    if (!selectedMaterialId.value) {
      selectedMaterialId.value = materials.value[0]?.id ?? null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

async function handleSourceUpload() {
  if (!sourceUpload.file) {
    actionMessage.value = '请选择待上传的来源文件。'
    return
  }

  actionMessage.value = ''
  errorMessage.value = ''

  try {
    await getRootLensService().uploadKGConstructionSource({
      file: sourceUpload.file,
      source_id: sourceUpload.source_id,
      source_type: sourceUpload.source_type,
      scenario: sourceUpload.scenario,
      source_format: sourceUpload.source_format,
    })
    actionMessage.value = '素材已上传并加入当前工坊。'
    await refreshWorkspace()
    selectedMaterialId.value = `uploaded:${sourceUpload.source_id}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

async function handleBuild() {
  if (!selectedMaterials.value.length) {
    actionMessage.value = '请先勾选至少一份素材。'
    return
  }

  actionMessage.value = ''
  errorMessage.value = ''

  try {
    const response = await getRootLensService().buildKGConstruction({
      output_name: buildForm.output_name,
      overwrite: false,
      sources: selectedMaterials.value.map((item) => ({
        ...item.buildSource,
        scenario: item.buildSource.scenario || buildForm.scenario,
      })),
    })
    actionMessage.value = `图谱已生成：${response.run_id}`
    await refreshWorkspace()
    await loadBuildDetail(response.run_id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

function handleExportBuild() {
  if (!buildDetail.value) {
    return
  }

  const payload: RootLensKGBuildExportV1 = {
    schema_version: 'rootlens-kg-build-export.v1',
    exported_at: new Date().toISOString(),
    source_mode: preferences.value.dataSourceMode,
    build: buildDetail.value.build,
    summary: buildDetail.value.summary,
    manifest: buildDetail.value.manifest,
    claim_boundary: buildDetail.value.build.claim_boundary,
  }

  downloadJsonFile(`rootlens-kg-build-${buildDetail.value.build.run_id}.json`, payload)
  actionMessage.value = `已导出图谱 bundle：${buildDetail.value.build.run_id}`
}

watch(
  () => [preferences.value.dataSourceMode, preferences.value.apiBaseUrl],
  () => {
    void refreshWorkspace()
  },
)

watch(filteredMaterials, (list) => {
  if (!list.length) {
    selectedMaterialId.value = null
    return
  }

  if (!list.some((item) => item.id === selectedMaterialId.value)) {
    selectedMaterialId.value = list[0].id
  }
})

watch(selectedMaterial, () => {
  syncEditorFromSelectedMaterial()
})

onMounted(() => {
  void refreshWorkspace()
})
</script>

<template>
  <div class="rl-page rl-screen" :class="{ 'rl-page--motion': preferences.enablePageEntranceMotion }">
    <WorkbenchHero
      eyebrow="图谱工坊"
      title="图谱素材、构图配方与构建结果"
      :metrics="heroMetrics"
      tone="amber"
    >
      <template #actions>
        <a-button size="small" @click="refreshWorkspace">
          <template #icon>
            <icon-refresh />
          </template>
          刷新视图
        </a-button>
      </template>
    </WorkbenchHero>

    <a-alert v-if="errorMessage" class="rl-alert" type="error" :title="errorMessage" />
    <a-alert v-if="actionMessage" class="rl-alert" type="success" :title="actionMessage" />

    <section class="workspace-shell workspace-shell--materials">
      <div class="workspace-materials-layout">
        <section class="workspace-materials-top-grid">
          <article class="rl-section-card workspace-materials-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-relation />
                  <span>素材列表</span>
                </h3>
                <p class="rl-section-card__desc">优先表格视图，支持选择、编辑、删除和批量构图。</p>
              </div>
              <a-tag color="green">{{ filteredMaterials.length }} 份</a-tag>
            </header>
            <div class="rl-section-card__body workspace-table-card workspace-table-card--fill">
              <div class="workspace-filter-row">
                <a-input v-model="filters.search" placeholder="搜索素材名称 / 路径 / 说明" />
                <a-select v-model="filters.dataset">
                  <a-option value="all">全部数据集</a-option>
                  <a-option value="shared">shared</a-option>
                  <a-option value="tep">tep</a-option>
                  <a-option value="mvtec">mvtec</a-option>
                  <a-option value="wafer">wafer</a-option>
                </a-select>
                <a-select v-model="filters.type">
                  <a-option value="all">全部类型</a-option>
                  <a-option value="manual_table">manual_table</a-option>
                  <a-option value="structured_records">structured_records</a-option>
                  <a-option value="tep_semantic_lift">tep_semantic_lift</a-option>
                  <a-option value="tep_variable_mapping">tep_variable_mapping</a-option>
                </a-select>
                <a-select v-model="filters.status">
                  <a-option value="all">全部状态</a-option>
                  <a-option value="内置">内置</a-option>
                  <a-option value="已上传">已上传</a-option>
                </a-select>
                <a-select v-model="filters.sortField">
                  <a-option value="updatedAt">按更新时间</a-option>
                  <a-option value="title">按名称</a-option>
                  <a-option value="type">按类型</a-option>
                </a-select>
                <a-select v-model="filters.sortOrder">
                  <a-option value="desc">降序</a-option>
                  <a-option value="asc">升序</a-option>
                </a-select>
              </div>

              <div class="workspace-table-wrap workspace-table-wrap--materials workspace-table-wrap--fill">
                <table class="workspace-table">
                  <thead>
                    <tr>
                      <th>选择</th>
                      <th>名称</th>
                      <th>类型</th>
                      <th>角色</th>
                      <th>数据集</th>
                      <th>更新时间</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="material in filteredMaterials"
                      :key="material.id"
                      :class="{ 'workspace-table__row--active': material.id === selectedMaterial?.id }"
                      @click="selectedMaterialId = material.id"
                    >
                      <td>
                        <input
                          type="checkbox"
                          :checked="selectedMaterialIds.includes(material.id)"
                          @click.stop
                          @change="toggleMaterialSelection(material.id, ($event.target as HTMLInputElement).checked)"
                        />
                      </td>
                      <td>
                        <strong>{{ material.title }}</strong>
                      </td>
                      <td>{{ material.type }}</td>
                      <td>{{ material.role }}</td>
                      <td>{{ material.dataset }}</td>
                      <td>{{ formatDateTime(material.updatedAt) }}</td>
                      <td>{{ material.status }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <a-empty v-if="!filteredMaterials.length">暂无素材</a-empty>
            </div>
          </article>

          <div class="workspace-materials-top-side-stack">
            <article class="rl-section-card workspace-material-editor-card">
              <header class="rl-section-card__header">
                <div>
                  <h3 class="rl-section-card__title workspace-title-with-icon">
                    <icon-storage />
                    <span>当前选中素材</span>
                  </h3>
                  <p class="rl-section-card__desc">先以 UI 层编辑为主，便于 mock / backend 双模式演示。</p>
                </div>
              </header>
              <div class="rl-section-card__body workspace-stack workspace-material-editor-form">
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-info-circle />
                    <span>名称</span>
                  </span>
                  <a-input v-model="materialEditor.title" />
                </div>
                <div class="workspace-form-row workspace-form-row--two">
                  <div class="rl-form-field">
                    <span class="workspace-field-label">
                      <icon-relation />
                      <span>数据集</span>
                    </span>
                    <a-input v-model="materialEditor.dataset" />
                  </div>
                  <div class="rl-form-field">
                    <span class="workspace-field-label">
                      <icon-bulb />
                      <span>角色</span>
                    </span>
                    <a-input v-model="materialEditor.role" />
                  </div>
                </div>
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-info-circle />
                    <span>说明</span>
                  </span>
                  <a-textarea v-model="materialEditor.note" :auto-size="{ minRows: 3, maxRows: 5 }" />
                </div>
                <div class="rl-form-actions">
                  <a-button type="primary" :disabled="!selectedMaterial" @click="applyMaterialEdit">保存展示修改</a-button>
                  <a-button status="danger" :disabled="!selectedMaterial" @click="deleteMaterialFromView">从视图删除</a-button>
                </div>
              </div>
            </article>

            <article class="rl-section-card workspace-upload-source-card">
              <header class="rl-section-card__header">
                <div>
                  <h3 class="rl-section-card__title workspace-title-with-icon">
                    <icon-upload />
                    <span>上传 / 新建素材</span>
                  </h3>
                  <p class="rl-section-card__desc">先用现有 backend 接口完成上传；编辑与删除先在前端视图层生效。</p>
                </div>
              </header>
              <div class="rl-section-card__body workspace-stack workspace-stack--fill">
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-storage />
                    <span>来源 ID</span>
                  </span>
                  <a-input v-model="sourceUpload.source_id" />
                </div>
                <div class="workspace-form-row workspace-form-row--two">
                  <div class="rl-form-field">
                    <span class="workspace-field-label">
                      <icon-relation />
                      <span>类型</span>
                    </span>
                    <a-select v-model="sourceUpload.source_type">
                      <a-option value="manual_table">manual_table</a-option>
                      <a-option value="structured_records">structured_records</a-option>
                      <a-option value="tep_semantic_lift">tep_semantic_lift</a-option>
                      <a-option value="tep_variable_mapping">tep_variable_mapping</a-option>
                    </a-select>
                  </div>
                  <div class="rl-form-field">
                    <span class="workspace-field-label">
                      <icon-info-circle />
                      <span>格式</span>
                    </span>
                    <a-select v-model="sourceUpload.source_format">
                      <a-option value="csv">csv</a-option>
                      <a-option value="json">json</a-option>
                      <a-option value="jsonl">jsonl</a-option>
                    </a-select>
                  </div>
                </div>
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-bulb />
                    <span>场景</span>
                  </span>
                  <a-input v-model="sourceUpload.scenario" />
                </div>
                <div class="rl-form-field workspace-dropzone-field">
                  <span class="workspace-field-label">
                    <icon-upload />
                    <span>文件</span>
                  </span>
                  <div
                    class="rl-file-dropzone rl-file-dropzone--fill"
                    :class="{ 'rl-file-dropzone--active': sourceUploadDragActive }"
                    @dragenter="handleSourceUploadDragEnter"
                    @dragover="handleSourceUploadDragOver"
                    @dragleave="handleSourceUploadDragLeave"
                    @drop="handleSourceUploadDrop"
                  >
                    <input
                      ref="sourceUploadInputRef"
                      class="rl-file-input-native"
                      type="file"
                      :accept="sourceUploadAccept"
                      @change="handleSourceUploadFileChange"
                    />
                    <div class="rl-file-dropzone__content rl-file-dropzone__content--fill">
                      <div class="rl-file-dropzone__copy">
                        <strong>{{ sourceUpload.file?.name ?? '拖动来源文件到这里，或点击按钮选择文件' }}</strong>
                        <span>{{ sourceUploadAccept }}</span>
                      </div>
                      <a-button size="small" @click="openSourceUploadPicker">选择文件</a-button>
                    </div>
                  </div>
                </div>
                <div class="rl-form-actions">
                  <a-button type="primary" @click="handleSourceUpload">
                    <template #icon>
                      <icon-upload />
                    </template>
                    上传素材
                  </a-button>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="workspace-materials-bottom-grid">
          <article class="rl-section-card workspace-builds-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-relation />
                  <span>构图结果 / 已生成图谱</span>
                </h3>
                <p class="rl-section-card__desc">查看构图批次、节点边数量以及当前默认批次。</p>
              </div>
              <a-tag color="gold">{{ builds?.builds.length ?? 0 }} 次</a-tag>
            </header>
            <div class="rl-section-card__body workspace-table-card workspace-table-card--fill">
              <div class="workspace-table-wrap workspace-table-wrap--builds workspace-table-wrap--fill">
                <table class="workspace-table">
                  <thead>
                    <tr>
                      <th>图谱名</th>
                      <th>来源素材数</th>
                      <th>节点/边</th>
                      <th>状态</th>
                      <th>更新时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="build in builds?.builds ?? []"
                      :key="build.run_id"
                      :class="{ 'workspace-table__row--active': build.run_id === buildDetail?.build.run_id }"
                      @click="loadBuildDetail(build.run_id)"
                    >
                      <td>
                        <strong>{{ build.run_id }}</strong>
                      </td>
                      <td>{{ build.source_count }}</td>
                      <td>{{ build.node_count }} / {{ build.edge_count }}</td>
                      <td>{{ build.status }}</td>
                      <td>{{ formatDateTime(build.created_at) }}</td>
                      <td>
                        <a-button size="mini" type="text" @click.stop="loadBuildDetail(build.run_id)">查看详情</a-button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </article>

          <article class="rl-section-card workspace-build-recipe-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-bulb />
                  <span>构图配方</span>
                </h3>
                <p class="rl-section-card__desc">基于当前勾选素材生成图谱批次，并支持导出当前 build bundle。</p>
              </div>
              <a-tag color="arcoblue">{{ selectedMaterials.length }} 份已选</a-tag>
            </header>
            <div class="rl-section-card__body workspace-stack">
              <div class="workspace-summary-list workspace-summary-list--two-col">
                <div class="workspace-summary-list__item">
                  <span class="workspace-summary-label">
                    <icon-upload />
                    <span>已选素材</span>
                  </span>
                  <strong>{{ selectedMaterials.length }}</strong>
                </div>
                <div class="workspace-summary-list__item">
                  <span class="workspace-summary-label">
                    <icon-storage />
                    <span>默认图谱</span>
                  </span>
                  <strong>{{ buildDetail?.build.run_id ?? '未选择' }}</strong>
                </div>
              </div>
              <div class="rl-form-field">
                <span class="workspace-field-label">
                  <icon-info-circle />
                  <span>输出图谱名</span>
                </span>
                <a-input v-model="buildForm.output_name" />
              </div>
              <div class="rl-form-field">
                <span class="workspace-field-label">
                  <icon-bulb />
                  <span>场景</span>
                </span>
                <a-input v-model="buildForm.scenario" />
              </div>
              <div class="rl-form-actions rl-form-actions--dual">
                <a-button type="primary" @click="handleBuild">生成图谱</a-button>
                <a-button :disabled="!canExportBuild" @click="handleExportBuild">导出到本地</a-button>
              </div>
            </div>
          </article>
        </section>
      </div>
    </section>
  </div>
</template>
