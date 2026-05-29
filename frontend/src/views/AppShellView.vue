<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Moon, Sunny } from '@element-plus/icons-vue'

import { usePlatformStore } from '@/stores/platform'
import type { UserRole } from '@/types/domain'

interface MenuItem {
  path: string
  label: string
  icon: string
  roles: UserRole[]
}

const route = useRoute()
const router = useRouter()
const store = usePlatformStore()

const menu: MenuItem[] = [
  {
    path: '/agent',
    label: '智能助手',
    icon: 'ChatDotRound',
    roles: ['farmer', 'technician', 'admin'],
  },
  {
    path: '/dashboard',
    label: '综合仪表盘',
    icon: 'Odometer',
    roles: ['farmer', 'technician', 'admin'],
  },
  {
    path: '/monitoring',
    label: '水质监测',
    icon: 'TrendCharts',
    roles: ['farmer', 'technician', 'admin'],
  },
  {
    path: '/density',
    label: '密度调控',
    icon: 'Histogram',
    roles: ['farmer', 'technician', 'admin'],
  },
  { path: '/alerts', label: '预警中心', icon: 'Bell', roles: ['farmer', 'technician', 'admin'] },
  { path: '/reports', label: '效益报表', icon: 'Document', roles: ['technician', 'admin'] },
  { path: '/operations', label: '运维管理', icon: 'Setting', roles: ['admin'] },
]

const availableMenu = computed(() => {
  if (!store.role) return []
  return menu.filter(
    (item) =>
      item.roles.includes(store.role as UserRole) &&
      (store.isOnline || ['/dashboard', '/monitoring', '/agent'].includes(item.path)),
  )
})

const pageTitle = computed(() => String(route.meta.title ?? '综合仪表盘'))

watch(
  () => store.isOnline,
  async (online) => {
    if (!online && !store.hasValidOfflineGrant) {
      await router.replace('/login')
    }
  },
)

watch(
  () => route.path,
  async () => {
    await nextTick()
    const main = document.getElementById('main-content')
    if (main) {
      main.setAttribute('tabindex', '-1')
      main.focus({ preventScroll: true })
    }
  },
)

async function exit() {
  store.logout()
  await router.push('/login')
}
</script>

<template>
  <div v-if="store.role" class="console" :class="{ contrast: store.highContrast }">
    <aside class="sidebar" aria-label="侧边导航">
      <div class="sidebar-brand">
        <img src="/logo.png" alt="" class="sidebar-logo" aria-hidden="true" />
        <div>
          <strong>水产现场台</strong>
          <span>惠州 50 亩基地</span>
        </div>
      </div>
      <nav class="menu" aria-label="业务菜单">
        <RouterLink
          v-for="item in availableMenu"
          :key="item.path"
          class="menu-link"
          :to="item.path"
        >
          <el-icon class="menu-icon" :size="18" aria-hidden="true">
            <component :is="item.icon" />
          </el-icon>
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="sidebar-status">
        <span class="online-dot" aria-hidden="true"></span>
        {{ store.isOnline ? '当前在线' : '当前离线' }}
        <small v-if="store.offlineGrant">离线授权有效期至 {{ store.offlineGrant.expiresAt }}</small>
        <small v-if="store.offlineGrant">仅允许：只读缓存、处置草稿</small>
        <small v-else>未签发离线授权</small>
      </div>
    </aside>

    <main id="main-content" class="workspace">
      <header class="topbar">
        <div>
          <h1>{{ pageTitle }}</h1>
        </div>
        <div class="topbar-actions">
          <button
            class="toggle-button"
            type="button"
            :aria-pressed="store.highContrast"
            :aria-label="store.highContrast ? '关闭高对比模式' : '开启高对比模式'"
            data-test="toggle-contrast"
            @click="store.toggleHighContrast"
          >
            <el-icon :size="18"><Moon v-if="store.highContrast" /><Sunny v-else /></el-icon>
          </button>
          <span class="role-tag">{{ store.displayName }}</span>
          <button
            class="text-button"
            type="button"
            aria-label="退出登录"
            data-test="logout"
            @click="exit"
          >
            退出
          </button>
        </div>
      </header>
      <div class="workspace-content">
        <RouterView />
      </div>
    </main>
  </div>
</template>
