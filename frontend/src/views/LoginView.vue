<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Moon, Sunny } from '@element-plus/icons-vue'

import { usePlatformStore } from '@/stores/platform'
import type { UserRole } from '@/types/domain'

const store = usePlatformStore()
const router = useRouter()
const loginError = ref<string | null>(null)

const accounts: Array<{ role: UserRole; name: string; detail: string }> = [
  { role: 'farmer', name: '养殖户', detail: '现场告警处置与反馈' },
  { role: 'technician', name: '技术员', detail: '读数复核与分析报告' },
  { role: 'admin', name: '管理员', detail: '审计与运维证据' },
]

async function enterDashboard(role: UserRole) {
  if (store.isLoading('login')) return
  loginError.value = null
  try {
    await store.login(role)
    await router.push('/dashboard')
  } catch (e) {
    loginError.value = e instanceof Error ? e.message : '登录没成功，检查下网络'
  }
}
</script>

<template>
  <main id="main-content" class="login-page" :class="{ contrast: store.highContrast }">
    <section class="login-intro">
      <img src="/logo.png" alt="" class="brand-logo" aria-hidden="true" />
      <h1>智慧水产养殖监测与调控平台</h1>
    </section>

    <section class="login-panel" aria-label="账号登录">
      <header class="login-panel-header">
        <div>
          <h2>选择角色</h2>
        </div>
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
      </header>
      <p class="field-hint" data-test="connectivity-state">
        {{ store.isOnline ? '当前在线，可登录并签发离线授权' : '当前离线，仅可读取已有缓存授权' }}
      </p>
      <div class="role-grid" role="group" aria-label="可选角色">
        <article
          v-for="account in accounts"
          :key="account.role"
          class="role-card"
          data-test="role-login"
        >
          <button
            class="role-button"
            type="button"
            :disabled="store.isLoading('login')"
            :data-test="`login-${account.role}`"
            @click="enterDashboard(account.role)"
          >
            <strong>{{ account.name }}</strong>
            <span>{{ account.detail }}</span>
            <small>
              <span
                v-if="store.isLoading('login')"
                class="is-loading login-spinner"
                aria-hidden="true"
              />
              {{ store.isLoading('login') ? '登录中...' : '进入控制台' }}
            </small>
          </button>
        </article>
      </div>

      <p v-if="loginError" class="login-error" role="alert" data-test="login-error">
        {{ loginError }}
      </p>
    </section>
  </main>
</template>

<style scoped>
.login-spinner {
  display: inline-block;
  width: var(--spinner-size);
  height: var(--spinner-size);
  border: 2px solid var(--accent-dark);
  border-top-color: transparent;
  border-radius: 50%;
  margin-right: var(--sp-2);
  vertical-align: middle;
  animation: spin 1s linear infinite;
}
.login-error {
  margin-top: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--font-base);
  text-align: center;
}
</style>
