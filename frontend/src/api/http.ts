import axios, { AxiosError, type AxiosRequestConfig } from 'axios'

import type {
  AdminUser,
  AdminUserUpsertInput,
  AdminUsersPayload,
  ApiEnvelope,
  AuthSession,
  DashboardOverviewPayload,
  RegisterInput,
  EventDetailPayload,
  EventsListPayload,
} from '@/types/api'

const http = axios.create({
  baseURL: '/api/v2',
  timeout: 15000,
  withCredentials: true,
})

export class ApiRequestError extends Error {
  code: number
  status?: number

  constructor(message: string, code: number, status?: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function requestData<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const { data } = await http.request<ApiEnvelope<T>>(config)
    if (!data || typeof data.code !== 'number') {
      throw new ApiRequestError('invalid server response', 1500)
    }
    if (data.code !== 0) {
      throw new ApiRequestError(data.message || 'request failed', data.code)
    }
    return data.data
  } catch (err) {
    if (err instanceof ApiRequestError) {
      throw err
    }

    const axiosErr = err as AxiosError<ApiEnvelope<unknown>>
    const status = axiosErr.response?.status
    const payload = axiosErr.response?.data
    if (payload && typeof payload.code === 'number') {
      throw new ApiRequestError(payload.message || 'request failed', payload.code, status)
    }

    throw new ApiRequestError(axiosErr.message || 'network error', status || 1500, status)
  }
}

export function loginByUidOrPhone(loginId: string, password: string) {
  return requestData<AuthSession>({
    url: '/auth/login',
    method: 'POST',
    data: {
      login_id: loginId,
      password,
    },
  })
}

export function registerDriver(input: RegisterInput) {
  return requestData<AuthSession>({
    url: '/auth/register',
    method: 'POST',
    data: input,
  })
}

export function logoutCurrentUser() {
  return requestData<{ logged_out: boolean }>({
    url: '/auth/logout',
    method: 'POST',
  })
}

export function getCurrentSession() {
  return requestData<AuthSession>({
    url: '/auth/me',
    method: 'GET',
  })
}

export function getDashboardOverview(days: 7 | 30 = 7) {
  return requestData<DashboardOverviewPayload>({
    url: '/dashboard/overview',
    method: 'GET',
    params: { days },
  })
}

export interface EventsQuery {
  q?: string
  review_status?: string
  min_conf?: number | string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export function getEvents(params: EventsQuery) {
  return requestData<EventsListPayload>({
    url: '/events',
    method: 'GET',
    params,
  })
}

export function getEventDetail(eventId: number) {
  return requestData<EventDetailPayload>({
    url: `/events/${eventId}`,
    method: 'GET',
  })
}

export function reviewEvent(eventId: number, reviewStatus: 'confirmed' | 'false_positive', note: string) {
  return requestData<EventDetailPayload>({
    url: `/events/${eventId}/review`,
    method: 'PATCH',
    data: {
      review_status: reviewStatus,
      note,
    },
  })
}

export function appealEvent(eventId: number, note: string) {
  return requestData<EventDetailPayload>({
    url: `/events/${eventId}/appeal`,
    method: 'PATCH',
    data: {
      note,
    },
  })
}

export interface AdminUsersQuery {
  q?: string
  role?: '' | 'admin' | 'driver'
  is_active?: '' | 'true' | 'false'
  page?: number
  page_size?: number
}

export function getAdminUsers(params: AdminUsersQuery) {
  return requestData<AdminUsersPayload>({
    url: '/admin/users',
    method: 'GET',
    params,
  })
}

export function createAdminUser(input: AdminUserUpsertInput) {
  return requestData<{ item: AdminUser }>({
    url: '/admin/users',
    method: 'POST',
    data: input,
  })
}

export function updateAdminUser(userId: number, input: AdminUserUpsertInput) {
  return requestData<{ item: AdminUser }>({
    url: `/admin/users/${userId}`,
    method: 'PATCH',
    data: input,
  })
}

export default http
