from django.contrib import admin

from .models import Booking, Service, Session


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """Allows administrators to manage gym services."""

    list_display = (
        "name",
        "service_type",
        "price",
        "is_active",
    )
    list_filter = (
        "service_type",
        "is_active",
    )
    search_fields = (
        "name",
        "description",
    )


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    """Allows administrators to manage scheduled sessions."""

    list_display = (
        "service",
        "date",
        "start_time",
        "end_time",
        "instructor",
        "capacity",
        "status",
    )
    list_filter = (
        "status",
        "date",
        "service__service_type",
    )
    search_fields = (
        "service__name",
        "instructor__first_name",
        "instructor__last_name",
        "instructor__email",
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Allows administrators to view and manage member bookings."""

    list_display = (
        "member",
        "session",
        "status",
        "booked_at",
        "cancelled_at",
    )
    list_filter = (
        "status",
        "session__date",
    )
    search_fields = (
        "member__first_name",
        "member__last_name",
        "member__email",
        "session__service__name",
    )
    readonly_fields = (
        "booked_at",
        "cancelled_at",
    )
