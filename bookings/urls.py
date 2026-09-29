from django.urls import path

from . import views


# This namespace lets templates use names such as "bookings:schedule".
app_name = "bookings"

urlpatterns = [
    # Public page showing all future sessions.
    path("", views.schedule, name="schedule"),

    # Page showing bookings belonging to the logged-in member.
    path("my-bookings/", views.my_bookings, name="my_bookings"),

    # Receives the form when a member books a session.
    path(
        "session/<int:session_id>/book/",
        views.book_session,
        name="book_session",
    ),

    # Receives the form when a member cancels their booking.
    path(
        "booking/<int:booking_id>/cancel/",
        views.cancel_booking,
        name="cancel_booking",
    ),
]