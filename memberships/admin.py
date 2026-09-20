from django.contrib import admin

from .models import Membership, MembershipPackage, Payment


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
    list_display = ("receipt_number", "member", "package", "amount", "status", "created_at")
    list_filter = ("status", "payment_method")
    search_fields = ("receipt_number", "member__email")
