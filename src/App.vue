<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import zhCN from '@arco-design/web-vue/es/locale/lang/zh-cn'
import { IconBook, IconRelation, IconExperiment, IconArrowRight, IconSettings, IconRefresh, IconCheckCircle, IconExclamationCircle } from '@arco-design/web-vue/es/icon'
import { workspace, currentGraph, refreshWorkspace, setBackend } from '@/services/workspace'
import { newAnalysisRoute } from '@/services/analysis-entry'
import { friendly } from '@/services/presentation'
const route = useRoute()
const settingsOpen = ref(false)
const backendUrl = ref(workspace.baseUrl)
const settingsError = ref('')
const navigation = [
  { name: 'materials', path: '/materials', number: '01', title: '素材管理', description: '导入资料，制作知识', icon: IconBook },
  { name: 'graphs', path: '/graphs', number: '02', title: '知识图谱', description: '理解、修改与启用', icon: IconRelation },
  { name: 'evidence', path: '/evidence', number: '03', title: '推理分析', description: '从样本找到解释', icon: IconExperiment },
]
const activeTasks = computed(() => workspace.tasks.filter((t) => ['running', 'queued'].includes(t.status)).length)
async function connect() {
  settingsError.value = ''
  try {
    const url = new URL(backendUrl.value)
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error('请输入 HTTP 或 HTTPS 服务地址。')
    setBackend(url.origin); await refreshWorkspace()
    if (workspace.connected) settingsOpen.value = false
    else settingsError.value = workspace.error
  } catch (error) { settingsError.value = error instanceof Error ? error.message : String(error) }
}
onMounted(refreshWorkspace)
</script>
<template>
  <a-config-provider size="medium" :locale="zhCN">
    <div class="app-shell">
      <aside class="app-rail">
        <RouterLink to="/materials" class="brand" aria-label="RootLens 首页"><span class="brand-mark"><span /><span /><span /></span><span>RootLens<small>知识与证据工作台</small></span></RouterLink>
        <div class="rail-label">工作空间</div>
        <nav class="main-nav" aria-label="主导航">
          <RouterLink v-for="item in navigation" :key="item.name" :to="item.path" :class="{ active: route.name === item.name }"><component :is="item.icon" /><span><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span><span class="nav-number">{{ item.number }}</span></RouterLink>
        </nav>
        <section class="rail-guide"><span class="eyebrow">两条路径，一个工作台</span><p>资料 <IconArrowRight /> 可用知识</p><p>样本 <IconArrowRight /> 可追溯解释</p></section>
        <div class="rail-bottom"><span class="rail-label">当前工作图</span><strong>{{ currentGraph ? friendly(currentGraph.title, '当前知识图谱') : '尚未选择图谱' }}</strong><span v-if="currentGraph" class="status-dot" :class="currentGraph.enabled ? 'status-dot--green' : 'status-dot--amber'">{{ currentGraph.enabled ? '已投入使用' : '待投入使用' }}</span><RouterLink :to="currentGraph?.enabled ? newAnalysisRoute(currentGraph.graph_id) : '/graphs'" class="text-button">{{ currentGraph?.enabled ? '使用此图分析' : '前往知识图谱' }} <IconArrowRight /></RouterLink></div>
      </aside>
      <div class="app-main">
        <header class="app-topbar"><div class="topbar-context"><span class="context-dot" />工业异常分析<span class="context-divider">/</span><strong>{{ route.meta.label }}</strong></div><div class="topbar-actions"><span v-if="activeTasks" class="running-label"><IconRefresh class="is-spinning" /> {{ activeTasks }} 项任务处理中</span><button class="connection-button" @click="backendUrl = workspace.baseUrl; settingsOpen = true"><IconCheckCircle v-if="workspace.connected" class="success-text" /><IconExclamationCircle v-else class="warning-text" /><span>{{ workspace.connected ? '后端已连接' : workspace.loading ? '正在连接…' : '后端未连接' }}</span><IconSettings /></button></div></header>
        <main class="app-content">
          <div v-if="workspace.error && !settingsOpen" class="alert alert--error global-connection-error"><IconExclamationCircle /><span>无法连接工作台服务：{{ workspace.error }}</span><button class="text-button" :disabled="workspace.loading" @click="refreshWorkspace">重新连接</button><button class="text-button" @click="settingsOpen = true">设置地址</button></div>
          <RouterView />
        </main>
      </div>
      <a-modal v-model:visible="settingsOpen" title="连接后端服务" :footer="false" width="520px">
        <form class="form-stack" @submit.prevent="connect"><p class="muted">资料解析、知识制作、模型测量与推理均在后端执行。</p><label class="field">服务地址<input v-model="backendUrl" type="url" required placeholder="http://127.0.0.1:8000" /></label><p v-if="settingsError" class="error-text">{{ settingsError }}</p><div class="button-row justify-end"><button type="button" class="button button--ghost" @click="settingsOpen = false">取消</button><button class="button button--primary" :disabled="workspace.loading">{{ workspace.loading ? '正在连接…' : '连接服务' }}</button></div></form>
      </a-modal>
    </div>
  </a-config-provider>
</template>
