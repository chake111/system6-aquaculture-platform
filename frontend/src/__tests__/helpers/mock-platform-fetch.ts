import { vi } from 'vitest'

type RecommendationStatus =
  | 'none'
  | 'generated'
  | 'reviewed'
  | 'confirmed'
  | 'completed'
  | 'evaluated'
type AlertStatus = 'none' | 'delivered' | 'acknowledged' | 'resolved'

export function createPlatformFetch() {
  let recommendationStatus: RecommendationStatus = 'none'
  let alertStatus: AlertStatus = 'none'

  return {
    fetch: vi.fn<typeof fetch>(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/api/v1/auth/login')) {
        const phone = JSON.parse(String(init?.body)).phone as string
        const roles: Record<string, 'farmer' | 'technician' | 'admin'> = {
          '13800000001': 'farmer',
          '13800000002': 'technician',
          '13800000003': 'admin',
        }
        return Response.json({
          access_token: `token-${roles[phone]}`,
          refresh_token: 'refresh',
          role: roles[phone],
        })
      }

      if (url.endsWith('/api/v1/auth/offline-grants')) {
        return Response.json({
          max_days: 7,
          permissions: ['read_cached_dashboard', 'draft_alert_resolution'],
          pond_scope: ['pond-hz-01', 'pond-ref'],
          source_mode: 'simulation',
          expires_at: '2026-06-03T00:00:00Z',
          signed_grant: 'signed-grant',
        })
      }

      if (url.includes('/api/v1/ponds/pond-ref/readings')) {
        const allItems = Array.from({ length: 24 }, (_, i) => ({
          id: `reading-${i}`,
          captured_at: `2025-10-01T${String(i).padStart(2, '0')}:00:00Z`,
          dissolved_oxygen_mg_l: 5.0 + (i % 5),
          ph: 7.0 + (i % 3) * 0.3,
          source_mode: 'external_observation',
          verified: true,
          quality_status: 'provisional',
          source_qualifiers: 'P',
        }))
        const parsedUrl = new URL(url, 'http://localhost')
        const page = Number(parsedUrl.searchParams.get('page') || '1')
        const pageSize = Number(parsedUrl.searchParams.get('page_size') || '50')
        const start = (page - 1) * pageSize
        return Response.json({
          items: allItems.slice(start, start + pageSize),
          total: allItems.length,
          page,
          page_size: pageSize,
        })
      }

      if (url.endsWith('/api/v1/ponds/pond-hz-01/recommendations')) {
        if (recommendationStatus === 'none') return Response.json([])
        return Response.json([
          { id: 'rec-1', status: recommendationStatus, source_mode: 'simulation' },
        ])
      }

      if (url.endsWith('/api/v1/alerts') && init?.method !== 'POST') {
        if (alertStatus === 'none') return Response.json([])
        return Response.json([
          {
            id: 'alert-1',
            status: alertStatus,
            source_mode: 'simulation',
            delivery_status: alertStatus === 'delivered' ? 'delivered' : 'delivered',
            recommendation_id: 'rec-1',
          },
        ])
      }

      if (url.endsWith('/api/v1/demo/ponds/pond-hz-01/low-oxygen')) {
        recommendationStatus = 'generated'
        alertStatus = 'delivered'
        return Response.json({
          reading: { dissolved_oxygen_mg_l: 3.2 },
          recommendation: { id: 'rec-1', status: 'generated' },
          alert: {
            id: 'alert-1',
            source_mode: 'simulation',
            delivery_status: 'delivered',
            recommendation_id: 'rec-1',
          },
        })
      }

      if (url.endsWith('/api/v1/recommendations/rec-1/review')) {
        recommendationStatus = 'reviewed'
        return Response.json({ id: 'rec-1', status: 'reviewed' })
      }

      if (url.endsWith('/api/v1/recommendations/rec-1/confirm')) {
        recommendationStatus = 'confirmed'
        return Response.json({ id: 'rec-1', status: 'confirmed' })
      }

      if (url.endsWith('/api/v1/recommendations/rec-1/executions') && init?.method === 'POST') {
        recommendationStatus = 'completed'
        return Response.json({
          id: 'exec-1',
          status: 'completed',
          execution_mode: 'simulation',
        })
      }

      if (url.endsWith('/api/v1/executions/exec-1/feedback')) {
        recommendationStatus = 'evaluated'
        return Response.json({ id: 'exec-1', status: 'evaluated' })
      }

      if (url.endsWith('/api/v1/alerts/alert-1/acknowledge')) {
        alertStatus = 'acknowledged'
        return Response.json({ status: 'acknowledged' })
      }

      if (url.endsWith('/api/v1/alerts/alert-1/resolve')) {
        alertStatus = 'resolved'
        return Response.json({ status: 'resolved' })
      }

      if (url.endsWith('/api/v1/alerts/alert-1/close')) {
        alertStatus = 'resolved'
        return Response.json({ status: 'closed' })
      }

      if (url.endsWith('/api/v1/reports/benefits')) {
        return Response.json({
          verified: false,
          source_mode: 'simulation',
          disclaimer: '演示评估数据',
          metrics: [
            { label: '增氧用电成本', value: 128.4, unit: 'CNY', source_mode: 'simulation' },
            { label: '鲈鱼成活率', value: 92.5, unit: '%', source_mode: 'simulation' },
          ],
        })
      }

      if (url.endsWith('/api/v1/operations/health')) {
        return Response.json({
          environment: 'demonstration',
          external_observation_count: 24,
          components: {
            sync: { status: 'healthy', retention_days: 7 },
            notifications: { status: 'healthy', provider_mode: 'simulation' },
          },
        })
      }

      if (url.endsWith('/api/v1/media-samples') && init?.method === 'POST') {
        return Response.json({ id: 'sample-1', source_mode: 'simulation' })
      }

      if (url.includes('/analyses') && init?.method === 'POST') {
        return Response.json({
          id: 'analysis-1',
          source_mode: 'simulation',
          review_status: 'pending',
          estimated_density_fish_m2: 38,
          error_margin_fish_m2: 4,
          model_version: 'density-demo-v1',
        })
      }

      if (url.includes('/density-analyses') && init?.method === 'PATCH') {
        return Response.json({
          id: 'analysis-1',
          source_mode: 'simulation',
          review_status: 'approved',
          estimated_density_fish_m2: 38,
          error_margin_fish_m2: 4,
          model_version: 'density-demo-v1',
        })
      }

      if (url.endsWith('/api/v1/exports') && init?.method === 'POST') {
        return Response.json({
          id: 'export-1',
          redacted: true,
          redaction_policy: 'mask-identifiers-v1',
          expires_at: '2026-06-03T00:00:00Z',
        })
      }

      if (url.endsWith('/api/v1/archives') && init?.method === 'POST') {
        return Response.json({
          id: 'archive-1',
          evidence_only: true,
          export_id: 'export-1',
          approval_ref: 'ARCH-APPROVAL-MOCK123',
        })
      }

      return Response.json([])
    }),
    getStatus: () => ({ recommendationStatus, alertStatus }),
  }
}
