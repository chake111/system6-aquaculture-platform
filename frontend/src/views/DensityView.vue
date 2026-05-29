<script setup lang="ts">
import { computed, ref } from 'vue'
import { Histogram, DataAnalysis, Loading } from '@element-plus/icons-vue'

import { usePlatformStore } from '@/stores/platform'

const store = usePlatformStore()
const actionError = ref<string | null>(null)

async function runAnalysis() {
  actionError.value = null
  try {
    await store.analyzeDensity()
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '分析没跑完，再试一下'
  }
}

const densityStatus = computed(() => {
  if (!store.densityResult) return null
  const status = store.densityResult.reviewStatus
  const tagType: 'success' | 'danger' | 'warning' =
    status === 'approved' ? 'success' : status === 'rejected' ? 'danger' : 'warning'
  return {
    label: status === 'approved' ? '已复核' : status === 'rejected' ? '已驳回' : '待复核',
    type: tagType,
  }
})
</script>

<template>
  <div class="view-grid split-grid">
    <el-card shadow="hover" class="mb-4" aria-label="密度分析">
      <template #header>
        <div class="card-header">
          <div>
            <h2>密度调控</h2>
          </div>
        </div>
      </template>

      <div
        v-if="store.densityResult"
        class="density-display"
        :aria-label="`估算密度: ${store.densityResult.estimatedDensityFishM2} 尾/m²`"
      >
        <el-icon :size="40" class="density-icon" aria-hidden="true"><Histogram /></el-icon>
        <el-statistic
          title="估算密度"
          :value="store.densityResult.estimatedDensityFishM2"
          :precision="1"
          suffix="尾/m²"
        />
      </div>

      <el-descriptions
        v-if="store.densityResult"
        :column="2"
        border
        size="small"
        class="mt-4"
        aria-label="密度分析结果"
        aria-live="polite"
      >
        <el-descriptions-item label="误差范围">
          ± {{ Number(store.densityResult.errorMarginFishM2).toFixed(1) }} 尾/m²
        </el-descriptions-item>
        <el-descriptions-item label="模型版本">
          {{ store.densityResult.modelVersion }}
        </el-descriptions-item>
        <el-descriptions-item label="复核状态">
          <el-tag :type="densityStatus?.type ?? 'info'" size="small">
            {{ densityStatus?.label || '待分析' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="数据来源">
          <el-tag type="success" size="small">声呐采样</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-empty
        v-else
        :description="
          actionError
            ? '分析没跑完，再试一下。'
            : '尚未运行密度分析。技术员可点击「运行密度分析」按钮启动声呐采样。'
        "
        role="status"
        aria-live="polite"
      />
    </el-card>

    <el-card shadow="hover" aria-label="调控建议">
      <template #header>
        <div class="card-header">
          <h2>调控建议</h2>
          <el-tag v-if="densityStatus" :type="densityStatus.type" size="small">{{
            densityStatus.label
          }}</el-tag>
          <el-tag v-else type="info" size="small">待分析</el-tag>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        description="声呐采样估算值，建议结合人工抽样校准后作为决策参考。"
        class="mb-4"
      />

      <p class="recommendation-text">
        保持当前投喂计划，48 小时后重新采样；如人工核验密度偏高，再评估分塘方案。
      </p>

      <el-button
        v-if="store.role === 'technician' && store.densityResult?.reviewStatus !== 'approved'"
        type="primary"
        size="large"
        class="mt-4"
        :loading="store.isLoading('analyzeDensity')"
        :disabled="store.isLoading('analyzeDensity')"
        :aria-busy="store.isLoading('analyzeDensity')"
        data-test="analyze-density"
        @click="runAnalysis"
      >
        <el-icon v-if="store.isLoading('analyzeDensity')" class="is-loading" aria-hidden="true"
          ><Loading
        /></el-icon>
        <el-icon v-else aria-hidden="true"><DataAnalysis /></el-icon>
        {{ store.isLoading('analyzeDensity') ? '分析中...' : '运行密度分析' }}
      </el-button>

      <p v-if="actionError" class="action-error" role="alert" data-test="density-error">
        {{ actionError }}
      </p>

      <div v-if="store.densityResult" class="mt-4">
        <el-tag type="success" size="small">操作记录：已完成</el-tag>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.density-display {
  text-align: center;
  padding: var(--sp-4) 0;
}
.density-icon {
  color: var(--accent-dark);
  margin-bottom: var(--sp-2);
}
.recommendation-text {
  line-height: 1.8;
  color: var(--muted);
}
</style>
