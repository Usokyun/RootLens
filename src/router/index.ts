import { createRouter, createWebHistory } from 'vue-router'
import { graphRunRedirect } from '@/services/working-graph-workspace'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/evidence',
    },
    {
      path: '/evidence',
      name: 'evidence',
      component: () => import('@/views/EvidenceHomeView.vue'),
      meta: { label: '运行与证据', description: '发起分析、查看任务与历史记录。' },
    },
    {
      path: '/evidence/runs/:runId',
      name: 'saved-analysis',
      component: () => import('@/views/SavedAnalysisDetailView.vue'),
      meta: { label: '运行与证据', description: '打开本次保存的输入、证据与解释。' },
    },
    {
      path: '/graphs',
      name: 'graphs',
      component: () => import('@/views/GraphHomeView.vue'),
      meta: {
        label: '根因与图谱',
        description: '选择、检查和编辑当前工作图。',
      },
    },
    {
      path: '/graphs/archive',
      name: 'graph-archive',
      component: () => import('@/views/GraphArchiveView.vue'),
      meta: { label: '旧运行档案', description: '只读查看既有运行及其路径。' },
    },
    {
      path: '/materials',
      name: 'materials',
      component: () => import('@/views/MaterialsManageView.vue'),
      meta: {
        label: '素材与构图',
        description: '管理素材、执行抽取与构图，并查看构图结果与审阅队列。',
        tags: ['Material Library', 'Graph Build', 'Review Queue'],
      },
    },
  ],
  scrollBehavior() {
    return {
      top: 0,
    }
  },
})

router.beforeEach(to => to.name === 'graphs' ? graphRunRedirect(to.query) ?? undefined : undefined)
