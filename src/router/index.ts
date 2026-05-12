import { createRouter, createWebHistory } from 'vue-router'

import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: WorkspaceLayout,
      redirect: '/import',
      children: [
        {
          path: 'overview',
          redirect: {
            name: 'import',
          },
        },
        {
          path: 'source-map',
          redirect: {
            name: 'import',
          },
        },
        {
          path: 'architecture',
          redirect: {
            name: 'import',
          },
        },
        {
          path: 'roadmap',
          redirect: {
            name: 'import',
          },
        },
        {
          path: 'import',
          name: 'import',
          component: () => import('@/views/ImportWorkbenchView.vue'),
          meta: {
            label: '系统入口',
            description: '导入本地文件，构建浏览器会话，并驱动后续图谱、Evidence 与 RCA 可视化。',
          },
        },
        {
          path: 'graphs',
          name: 'graphs',
          component: () => import('@/views/KnowledgeGraphsView.vue'),
          meta: {
            label: '图谱可视化',
            description: '统一格式后的图谱渲染、切换、搜索与结构检查。',
          },
        },
        {
          path: 'evidence',
          name: 'evidence',
          component: () => import('@/views/EvidenceWorkbenchView.vue'),
          meta: {
            label: 'Evidence 审查',
            description: '统一 Evidence contract 浏览、facet 筛选与本地 draft case 对照。',
          },
        },
        {
          path: 'reasoning',
          name: 'reasoning',
          component: () => import('@/views/ReasoningWorkbenchView.vue'),
          meta: {
            label: 'RCA 分析',
            description: '路线 1 / 路线 2 对比、what-if 回放、人工反馈与 cross-route signals。',
          },
        },
      ],
    },
  ],
  scrollBehavior() {
    return {
      top: 0,
    }
  },
})
