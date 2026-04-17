import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'

import { createAdminUser, getAdminUsers, updateAdminUser } from '@/api/http'
import type { AdminUser, AdminUserUpsertInput, EventPagination } from '@/types/api'

const EMPTY_PAGINATION: EventPagination = {
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 1,
}

export const useAdminUsersStore = defineStore('adminUsers', () => {
  const loading = ref(false)
  const actionLoading = ref(false)
  const error = ref('')

  const items = ref<AdminUser[]>([])
  const pagination = ref<EventPagination>(EMPTY_PAGINATION)

  const filters = reactive({
    q: '',
    role: '' as '' | 'admin' | 'driver',
    is_active: '' as '' | 'true' | 'false',
  })

  async function fetchList(resetPage = false) {
    loading.value = true
    error.value = ''
    try {
      if (resetPage) {
        pagination.value.page = 1
      }
      const payload = await getAdminUsers({
        q: filters.q || undefined,
        role: filters.role,
        is_active: filters.is_active,
        page: pagination.value.page,
        page_size: pagination.value.page_size,
      })
      items.value = payload.items
      pagination.value = payload.pagination
    } catch (err) {
      error.value = err instanceof Error ? err.message : '账号列表加载失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createUser(input: AdminUserUpsertInput) {
    actionLoading.value = true
    try {
      await createAdminUser(input)
      await fetchList()
    } finally {
      actionLoading.value = false
    }
  }

  async function patchUser(userId: number, input: AdminUserUpsertInput) {
    actionLoading.value = true
    try {
      await updateAdminUser(userId, input)
      await fetchList()
    } finally {
      actionLoading.value = false
    }
  }

  function resetFilters() {
    filters.q = ''
    filters.role = ''
    filters.is_active = ''
  }

  return {
    loading,
    actionLoading,
    error,
    items,
    pagination,
    filters,
    fetchList,
    createUser,
    patchUser,
    resetFilters,
  }
})
