from django.urls import path

from .views_v2 import (
    admin_users_list_v2,
    admin_users_update_v2,
    auth_login_v2,
    auth_register_v2,
    auth_logout_v2,
    auth_me_v2,
    dashboard_overview_v2,
    event_appeal_v2,
    event_detail_v2,
    event_review_v2,
    events_list_v2,
)

urlpatterns = [
    path("auth/login", auth_login_v2, name="api-v2-auth-login"),
    path("auth/register", auth_register_v2, name="api-v2-auth-register"),
    path("auth/logout", auth_logout_v2, name="api-v2-auth-logout"),
    path("auth/me", auth_me_v2, name="api-v2-auth-me"),
    path("dashboard/overview", dashboard_overview_v2, name="api-v2-dashboard-overview"),
    path("events", events_list_v2, name="api-v2-events-list"),
    path("events/<int:event_id>", event_detail_v2, name="api-v2-event-detail"),
    path("events/<int:event_id>/review", event_review_v2, name="api-v2-event-review"),
    path("events/<int:event_id>/appeal", event_appeal_v2, name="api-v2-event-appeal"),
    path("admin/users", admin_users_list_v2, name="api-v2-admin-users-list-create"),
    path("admin/users/<int:user_id>", admin_users_update_v2, name="api-v2-admin-users-update"),
]
