import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

FRONTEND_BASE_URL = os.getenv("DMS_FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")

urlpatterns = [
    path("admin/", admin.site.urls),
    # Default web entrypoints now point to the Vue frontend.
    path("", RedirectView.as_view(url=f"{FRONTEND_BASE_URL}/login", permanent=False)),
    path("login/", RedirectView.as_view(url=f"{FRONTEND_BASE_URL}/login", permanent=False)),
    path("signup/", RedirectView.as_view(url=f"{FRONTEND_BASE_URL}/register", permanent=False)),
    path("dashboard/", RedirectView.as_view(url=f"{FRONTEND_BASE_URL}/dashboard", permanent=False)),
    path("records/", RedirectView.as_view(url=f"{FRONTEND_BASE_URL}/events", permanent=False)),
    path("", include("monitoring.urls")),
    path("api/", include("monitoring.api_urls")),
    path("api/v2/", include("monitoring.api_v2_urls")),
    # Backward-compatible page entrypoints under /api/*
    path("api/login/", RedirectView.as_view(url="/login/", permanent=False)),
    path("api/signup/", RedirectView.as_view(url="/signup/", permanent=False)),
    path("api/logout/", RedirectView.as_view(url="/logout/", permanent=False)),
    path("api/records/", RedirectView.as_view(url="/records/", permanent=False)),
    path("api/dashboard/", RedirectView.as_view(url="/dashboard/", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
