import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '登录 - Openlist-Ani WebUI' },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { title: '仪表盘 - Openlist-Ani WebUI' },
    },
    {
      path: '/downloads',
      name: 'downloads',
      component: () => import('@/views/DownloadsView.vue'),
      meta: { title: '下载管理 - Openlist-Ani WebUI' },
    },
    {
      path: '/recognition',
      name: 'recognition',
      component: () => import('@/views/RecognitionView.vue'),
      meta: { title: '番剧识别 - Openlist-Ani WebUI' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { title: '系统设置 - Openlist-Ani WebUI' },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/downloads',
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) {
    await auth.checkSession()
  }

  if (to.meta.public) {
    if (auth.authenticated && to.name === 'login') {
      return { name: 'downloads' }
    }
    return true
  }

  if (!auth.authenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  return true
})

router.afterEach((to) => {
  if (typeof to.meta.title === 'string') {
    document.title = to.meta.title
  }
})

export default router
