from django.urls import path
from . import views

app_name = "attendance"

urlpatterns = [
    path("my-qr/", views.my_qr_code, name = "my_qr_code"),
    path("staff/", views.staff_attendance, name = "staff_attendance"),
]