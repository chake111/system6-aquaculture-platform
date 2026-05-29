import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { Observation } from '@/types/domain'
import { STORAGE_KEYS, storedValue } from '@/utils/storage'
import { useAuthStore } from './auth'

interface ReadingResponse {
  id: string
  captured_at: string
  dissolved_oxygen_mg_l: number
  ph: number
  source_mode: 'external_observation'
  verified: true
  quality_status: 'provisional'
  source_qualifiers: 'P'
}

interface ObservationCache {
  observations: Observation[]
  syncedAt: string
}

interface PagedReadingsResponse {
  items: ReadingResponse[]
  total: number
  page: number
  page_size: number
}

export const useObservationsStore = defineStore('observations', () => {
  const cachedObservations = storedValue<ObservationCache>(STORAGE_KEYS.observationCache)
  const observations = ref<Observation[]>(cachedObservations?.observations ?? [])
  const lastObservationSyncAt = ref<string | null>(cachedObservations?.syncedAt ?? null)
  const usingCachedObservations = ref(false)
  const loading = ref(false)

  // paginated readings for the table
  const readingsPage = ref<Observation[]>([])
  const readingsTotal = ref(0)
  const readingsCurrentPage = ref(1)
  const readingsPageSize = ref(50)
  const readingsLoading = ref(false)

  function latestDo(): number | null {
    if (observations.value.length === 0) return null
    return observations.value[observations.value.length - 1]!.dissolvedOxygenMgL
  }

  function latestPh(): number | null {
    if (observations.value.length === 0) return null
    return observations.value[observations.value.length - 1]!.ph
  }

  async function loadObservations() {
    const auth = useAuthStore()
    loading.value = true
    try {
      if (!navigator.onLine) {
        usingCachedObservations.value = auth.hasValidOfflineGrant && observations.value.length > 0
        if (!auth.hasValidOfflineGrant) observations.value = []
        return
      }
      try {
        const result = await auth.request<{ items: ReadingResponse[] }>(
          '/api/v1/ponds/pond-ref/readings',
        )
        observations.value = result.items.map(mapReading)
        lastObservationSyncAt.value = new Date().toISOString()
        usingCachedObservations.value = false
        sessionStorage.setItem(
          STORAGE_KEYS.observationCache,
          JSON.stringify({
            observations: observations.value,
            syncedAt: lastObservationSyncAt.value,
          } satisfies ObservationCache),
        )
      } catch (e) {
        usingCachedObservations.value = observations.value.length > 0
        throw e instanceof Error ? e : new Error('观测数据没拉到')
      }
    } finally {
      loading.value = false
    }
  }

  function mapReading(reading: ReadingResponse): Observation {
    return {
      id: reading.id,
      capturedAt: reading.captured_at,
      dissolvedOxygenMgL: reading.dissolved_oxygen_mg_l,
      ph: reading.ph,
      station: 'USGS 01463500' as const,
      sourceMode: reading.source_mode,
      sourceVerified: reading.verified,
      qualityStatus: reading.quality_status,
      sourceQualifiers: reading.source_qualifiers,
    }
  }

  async function loadReadingsPage(page: number, pageSize: number) {
    const auth = useAuthStore()
    readingsLoading.value = true
    try {
      const result = await auth.request<PagedReadingsResponse>(
        `/api/v1/ponds/pond-ref/readings?page=${page}&page_size=${pageSize}`,
      )
      readingsPage.value = result.items.map(mapReading)
      readingsTotal.value = result.total
      readingsCurrentPage.value = result.page
      readingsPageSize.value = result.page_size
    } catch {
      readingsPage.value = []
    } finally {
      readingsLoading.value = false
    }
  }

  return {
    observations,
    lastObservationSyncAt,
    usingCachedObservations,
    loading,
    readingsPage,
    readingsTotal,
    readingsCurrentPage,
    readingsPageSize,
    readingsLoading,
    latestDo,
    latestPh,
    loadObservations,
    loadReadingsPage,
  }
})
