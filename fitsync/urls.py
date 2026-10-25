from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from gym import views
from gym.forms import StyledPasswordResetForm, StyledSetPasswordForm


# Accounts and profiles — Rheva

# 1.4 Registration; 1.5 Login and password reset; 2.1–2.3 Member account; 3.1 Staff and coach login; 4.1–4.3 Administration; 4.12 Coach assignment
accounts_routes = [
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
    path(
        "password/change/done/", views.password_change_done, name="password_change_done"
    ),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="authentication/password_reset_form.html",
            email_template_name="authentication/password_reset_email.html",
            subject_template_name="authentication/password_reset_subject.txt",
            form_class=StyledPasswordResetForm,
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="authentication/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="authentication/password_reset_confirm.html",
            form_class=StyledSetPasswordForm,
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="authentication/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("manage/users/", views.admin_user_list, name="admin_user_list"),
    path("manage/users/add/", views.admin_user_create, name="admin_user_create"),
    path(
        "manage/users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"
    ),
    path(
        "manage/users/<int:user_id>/role/",
        views.admin_user_role,
        name="admin_user_role",
    ),
    path(
        "manage/users/<int:user_id>/status/",
        views.admin_user_status,
        name="admin_user_status",
    ),
    path(
        "manage/coach-assignments/",
        views.coach_assignment_list,
        name="coach_assignment_list",
    ),
    path(
        "manage/coach-assignments/add/",
        views.coach_assignment_create,
        name="coach_assignment_create",
    ),
    path(
        "manage/coach-assignments/<int:assignment_id>/delete/",
        views.coach_assignment_delete,
        name="coach_assignment_delete",
    ),
    path("staff/members/", views.staff_member_list, name="staff_member_list"),
    path(
        "staff/members/<int:user_id>/",
        views.staff_member_detail,
        name="staff_member_detail",
    ),
]

# Memberships and payments — Noorie

# 1.2 Package comparison; 2.4–2.6 Membership and payment; 4.4–4.5 Membership management
memberships_routes = [
    path("", views.public_packages, name="public_packages"),
    path(
        "plans/<slug:slug>/", views.public_package_detail, name="public_package_detail"
    ),
    path("auth-required/<int:package_id>/", views.auth_required, name="auth_required"),
    path("member/plans/", views.member_packages, name="member_packages"),
    path("member/current/", views.current_membership, name="current_membership"),
    path("member/history/", views.membership_history, name="membership_history"),
    path("member/payments/", views.payment_history, name="payment_history"),
    path("member/checkout/<int:package_id>/", views.checkout, name="checkout"),
    path(
        "member/renew/<int:membership_id>/",
        views.renew_membership,
        name="renew_membership",
    ),
    path(
        "member/payment/<int:payment_id>/success/",
        views.payment_success,
        name="payment_success",
    ),
    path(
        "member/payment/<int:payment_id>/failed/",
        views.payment_failed,
        name="payment_failed",
    ),
    path("member/receipt/<int:payment_id>/", views.receipt, name="receipt"),
    path(
        "member/receipt/<int:payment_id>/download/",
        views.receipt_download,
        name="receipt_download",
    ),
    path("manage/packages/", views.admin_package_list, name="admin_package_list"),
    path(
        "manage/packages/add/", views.admin_package_create, name="admin_package_create"
    ),
    path(
        "manage/packages/<int:package_id>/edit/",
        views.admin_package_edit,
        name="admin_package_edit",
    ),
    path(
        "manage/packages/<int:package_id>/toggle/",
        views.admin_package_toggle,
        name="admin_package_toggle",
    ),
    path(
        "manage/memberships/", views.admin_membership_list, name="admin_membership_list"
    ),
    path(
        "manage/memberships/<int:membership_id>/edit/",
        views.admin_membership_edit,
        name="admin_membership_edit",
    ),
    path("manage/payments/", views.admin_payment_list, name="admin_payment_list"),
    path(
        "manage/payments/<int:payment_id>/",
        views.admin_payment_detail,
        name="admin_payment_detail",
    ),
    path(
        "manage/payments/<int:payment_id>/edit/",
        views.admin_payment_edit,
        name="admin_payment_edit",
    ),
    path(
        "manage/report/", views.admin_membership_report, name="admin_membership_report"
    ),
]

# Services, sessions and bookings — Mehnaz

# 1.3 Public schedule; 2.8–2.12 Member bookings; 3.6–3.7 Session management; 4.6 Services
bookings_routes = [
    path("", views.schedule, name="schedule"),
    path("sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("booking/<int:booking_id>/", views.booking_detail, name="booking_detail"),
    path("session/<int:session_id>/book/", views.book_session, name="book_session"),
    path(
        "booking/<int:booking_id>/cancel/", views.cancel_booking, name="cancel_booking"
    ),
    path("manage/services/", views.service_list, name="service_list"),
    path("manage/services/add/", views.service_create, name="service_create"),
    path(
        "manage/services/<int:service_id>/edit/",
        views.service_edit,
        name="service_edit",
    ),
    path(
        "manage/services/<int:service_id>/delete/",
        views.service_delete,
        name="service_delete",
    ),
    path("manage/sessions/", views.session_list, name="session_list"),
    path("manage/sessions/add/", views.session_create, name="session_create"),
    path(
        "manage/sessions/<int:session_id>/edit/",
        views.session_edit,
        name="session_edit",
    ),
    path(
        "manage/sessions/<int:session_id>/cancel/",
        views.session_cancel,
        name="session_cancel",
    ),
    path(
        "manage/sessions/<int:session_id>/roster/",
        views.session_roster,
        name="session_roster",
    ),
    path("manage/report/", views.booking_report, name="booking_report"),
]

# Workouts, progress and water intake — Hanshinee

# 2.14–2.18 Plans and progress; 2.22–2.23 Workout sessions; 2.25 Water intake; 3.8–3.10 Coaching; 4.11 Exercise library
workouts_routes = [
    path("water/", views.water_intake, name="water_intake"),
    path("", views.workout_plans, name="plans"),
    path("exercises/", views.exercise_library, name="exercise_library"),
    path("exercises/<int:exercise_id>/", views.exercise_detail, name="exercise_detail"),
    path("exercises/manage/", views.exercise_manage, name="exercise_manage"),
    path("exercises/manage/add/", views.exercise_create, name="exercise_create"),
    path(
        "exercises/manage/<int:exercise_id>/edit/",
        views.exercise_edit,
        name="exercise_edit",
    ),
    path(
        "exercises/manage/<int:exercise_id>/toggle/",
        views.exercise_toggle,
        name="exercise_toggle",
    ),
    path("plans/create/", views.plan_create, name="plan_create"),
    path("plans/<int:plan_id>/", views.plan_detail, name="plan_detail"),
    path("plans/<int:plan_id>/edit/", views.plan_edit, name="plan_edit"),
    path("plans/<int:plan_id>/delete/", views.plan_delete, name="plan_delete"),
    path(
        "plans/<int:plan_id>/exercises/",
        views.plan_add_exercises,
        name="plan_add_exercises",
    ),
    path(
        "plans/<int:plan_id>/exercises/<int:entry_id>/remove/",
        views.plan_remove_exercise,
        name="plan_remove_exercise",
    ),
    path("plans/<int:plan_id>/start/", views.start_workout, name="start_workout"),
    path("sessions/<int:session_id>/", views.active_workout, name="active_workout"),
    path(
        "sessions/<int:session_id>/finish/", views.finish_workout, name="finish_workout"
    ),
    path("history/", views.workout_history, name="history"),
    path(
        "history/<int:session_id>/", views.workout_history_detail, name="history_detail"
    ),
    path("progress/", views.progress, name="progress"),
    path("progress/add/", views.weight_add, name="weight_add"),
    path("progress/<int:record_id>/edit/", views.weight_edit, name="weight_edit"),
    path("progress/<int:record_id>/delete/", views.weight_delete, name="weight_delete"),
    path("coach/members/", views.coach_members, name="coach_members"),
    path("coach/plans/", views.coach_plans, name="coach_plans"),
    path("coach/progress/", views.coach_progress, name="coach_progress"),
    path(
        "coach/members/<int:member_id>/plan/create/",
        views.coach_plan_create,
        name="coach_plan_create",
    ),
    path(
        "coach/members/<int:member_id>/progress/",
        views.coach_member_progress,
        name="coach_member_progress",
    ),
]

# Attendance — Bhavshika

# 2.7 QR code; 2.13 Occupancy; 3.3–3.5 Entry; 4.7–4.8 Capacity and corrections
attendance_routes = [
    path("my-qr/", views.my_qr_code, name="my_qr_code"),
    path("occupancy/", views.occupancy, name="occupancy"),
    path("staff/", views.staff_attendance, name="staff_attendance"),
    path("history/", views.attendance_history, name="attendance_history"),
    path("correct/<int:pk>/", views.correct_attendance, name="correct_attendance"),
    path("report/", views.attendance_report, name="attendance_report"),
    path("capacity/", views.capacity_settings, name="capacity_settings"),
]

# Outdoor activities — Bhavshika

# 2.20–2.21 Activity summaries and history (GPS recording remains mobile-phase work)
activities_routes = [
    path("", views.activity_list, name="activity_list"),
    path("add/", views.add_activity, name="add_activity"),
    path("<int:pk>/", views.activity_detail, name="activity_detail"),
    path("<int:pk>/delete/", views.delete_activity, name="delete_activity"),
]

# Notifications and notices — Anjie

# 2.24 Notifications; 4.10 Gym notices
notifications_routes = [
    path("", views.notification_list, name="list"),
    path("<int:notification_id>/", views.notification_detail, name="detail"),
    path("<int:notification_id>/read/", views.mark_as_read, name="mark_as_read"),
    path("read-all/", views.mark_all_as_read, name="mark_all_as_read"),
    path("manage/notices/", views.notice_list, name="notice_list"),
    path("manage/notices/add/", views.notice_create, name="notice_create"),
    path("manage/notices/<int:notice_id>/edit/", views.notice_edit, name="notice_edit"),
    path(
        "manage/notices/<int:notice_id>/delete/",
        views.notice_delete,
        name="notice_delete",
    ),
]

# About page — Rheva

# 1.1 Gym information
aboutus_routes = [path("", views.aboutus, name="index")]

# Team profiles — Rheva

# 1.6 Public team; 4.13 Team management
ourteam_routes = [path("", views.ourteam, name="index")]

# Public pages — Shared

# 1.1 Gym information; 1.7 Contact enquiries; 4.14–4.15 Contact management
core_routes = [
    path(
        "manage/contact-details/", views.public_content_settings, name="manage_settings"
    ),
    path("manage/team/", views.public_team_list, name="manage_team"),
    path("manage/team/add/", views.public_team_edit, name="manage_team_add"),
    path(
        "manage/team/<int:person_id>/edit/",
        views.public_team_edit,
        name="manage_team_edit",
    ),
    path(
        "manage/team/<int:person_id>/visibility/",
        views.public_team_toggle,
        name="manage_team_toggle",
    ),
    path("manage/enquiries/", views.contact_inbox, name="manage_inbox"),
    path(
        "manage/enquiries/<int:enquiry_id>/",
        views.contact_enquiry_detail,
        name="manage_enquiry",
    ),
    path("", views.home, name="home"),
    path("features/", views.features, name="features"),
    path("contact/", views.contact, name="contact"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include((accounts_routes, "accounts"), namespace="accounts")),
    path(
        "memberships/",
        include((memberships_routes, "memberships"), namespace="memberships"),
    ),
    path("bookings/", include((bookings_routes, "bookings"), namespace="bookings")),
    path("workouts/", include((workouts_routes, "workouts"), namespace="workouts")),
    path(
        "attendance/",
        include((attendance_routes, "attendance"), namespace="attendance"),
    ),
    path(
        "activities/",
        include((activities_routes, "activities"), namespace="activities"),
    ),
    path(
        "notifications/",
        include((notifications_routes, "notifications"), namespace="notifications"),
    ),
    path("aboutus/", include((aboutus_routes, "aboutus"), namespace="aboutus")),
    path("ourteam/", include((ourteam_routes, "ourteam"), namespace="ourteam")),
    path("", include((core_routes, "core"), namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
