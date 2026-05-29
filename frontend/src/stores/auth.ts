import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { OfflineGrant, OfflinePermission, UserRole } from '@/types/domain'
import { STORAGE_KEYS, storedValue } from '@/utils/storage'
import { createRequest } from '@/utils/api'

interface AuthResponse {
  access_token: string
  role: UserRole
}

interface OfflineGrantResponse {
  max_days: number
  permissions: OfflinePermission[]
  pond_scope: string[]
  expires_at: string
  signed_grant: string
}

const accounts: Record<UserRole, string> = {
  farmer: '13800000001',
  technician: '13800000002',
  admin: '13800000003',
}

export const useAuthStore = defineStore('auth', () => {
  const role = ref<UserRole | null>(sessionStorage.getItem(STORAGE_KEYS.role) as UserRole | null)
  const accessToken = ref<string | null>(sessionStorage.getItem(STORAGE_KEYS.token))
  const offlineGrant = ref<OfflineGrant | null>(
    storedValue<OfflineGrant>(STORAGE_KEYS.offlineGrant),
  )
  const loginLoading = ref(false)

  const displayName = computed(() => {
    const names: Record<UserRole, string> = {
      farmer: '养殖户',
      technician: '技术员',
      admin: '管理员',
    }
    return role.value ? names[role.value] : '访客'
  })

  const hasValidOfflineGrant = computed(
    () =>
      offlineGrant.value !== null &&
      offlineGrant.value.permissions.includes('read_cached_dashboard') &&
      Date.parse(offlineGrant.value.expiresAt) > Date.now(),
  )

  function clearSession() {
    role.value = null
    accessToken.value = null
    sessionStorage.removeItem(STORAGE_KEYS.role)
    sessionStorage.removeItem(STORAGE_KEYS.token)
  }

  const request = createRequest(
    () => accessToken.value,
    () => {
      clearSession()
      window.location.href = '/login'
    },
  )

  async function login(selectedRole: UserRole, afterLogin: () => Promise<void>) {
    loginLoading.value = true
    try {
      const authenticated = await request<AuthResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ phone: accounts[selectedRole], credential: 'demo-246810' }),
      })
      role.value = authenticated.role
      accessToken.value = authenticated.access_token
      sessionStorage.setItem(STORAGE_KEYS.role, authenticated.role)
      sessionStorage.setItem(STORAGE_KEYS.token, authenticated.access_token)

      const grant = await request<OfflineGrantResponse>('/api/v1/auth/offline-grants', {
        method: 'POST',
      })
      offlineGrant.value = {
        maxDays: grant.max_days,
        permissions: grant.permissions,
        pondScope: grant.pond_scope,
        expiresAt: grant.expires_at,
        signedGrant: grant.signed_grant,
      }
      sessionStorage.setItem(STORAGE_KEYS.offlineGrant, JSON.stringify(offlineGrant.value))

      await afterLogin()
    } finally {
      loginLoading.value = false
    }
  }

  function logout() {
    role.value = null
    accessToken.value = null
    offlineGrant.value = null
    sessionStorage.removeItem(STORAGE_KEYS.role)
    sessionStorage.removeItem(STORAGE_KEYS.token)
    sessionStorage.removeItem(STORAGE_KEYS.offlineGrant)
  }

  return {
    role,
    accessToken,
    offlineGrant,
    loginLoading,
    displayName,
    hasValidOfflineGrant,
    request,
    login,
    logout,
    clearSession,
  }
})
