import { createRouter, createWebHistory } from 'vue-router'
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/materials' },
    { path: '/materials', name: 'materials', component: () => import('@/views/MaterialsManageView.vue'), meta: { label: '素材管理' } },
    { path: '/graphs', name: 'graphs', component: () => import('@/views/GraphExploreView.vue'), meta: { label: '知识图谱' } },
    { path: '/evidence', name: 'evidence', component: () => import('@/views/EvidenceManageView.vue'), meta: { label: '推理分析' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
