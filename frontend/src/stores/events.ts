import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'

import { appealEvent, getEventDetail, getEvents, reviewEvent } from '@/api/http'
import type { EventDetailPayload, EventItem, EventPagination, EventSummary } from '@/types/api'

const EMPTY_SUMMARY: EventSummary = {
  total: 0,
  total_duration_sec: 0,
  avg_conf: 0,
  max_conf: 0,
  pending_count: 0,
  confirmed_count: 0,
  false_positive_count: 0,
  auto_count: 0,
}

const EMPTY_PAGINATION: EventPagination = {
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 1,
}

export const useEventsStore = defineStore('events', () => {
  const loading = ref(false)
  const detailLoading = ref(false)
  const actionLoading = ref(false)
  const error = ref('')

  const items = ref<EventItem[]>([])
  const summary = ref<EventSummary>(EMPTY_SUMMARY)
  const pagination = ref<EventPagination>(EMPTY_PAGINATION)
  const selectedEvent = ref<EventItem | null>(null)

  const filters = reactive({
    q: '',
    review_status: '',
    min_conf: '',
    start_date: '',
    end_date: '',
  })

  async function fetchList(resetPage = false) {
    loading.value = true
    error.value = ''
    try {
      if (resetPage) {
        pagination.value.page = 1
      }
      const payload = await getEvents({
        q: filters.q || undefined,
        review_status: filters.review_status || undefined,
        min_conf: filters.min_conf === '' ? undefined : filters.min_conf,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
        page: pagination.value.page,
        page_size: pagination.value.page_size,
      })
      items.value = payload.items
      summary.value = payload.summary
      pagination.value = payload.pagination
    } catch (err) {
      error.value = err instanceof Error ? err.message : '事件加载失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(eventId: number) {
    detailLoading.value = true
    try {
      const payload = await getEventDetail(eventId)
      selectedEvent.value = payload.item
      return payload.item
    } finally {
      detailLoading.value = false
    }
  }

  function applySingleEventUpdate(payload: EventDetailPayload) {
    selectedEvent.value = payload.item
    const idx = items.value.findIndex((item) => item.id === payload.item.id)
    if (idx >= 0) {
      items.value[idx] = { ...items.value[idx], ...payload.item }
    }
  }

  async function review(eventId: number, reviewStatus: 'confirmed' | 'false_positive', note: string) {
    actionLoading.value = true
    try {
      const payload = await reviewEvent(eventId, reviewStatus, note)
      applySingleEventUpdate(payload)
      await fetchList()
    } finally {
      actionLoading.value = false
    }
  }

  async function appeal(eventId: number, note: string) {
    actionLoading.value = true
    try {
      const payload = await appealEvent(eventId, note)
      applySingleEventUpdate(payload)
      await fetchList()
    } finally {
      actionLoading.value = false
    }
  }

  function resetFilters() {
    filters.q = ''
    filters.review_status = ''
    filters.min_conf = ''
    filters.start_date = ''
    filters.end_date = ''
  }

  return {
    loading,
    detailLoading,
    actionLoading,
    error,
    items,
    summary,
    pagination,
    selectedEvent,
    filters,
    fetchList,
    fetchDetail,
    review,
    appeal,
    resetFilters,
  }
})
