<script setup lang="ts">
import { computed, onMounted } from 'vue'

import ErrorBanner from '@/components/ErrorBanner.vue'
import TrendChart from '@/components/TrendChart.vue'
import { useDataLoader } from '@/composables/useDataLoader'
import { usePolling } from '@/composables/usePolling'
import { useWaterQuality } from '@/composables/useWaterQuality'
import { usePlatformStore } from '@/stores/platform'
import { useObservationsStore } from '@/stores/observations'
import { useAuthStore } from '@/stores/auth'

const store = usePlatformStore()
const obs = useObservationsStore()
const auth = useAuthStore()

const { latestDo, latestPh, doStatus } = useWaterQuality(() => obs.observations)

const {
  loadError,
  retry: loadObservationData,
  load,
} = useDataLoader(async () => {
  if (auth.role) {
    await obs.loadObservations()
    await obs.loadReadingsPage(1, obs.readingsPageSize)
  }
})

const {
  start: startPolling,
  toggle: togglePolling,
  isPolling,
} = usePolling(async () => {
  if (auth.role) {
    await obs.loadObservations()
  }
}, 10_000)

const doChartData = computed(() =>
  obs.observations.map((obs) => ({
    x: obs.capturedAt,
    y: obs.dissolvedOxygenMgL,
  })),
)

const phChartData = computed(() =>
  obs.observations.map((obs) => ({
    x: obs.capturedAt,
    y: obs.ph,
  })),
)

function doSourceTag(mode: string) {
  return mode === 'simulation' || mode === 'external_observation' ? 'success' : 'info'
}

function doSourceLabel(mode: string) {
  return mode === 'simulation'
    ? '塘口传感器'
    : mode === 'external_observation'
      ? '外部观测'
      : '未知来源'
}

function handlePageChange(page: number) {
  obs.loadReadingsPage(page, obs.readingsPageSize)
}

function handleSizeChange(size: number) {
  obs.loadReadingsPage(1, size)
}

onMounted(async () => {
  await load()
  startPolling()
})
</script>

<template>
  <div class="view-grid monitoring-grid">
    <!-- Cache warning banner -->
    <section
      v-if="obs.usingCachedObservations"
      class="banner warning-banner"
      role="alert"
      data-test="cache-warning"
    >
      <strong>离线缓存数据</strong>
      <span>当前离线，所见内容不是实时数据。最后同步时间 {{ obs.lastObservationSyncAt }}</span>
    </section>

    <!-- Load error banner -->
    <ErrorBanner
      v-if="loadError"
      message="观测数据加载出了问题，检查下网络。"
      @retry="loadObservationData"
    />

    <!-- Live status cards -->
    <section class="status-cards">
      <el-card
        shadow="hover"
        class="status-card"
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
      <el-card shadow="hover" class="status-card" :aria-label="`最新 pH: ${latestPh ?? '无数据'}`">
        <el-statistic v-if="latestPh !== null" title="最新 pH" :value="latestPh" :precision="2" />
        <div v-else class="stat-empty">
          <span class="stat-empty-label">最新 pH</span>
          <span class="stat-empty-value">—</span>
        </div>
      </el-card>
      <el-card
        shadow="hover"
        class="status-card"
        :aria-label="`观测记录数: ${obs.observations.length}`"
      >
        <el-statistic title="观测记录数" :value="obs.observations.length" />
      </el-card>
      <el-card shadow="hover" class="status-card" aria-label="轮询控制">
        <div class="polling-control">
          <span class="card-label">轮询状态</span>
          <span aria-live="polite">
            <el-tag
              :type="isPolling ? 'success' : 'info'"
              size="large"
              class="polling-tag"
              role="button"
              tabindex="0"
              :aria-pressed="isPolling"
              :aria-label="isPolling ? '暂停自动刷新' : '恢复自动刷新'"
              data-test="toggle-polling"
              @click="togglePolling"
              @keydown.enter="togglePolling"
              @keydown.space.prevent="togglePolling"
            >
              {{ isPolling ? '10s 自动刷新中 (点击暂停)' : '已暂停 (点击恢复)' }}
            </el-tag>
          </span>
        </div>
      </el-card>
    </section>

    <!-- Trend charts -->
    <section class="panel charts-panel" aria-label="趋势图">
      <div class="panel-heading">
        <h2>趋势图</h2>
      </div>
      <div class="charts-grid">
        <TrendChart
          :data="doChartData"
          label="溶氧 DO (mg/L)"
          color="var(--accent)"
          :threshold="6"
        />
        <TrendChart :data="phChartData" label="pH 值" color="var(--success)" />
      </div>
    </section>

    <!-- Readings table -->
    <section class="panel readings-panel" aria-label="观测数据表">
      <div class="panel-heading">
        <h2>官方观测配对读数</h2>
        <el-tag type="success" effect="plain">已验证 / 临时数据</el-tag>
      </div>
      <div class="table-scroll">
        <table class="readings-table">
          <caption class="sr-only">
            官方观测配对读数表
          </caption>
          <thead>
            <tr>
              <th scope="col">采集时间</th>
              <th scope="col">溶氧 mg/L</th>
              <th scope="col">pH</th>
              <th scope="col">来源模式</th>
              <th scope="col">质量状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="reading in obs.readingsPage" :key="reading.id" data-test="reading-row">
              <td>{{ reading.capturedAt }}</td>
              <td>
                <span class="do-cell">
                  {{ reading.dissolvedOxygenMgL.toFixed(1) }}
                  <span class="sr-only">{{
                    reading.dissolvedOxygenMgL >= 6
                      ? '正常'
                      : reading.dissolvedOxygenMgL >= 4
                        ? '偏低'
                        : '危险'
                  }}</span>
                  <span
                    class="do-indicator"
                    aria-hidden="true"
                    :style="{
                      background:
                        reading.dissolvedOxygenMgL >= 6
                          ? 'var(--success)'
                          : reading.dissolvedOxygenMgL >= 4
                            ? 'var(--warning-contrast)'
                            : 'var(--danger)',
                    }"
                    :title="
                      reading.dissolvedOxygenMgL >= 6
                        ? '正常'
                        : reading.dissolvedOxygenMgL >= 4
                          ? '偏低'
                          : '危险'
                    "
                  />
                </span>
              </td>
              <td>{{ reading.ph.toFixed(2) }}</td>
              <td>
                <el-tag :type="doSourceTag(reading.sourceMode)" size="small">
                  {{ doSourceLabel(reading.sourceMode) }}
                </el-tag>
              </td>
              <td>
                {{
                  { provisional: '临时数据', approved: '已批准', rejected: '已驳回' }[
                    reading.qualityStatus
                  ] ?? '未知'
                }}
                ({{ reading.sourceQualifiers }})
              </td>
            </tr>
            <tr v-if="obs.readingsPage.length === 0">
              <td colspan="5" class="empty-row">暂无观测数据</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="obs.readingsTotal > obs.readingsPageSize" class="pagination-wrap">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="obs.readingsTotal"
          :current-page="obs.readingsCurrentPage"
          :page-size="obs.readingsPageSize"
          :page-sizes="[20, 50, 100, 200]"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.monitoring-grid {
  gap: var(--sp-4);
}

.status-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-4);
}

.status-card :deep(.el-card__body) {
  padding: var(--sp-4) var(--sp-5);
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

.polling-control {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.card-label {
  color: var(--muted);
  font-size: var(--font-sm);
}

.charts-panel {
  padding: var(--sp-6);
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--sp-6);
}

.do-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
}

.do-indicator {
  display: inline-block;
  width: var(--do-indicator-size);
  height: var(--do-indicator-size);
  border-radius: 50%;
}

.status-tag {
  border: none;
  margin-left: var(--sp-2);
}

.polling-tag {
  cursor: pointer;
  margin-top: var(--sp-2);
  min-height: var(--sp-touch);
}

.polling-tag:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.empty-row {
  text-align: center;
  padding: var(--sp-6);
  color: var(--muted);
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  padding: var(--sp-4) var(--sp-6);
}

@media (max-width: 960px) {
  .status-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 580px) {
  .status-cards {
    grid-template-columns: 1fr;
  }
}

@media print {
  .status-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
