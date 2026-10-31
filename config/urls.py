from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from core.views import HealthView

api = [
    path("health", HealthView.as_view()),
    path("", include("accounts.urls")),
    path("", include("bookings.urls")),
    path("", include("content.urls")),
]

urlpatterns = [
    path("v1/", include(api)),
    path("django-admin/", admin.site.urls),
]

if settings.SERVE_MEDIA:
    # Uploaded images on local disk. In production, prefer S3-compatible storage (S3_BUCKET).
    urlpatterns.append(re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}))

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
