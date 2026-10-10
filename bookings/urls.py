from django.urls import path

from . import views


app_name = "bookings"

urlpatterns = [
    path("", views.schedule, name="schedule"),
    path("sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("booking/<int:booking_id>/", views.booking_detail, name="booking_detail"),
    path("session/<int:session_id>/book/", views.book_session, name="book_session"),
    path("booking/<int:booking_id>/cancel/", views.cancel_booking, name="cancel_booking"),
    path("manage/services/", views.service_list, name="service_list"),
    path("manage/services/add/", views.service_create, name="service_create"),
    path("manage/services/<int:service_id>/edit/", views.service_edit, name="service_edit"),
    path("manage/services/<int:service_id>/delete/", views.service_delete, name="service_delete"),
    path("manage/sessions/", views.session_list, name="session_list"),
    path("manage/sessions/add/", views.session_create, name="session_create"),
    path("manage/sessions/<int:session_id>/edit/", views.session_edit, name="session_edit"),
    path("manage/sessions/<int:session_id>/cancel/", views.session_cancel, name="session_cancel"),
    path("manage/sessions/<int:session_id>/roster/", views.session_roster, name="session_roster"),
    path("manage/report/", views.booking_report, name="booking_report"),
]
