<script setup lang="ts">
import type { ECharts, EChartsOption } from 'echarts'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as echarts from 'echarts/core'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { TrendPoint } from '@/types/api'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    title: string
    metric: 'event_count' | 'duration_sec' | 'avg_conf'
    series: TrendPoint[]
    color?: string
  }>(),
  {
    color: '#3ecbff',
  },
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null

const labels = computed(() => props.series.map((item) => item.day.slice(5)))
const values = computed(() => props.series.map((item) => Number(item[props.metric] ?? 0)))

function buildOption(): EChartsOption {
  return {
    backgroundColor: 'transparent',
    grid: {
      top: 26,
      right: 18,
      bottom: 28,
      left: 42,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0f1a2d',
      borderColor: '#34507b',
      textStyle: { color: '#dbe9ff' },
    },
    xAxis: {
      type: 'category',
      data: labels.value,
      axisLine: { lineStyle: { color: '#355179' } },
      axisLabel: { color: '#8ea6ca' },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(70, 98, 140, 0.35)' } },
      axisLabel: { color: '#8ea6ca' },
    },
    series: [
      {
        name: props.title,
        type: 'line',
        smooth: true,
        symbolSize: 7,
        data: values.value,
        lineStyle: { width: 2.6, color: props.color },
        itemStyle: { color: props.color },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(61,198,255,0.35)' },
            { offset: 1, color: 'rgba(61,198,255,0.02)' },
          ]),
        },
      },
    ],
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  chart.setOption(buildOption(), true)
}

function onResize() {
  chart?.resize()
}

watch(() => props.series, renderChart, { deep: true })
watch(() => props.metric, renderChart)

onMounted(() => {
  renderChart()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="chartRef" class="chart" />
</template>

<style scoped>
.chart {
  width: 100%;
  height: 250px;
}
</style>
