import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getCurrentSession, loginByUidOrPhone, logoutCurrentUser, registerDriver } from '@/api/http'
import type { RegisterInput, User } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)
  const checking = ref(false)
  const initialized = ref(false)

  const isLoggedIn = computed(() => Boolean(user.value))
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function fetchSession(silent = true) {
    checking.value = true
    try {
      const payload = await getCurrentSession()
      user.value = payload.session.user
      initialized.value = true
      return user.value
    } catch {
      user.value = null
      initialized.value = true
      if (!silent) {
        throw new Error('登录状态已失效，请重新登录')
      }
      return null
    } finally {
      checking.value = false
    }
  }

  async function login(loginId: string, password: string) {
    loading.value = true
    try {
      const payload = await loginByUidOrPhone(loginId, password)
      user.value = payload.session.user
      initialized.value = true
      return payload.session.user
    } finally {
      loading.value = false
    }
  }

  async function register(input: RegisterInput) {
    loading.value = true
    try {
      const payload = await registerDriver(input)
      user.value = payload.session.user
      initialized.value = true
      return payload.session.user
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await logoutCurrentUser()
    } finally {
      user.value = null
      initialized.value = true
    }
  }

  return {
    user,
    loading,
    checking,
    initialized,
    isLoggedIn,
    isAdmin,
    fetchSession,
    login,
    register,
    logout,
  }
})
