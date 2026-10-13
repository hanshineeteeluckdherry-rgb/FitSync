from django.urls import path

from . import views


app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("<int:notification_id>/", views.notification_detail, name="detail"),
    path("<int:notification_id>/read/", views.mark_as_read, name="mark_as_read"),
    path("read-all/", views.mark_all_as_read, name="mark_all_as_read"),
    path("manage/notices/", views.notice_list, name="notice_list"),
    path("manage/notices/add/", views.notice_create, name="notice_create"),
    path("manage/notices/<int:notice_id>/edit/", views.notice_edit, name="notice_edit"),
    path("manage/notices/<int:notice_id>/delete/", views.notice_delete, name="notice_delete"),
]
