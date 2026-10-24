from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from gym.models import (
    AttendanceRecord,
    Booking,
    CoachAssignment,
    CoachProfile,
    Exercise,
    GymConfiguration,
    MemberProfile,
    MemberQRCode,
    Membership,
    MembershipPackage,
    Notice,
    Notification,
    OutdoorActivity,
    Payment,
    Service,
    Session,
    User,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)

# Accounts and profiles — Rheva

# 2.3 Fitness information and goals


@admin.register(User)
class FitSyncUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("FitSync", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("FitSync", {"fields": ("email", "first_name", "last_name", "role")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active")
    list_filter = UserAdmin.list_filter + ("role",)


admin.site.register(MemberProfile)
admin.site.register(CoachProfile)
admin.site.register(CoachAssignment)


# Memberships and payments — Noorie


@admin.register(MembershipPackage)
class MembershipPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "duration_months", "is_featured", "is_active")
    list_filter = ("is_active", "is_featured")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("member", "package", "start_date", "end_date", "status")
    list_filter = ("status", "package")
    search_fields = ("member__email", "member__first_name", "member__last_name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "member",
        "package",
        "amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "payment_method")
    search_fields = ("receipt_number", "member__email")


# Services, sessions and bookings — Mehnaz

# 3.6 Manage scheduled sessions


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """Allows administrators to manage gym services."""

    list_display = ("name", "service_type", "price", "is_active")
    list_filter = ("service_type", "is_active")
    search_fields = ("name", "description")


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
    list_filter = ("status", "date", "service__service_type")
    search_fields = (
        "service__name",
        "instructor__first_name",
        "instructor__last_name",
        "instructor__email",
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Allows administrators to view and manage member bookings."""

    list_display = ("member", "session", "status", "booked_at", "cancelled_at")
    list_filter = ("status", "session__date")
    search_fields = (
        "member__first_name",
        "member__last_name",
        "member__email",
        "session__service__name",
    )
    readonly_fields = ("booked_at", "cancelled_at")


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "equipment", "difficulty", "is_active")
    list_filter = ("category", "equipment", "difficulty", "is_active")
    search_fields = ("name", "secondary_muscles")


class WorkoutPlanExerciseInline(admin.TabularInline):
    model = WorkoutPlanExercise
    extra = 0


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "member", "plan_type", "coach", "is_active")
    list_filter = ("plan_type", "is_active")
    inlines = [WorkoutPlanExerciseInline]


admin.site.register(WorkoutSession)
admin.site.register(WorkoutExerciseRecord)
admin.site.register(WeightRecord)


# Attendance — Bhavshika

# 4.8 Attendance corrections


admin.site.register(MemberQRCode)
admin.site.register(AttendanceRecord)
admin.site.register(GymConfiguration)


# Outdoor activities — Bhavshika

# 2.19 GPS activity (mobile phase); 2.20 Activity history


admin.site.register(OutdoorActivity)


# Notifications and notices — Anjie


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
