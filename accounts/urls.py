from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import StyledPasswordResetForm, StyledSetPasswordForm

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path("dashboard/member/", views.member_dashboard, name="member_dashboard"),
    path("dashboard/staff/", views.staff_dashboard, name="staff_dashboard"),
    path("dashboard/coach/", views.coach_dashboard, name="coach_dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("password/change/", views.password_change, name="password_change"),
    path("password/change/done/", views.password_change_done, name="password_change_done"),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            form_class=StyledPasswordResetForm,
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            form_class=StyledSetPasswordForm,
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("manage/users/", views.admin_user_list, name="admin_user_list"),
    path("manage/users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"),
    path("manage/users/<int:user_id>/role/", views.admin_user_role, name="admin_user_role"),
    path("manage/users/<int:user_id>/status/", views.admin_user_status, name="admin_user_status"),
    path("manage/coach-assignments/", views.coach_assignment_list, name="coach_assignment_list"),
    path("manage/coach-assignments/add/", views.coach_assignment_create, name="coach_assignment_create"),
    path(
        "manage/coach-assignments/<int:assignment_id>/delete/",
        views.coach_assignment_delete,
        name="coach_assignment_delete",
    ),
    path("staff/members/", views.staff_member_list, name="staff_member_list"),
    path("staff/members/<int:user_id>/", views.staff_member_detail, name="staff_member_detail"),
]
