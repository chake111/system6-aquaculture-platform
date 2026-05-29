import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { DensityResult, OperationsRecord, UserRole } from '@/types/domain'
import { DEFAULT_POND_ID } from '@/utils/constants'
import { STORAGE_KEYS } from '@/utils/storage'

import { useAuthStore } from './auth'
import { useObservationsStore } from './observations'
import { useAlertsStore } from './alerts'
import { useReportsStore } from './reports'

interface HealthResponse {
  external_observation_count: number
  components: {
    sync: { status: string; retention_days: number }
    notifications: { status: string; provider_mode: string }
  }
}

interface DensityResponse {
  id: string
  estimated_density_fish_m2: number
  error_margin_fish_m2: number
  model_version: string
  review_status: string
}

export const usePlatformStore = defineStore('platform', () => {
  const auth = useAuthStore()
  const obs = useObservationsStore()
  const alerts = useAlertsStore()
  const reports = useReportsStore()

  const highContrast = ref(sessionStorage.getItem(STORAGE_KEYS.highContrast) === 'true')
  const isOnline = ref(typeof navigator === 'undefined' || navigator.onLine)

  const operations = ref<OperationsRecord[]>([])
  const densityResult = ref<DensityResult | null>(null)

  const operationsLoading = ref(false)
  const densityLoading = ref(false)

  // --- online/offline listeners ---
  if (typeof window !== 'undefined') {
    window.addEventListener('online', () => {
      isOnline.value = true
    })
    window.addEventListener('offline', () => {
      isOnline.value = false
      obs.usingCachedObservations = auth.hasValidOfflineGrant && obs.observations.length > 0
    })
  }

  // --- ui actions ---
  function toggleHighContrast() {
    highContrast.value = !highContrast.value
    sessionStorage.setItem(STORAGE_KEYS.highContrast, String(highContrast.value))
  }

  // --- loading helper ---
  function isLoading(action: string) {
    if (action === 'login') return auth.loginLoading
    if (action === 'loadObservations') return obs.loading
    if (
      action === 'injectLowOxygen' ||
      action === 'loadWorkflow' ||
      action === 'reviewRecommendation' ||
      action === 'confirmRecommendation' ||
      action === 'executeSimulation' ||
      action === 'resolveAlert' ||
      action === 'closeAlert' ||
      action === 'quickResponse'
    )
      return alerts.loading
    if (
      action === 'loadReport' ||
      action === 'exportReport' ||
      action === 'registerArchiveEvidence'
    )
      return reports.loading
    if (action === 'loadOperations') return operationsLoading.value
    if (action === 'analyzeDensity') return densityLoading.value
    return false
  }

  // --- operations ---
  async function loadOperations() {
    operationsLoading.value = true
    try {
      const result = await auth.request<HealthResponse>('/api/v1/operations/health')
      operations.value = [
        {
          component: '官方参考观测',
          status: '可溯源',
          evidence: `${result.external_observation_count} 条官方外部观测`,
        },
        {
          component: '边缘同步',
          status: result.components.sync.status,
          evidence: `保留策略 ${result.components.sync.retention_days} 天`,
        },
        {
          component: '告警通知适配器',
          status: result.components.notifications.status,
          evidence: '短信、钉钉多渠道送达',
        },
      ]
    } catch (e) {
      operations.value = []
      throw e instanceof Error ? e : new Error('运维数据加载出了问题')
    } finally {
      operationsLoading.value = false
    }
  }

  // --- density ---
  async function analyzeDensity() {
    densityLoading.value = true
    try {
      const sample = await auth.request<{ id: string }>('/api/v1/media-samples', {
        method: 'POST',
        body: JSON.stringify({
          pond_id: DEFAULT_POND_ID,
          sample_type: 'sonar',
          object_ref: `sample://${DEFAULT_POND_ID}-sonar`,
          source_mode: 'auto',
        }),
      })
      const analysis = await auth.request<DensityResponse>(
        `/api/v1/media-samples/${sample.id}/analyses`,
        { method: 'POST' },
      )
      const reviewed = await auth.request<DensityResponse>(
        `/api/v1/density-analyses/${analysis.id}/review`,
        {
          method: 'PATCH',
          body: JSON.stringify({ approved: true, comment: '声呐密度采样技术复核' }),
        },
      )
      densityResult.value = {
        estimatedDensityFishM2: reviewed.estimated_density_fish_m2,
        errorMarginFishM2: reviewed.error_margin_fish_m2,
        modelVersion: reviewed.model_version,
        reviewStatus: reviewed.review_status,
      }
    } catch (e) {
      densityResult.value = null
      throw e instanceof Error ? e : new Error('密度分析没跑完')
    } finally {
      densityLoading.value = false
    }
  }

  // --- composed login/logout for backward compat ---
  async function login(selectedRole: UserRole) {
    await auth.login(selectedRole, async () => {
      alerts.resetAlertState()
      try {
        await obs.loadObservations()
      } catch {
        /* views handle retry */
      }
      try {
        await alerts.loadWorkflow()
      } catch {
        /* views handle retry */
      }
      if (auth.role === 'technician' || auth.role === 'admin') {
        try {
          await reports.loadReport()
        } catch {
          /* views handle retry */
        }
      }
      if (auth.role === 'admin') {
        try {
          await loadOperations()
        } catch {
          /* views handle retry */
        }
      }
    })
  }

  function logout() {
    auth.logout()
    alerts.resetAlertState()
  }

  return {
    // re-exports from sub-stores for backward compat
    role: computed(() => auth.role),
    accessToken: computed(() => auth.accessToken),
    displayName: computed(() => auth.displayName),
    offlineGrant: computed(() => auth.offlineGrant),
    hasValidOfflineGrant: computed(() => auth.hasValidOfflineGrant),
    observations: computed(() => obs.observations),
    lastObservationSyncAt: computed(() => obs.lastObservationSyncAt),
    readingsPage: computed(() => obs.readingsPage),
    readingsTotal: computed(() => obs.readingsTotal),
    readingsCurrentPage: computed(() => obs.readingsCurrentPage),
    readingsPageSize: computed(() => obs.readingsPageSize),
    readingsLoading: computed(() => obs.readingsLoading),
    usingCachedObservations: computed({
      get: () => obs.usingCachedObservations,
      set: (v: boolean) => {
        obs.usingCachedObservations = v
      },
    }),
    activeAlert: computed(() => alerts.activeAlert),
    report: computed(() => reports.report),
    exportEvidence: computed(() => reports.exportEvidence),
    archiveEvidence: computed(() => reports.archiveEvidence),
    // own state
    highContrast,
    isOnline,
    operations,
    densityResult,
    // actions
    isLoading,
    login,
    logout,
    toggleHighContrast,
    loadObservations: () => obs.loadObservations(),
    loadReadingsPage: (page: number, pageSize: number) => obs.loadReadingsPage(page, pageSize),
    loadWorkflow: () => useAlertsStore().loadWorkflow(),
    loadReport: () => useReportsStore().loadReport(),
    loadOperations,
    analyzeDensity,
    exportReport: () => useReportsStore().exportReport(),
    registerArchiveEvidence: () => useReportsStore().registerArchiveEvidence(),
    injectLowOxygen: () => useAlertsStore().injectLowOxygen(),
    reviewRecommendation: () => useAlertsStore().reviewRecommendation(),
    confirmRecommendation: () => useAlertsStore().confirmRecommendation(),
    executeSimulation: () => useAlertsStore().executeSimulation(),
    resolveAlert: () => useAlertsStore().resolveAlert(),
    closeAlert: () => useAlertsStore().closeAlert(),
    quickResponse: () => useAlertsStore().quickResponse(),
  }
})
