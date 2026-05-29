import { computed } from 'vue'

import type { Observation } from '@/types/domain'

export interface DoStatus {
  level: 'unknown' | 'good' | 'warning' | 'danger'
  label: string
  color: string
  textColor: string
}

export function useWaterQuality(observations: () => Observation[]) {
  const latestDo = computed(() => {
    const obs = observations()
    if (obs.length === 0) return null
    return obs[obs.length - 1]!.dissolvedOxygenMgL
  })

  const latestPh = computed(() => {
    const obs = observations()
    if (obs.length === 0) return null
    return obs[obs.length - 1]!.ph
  })

  const doStatus = computed<DoStatus>(() => {
    if (latestDo.value === null)
      return { level: 'unknown', label: '无数据', color: 'var(--muted)', textColor: 'var(--white)' }
    if (latestDo.value >= 6)
      return { level: 'good', label: '正常', color: 'var(--success)', textColor: 'var(--white)' }
    if (latestDo.value >= 4)
      return {
        level: 'warning',
        label: '偏低',
        color: 'var(--warning-contrast)',
        textColor: 'var(--white)',
      }
    return { level: 'danger', label: '危险', color: 'var(--danger)', textColor: 'var(--white)' }
  })

  return { latestDo, latestPh, doStatus }
}
