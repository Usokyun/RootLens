import { createRouter, createWebHistory } from 'vue-router'

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
      component: () => import('@/views/EvidenceManageView.vue'),
      meta: {
        label: '证据管理',
        description: '管理 case 与 observation，审查并编辑统一 Evidence。',
      },
    },
    {
      path: '/graphs',
      name: 'graphs',
      component: () => import('@/views/GraphExploreView.vue'),
      meta: {
        label: '图谱探索',
        description: '图谱可视化、RCA 双路线结果、反馈与编辑入口。',
      },
    },
    {
      path: '/materials',
      name: 'materials',
      component: () => import('@/views/MaterialsManageView.vue'),
      meta: {
        label: '素材管理',
        description: '导入多模态素材、管理素材库并发起图谱构建。',
      },
    },
  ],
  scrollBehavior() {
    return {
      top: 0,
    }
  },
})
