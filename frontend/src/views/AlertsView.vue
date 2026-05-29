<script setup lang="ts">
import { computed, onMounted } from 'vue'

import ErrorBanner from '@/components/ErrorBanner.vue'
import { useDataLoader } from '@/composables/useDataLoader'
import { usePlatformStore } from '@/stores/platform'

const store = usePlatformStore()

const { loadError, retry: loadAlertData } = useDataLoader(async () => {
  if (store.role) {
    await store.loadWorkflow()
  }
})

onMounted(loadAlertData)

const statusLabel: Record<string, string> = {
  generated: '待复核',
  reviewed: '已复核',
  confirmed: '已确认',
  completed: '已执行',
  evaluated: '已评估',
  delivered: '已送达',
  delivery_failed: '送达失败',
  acknowledged: '已确认',
  resolved: '已处置',
  closed: '已关闭',
  pending: '待处理',
  failed: '失败',
}

type TagType = 'warning' | 'info' | 'primary' | 'success' | 'danger'

const statusType: Record<string, TagType> = {
  generated: 'warning',
  reviewed: 'info',
  confirmed: 'primary',
  completed: 'success',
  evaluated: 'success',
  delivered: 'success',
  delivery_failed: 'danger',
  acknowledged: 'info',
  resolved: 'success',
  closed: 'info',
}

function deliveryStatusType(status: string): TagType {
  return status === 'delivered' ? 'success' : status === 'failed' ? 'danger' : 'info'
}

function deliveryStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    delivered: '已送达',
    delivery_failed: '送达失败',
    failed: '送达失败',
    pending: '待发送',
    sending: '发送中',
    retrying: '重试中',
    queued: '排队中',
  }
  return labels[status] ?? `未知状态`
}

const hasAlert = computed(() => store.activeAlert !== null)
</script>

<template>
  <div class="view-grid">
    <ErrorBanner
      v-if="loadError"
      message="预警数据加载出了问题，检查下网络。"
      @retry="loadAlertData"
    />

    <el-card shadow="hover" class="mb-4" aria-label="当前预警">
      <template #header>
        <div class="card-header">
          <h2>当前预警</h2>
        </div>
      </template>

      <div v-if="hasAlert" class="alert-detail" aria-live="polite">
        <el-descriptions :column="2" border size="small" aria-label="当前预警详情">
          <el-descriptions-item label="预警类型">
            {{ store.activeAlert!.title }}
          </el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag type="danger" size="small">{{
              { high: '高风险', medium: '中风险', low: '低风险' }[store.activeAlert!.severity] ??
              '未知风险'
            }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="溶氧读数">
            {{ store.activeAlert!.dissolvedOxygenMgL }} mg/L
          </el-descriptions-item>
          <el-descriptions-item label="当前状态">
            <el-tag
              :type="(statusType[store.activeAlert!.status] ?? 'info') as TagType"
              size="small"
            >
              {{ statusLabel[store.activeAlert!.status] || '未知状态' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="数据来源" :span="2">
            <el-tag type="success" size="small">塘口传感器</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="处置建议" :span="2">
            {{ store.activeAlert!.recommendation }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <el-empty
        v-else
        description="暂无告警。养殖户可在综合仪表盘触发低溶氧预警。"
        role="status"
        aria-live="polite"
      />
    </el-card>

    <el-card shadow="hover" aria-label="渠道回执状态">
      <template #header>
        <div class="card-header">
          <h2>渠道回执样例</h2>
          <el-tag type="info" size="small">通知渠道</el-tag>
        </div>
      </template>

      <el-table
        aria-label="渠道回执状态"
        :data="[
          {
            channel: 'sms',
            label: '短信通知',
            status: store.activeAlert
              ? deliveryStatusLabel(store.activeAlert.deliveryStatus)
              : '未发送',
          },
          {
            channel: 'dingtalk',
            label: '钉钉通知',
            status: store.activeAlert
              ? deliveryStatusLabel(store.activeAlert.deliveryStatus)
              : '待发送',
          },
        ]"
        stripe
        size="small"
      >
        <el-table-column prop="label" label="渠道" width="120" />
        <el-table-column label="送达状态">
          <template #default="{ row }">
            <el-tag
              :type="
                (store.activeAlert
                  ? deliveryStatusType(store.activeAlert.deliveryStatus)
                  : 'info') as TagType
              "
              size="small"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.alert-detail {
  margin-top: var(--sp-2);
}
</style>
