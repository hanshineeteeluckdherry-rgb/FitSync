from django.urls import path
from . import views

app_name = "attendance"

urlpatterns = [
    path("my-qr/", views.my_qr_code, name = "my_qr_code"),
    path("staff/", views.staff_attendance, name = "staff_attendance"),
    path("history/", views.attendance_history, name="attendance_history"),
    path("correct/<int:pk>/", views.correct_attendance, name="correct_attendance"),
    path("report/", views.attendance_report, name="attendance_report"),
]