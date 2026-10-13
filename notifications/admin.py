from django.contrib import admin

from .models import Notice, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("title", "message", "recipient__email")


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "publish_date", "expires_on", "is_active")
    list_filter = ("is_active", "publish_date")
    search_fields = ("title", "message")
