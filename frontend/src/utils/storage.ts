export const STORAGE_KEYS = {
  role: 'aquaculture-role',
  token: 'aquaculture-token',
  highContrast: 'aquaculture-high-contrast',
  offlineGrant: 'aquaculture-offline-grant',
  observationCache: 'aquaculture-observation-cache',
} as const

export function storedValue<T>(key: string): T | null {
  const value = sessionStorage.getItem(key)
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    sessionStorage.removeItem(key)
    return null
  }
}
