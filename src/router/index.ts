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
        label: '运行与证据',
        description: '上传运行、浏览 run / case / observation，并导入回放资产。',
        tags: ['Run Upload', 'Observation Browse', 'Replay Import'],
      },
    },
    {
      path: '/graphs',
      name: 'graphs',
      component: () => import('@/views/GraphExploreView.vue'),
      meta: {
        label: '根因与图谱',
        description: '围绕根因候选浏览总图、子图、路径与反馈链路。',
        tags: ['Root Cause', 'Graph Explore', 'Feedback Review'],
      },
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
