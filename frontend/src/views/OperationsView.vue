<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { FolderChecked, Loading } from '@element-plus/icons-vue'

import ErrorBanner from '@/components/ErrorBanner.vue'
import { useDataLoader } from '@/composables/useDataLoader'
import { usePlatformStore } from '@/stores/platform'

const store = usePlatformStore()
const actionError = ref<string | null>(null)

async function runArchive() {
  actionError.value = null
  try {
    await store.registerArchiveEvidence()
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '归档没登记上，再试一下'
  }
}

const { loadError, retry: loadOperationsData } = useDataLoader(async () => {
  if (store.role === 'admin') {
    await store.loadOperations()
  }
})

onMounted(loadOperationsData)

const statusLabels: Record<string, string> = {
  healthy: '正常',
  degraded: '降级',
  down: '离线',
  可溯源: '可溯源',
}

function statusLabel(status: string): string {
  return statusLabels[status] ?? '未知'
}
</script>

<template>
  <div v-if="store.role === 'admin'" class="view-grid">
    <ErrorBanner
      v-if="loadError"
      message="运维数据加载出了问题，检查下网络。"
      @retry="loadOperationsData"
    />

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="审计与运维"
      description="管理员专属视图 · 系统运维与审计"
      class="mb-4"
    />

    <el-card shadow="hover" class="mb-4" aria-label="节点与服务状态">
      <template #header>
        <div class="card-header">
          <h2>节点与服务状态</h2>
        </div>
      </template>

      <el-table :data="store.operations" stripe size="small" aria-label="节点与服务状态">
        <el-table-column prop="component" label="组件" width="150" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'healthy' || row.status === '可溯源' ? 'success' : 'warning'"
              size="small"
            >
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="evidence" label="证据" />
      </el-table>
    </el-card>

    <el-card shadow="hover" class="mb-4" aria-label="归档控制">
      <template #header>
        <h2>归档控制</h2>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        description="归档操作记录审批与证据；数据销毁需二次确认。"
        class="mb-4"
      />

      <el-button
        type="warning"
        size="large"
        :loading="store.isLoading('registerArchiveEvidence')"
        :aria-busy="store.isLoading('registerArchiveEvidence')"
        data-test="archive-evidence"
        @click="runArchive"
      >
        <el-icon
          v-if="store.isLoading('registerArchiveEvidence')"
          class="is-loading"
          aria-hidden="true"
          ><Loading
        /></el-icon>
        <el-icon v-else aria-hidden="true"><FolderChecked /></el-icon>
        {{ store.isLoading('registerArchiveEvidence') ? '处理中...' : '登记归档审批' }}
      </el-button>

      <p v-if="actionError" class="action-error" role="alert" data-test="archive-error">
        {{ actionError }}
      </p>

      <el-descriptions
        v-if="store.archiveEvidence"
        :column="2"
        border
        size="small"
        class="mt-4"
        aria-label="归档证据详情"
        aria-live="polite"
      >
        <el-descriptions-item label="归档ID">
          {{ store.archiveEvidence.id }}
        </el-descriptions-item>
        <el-descriptions-item label="审批引用">
          {{ store.archiveEvidence.approvalRef }}
        </el-descriptions-item>
        <el-descriptions-item label="仅证据">
          <el-tag :type="store.archiveEvidence.evidenceOnly ? 'success' : 'danger'" size="small">
            {{ store.archiveEvidence.evidenceOnly ? '是（仅记录证据）' : '否' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>
