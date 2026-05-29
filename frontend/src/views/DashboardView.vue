<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  WarningFilled,
  Select,
  CircleCheck,
  Promotion,
  SuccessFilled,
  CircleCloseFilled,
  Loading,
} from '@element-plus/icons-vue'

import ErrorBanner from '@/components/ErrorBanner.vue'
import { useDataLoader } from '@/composables/useDataLoader'
import { useWaterQuality } from '@/composables/useWaterQuality'
import { usePlatformStore } from '@/stores/platform'

const store = usePlatformStore()
const actionError = ref<string | null>(null)

const { loadError, retry: loadWorkflowData } = useDataLoader(async () => {
  if (store.role) {
    await store.loadWorkflow()
  }
})

onMounted(loadWorkflowData)

const alertStatus = computed(() => {
  const status = store.activeAlert?.status
  if (status === 'generated') return '已生成处置建议，等待技术员复核'
  if (status === 'reviewed') return '建议已由技术员复核，等待养殖户确认'
  if (status === 'confirmed') return '建议已确认，等待增氧执行'
  if (status === 'completed') return '增氧执行已记录，等待处置确认'
  if (status === 'evaluated') return '效果反馈已记录，等待告警处置'
  if (status === 'resolved') return '已处置，等待技术员复核关闭'
  if (status === 'closed') return '预警已关闭，审计记录可查询'
  return ''
})

const { latestDo, latestPh, doStatus } = useWaterQuality(() => store.observations)

async function runAction(fn: () => Promise<void>, errorMsg: string) {
  actionError.value = null
  try {
    await fn()
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : errorMsg
  }
}
</script>

<template>
  <div class="view-grid dashboard">
    <section v-if="!store.isOnline" class="banner warning-banner" role="alert">
      <strong>当前离线</strong>
      <span>离线授权仅允许读取缓存和记录处置草稿；控制操作需在线执行。</span>
    </section>
    <ErrorBanner
      v-if="loadError"
      message="工作流数据加载出了问题，检查下网络。"
      @retry="loadWorkflowData"
    />
    <!-- Latest water quality statistic cards -->
    <div class="metric-row">
      <el-card
        shadow="hover"
        class="metric-el-card"
        :aria-label="`最新溶氧: ${latestDo ?? '无数据'} mg/L`"
      >
        <el-statistic
          v-if="latestDo !== null"
          title="最新溶氧 (mg/L)"
          :value="latestDo"
          :precision="1"
        >
          <template #suffix>
            <el-tag
              :color="doStatus.color"
              :style="{ color: doStatus.textColor, borderColor: doStatus.color }"
              class="status-tag"
              size="small"
            >
              {{ doStatus.label }}
            </el-tag>
          </template>
        </el-statistic>
        <div v-else class="stat-empty">
          <span class="stat-empty-label">最新溶氧 (mg/L)</span>
          <span class="stat-empty-value">—</span>
        </div>
      </el-card>
      <el-card
        shadow="hover"
        class="metric-el-card"
        :aria-label="`最新 pH: ${latestPh ?? '无数据'}`"
      >
        <el-statistic v-if="latestPh !== null" title="最新 pH" :value="latestPh" :precision="2" />
        <div v-else class="stat-empty">
          <span class="stat-empty-label">最新 pH</span>
          <span class="stat-empty-value">—</span>
        </div>
      </el-card>
    </div>

    <div class="metric-row">
      <article class="metric-card" :aria-label="`外部观测记录: ${store.observations.length} 条`">
        <span>外部观测记录</span>
        <strong>{{ store.observations.length }} 条</strong>
      </article>
      <article
        class="metric-card risk"
        :aria-label="`塘口预警: ${store.activeAlert ? '1 条待处置' : '正常'}`"
      >
        <span>塘口预警</span>
        <strong>{{ store.activeAlert ? '1 条' : '正常' }}</strong>
      </article>
    </div>

    <section class="panel action-panel" aria-label="增氧处置">
      <div class="panel-heading">
        <h2>增氧处置闭环</h2>
      </div>

      <button
        v-if="store.role === 'farmer' && store.isOnline && !store.activeAlert"
        class="large-action danger"
        type="button"
        :disabled="store.isLoading('injectLowOxygen')"
        :aria-busy="store.isLoading('injectLowOxygen')"
        data-test="inject-low-oxygen"
        @click="runAction(store.injectLowOxygen, '预警没触发成功，再试一次')"
      >
        <el-icon v-if="store.isLoading('injectLowOxygen')" class="is-loading" aria-hidden="true"
          ><Loading
        /></el-icon>
        <el-icon v-else aria-hidden="true"><WarningFilled /></el-icon>
        {{ store.isLoading('injectLowOxygen') ? '处理中...' : '触发低溶氧预警' }}
      </button>

      <article v-if="store.activeAlert" class="alert-workflow">
        <header>
          <div>
            <h3>{{ store.activeAlert.title }}</h3>
            <p>{{ store.activeAlert.dissolvedOxygenMgL }} mg/L · 高风险</p>
          </div>
        </header>
        <p class="recommendation">{{ store.activeAlert.recommendation }}</p>
        <p class="status-text" aria-live="polite">{{ alertStatus }}</p>
        <div v-if="store.role === 'technician' && store.isOnline" class="workflow-actions">
          <button
            v-if="store.activeAlert.status === 'generated'"
            class="large-action"
            type="button"
            :disabled="store.isLoading('reviewRecommendation')"
            :aria-busy="store.isLoading('reviewRecommendation')"
            data-test="review-recommendation"
            @click="runAction(store.reviewRecommendation, '复核没通过，再试一次')"
          >
            <el-icon
              v-if="store.isLoading('reviewRecommendation')"
              class="is-loading"
              aria-hidden="true"
              ><Loading
            /></el-icon>
            <el-icon v-else aria-hidden="true"><Select /></el-icon>
            {{ store.isLoading('reviewRecommendation') ? '处理中...' : '复核建议' }}
          </button>
          <button
            v-if="store.activeAlert.status === 'resolved'"
            class="large-action resolved"
            type="button"
            :disabled="store.isLoading('closeAlert')"
            :aria-busy="store.isLoading('closeAlert')"
            data-test="close-alert"
            @click="runAction(store.closeAlert, '预警没关掉，再试一次')"
          >
            <el-icon v-if="store.isLoading('closeAlert')" class="is-loading" aria-hidden="true"
              ><Loading
            /></el-icon>
            <el-icon v-else aria-hidden="true"><CircleCloseFilled /></el-icon>
            {{ store.isLoading('closeAlert') ? '处理中...' : '复核并关闭预警' }}
          </button>
        </div>
        <div v-if="store.role === 'farmer' && store.isOnline" class="workflow-actions">
          <button
            v-if="store.activeAlert.status === 'generated'"
            class="large-action quick-response"
            type="button"
            :disabled="store.isLoading('quickResponse')"
            :aria-busy="store.isLoading('quickResponse')"
            data-test="quick-response"
            @click="runAction(store.quickResponse, '一键处理没成功，再试一次')"
          >
            <el-icon v-if="store.isLoading('quickResponse')" class="is-loading" aria-hidden="true"
              ><Loading
            /></el-icon>
            <el-icon v-else aria-hidden="true"><SuccessFilled /></el-icon>
            {{ store.isLoading('quickResponse') ? '处理中...' : '一键处理（演示模式）' }}
          </button>
          <button
            v-if="store.activeAlert.status === 'reviewed'"
            class="large-action"
            type="button"
            :disabled="store.isLoading('confirmRecommendation')"
            :aria-busy="store.isLoading('confirmRecommendation')"
            data-test="confirm-recommendation"
            @click="runAction(store.confirmRecommendation, '确认没成功，再试一次')"
          >
            <el-icon
              v-if="store.isLoading('confirmRecommendation')"
              class="is-loading"
              aria-hidden="true"
              ><Loading
            /></el-icon>
            <el-icon v-else aria-hidden="true"><CircleCheck /></el-icon>
            {{ store.isLoading('confirmRecommendation') ? '处理中...' : '确认建议' }}
          </button>
          <button
            v-if="store.activeAlert.status === 'confirmed'"
            class="large-action"
            type="button"
            :disabled="store.isLoading('executeSimulation')"
            :aria-busy="store.isLoading('executeSimulation')"
            data-test="execute-simulation"
            @click="runAction(store.executeSimulation, '执行没成功，再试一次')"
          >
            <el-icon
              v-if="store.isLoading('executeSimulation')"
              class="is-loading"
              aria-hidden="true"
              ><Loading
            /></el-icon>
            <el-icon v-else aria-hidden="true"><Promotion /></el-icon>
            {{ store.isLoading('executeSimulation') ? '处理中...' : '执行增氧' }}
          </button>
          <button
            v-if="store.activeAlert.status === 'completed'"
            class="large-action resolved"
            type="button"
            :disabled="store.isLoading('resolveAlert')"
            :aria-busy="store.isLoading('resolveAlert')"
            data-test="resolve-alert"
            @click="runAction(store.resolveAlert, '处置没成功，再试一次')"
          >
            <el-icon v-if="store.isLoading('resolveAlert')" class="is-loading" aria-hidden="true"
              ><Loading
            /></el-icon>
            <el-icon v-else aria-hidden="true"><SuccessFilled /></el-icon>
            {{ store.isLoading('resolveAlert') ? '处理中...' : '记录处置完成' }}
          </button>
        </div>
        <p v-if="actionError" class="action-error" role="alert" data-test="action-error">
          {{ actionError }}
        </p>
      </article>
    </section>
  </div>
</template>

<style scoped>
.metric-el-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.metric-el-card :deep(.el-card__body) {
  padding: var(--sp-4) var(--sp-5);
}

.card-label {
  display: block;
  margin-bottom: var(--sp-1);
  color: var(--muted);
  font-size: var(--font-sm);
}

.stat-empty {
  display: grid;
  gap: var(--sp-2);
}

.stat-empty-label {
  color: var(--muted);
  font-size: var(--font-sm);
}

.stat-empty-value {
  color: var(--text);
  font-size: var(--font-4xl);
  line-height: 1.1;
}

.metric-el-card strong {
  display: block;
  color: var(--text);
  font-size: var(--font-4xl);
  line-height: 1.1;
}

.status-tag {
  border: none;
  margin-left: var(--sp-2);
}

.source-tag {
  margin-top: var(--sp-2);
}

.large-action {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
}
</style>
