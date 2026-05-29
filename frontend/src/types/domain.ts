export type UserRole = 'farmer' | 'technician' | 'admin'

export type OfflinePermission = 'read_cached_dashboard' | 'draft_alert_resolution'

export interface OfflineGrant {
  maxDays: number
  permissions: OfflinePermission[]
  pondScope: string[]
  expiresAt: string
  signedGrant: string
}

export interface Observation {
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

export type AlertStatus =
  | 'generated'
  | 'reviewed'
  | 'confirmed'
  | 'completed'
  | 'evaluated'
  | 'resolved'
  | 'closed'
  | 'rejected'

export interface OxygenAlert {
  id: string
  title: string
  dissolvedOxygenMgL: number
  severity: 'high'
  sourceMode: string
  status: AlertStatus
  recommendation: string
  executionMode: string
  recommendationId: string
  deliveryStatus: string
}

export interface BenefitReport {
  title: string
  period: string
  entries: Array<{ label: string; value: string }>
  evidenceLevel: string
}

export interface OperationsRecord {
  component: string
  status: string
  evidence: string
}

export interface DensityResult {
  estimatedDensityFishM2: number
  errorMarginFishM2: number
  modelVersion: string
  reviewStatus: string
}

export interface ExportEvidence {
  id: string
  redacted: boolean
  redactionPolicy: string
  expiresAt: string
}

export interface ArchiveEvidence {
  id: string
  evidenceOnly: boolean
  approvalRef: string
}

export interface AgentAdvice {
  content: string
  mode: 'llm' | 'fallback'
  model: string
}

export interface StructuredAdvice {
  summary: string
  riskLevel: 'low' | 'medium' | 'high' | 'critical'
  category: string
  actions: string[]
  explanation: string
  dataRefs: Record<string, unknown>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: string
  toolCall?: { name: string; args: Record<string, unknown>; result?: unknown }
  structured?: StructuredAdvice
}
