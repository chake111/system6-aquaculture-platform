<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Download, Loading } from '@element-plus/icons-vue'

import ErrorBanner from '@/components/ErrorBanner.vue'
import { useDataLoader } from '@/composables/useDataLoader'
import { usePlatformStore } from '@/stores/platform'

const store = usePlatformStore()
const actionError = ref<string | null>(null)

async function runExport() {
  actionError.value = null
  try {
    await store.exportReport()
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '导出没成功，再试一下'
  }
}

const { loadError, retry: loadReportData } = useDataLoader(async () => {
  if (store.role === 'technician' || store.role === 'admin') {
    await store.loadReport()
  }
})

onMounted(loadReportData)
</script>

<template>
  <div class="view-grid">
    <ErrorBanner
      v-if="loadError"
      message="报表数据加载出了问题，检查下网络。"
      @retry="loadReportData"
    />

    <el-card shadow="hover" class="mb-4" aria-label="效益报表">
      <template #header>
        <div class="card-header">
          <div>
            <p class="section-label">{{ store.report.period }}</p>
            <h2>{{ store.report.title }}</h2>
          </div>
          <el-tag type="success" size="small">{{ store.report.evidenceLevel }}</el-tag>
        </div>
      </template>

      <el-table :data="store.report.entries" stripe size="small" aria-label="效益指标明细">
        <el-table-column prop="label" label="指标名称" min-width="150" />
        <el-table-column prop="value" label="数值" min-width="200">
          <template #default="{ row }">
            <span>{{ row.value }}</span>
          </template>
        </el-table-column>
      </el-table>

      <el-button
        type="primary"
        size="large"
        class="mt-4"
        :loading="store.isLoading('exportReport')"
        :aria-busy="store.isLoading('exportReport')"
        data-test="export-report"
        @click="runExport"
      >
        <el-icon v-if="store.isLoading('exportReport')" class="is-loading" aria-hidden="true"
          ><Loading
        /></el-icon>
        <el-icon v-else aria-hidden="true"><Download /></el-icon>
        {{ store.isLoading('exportReport') ? '导出中...' : '导出报告摘要' }}
      </el-button>

      <p v-if="actionError" class="action-error" role="alert" data-test="export-error">
        {{ actionError }}
      </p>

      <el-descriptions
        v-if="store.exportEvidence"
        :column="2"
        border
        size="small"
        class="mt-4"
        aria-label="导出证据详情"
        aria-live="polite"
      >
        <el-descriptions-item label="导出ID">
          {{ store.exportEvidence.id }}
        </el-descriptions-item>
        <el-descriptions-item label="脱敏策略">
          {{
            store.exportEvidence.redactionPolicy === 'mask-identifiers-v1'
              ? '标识脱敏策略 v1'
              : store.exportEvidence.redactionPolicy
          }}
        </el-descriptions-item>
        <el-descriptions-item label="是否脱敏">
          <el-tag :type="store.exportEvidence.redacted ? 'success' : 'danger'" size="small">
            {{ store.exportEvidence.redacted ? '已脱敏' : '未脱敏' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="到期时间">
          {{ store.exportEvidence.expiresAt }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>
