export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  request_id: string
  timestamp: string
}

export type UserRole = 'admin' | 'driver'

export interface User {
  id: number
  username: string
  display_name: string
  full_name: string
  phone: string
  role: UserRole
  is_staff: boolean
  is_superuser: boolean
  is_active: boolean
  can_access_dashboard: boolean
}

export interface AuthSession {
  session: {
    user: User
  }
}

export interface RegisterInput {
  username: string
  password: string
  full_name?: string
  phone: string
  id_card?: string
}

export type EventReviewStatus = 'auto' | 'pending' | 'confirmed' | 'false_positive'

export interface EventItem {
  id: number
  driver_name: string
  event_type: string
  event_type_display: string
  source_event_id: string
  source_session_id: string
  source_label: string
  start_time: string
  end_time: string
  duration_sec: number
  peak_risk_conf: number
  review_status: EventReviewStatus
  review_status_display: string
  trigger_frames: number
  recover_frames: number
  snapshot_path: string
  snapshot_sha256: string
  owner_username: string
  permissions?: {
    can_review: boolean
    can_appeal: boolean
  }
}

export interface EventSummary {
  total: number
  total_duration_sec: number
  avg_conf: number
  max_conf: number
  pending_count: number
  confirmed_count: number
  false_positive_count: number
  auto_count: number
}

export interface EventPagination {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface EventsListPayload {
  items: EventItem[]
  summary: EventSummary
  pagination: EventPagination
  filters: {
    q: string
    review_status: string
    start_date: string
    end_date: string
    min_conf: number | null
  }
  meta: {
    is_admin: boolean
  }
}

export interface EventDetailPayload {
  item: EventItem
}

export interface DashboardKpis {
  total_events: number
  total_duration_sec: number
  avg_conf: number
  max_conf: number
  high_risk_count: number
  pending_count: number
  confirmed_count: number
  false_positive_count: number
  auto_count: number
}

export interface TrendPoint {
  day: string
  event_count: number
  duration_sec: number
  avg_conf: number
}

export interface DashboardOverviewPayload {
  window_days: 7 | 30
  kpis: DashboardKpis
  trend: TrendPoint[]
  recent_events: EventItem[]
  meta: {
    is_admin: boolean
  }
}

export interface AdminUser extends User {}

export interface AdminUsersPayload {
  items: AdminUser[]
  pagination: EventPagination
  filters: {
    q: string
    role: '' | UserRole
    is_active: boolean | null
  }
}

export interface AdminUserUpsertInput {
  username?: string
  password?: string
  full_name?: string
  role?: UserRole
  phone?: string
  id_card?: string
  is_active?: boolean
}
