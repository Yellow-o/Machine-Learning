import dayjs from 'dayjs'
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getDashboardOverview } from '@/api/http'
import type { DashboardOverviewPayload } from '@/types/api'

const EMPTY_OVERVIEW: DashboardOverviewPayload = {
  window_days: 7,
  kpis: {
    total_events: 0,
    total_duration_sec: 0,
    avg_conf: 0,
    max_conf: 0,
    high_risk_count: 0,
    pending_count: 0,
    confirmed_count: 0,
    false_positive_count: 0,
    auto_count: 0,
  },
  trend: [],
  recent_events: [],
  meta: {
    is_admin: false,
  },
}

export const useDashboardStore = defineStore('dashboard', () => {
  const loading = ref(false)
  const error = ref('')
  const overview = ref<DashboardOverviewPayload>(EMPTY_OVERVIEW)
  const loadedAt = ref('')
  const windowDays = ref<7 | 30>(7)
  const pollingHandle = ref<number | null>(null)

  async function loadOverview(days = windowDays.value) {
    loading.value = true
    error.value = ''
    try {
      const payload = await getDashboardOverview(days)
      overview.value = payload
      windowDays.value = payload.window_days
      loadedAt.value = dayjs().format('YYYY-MM-DD HH:mm:ss')
    } catch (err) {
      error.value = err instanceof Error ? err.message : '看板数据加载失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  function stopPolling() {
    if (pollingHandle.value !== null) {
      window.clearInterval(pollingHandle.value)
      pollingHandle.value = null
    }
  }

  function startPolling() {
    stopPolling()
    pollingHandle.value = window.setInterval(() => {
      loadOverview().catch(() => {})
    }, 30_000)
  }

  return {
    loading,
    error,
    overview,
    loadedAt,
    windowDays,
    loadOverview,
    startPolling,
    stopPolling,
  }
})
