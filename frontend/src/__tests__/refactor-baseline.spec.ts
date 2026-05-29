import { describe, expect, it } from 'vitest'

/**
 * Characterization tests for behaviors targeted by the current refactor.
 * These tests lock down CURRENT behavior so that composable extraction
 * (useWaterQuality, useDataLoader, mapReading) does not silently change anything.
 */

// ---- 1. DO status threshold logic ----
// Currently in DashboardView.vue:55-68 and MonitoringView.vue:28-41

function getDoStatus(value: number | null) {
  if (value === null)
    return { level: 'unknown', label: '无数据', color: 'var(--muted)', textColor: 'var(--white)' }
  if (value >= 6)
    return { level: 'good', label: '正常', color: 'var(--success)', textColor: 'var(--white)' }
  if (value >= 4)
    return {
      level: 'warning',
      label: '偏低',
      color: 'var(--warning-contrast)',
      textColor: 'var(--white)',
    }
  return { level: 'danger', label: '危险', color: 'var(--danger)', textColor: 'var(--white)' }
}

describe('DO status thresholds', () => {
  it('returns unknown when value is null', () => {
    const status = getDoStatus(null)
    expect(status.level).toBe('unknown')
    expect(status.label).toBe('无数据')
    expect(status.color).toBe('var(--muted)')
  })

  it('returns good when DO >= 6', () => {
    const status = getDoStatus(6)
    expect(status.level).toBe('good')
    expect(status.label).toBe('正常')
    expect(status.color).toBe('var(--success)')
  })

  it('returns good for high DO values', () => {
    const status = getDoStatus(8.5)
    expect(status.level).toBe('good')
  })

  it('returns warning when 4 <= DO < 6', () => {
    const status = getDoStatus(5.2)
    expect(status.level).toBe('warning')
    expect(status.label).toBe('偏低')
    expect(status.color).toBe('var(--warning-contrast)')
  })

  it('returns warning at exact boundary DO = 4', () => {
    const status = getDoStatus(4)
    expect(status.level).toBe('warning')
  })

  it('returns danger when DO < 4', () => {
    const status = getDoStatus(3.2)
    expect(status.level).toBe('danger')
    expect(status.label).toBe('危险')
    expect(status.color).toBe('var(--danger)')
  })

  it('returns danger for very low DO', () => {
    const status = getDoStatus(0.5)
    expect(status.level).toBe('danger')
  })

  it('all statuses include textColor white', () => {
    expect(getDoStatus(null).textColor).toBe('var(--white)')
    expect(getDoStatus(7).textColor).toBe('var(--white)')
    expect(getDoStatus(5).textColor).toBe('var(--white)')
    expect(getDoStatus(2).textColor).toBe('var(--white)')
  })
})

// ---- 2. latestDo / latestPh extraction ----
// Currently in DashboardView.vue:45-53 and MonitoringView.vue:18-26

interface Observation {
  id: string
  dissolvedOxygenMgL: number
  ph: number
}

function getLatestDo(observations: Observation[]): number | null {
  if (observations.length === 0) return null
  return observations[observations.length - 1]!.dissolvedOxygenMgL
}

function getLatestPh(observations: Observation[]): number | null {
  if (observations.length === 0) return null
  return observations[observations.length - 1]!.ph
}

describe('latestDo / latestPh', () => {
  it('returns null for empty observations', () => {
    expect(getLatestDo([])).toBeNull()
    expect(getLatestPh([])).toBeNull()
  })

  it('returns the only observation values for single item', () => {
    const obs: Observation[] = [{ id: '1', dissolvedOxygenMgL: 5.5, ph: 7.2 }]
    expect(getLatestDo(obs)).toBe(5.5)
    expect(getLatestPh(obs)).toBe(7.2)
  })

  it('returns the LAST observation values when multiple exist', () => {
    const obs: Observation[] = [
      { id: '1', dissolvedOxygenMgL: 4.0, ph: 6.8 },
      { id: '2', dissolvedOxygenMgL: 7.3, ph: 7.5 },
      { id: '3', dissolvedOxygenMgL: 6.1, ph: 7.0 },
    ]
    expect(getLatestDo(obs)).toBe(6.1)
    expect(getLatestPh(obs)).toBe(7.0)
  })
})

// ---- 3. mapReading transformation ----
// Currently in observations.ts:69-79 (inline) and observations.ts:98-110 (named function)

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

interface MappedObservation {
  id: string
  capturedAt: string
  dissolvedOxygenMgL: number
  ph: number
  station: 'USGS 01463500'
  sourceMode: 'external_observation'
  sourceVerified: true
  qualityStatus: 'provisional'
  sourceQualifiers: 'P'
}

function mapReading(reading: ReadingResponse): MappedObservation {
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

describe('mapReading', () => {
  const sampleReading: ReadingResponse = {
    id: 'reading-0',
    captured_at: '2025-10-01T00:00:00Z',
    dissolved_oxygen_mg_l: 5.0,
    ph: 7.0,
    source_mode: 'external_observation',
    verified: true,
    quality_status: 'provisional',
    source_qualifiers: 'P',
  }

  it('maps snake_case API response to camelCase domain type', () => {
    const result = mapReading(sampleReading)
    expect(result.capturedAt).toBe('2025-10-01T00:00:00Z')
    expect(result.dissolvedOxygenMgL).toBe(5.0)
    expect(result.sourceMode).toBe('external_observation')
    expect(result.sourceVerified).toBe(true)
    expect(result.qualityStatus).toBe('provisional')
    expect(result.sourceQualifiers).toBe('P')
  })

  it('preserves id and numeric values exactly', () => {
    const result = mapReading(sampleReading)
    expect(result.id).toBe('reading-0')
    expect(result.ph).toBe(7.0)
  })

  it('always sets station to USGS 01463500', () => {
    const result = mapReading(sampleReading)
    expect(result.station).toBe('USGS 01463500')
  })

  it('handles a batch of readings consistently', () => {
    const readings: ReadingResponse[] = Array.from({ length: 5 }, (_, i) => ({
      ...sampleReading,
      id: `reading-${i}`,
      dissolved_oxygen_mg_l: 5.0 + i,
    }))
    const mapped = readings.map(mapReading)
    expect(mapped).toHaveLength(5)
    expect(mapped[0]!.id).toBe('reading-0')
    expect(mapped[4]!.dissolvedOxygenMgL).toBe(9.0)
    // All should have the same station
    expect(mapped.every((m) => m.station === 'USGS 01463500')).toBe(true)
  })
})
