import { createRouter, createWebHistory } from 'vue-router'

import { STORAGE_KEYS } from '@/utils/storage'
import AppShellView from '@/views/AppShellView.vue'
import LoginView from '@/views/LoginView.vue'
import AgentView from '@/views/AgentView.vue'
import DashboardView from '@/views/DashboardView.vue'
import MonitoringView from '@/views/MonitoringView.vue'
import AlertsView from '@/views/AlertsView.vue'
import ReportsView from '@/views/ReportsView.vue'
import OperationsView from '@/views/OperationsView.vue'
import DensityView from '@/views/DensityView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/login',
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: '登录' },
    },
    {
      path: '/',
      component: AppShellView,
      children: [
        {
          path: 'agent',
          name: 'agent',
          component: AgentView,
          meta: { title: '智能助手', roles: ['farmer', 'technician', 'admin'] },
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardView,
          meta: { title: '综合仪表盘', roles: ['farmer', 'technician', 'admin'] },
        },
        {
          path: 'monitoring',
          name: 'monitoring',
          component: MonitoringView,
          meta: { title: '水质监测', roles: ['farmer', 'technician', 'admin'] },
        },
        {
          path: 'alerts',
          name: 'alerts',
          component: AlertsView,
          meta: { title: '预警中心', roles: ['farmer', 'technician', 'admin'] },
        },
        {
          path: 'reports',
          name: 'reports',
          component: ReportsView,
          meta: { title: '效益报表', roles: ['technician', 'admin'] },
        },
        {
          path: 'operations',
          name: 'operations',
          component: OperationsView,
          meta: { title: '运维管理', roles: ['admin'] },
        },
        {
          path: 'density',
          name: 'density',
          component: DensityView,
          meta: { title: '密度调控', roles: ['farmer', 'technician', 'admin'] },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (to.path === '/login') return true

  const role = sessionStorage.getItem(STORAGE_KEYS.role)
  if (!role) return { path: '/login' }

  const isOnline = typeof navigator === 'undefined' || navigator.onLine

  if (!isOnline) {
    const grantRaw = sessionStorage.getItem(STORAGE_KEYS.offlineGrant)
    if (!grantRaw) return { path: '/login' }
    try {
      const grant = JSON.parse(grantRaw)
      if (
        !grant.permissions?.includes('read_cached_dashboard') ||
        Date.parse(grant.expiresAt) <= Date.now()
      ) {
        return { path: '/login' }
      }
    } catch {
      return { path: '/login' }
    }
    const offlineAllowed = ['/dashboard', '/monitoring', '/agent']
    if (!offlineAllowed.includes(to.path)) {
      return { path: '/dashboard' }
    }
  }

  const allowedRoles = to.meta.roles as string[] | undefined
  if (allowedRoles && !allowedRoles.includes(role)) {
    return { path: '/dashboard' }
  }

  return true
})

export default router
