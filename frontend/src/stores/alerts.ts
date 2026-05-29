import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { AlertStatus, OxygenAlert } from '@/types/domain'
import { DEFAULT_POND_ID } from '@/utils/constants'
import { useAuthStore } from './auth'
import { useObservationsStore } from './observations'

interface InjectionResponse {
  reading: { dissolved_oxygen_mg_l: number }
  recommendation: { id: string; status: 'generated' }
  alert: {
    id: string
    source_mode: 'simulation'
    delivery_status: string
    recommendation_id?: string
  }
}

interface RecommendationResponse {
  id: string
  status: AlertStatus
  source_mode: 'simulation'
}

interface AlertResponse {
  id: string
  status: string
  source_mode: 'simulation'
  delivery_status: string
  recommendation_id: string
}

export const useAlertsStore = defineStore('alerts', () => {
  const activeAlert = ref<OxygenAlert | null>(null)
  const executionId = ref<string | null>(null)
  const loading = ref(false)
  let resolveStep = 0

  function isLoading(_action: string) {
    return loading.value
  }

  async function injectLowOxygen() {
    const auth = useAuthStore()
    if (activeAlert.value) {
      throw new Error('已有活跃预警，请先处置当前预警')
    }
    resolveStep = 0
    loading.value = true
    try {
      const injected = await auth.request<InjectionResponse>(
        `/api/v1/demo/ponds/${DEFAULT_POND_ID}/low-oxygen`,
        {
          method: 'POST',
          body: JSON.stringify({ notification_scenario: 'retry_success' }),
        },
      )
      activeAlert.value = {
        id: injected.alert.id,
        title: '低溶氧预警',
        dissolvedOxygenMgL: injected.reading.dissolved_oxygen_mg_l,
        severity: 'high',
        sourceMode: injected.alert.source_mode,
        status: injected.recommendation.status,
        recommendation: '建议启动 1 号增氧机 30 分钟，并安排人工复核读数。',
        executionMode: 'auto',
        recommendationId: injected.recommendation.id,
        deliveryStatus: injected.alert.delivery_status,
      }
    } finally {
      loading.value = false
    }
  }

  async function loadWorkflow() {
    const auth = useAuthStore()
    const obs = useObservationsStore()
    loading.value = true
    try {
      const [recommendations, alerts] = await Promise.all([
        auth.request<RecommendationResponse[]>(`/api/v1/ponds/${DEFAULT_POND_ID}/recommendations`),
        auth.request<AlertResponse[]>('/api/v1/alerts'),
      ])
      const alert = alerts[alerts.length - 1]
      const recommendation = recommendations.find((item) => item.id === alert?.recommendation_id)
      if (!alert || !recommendation) {
        activeAlert.value = null
        resolveStep = 0
        return
      }
      if (obs.observations.length === 0) {
        await obs.loadObservations()
      }
      const latestObs =
        obs.observations.length > 0 ? obs.observations[obs.observations.length - 1] : null
      activeAlert.value = {
        id: alert.id,
        title: '低溶氧预警',
        dissolvedOxygenMgL: latestObs?.dissolvedOxygenMgL ?? 0,
        severity: 'high',
        sourceMode: alert.source_mode,
        status:
          alert.status === 'resolved' || alert.status === 'closed'
            ? (alert.status as AlertStatus)
            : recommendation.status,
        recommendation: '建议启动 1 号增氧机 30 分钟，并安排人工复核读数。',
        executionMode: 'auto',
        recommendationId: recommendation.id,
        deliveryStatus: alert.delivery_status,
      }
    } catch (e) {
      activeAlert.value = null
      resolveStep = 0
      throw e instanceof Error ? e : new Error('工作流数据加载出了问题')
    } finally {
      loading.value = false
    }
  }

  async function reviewRecommendation() {
    const auth = useAuthStore()
    if (!activeAlert.value || activeAlert.value.status !== 'generated') {
      throw new Error('当前状态不对，刷新后再试')
    }
    const recId = activeAlert.value.recommendationId
    const alert = activeAlert.value
    loading.value = true
    try {
      await auth.request(`/api/v1/recommendations/${recId}/review`, {
        method: 'PATCH',
        body: JSON.stringify({ approved: true, comment: '溶氧阈值复核通过' }),
      })
      alert.status = 'reviewed'
    } finally {
      loading.value = false
    }
  }

  async function confirmRecommendation() {
    const auth = useAuthStore()
    if (activeAlert.value?.status !== 'reviewed') {
      throw new Error('当前状态不对，刷新后再试')
    }
    const recId = activeAlert.value.recommendationId
    const alert = activeAlert.value
    loading.value = true
    try {
      await auth.request(`/api/v1/recommendations/${recId}/confirm`, { method: 'POST' })
      alert.status = 'confirmed'
    } finally {
      loading.value = false
    }
  }

  async function executeSimulation() {
    const auth = useAuthStore()
    if (activeAlert.value?.status !== 'confirmed') {
      throw new Error('当前状态不对，刷新后再试')
    }
    const recId = activeAlert.value.recommendationId
    const alert = activeAlert.value
    loading.value = true
    try {
      const execution = await auth.request<{ id: string; status: 'completed' }>(
        `/api/v1/recommendations/${recId}/executions`,
        {
          method: 'POST',
          body: JSON.stringify({ idempotency_key: `ui-${recId}` }),
        },
      )
      executionId.value = execution.id
      alert.status = 'completed'
    } finally {
      loading.value = false
    }
  }

  async function resolveAlert() {
    const auth = useAuthStore()
    if (activeAlert.value?.status !== 'completed' || !executionId.value) {
      throw new Error('当前状态不对，刷新后再试')
    }
    const alertId = activeAlert.value.id
    const alert = activeAlert.value
    const execId = executionId.value
    loading.value = true
    try {
      if (resolveStep < 1) {
        try {
          await auth.request(`/api/v1/executions/${execId}/feedback`, {
            method: 'PATCH',
            body: JSON.stringify({ dissolved_oxygen_mg_l: 6.3, note: '增氧处置后现场复核' }),
          })
        } catch {
          throw new Error('效果反馈没提交上去')
        }
        resolveStep = 1
      }
      if (resolveStep < 2) {
        try {
          await auth.request(`/api/v1/alerts/${alertId}/acknowledge`, { method: 'POST' })
        } catch {
          throw new Error('告警没确认成功')
        }
        resolveStep = 2
      }
      if (resolveStep < 3) {
        try {
          await auth.request(`/api/v1/alerts/${alertId}/resolve`, {
            method: 'POST',
            body: JSON.stringify({ resolution: '增氧处置完成，溶氧已恢复' }),
          })
        } catch {
          throw new Error('告警没处置完')
        }
      }
      resolveStep = 0
      alert.status = 'resolved'
    } finally {
      loading.value = false
    }
  }

  async function closeAlert() {
    const auth = useAuthStore()
    if (activeAlert.value?.status !== 'resolved') {
      throw new Error('当前状态不对，刷新后再试')
    }
    const alertId = activeAlert.value.id
    const alert = activeAlert.value
    loading.value = true
    try {
      await auth.request(`/api/v1/alerts/${alertId}/close`, { method: 'POST' })
      alert.status = 'closed'
    } finally {
      loading.value = false
    }
  }

  async function quickResponse() {
    const auth = useAuthStore()
    if (!activeAlert.value || activeAlert.value.status !== 'generated') {
      throw new Error('当前状态不对，刷新后再试')
    }
    const alertId = activeAlert.value.id
    const alert = activeAlert.value
    loading.value = true
    try {
      await auth.request(`/api/v1/alerts/${alertId}/quick-response`, { method: 'POST' })
      alert.status = 'closed'
    } finally {
      loading.value = false
    }
  }

  function resetAlertState() {
    activeAlert.value = null
    executionId.value = null
    resolveStep = 0
  }

  return {
    activeAlert,
    executionId,
    loading,
    isLoading,
    injectLowOxygen,
    loadWorkflow,
    reviewRecommendation,
    confirmRecommendation,
    executeSimulation,
    resolveAlert,
    closeAlert,
    quickResponse,
    resetAlertState,
  }
})
