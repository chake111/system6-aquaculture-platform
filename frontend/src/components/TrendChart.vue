<script setup lang="ts">
import { computed } from 'vue'

import { lttb, type Point } from '@/utils/lttb'

const props = withDefaults(
  defineProps<{
    data: Point[]
    label: string
    color: string
    threshold?: number
    maxPoints?: number
  }>(),
  { threshold: undefined, maxPoints: 200 },
)

const displayData = computed(() =>
  props.data.length > props.maxPoints ? lttb(props.data, props.maxPoints) : props.data,
)

const width = 500
const height = 180
const padding = { top: 20, right: 20, bottom: 30, left: 45 }

const chartWidth = width - padding.left - padding.right
const chartHeight = height - padding.top - padding.bottom

const yRange = computed(() => {
  if (displayData.value.length === 0) return { min: 0, max: 10 }
  const values = displayData.value.map((d) => d.y)
  const dataMin = Math.min(...values)
  const dataMax = Math.max(...values)
  const thresholdMax =
    props.threshold !== undefined ? Math.max(dataMax, props.threshold + 1) : dataMax
  const thresholdMin =
    props.threshold !== undefined ? Math.min(dataMin, props.threshold - 1) : dataMin
  const range = thresholdMax - thresholdMin || 1
  return {
    min: thresholdMin - range * 0.1,
    max: thresholdMax + range * 0.1,
  }
})

function scaleY(value: number): number {
  const { min, max } = yRange.value
  return chartHeight - ((value - min) / (max - min)) * chartHeight
}

function scaleX(index: number): number {
  if (displayData.value.length <= 1) return chartWidth / 2
  return (index / (displayData.value.length - 1)) * chartWidth
}

const polylinePoints = computed(() => {
  return displayData.value.map((d, i) => `${scaleX(i)},${scaleY(d.y)}`).join(' ')
})

const thresholdY = computed(() => {
  if (props.threshold === undefined) return null
  return scaleY(props.threshold)
})

const yTicks = computed(() => {
  const { min, max } = yRange.value
  const step = (max - min) / 4
  return Array.from({ length: 5 }, (_, i) => {
    const value = min + step * i
    return { y: scaleY(value), label: value.toFixed(1) }
  })
})

const xLabels = computed(() => {
  if (displayData.value.length === 0) return []
  const step = Math.max(1, Math.floor(displayData.value.length / 6))
  return displayData.value
    .map((d, i) => ({ i, d }))
    .filter(({ i }) => i % step === 0 || i === displayData.value.length - 1)
    .map(({ i, d }) => ({
      x: scaleX(i),
      label: d.x.length > 10 ? d.x.slice(11, 16) : d.x,
    }))
})
</script>

<template>
  <div class="trend-chart">
    <h4 class="trend-chart-label">{{ label }}</h4>
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      :width="width"
      :height="height"
      class="trend-svg"
      role="img"
      :aria-label="`${label} 趋势图`"
      preserveAspectRatio="xMidYMid meet"
    >
      <title>{{ label }}</title>
      <desc>
        {{ data.length }} 个数据点{{
          data.length > displayData.length ? `（显示 ${displayData.length} 个）` : ''
        }}，范围 {{ yRange.min.toFixed(1) }} 至 {{ yRange.max.toFixed(1) }}
      </desc>
      <g :transform="`translate(${padding.left}, ${padding.top})`">
        <!-- Y-axis grid lines and labels -->
        <g v-for="tick in yTicks" :key="tick.label">
          <line
            :x1="0"
            :y1="tick.y"
            :x2="chartWidth"
            :y2="tick.y"
            stroke="var(--line)"
            stroke-width="1"
          />
          <text :x="-8" :y="tick.y + 4" text-anchor="end" fill="var(--muted)">
            {{ tick.label }}
          </text>
        </g>

        <!-- X-axis labels -->
        <text
          v-for="labelItem in xLabels"
          :key="labelItem.x"
          :x="labelItem.x"
          :y="chartHeight + 20"
          text-anchor="middle"
          fill="var(--muted)"
        >
          {{ labelItem.label }}
        </text>

        <!-- Threshold line -->
        <line
          v-if="threshold !== undefined && thresholdY !== null"
          :x1="0"
          :y1="thresholdY"
          :x2="chartWidth"
          :y2="thresholdY"
          stroke="var(--danger)"
          stroke-width="1.5"
          stroke-dasharray="6 3"
        />
        <text
          v-if="threshold !== undefined && thresholdY !== null"
          :x="chartWidth - 4"
          :y="thresholdY - 5"
          text-anchor="end"
          fill="var(--danger)"
          font-weight="600"
        >
          {{ threshold }}
        </text>

        <!-- Data polyline -->
        <polyline
          v-if="displayData.length > 1"
          :points="polylinePoints"
          fill="none"
          :stroke="color"
          stroke-width="2"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <!-- Data points -->
        <circle
          v-for="(point, i) in displayData"
          :key="i"
          :cx="scaleX(i)"
          :cy="scaleY(point.y)"
          r="3"
          :fill="color"
          stroke="var(--surface)"
          stroke-width="1"
        >
          <title>{{ point.x }}: {{ point.y.toFixed(2) }}</title>
        </circle>
      </g>
    </svg>
    <p v-if="displayData.length < 2" class="trend-chart-empty">
      数据不足，至少需要 2 个数据点才能显示趋势。
    </p>
  </div>
</template>

<style scoped>
.trend-chart {
  margin-bottom: var(--sp-4);
}

.trend-chart-label {
  margin: 0 0 var(--sp-2);
  color: var(--text);
  font-size: var(--font-base);
  font-weight: 650;
}

.trend-svg {
  display: block;
  max-width: 100%;
  height: auto;
}

.trend-svg text {
  font-size: var(--font-xs);
}

.trend-chart-empty {
  margin-top: var(--sp-2);
  color: var(--muted);
  font-size: var(--font-sm);
  text-align: center;
}
</style>
