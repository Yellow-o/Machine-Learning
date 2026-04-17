<script setup lang="ts">
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted } from 'vue'

import TrendLineChart from '@/components/TrendLineChart.vue'
import { useDashboardStore } from '@/stores/dashboard'

const dashboardStore = useDashboardStore()

const kpis = computed(() => dashboardStore.overview.kpis)
const trend = computed(() => dashboardStore.overview.trend)
const recentEvents = computed(() => dashboardStore.overview.recent_events)

function fmtNum(value: number, digits = 0) {
  return Number(value || 0).toFixed(digits)
}

function fmtTime(value: string) {
  const dt = dayjs(value)
  return dt.isValid() ? dt.format('YYYY-MM-DD HH:mm:ss') : '-'
}

function tagType(status: string) {
  if (status === 'confirmed') return 'danger'
  if (status === 'pending') return 'warning'
  if (status === 'false_positive') return 'info'
  return 'primary'
}

function riskType(conf: number) {
  if (conf >= 0.85) return 'danger'
  if (conf >= 0.7) return 'warning'
  return 'success'
}

async function setWindow(days: 7 | 30) {
  try {
    await dashboardStore.loadOverview(days)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载失败')
  }
}

async function refresh() {
  try {
    await dashboardStore.loadOverview()
    ElMessage.success('看板数据已刷新')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '刷新失败')
  }
}

onMounted(async () => {
  await dashboardStore.loadOverview().catch(() => {})
  dashboardStore.startPolling()
})

onBeforeUnmount(() => {
  dashboardStore.stopPolling()
})
</script>

<template>
  <section class="grid fade-up">
    <header class="page-head">
      <div>
        <h3>运营风险总览</h3>
        <p>自动轮询周期 30 秒，可手动刷新</p>
      </div>
      <div class="head-actions">
        <el-segmented
          :model-value="dashboardStore.windowDays"
          :options="[
            { label: '近7天', value: 7 },
            { label: '近30天', value: 30 },
          ]"
          @change="(v) => setWindow(v as 7 | 30)"
        />
        <span class="stamp">{{ dashboardStore.loadedAt ? `更新于 ${dashboardStore.loadedAt}` : '未加载' }}</span>
        <el-button :loading="dashboardStore.loading" @click="refresh">刷新</el-button>
      </div>
    </header>

    <el-alert
      v-if="dashboardStore.error"
      type="error"
      show-icon
      :closable="false"
      :title="dashboardStore.error"
    />

    <div class="kpi-grid">
      <article class="panel kpi-item">
        <span>事件总数</span>
        <strong>{{ kpis.total_events }}</strong>
        <small>{{ dashboardStore.windowDays }} 天窗口</small>
      </article>
      <article class="panel kpi-item">
        <span>累计疲劳时长</span>
        <strong>{{ fmtNum(kpis.total_duration_sec, 1) }}s</strong>
        <small>窗口内时长总和</small>
      </article>
      <article class="panel kpi-item">
        <span>平均峰值风险</span>
        <strong>{{ fmtNum(kpis.avg_conf, 3) }}</strong>
        <small>越接近 1 风险越高</small>
      </article>
      <article class="panel kpi-item warn">
        <span>高风险事件</span>
        <strong>{{ kpis.high_risk_count }}</strong>
        <small>峰值风险 >= 0.80</small>
      </article>
    </div>

    <div class="status-strip panel">
      <el-tag type="primary" round effect="dark">系统判定 {{ kpis.auto_count }}</el-tag>
      <el-tag type="warning" round effect="dark">待复核 {{ kpis.pending_count }}</el-tag>
      <el-tag type="danger" round effect="dark">确认疲劳 {{ kpis.confirmed_count }}</el-tag>
      <el-tag type="info" round effect="dark">误报 {{ kpis.false_positive_count }}</el-tag>
    </div>

    <div class="chart-grid">
      <el-card class="panel chart-card" shadow="never">
        <template #header>事件次数趋势</template>
        <TrendLineChart title="事件次数" metric="event_count" :series="trend" />
      </el-card>
      <el-card class="panel chart-card" shadow="never">
        <template #header>疲劳时长趋势</template>
        <TrendLineChart title="疲劳时长(秒)" metric="duration_sec" :series="trend" color="#ff9f43" />
      </el-card>
    </div>

    <el-card class="panel" shadow="never">
      <template #header>近期事件</template>
      <el-table :data="recentEvents" stripe>
        <el-table-column prop="id" label="ID" width="78" />
        <el-table-column prop="driver_name" label="账号" min-width="120" />
        <el-table-column prop="source_label" label="标签" min-width="110" />
        <el-table-column label="风险值" width="130">
          <template #default="{ row }">
            <el-tag :type="riskType(row.peak_risk_conf)">{{ fmtNum(row.peak_risk_conf, 3) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="复核状态" width="126">
          <template #default="{ row }">
            <el-tag :type="tagType(row.review_status)">{{ row.review_status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" min-width="170">
          <template #default="{ row }">{{ fmtTime(row.start_time) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stamp {
  color: var(--ink-2);
  font-size: 12px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-item {
  padding: 14px;
  display: grid;
  gap: 4px;
}

.kpi-item span {
  color: var(--ink-2);
  font-size: 12px;
}

.kpi-item strong {
  font-size: 30px;
  color: var(--ink-0);
}

.kpi-item small {
  color: var(--ink-2);
}

.warn {
  border-color: rgba(255, 159, 67, 0.42);
}

.status-strip {
  padding: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chart-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.chart-card {
  overflow: hidden;
}

@media (max-width: 1080px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
