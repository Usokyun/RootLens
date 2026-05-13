<script setup lang="ts">
import { computed, ref } from 'vue'

interface MaterialItem {
  id: string
  name: string
  type: 'graph' | 'image' | 'text' | 'json'
  summary: string
  role: string
}

interface GraphSummary {
  id: string
  name: string
  source: string
  nodes: number
  edges: number
  builtAt: string
}

const keyword = ref('')
const filterType = ref<'all' | MaterialItem['type']>('all')
const selectedMaterialIds = ref<string[]>(['tep-nodes', 'tep-edges'])

const materialItems: MaterialItem[] = [
  {
    id: 'tep-nodes',
    name: 'nodes.jsonl',
    type: 'graph',
    summary: '140 rows',
    role: 'layer: rca-node',
  },
  {
    id: 'tep-edges',
    name: 'edges.jsonl',
    type: 'graph',
    summary: '252 rows',
    role: 'layer: rca-edge',
  },
  {
    id: 'mvtec-image',
    name: 'bottle_001.png',
    type: 'image',
    summary: '512 x 512',
    role: 'image sample',
  },
  {
    id: 'tep-log',
    name: 'tep_fault_log.txt',
    type: 'text',
    summary: '1.2 KB',
    role: 'raw log text',
  },
  {
    id: 'mvtec-nodes',
    name: 'mvtec_nodes.csv',
    type: 'graph',
    summary: '85 rows',
    role: 'layer: mvtec-node',
  },
  {
    id: 'mvtec-edges',
    name: 'mvtec_edges.csv',
    type: 'graph',
    summary: '140 rows',
    role: 'layer: mvtec-edge',
  },
  {
    id: 'case-import',
    name: 'runtime_case_bundle.json',
    type: 'json',
    summary: '4 cases',
    role: 'session bundle',
  },
]

const builtGraphs: GraphSummary[] = [
  {
    id: 'tep-kg',
    name: 'TEP_KG RCA Graph',
    source: 'nodes.jsonl + edges.jsonl',
    nodes: 140,
    edges: 252,
    builtAt: '2026-05-12 22:18',
  },
  {
    id: 'mvtec-runtime',
    name: 'MVTec Runtime KG',
    source: 'mvtec_nodes.csv + mvtec_edges.csv',
    nodes: 85,
    edges: 140,
    builtAt: '2026-05-12 22:27',
  },
]

const filteredMaterials = computed(() => {
  const search = keyword.value.trim().toLowerCase()

  return materialItems.filter((item) => {
    const matchType = filterType.value === 'all' || item.type === filterType.value
    const matchKeyword = !search || item.name.toLowerCase().includes(search)

    return matchType && matchKeyword
  })
})

const selectedCount = computed(() => selectedMaterialIds.value.length)

function toggleMaterialSelection(id: string) {
  if (selectedMaterialIds.value.includes(id)) {
    selectedMaterialIds.value = selectedMaterialIds.value.filter((item) => item !== id)
    return
  }

  selectedMaterialIds.value = [...selectedMaterialIds.value, id]
}

function resolveTypeLabel(type: MaterialItem['type']) {
  switch (type) {
    case 'graph':
      return '图谱'
    case 'image':
      return '图像'
    case 'text':
      return '文本'
    case 'json':
      return 'JSON'
    default:
      return type
  }
}

function resolveTagColor(type: MaterialItem['type']) {
  switch (type) {
    case 'graph':
      return 'arcoblue'
    case 'image':
      return 'orangered'
    case 'text':
      return 'green'
    case 'json':
      return 'purple'
    default:
      return 'gray'
  }
}
</script>

<template>
  <div class="rl-page materials-page">
    <section class="rl-section-card">
      <header class="rl-section-card__header">
        <h3 class="rl-section-card__title">导入区</h3>
        <a-space>
          <a-button type="primary">上传文件</a-button>
          <a-button>恢复历史会话</a-button>
          <a-button status="success">切换到内置 Demo</a-button>
        </a-space>
      </header>
      <div class="rl-section-card__body">
        <div class="materials-import-dropzone">
          <h4>拖拽文件到此区域，或点击上传</h4>
          <p>支持 .csv / .jsonl / .json / .png / .txt 等多模态素材</p>
          <div class="materials-import-tags">
            <a-tag>图谱素材</a-tag>
            <a-tag color="orangered">图像素材</a-tag>
            <a-tag color="green">日志与文本</a-tag>
            <a-tag color="purple">Session Bundle</a-tag>
          </div>
        </div>
      </div>
    </section>

    <section class="rl-section-card">
      <header class="rl-section-card__header">
        <h3 class="rl-section-card__title">素材库</h3>
        <a-space>
          <a-input-search
            v-model="keyword"
            :style="{ width: '220px' }"
            placeholder="按文件名搜索"
            allow-clear
          />
          <a-select v-model="filterType" :style="{ width: '140px' }">
            <a-option value="all">全部类型</a-option>
            <a-option value="graph">图谱</a-option>
            <a-option value="image">图像</a-option>
            <a-option value="text">文本</a-option>
            <a-option value="json">JSON</a-option>
          </a-select>
          <a-tag color="arcoblue">已选中 {{ selectedCount }} 项</a-tag>
        </a-space>
      </header>
      <div class="rl-section-card__body">
        <div class="material-grid">
          <article
            v-for="item in filteredMaterials"
            :key="item.id"
            class="material-card"
            :class="{ 'material-card--selected': selectedMaterialIds.includes(item.id) }"
            @click="toggleMaterialSelection(item.id)"
          >
            <div class="material-card__header">
              <a-checkbox
                :model-value="selectedMaterialIds.includes(item.id)"
                @change="toggleMaterialSelection(item.id)"
                @click.stop
              />
              <a-tag :color="resolveTagColor(item.type)">{{ resolveTypeLabel(item.type) }}</a-tag>
            </div>
            <h4 class="material-card__title">{{ item.name }}</h4>
            <p class="material-card__meta">{{ item.summary }}</p>
            <p class="material-card__meta">{{ item.role }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="rl-section-card">
      <header class="rl-section-card__header">
        <h3 class="rl-section-card__title">已构建图谱</h3>
        <a-button>刷新列表</a-button>
      </header>
      <div class="rl-section-card__body built-graph-list">
        <article v-for="graph in builtGraphs" :key="graph.id" class="built-graph-item">
          <div>
            <h4>{{ graph.name }}</h4>
            <p>来源：{{ graph.source }}</p>
            <p>构建时间：{{ graph.builtAt }}</p>
          </div>
          <div class="built-graph-item__stats">
            <span>nodes: {{ graph.nodes }}</span>
            <span>edges: {{ graph.edges }}</span>
            <a-button type="text">查看</a-button>
          </div>
        </article>
      </div>
    </section>

    <footer class="materials-footer-action">
      <a-space>
        <a-button type="primary" :disabled="selectedCount === 0">构建图谱</a-button>
        <span>基于已选素材触发构建，后续将接入实际逻辑函数。</span>
      </a-space>
    </footer>
  </div>
</template>

<style scoped>
.materials-page {
  padding-bottom: 18px;
}

.materials-import-dropzone {
  border: 1px dashed #94b6ff;
  border-radius: 12px;
  background: #f6f9ff;
  padding: 32px;
  text-align: center;
}

.materials-import-dropzone h4 {
  margin: 0;
  font-size: 18px;
}

.materials-import-dropzone p {
  margin: 10px 0 0;
  color: #4e5969;
}

.materials-import-tags {
  margin-top: 18px;
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.material-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.material-card {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
  cursor: pointer;
  transition: all 0.16s ease;
}

.material-card:hover {
  border-color: #94b6ff;
  transform: translateY(-1px);
}

.material-card--selected {
  border-color: #3f7cff;
  box-shadow: 0 0 0 1px rgba(63, 124, 255, 0.2);
  background: #f7faff;
}

.material-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.material-card__title {
  margin: 14px 0 8px;
  font-size: 15px;
}

.material-card__meta {
  margin: 4px 0;
  color: #86909c;
  font-size: 13px;
  line-height: 1.5;
}

.built-graph-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.built-graph-item {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  background: #fff;
  padding: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.built-graph-item h4 {
  margin: 0 0 8px;
}

.built-graph-item p {
  margin: 3px 0;
  color: #4e5969;
  font-size: 13px;
}

.built-graph-item__stats {
  min-width: 180px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  color: #4e5969;
  font-size: 13px;
}

.materials-footer-action {
  border: 1px solid #dfe3ea;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.86);
  padding: 12px 14px;
  color: #4e5969;
}

@media (max-width: 768px) {
  .materials-import-dropzone {
    padding: 24px 14px;
  }

  .built-graph-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .built-graph-item__stats {
    min-width: 0;
    align-items: flex-start;
  }
}
</style>
