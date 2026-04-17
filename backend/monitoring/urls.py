from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    RoleBasedLoginView,
    dashboard,
    event_detail_page,
    event_report_api,
    export_records_csv,
    health,
    home,
    recent_events_api,
    records_page,
    session_report_api,
    signup,
)

urlpatterns = [
    path("", home, name="home"),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    path("signup/", signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("records/", records_page, name="records-page"),
    path("records/export/", export_records_csv, name="records-export"),
    path("records/<int:event_id>/", event_detail_page, name="event-detail"),
    path("health/", health, name="health"),
    path("events/recent/", recent_events_api, name="recent-events"),
    path("events/report/", event_report_api, name="event-report"),
    path("sessions/report/", session_report_api, name="session-report"),
]
