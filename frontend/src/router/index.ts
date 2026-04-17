import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import { pinia } from '@/stores/pinia'
import { useAuthStore } from '@/stores/auth'
import AdminUsersView from '@/views/AdminUsersView.vue'
import DashboardView from '@/views/DashboardView.vue'
import EventsView from '@/views/EventsView.vue'
import LoginView from '@/views/LoginView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import RegisterView from '@/views/RegisterView.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { title: '账号登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterView,
    meta: { title: '账号注册' },
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: DashboardView,
        meta: { requiresAuth: true, requiresAdmin: true, title: '运营看板' },
      },
      {
        path: 'events',
        name: 'events',
        component: EventsView,
        meta: { requiresAuth: true, title: '事件中心' },
      },
      {
        path: 'admin/users',
        name: 'admin-users',
        component: AdminUsersView,
        meta: { requiresAuth: true, requiresAdmin: true, title: '账号管理' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView,
    meta: { title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)
  const isPublicRoute = to.path === '/login' || to.path === '/register'

  if (!authStore.initialized && !isPublicRoute) {
    await authStore.fetchSession(true)
  }

  if (isPublicRoute) {
    if (authStore.isLoggedIn) {
      return authStore.isAdmin ? '/dashboard' : '/events'
    }
    return true
  }

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return {
      path: '/login',
      query: { redirect: to.fullPath },
    }
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return '/events'
  }

  return true
})

router.afterEach((to) => {
  const suffix = '驾驶监测系统'
  const title = typeof to.meta.title === 'string' ? `${to.meta.title} - ${suffix}` : suffix
  document.title = title
})

export default router
