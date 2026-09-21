from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("memberships/", include("memberships.urls")),
    path("", include("core.urls")),
    path("attendance/", include("attendance.urls")),
    path("activities/", include("activities.urls")),
]
