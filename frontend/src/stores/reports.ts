import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { ArchiveEvidence, BenefitReport, ExportEvidence } from '@/types/domain'
import { DEFAULT_POND_ID } from '@/utils/constants'
import { useAuthStore } from './auth'

interface BenefitsResponse {
  disclaimer: string
  metrics: Array<{ label: string; value: number; unit: string }>
}

interface ExportResponse {
  id: string
  redacted: boolean
  redaction_policy: string
  expires_at: string
}

interface ArchiveResponse {
  id: string
  evidence_only: boolean
  approval_ref: string
}

export const useReportsStore = defineStore('reports', () => {
  const report = ref<BenefitReport>({
    title: '塘口处置效益月度报告',
    period: '2026年5月',
    entries: [],
    evidenceLevel: '已归档',
  })
  const exportEvidence = ref<ExportEvidence | null>(null)
  const archiveEvidence = ref<ArchiveEvidence | null>(null)
  const loading = ref(false)

  async function loadReport() {
    const auth = useAuthStore()
    loading.value = true
    try {
      const result = await auth.request<BenefitsResponse>('/api/v1/reports/benefits')
      report.value.entries = result.metrics.map((metric) => ({
        label: metric.label,
        value: `${metric.value} ${metric.unit}`,
      }))
    } catch (e) {
      report.value.entries = []
      throw e instanceof Error ? e : new Error('报表数据没拉到')
    } finally {
      loading.value = false
    }
  }

  async function exportReport() {
    const auth = useAuthStore()
    loading.value = true
    try {
      const result = await auth.request<ExportResponse>('/api/v1/exports', {
        method: 'POST',
        body: JSON.stringify({
          purpose: '塘口效益月度摘要',
          pond_id: DEFAULT_POND_ID,
          idempotency_key: 'ui-report-export',
        }),
      })
      exportEvidence.value = {
        id: result.id,
        redacted: result.redacted,
        redactionPolicy: result.redaction_policy,
        expiresAt: result.expires_at,
      }
    } catch (e) {
      exportEvidence.value = null
      throw e instanceof Error ? e : new Error('报告导出没成功')
    } finally {
      loading.value = false
    }
  }

  async function registerArchiveEvidence() {
    const auth = useAuthStore()
    loading.value = true
    try {
      const exported = await auth.request<ExportResponse>('/api/v1/exports', {
        method: 'POST',
        body: JSON.stringify({
          purpose: '管理员归档审批',
          pond_id: DEFAULT_POND_ID,
          idempotency_key: 'ui-archive-export',
        }),
      })
      const archived = await auth.request<ArchiveResponse>('/api/v1/archives', {
        method: 'POST',
        body: JSON.stringify({
          action: 'archive',
          scope: exported.id,
          approval_ref: 'ARCH-APPROVAL-' + Date.now().toString(36).toUpperCase(),
          idempotency_key: 'ui-archive-record',
        }),
      })
      archiveEvidence.value = {
        id: archived.id,
        evidenceOnly: archived.evidence_only,
        approvalRef: archived.approval_ref,
      }
    } catch (e) {
      archiveEvidence.value = null
      throw e instanceof Error ? e : new Error('归档没登记上')
    } finally {
      loading.value = false
    }
  }

  return {
    report,
    exportEvidence,
    archiveEvidence,
    loading,
    loadReport,
    exportReport,
    registerArchiveEvidence,
  }
})
