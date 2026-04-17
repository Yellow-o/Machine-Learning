from django.urls import path

from .views import (
    api_login,
    dashboard_overview_api,
    event_report_api,
    events_list_api,
    health,
    recent_events_api,
    session_report_api,
)

urlpatterns = [
    path("auth/login/", api_login, name="api-login"),
    path("health/", health, name="api-health"),
    path("dashboard/overview/", dashboard_overview_api, name="api-dashboard-overview"),
    path("events/", events_list_api, name="api-events-list"),
    path("events/recent/", recent_events_api, name="api-recent-events"),
    path("events/report/", event_report_api, name="api-event-report"),
    path("sessions/report/", session_report_api, name="api-session-report"),
]
