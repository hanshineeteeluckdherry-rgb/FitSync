from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Booking, Service, Session
from memberships.models import Membership


def schedule(request):
    """Display future scheduled sessions with search and filters."""

    search_query = request.GET.get("search", "").strip()
    selected_type = request.GET.get("type", "").strip()
    selected_status = request.GET.get("status", "").strip()

    sessions = (
        Session.objects.select_related("service", "instructor")
        .filter(
            service__is_active=True,
            date__gte=timezone.localdate(),
            status=Session.Status.SCHEDULED,
        )
        .annotate(
            confirmed_count=Count(
                "bookings",
                filter=Q(bookings__status=Booking.Status.CONFIRMED),
            )
        )
    )

    if search_query:
        sessions = sessions.filter(
            Q(service__name__icontains=search_query)
            | Q(service__description__icontains=search_query)
            | Q(instructor__first_name__icontains=search_query)
            | Q(instructor__last_name__icontains=search_query)
        )

    if selected_type:
        sessions = sessions.filter(service__service_type=selected_type)

    if selected_status == "AVAILABLE":
        sessions = sessions.filter(confirmed_count__lt=F("capacity"))

    elif selected_status == "FULL":
        sessions = sessions.filter(confirmed_count__gte=F("capacity"))

    booked_session_ids = []

    if request.user.is_authenticated:
        booked_session_ids = list(
            Booking.objects.filter(
                member=request.user,
                status=Booking.Status.CONFIRMED,
            ).values_list("session_id", flat=True)
        )

    context = {
       "sessions": sessions,
       "service_types": Service.Type.choices,
       "search_query": search_query,
       "selected_type": selected_type,
       "selected_status": selected_status,
       "booked_session_ids": booked_session_ids,
    }

    return render(request, "bookings/schedule.html", context)


@login_required
@require_POST
def book_session(request, session_id):
    """Create a confirmed booking for the logged-in member."""

    if request.user.role != "MEMBER":
        messages.error(
            request,
            "Only member accounts can book a session.",
        )
        return redirect("bookings:schedule")
    today = timezone.localdate()

    has_active_membership = Membership.objects.filter(
        member=request.user,
        status=Membership.Status.ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).exists()

    if not has_active_membership:
        messages.error(
            request,
            "You need an active membership to book a session.",
        )
        return redirect("bookings:schedule")

    with transaction.atomic():
        session = get_object_or_404(
            Session.objects.select_for_update().select_related("service"),
            pk=session_id,
        )

        if session.status != Session.Status.SCHEDULED:
            messages.error(
                request,
                "This session is no longer available for booking.",
            )
            return redirect("bookings:schedule")

        if session.date < timezone.localdate():
            messages.error(
                request,
                "You cannot book a session that has already passed.",
            )
            return redirect("bookings:schedule")

        already_booked = Booking.objects.filter(
            member=request.user,
            session=session,
            status=Booking.Status.CONFIRMED,
        ).exists()

        if already_booked:
            messages.warning(
                request,
                "You have already booked this session.",
            )
            return redirect("bookings:schedule")
        has_time_conflict = Booking.objects.filter(
            member=request.user,
            status=Booking.Status.CONFIRMED,
            session__status=Session.Status.SCHEDULED,
            session__date=session.date,
            session__start_time__lt=session.end_time,
            session__end_time__gt=session.start_time,
        ).exists()

        if has_time_conflict:
            messages.error(
                request,
                "You already have another booking at this time.",
            )
            return redirect("bookings:schedule")

        confirmed_count = Booking.objects.filter(
            session=session,
            status=Booking.Status.CONFIRMED,
        ).count()

        if confirmed_count >= session.capacity:
            messages.error(
                request,
                "Sorry, this session is now full.",
            )
            return redirect("bookings:schedule")

        Booking.objects.create(
            member=request.user,
            session=session,
            status=Booking.Status.CONFIRMED,
        )

    messages.success(
        request,
        f"Your booking for {session.service.name} was successful.",
    )

    return redirect("bookings:schedule")

@login_required
def my_bookings(request):
    """Display all bookings belonging to the logged-in member."""

    if request.user.role != "MEMBER":
        messages.error(
            request,
            "Only member accounts can view personal bookings.",
        )
        return redirect("bookings:schedule")

    bookings = (
        Booking.objects.filter(member=request.user)
        .select_related(
            "session",
            "session__service",
            "session__instructor",
        )
        .order_by("-session__date", "-session__start_time")
    )

    return render(
        request,
        "bookings/my_bookings.html",
        {"bookings": bookings},
    )


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """Cancel one confirmed booking belonging to the logged-in member."""

    booking = get_object_or_404(
        Booking.objects.select_related("session", "session__service"),
        pk=booking_id,
        member=request.user,
    )

    if booking.status != Booking.Status.CONFIRMED:
        messages.warning(
            request,
            "This booking is no longer active.",
        )
        return redirect("bookings:my_bookings")

    if booking.session.date < timezone.localdate():
        messages.error(
            request,
            "A past session cannot be cancelled.",
        )
        return redirect("bookings:my_bookings")

    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = timezone.now()
    booking.save(update_fields=["status", "cancelled_at"])

    messages.success(
        request,
        f"Your booking for {booking.session.service.name} was cancelled.",
    )

    return redirect("bookings:my_bookings")
