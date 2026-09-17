from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CoachAssignment, CoachProfile, MemberProfile, User


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
