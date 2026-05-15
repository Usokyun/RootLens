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
        label: '证据与审阅',
        description: '上传 record、查看运行状态，并按 run / graph 筛选 Evidence。',
        tags: ['Run Upload', 'Evidence Filter', 'Case Review'],
      },
    },
    {
      path: '/graphs',
      name: 'graphs',
      component: () => import('@/views/GraphExploreView.vue'),
      meta: {
        label: '图谱探索',
        description: '总图谱、path_graph 子图、根因列表与反馈卡。',
        tags: ['Total Graph', 'Path Graph', 'Feedback Review'],
      },
    },
    {
      path: '/materials',
      name: 'materials',
      component: () => import('@/views/MaterialsManageView.vue'),
      meta: {
        label: '图谱工坊',
        description: '管理图谱素材、排序筛选、批量构图与构建结果。',
        tags: ['Materials CRUD', 'Graph Build', 'Build Result'],
      },
    },
  ],
  scrollBehavior() {
    return {
      top: 0,
    }
  },
})
