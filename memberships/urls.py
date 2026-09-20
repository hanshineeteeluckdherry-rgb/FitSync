from django.urls import path

from . import views

app_name = "memberships"

urlpatterns = [
    path("", views.public_packages, name="public_packages"),
    path("plans/<slug:slug>/", views.public_package_detail, name="public_package_detail"),
    path("auth-required/<int:package_id>/", views.auth_required, name="auth_required"),
    path("member/plans/", views.member_packages, name="member_packages"),
    path("member/current/", views.current_membership, name="current_membership"),
    path("member/history/", views.membership_history, name="membership_history"),
    path("member/payments/", views.payment_history, name="payment_history"),
    path("member/checkout/<int:package_id>/", views.checkout, name="checkout"),
    path("member/renew/<int:membership_id>/", views.renew_membership, name="renew_membership"),
    path("member/payment/<int:payment_id>/success/", views.payment_success, name="payment_success"),
    path("member/payment/<int:payment_id>/failed/", views.payment_failed, name="payment_failed"),
    path("member/receipt/<int:payment_id>/", views.receipt, name="receipt"),
    path("manage/packages/", views.admin_package_list, name="admin_package_list"),
    path("manage/packages/add/", views.admin_package_create, name="admin_package_create"),
    path("manage/packages/<int:package_id>/edit/", views.admin_package_edit, name="admin_package_edit"),
    path("manage/packages/<int:package_id>/toggle/", views.admin_package_toggle, name="admin_package_toggle"),
    path("manage/memberships/", views.admin_membership_list, name="admin_membership_list"),
    path("manage/payments/", views.admin_payment_list, name="admin_payment_list"),
    path("manage/payments/<int:payment_id>/", views.admin_payment_detail, name="admin_payment_detail"),
    path("manage/report/", views.admin_membership_report, name="admin_membership_report"),
]
