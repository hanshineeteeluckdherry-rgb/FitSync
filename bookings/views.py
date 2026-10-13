from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from accounts.models import User
from memberships.models import Membership
from notifications.models import Notification
from notifications.services import create_notification

from .forms import ServiceForm, SessionForm
from .models import Booking, Service, Session


def session_start(session):
    """Combine the session date and start time into one timezone-aware value."""
    start = datetime.combine(session.date, session.start_time)
    return timezone.make_aware(start, timezone.get_current_timezone())


def session_has_started(session):
    """Check whether the session has already started."""
    return session_start(session) <= timezone.now()


def valid_date(value):
    """Convert a valid date string into a date object for filtering."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def management_layout(user):
    """Select the correct dashboard layout for an administrator or staff member."""
    if user.is_superuser or user.role == User.Role.ADMIN:
        return "layouts/admin_base.html"
    return "layouts/staff_base.html"


def upcoming_sessions():
    """Return scheduled sessions that have not yet started."""
    now = timezone.localtime()
    return Session.objects.filter(
        service__is_active=True,
        status=Session.Status.SCHEDULED,
    ).filter(
        Q(date__gt=now.date())
        | Q(date=now.date(), start_time__gt=now.time())
    )


def schedule(request):
    """Display future sessions and apply the selected schedule filters."""
    search_query = request.GET.get("search", "").strip()
    selected_type = request.GET.get("type", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_date = valid_date(request.GET.get("date", ""))
    selected_instructor = request.GET.get("instructor", "").strip()

    sessions = upcoming_sessions().select_related("service", "instructor").annotate(
        confirmed_count=Count(
            "bookings",
            filter=Q(bookings__status=Booking.Status.CONFIRMED),
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
    if selected_date:
        sessions = sessions.filter(date=selected_date)
    if selected_instructor.isdigit():
        sessions = sessions.filter(instructor_id=selected_instructor)
    if selected_status == "AVAILABLE":
        sessions = sessions.filter(confirmed_count__lt=F("capacity"))
    elif selected_status == "FULL":
        sessions = sessions.filter(confirmed_count__gte=F("capacity"))

    booked_session_ids = []
    if request.user.is_authenticated:
        booked_session_ids = list(
            # Cancel every confirmed booking when staff cancels the session.
            Booking.objects.filter(
                member=request.user,
                status=Booking.Status.CONFIRMED,
            ).values_list("session_id", flat=True)
        )

    context = {
        "sessions": sessions,
        "service_types": Service.Type.choices,
        "instructors": User.objects.filter(role=User.Role.COACH, is_active=True),
        "search_query": search_query,
        "selected_type": selected_type,
        "selected_status": selected_status,
        "selected_date": request.GET.get("date", ""),
        "selected_instructor": selected_instructor,
        "booked_session_ids": booked_session_ids,
    }
    return render(request, "bookings/schedule.html", context)


def session_detail(request, session_id):
    """Display the details and current availability of one session."""
    session = get_object_or_404(
        Session.objects.select_related("service", "instructor"),
        pk=session_id,
    )
    confirmed_count = session.bookings.filter(status=Booking.Status.CONFIRMED).count()
    already_booked = False
    if request.user.is_authenticated:
        already_booked = session.bookings.filter(
            member=request.user,
            status=Booking.Status.CONFIRMED,
        ).exists()
    return render(
        request,
        "bookings/session_detail.html",
        {
            "session": session,
            "confirmed_count": confirmed_count,
            "remaining_spaces": max(session.capacity - confirmed_count, 0),
            "already_booked": already_booked,
            "has_started": session_has_started(session),
        },
    )


@login_required
@require_POST
def book_session(request, session_id):
    """Validate the member and create a confirmed session booking."""
    if request.user.role != User.Role.MEMBER:
        messages.error(request, "Only member accounts can book a session.")
        return redirect("bookings:schedule")

    today = timezone.localdate()
    active_membership = (
        Membership.objects.select_related("package")
        .filter(
            member=request.user,
            status=Membership.Status.ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        )
        .order_by("-end_date")
        .first()
    )
    if not active_membership:
        messages.error(request, "You need an active membership to book a session.")
        return redirect("bookings:schedule")

    # Lock the session row so two members cannot take the final place simultaneously.
    with transaction.atomic():
        session = get_object_or_404(
            Session.objects.select_for_update().select_related("service"),
            pk=session_id,
        )
        # Confirm that the member's package includes this type of service.
        if not active_membership.package.allows_service(session.service.service_type):
            messages.error(request, "Your membership plan does not include this service.")
            return redirect("bookings:schedule")
        if session.status != Session.Status.SCHEDULED:
            messages.error(request, "This session is no longer available for booking.")
            return redirect("bookings:schedule")
        if session_has_started(session):
            messages.error(request, "You cannot book a session that has already started.")
            return redirect("bookings:schedule")
        if Booking.objects.filter(
            member=request.user,
            session=session,
            status=Booking.Status.CONFIRMED,
        ).exists():
            messages.warning(request, "You have already booked this session.")
            return redirect("bookings:schedule")
        # Prevent the member from booking another confirmed session at an overlapping time.
        if Booking.objects.filter(
            member=request.user,
            status=Booking.Status.CONFIRMED,
            session__status=Session.Status.SCHEDULED,
            session__date=session.date,
            session__start_time__lt=session.end_time,
            session__end_time__gt=session.start_time,
        ).exists():
            messages.error(request, "You already have another booking at this time.")
            return redirect("bookings:schedule")
        confirmed_count = Booking.objects.filter(
            session=session,
            status=Booking.Status.CONFIRMED,
        ).count()
        if confirmed_count >= session.capacity:
            messages.error(request, "Sorry, this session is now full.")
            return redirect("bookings:schedule")

        booking = Booking.objects.create(
            member=request.user,
            session=session,
            status=Booking.Status.CONFIRMED,
        )

        create_notification(
            recipient=request.user,
            notification_type=Notification.Type.BOOKING,
            title="Booking Confirmed",
            message=f"Your booking for {session.service.name} on {session.date:%d %B %Y} is confirmed.",
            link=reverse("bookings:booking_detail", args=[booking.id]),
            reference_key=f"booking-confirmed-{booking.id}",
        )

    messages.success(request, f"Your booking for {session.service.name} was successful.")
    return redirect("bookings:schedule")


@login_required
def my_bookings(request):
    """Group the member's bookings into upcoming, previous and cancelled sections."""
    if request.user.role != User.Role.MEMBER:
        messages.error(request, "Only member accounts can view personal bookings.")
        return redirect("bookings:schedule")

    bookings = Booking.objects.filter(member=request.user).select_related(
        "session",
        "session__service",
        "session__instructor",
    )
    upcoming = []
    previous = []
    cancelled = []
    for booking in bookings.order_by("session__date", "session__start_time"):
        if booking.status == Booking.Status.CANCELLED:
            cancelled.append(booking)
        elif session_has_started(booking.session):
            previous.append(booking)
        else:
            upcoming.append(booking)

    return render(
        request,
        "bookings/my_bookings.html",
        {
            "upcoming_bookings": upcoming,
            "previous_bookings": list(reversed(previous)),
            "cancelled_bookings": list(reversed(cancelled)),
        },
    )


@login_required
def booking_detail(request, booking_id):
    """Display the details of one booking belonging to the logged-in member."""
    booking = get_object_or_404(
        Booking.objects.select_related("session", "session__service", "session__instructor"),
        pk=booking_id,
        member=request.user,
    )
    can_cancel = booking.status == Booking.Status.CONFIRMED and not session_has_started(booking.session)
    return render(
        request,
        "bookings/booking_detail.html",
        {"booking": booking, "can_cancel": can_cancel},
    )


@login_required
def cancel_booking(request, booking_id):
    """Cancel the member's booking only if its session has not started."""
    booking = get_object_or_404(
        Booking.objects.select_related("session", "session__service"),
        pk=booking_id,
        member=request.user,
    )
    if booking.status != Booking.Status.CONFIRMED:
        messages.warning(request, "This booking is no longer active.")
        return redirect("bookings:my_bookings")
    if session_has_started(booking.session):
        messages.error(request, "A booking cannot be cancelled after the session has started.")
        return redirect("bookings:my_bookings")
    if request.method == "POST":
        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["status", "cancelled_at"])
        messages.success(request, f"Your booking for {booking.session.service.name} was cancelled.")
        return redirect("bookings:my_bookings")
    return render(request, "bookings/booking_confirm_cancel.html", {"booking": booking})


@staff_required
def service_list(request):
    """Display all services for staff and administrator management."""
    services = Service.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        services = services.filter(Q(name__icontains=query) | Q(description__icontains=query))
    return render(
        request,
        "bookings/manage/service_list.html",
        {
            "services": services,
            "query": query,
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@staff_required
def service_create(request):
    """Allow staff or administrators to create a bookable service."""
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Service created successfully.")
        return redirect("bookings:service_list")
    return render(
        request,
        "bookings/manage/form.html",
        {"form": form, "title": "Add Service", "layout_template": management_layout(request.user), "active_sidebar": "sessions"},
    )


@staff_required
def service_edit(request, service_id):
    """Allow staff or administrators to update an existing service."""
    service = get_object_or_404(Service, pk=service_id)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Service updated successfully.")
        return redirect("bookings:service_list")
    return render(
        request,
        "bookings/manage/form.html",
        {"form": form, "title": "Edit Service", "layout_template": management_layout(request.user), "active_sidebar": "sessions"},
    )


@staff_required
def service_delete(request, service_id):
    """Allow staff or administrators to delete a service safely."""
    service = get_object_or_404(Service, pk=service_id)
    if request.method == "POST":
        if service.sessions.exists():
            service.is_active = False
            service.save(update_fields=["is_active"])
            messages.success(request, "Service deactivated because it has session records.")
        else:
            service.delete()
            messages.success(request, "Service deleted successfully.")
        return redirect("bookings:service_list")
    return render(
        request,
        "bookings/manage/service_confirm_delete.html",
        {"service": service, "layout_template": management_layout(request.user), "active_sidebar": "sessions"},
    )


@staff_required
def session_list(request):
    """Display sessions for staff and administrator management."""
    sessions = Session.objects.select_related("service", "instructor").annotate(
        booking_total=Count("bookings", filter=Q(bookings__status=Booking.Status.CONFIRMED))
    )
    status = request.GET.get("status", "")
    selected_date = valid_date(request.GET.get("date", ""))
    if status:
        sessions = sessions.filter(status=status)
    if selected_date:
        sessions = sessions.filter(date=selected_date)
    return render(
        request,
        "bookings/manage/session_list.html",
        {
            "sessions": sessions,
            "status_choices": Session.Status.choices,
            "selected_status": status,
            "selected_date": request.GET.get("date", ""),
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@staff_required
def session_create(request):
    """Allow staff or administrators to schedule a new session."""
    form = SessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session created successfully.")
        return redirect("bookings:session_list")
    return render(
        request,
        "bookings/manage/form.html",
        {"form": form, "title": "Add Session", "layout_template": management_layout(request.user), "active_sidebar": "sessions"},
    )


@staff_required
def session_edit(request, session_id):
    """Allow staff or administrators to update a scheduled session."""
    session = get_object_or_404(Session, pk=session_id)
    form = SessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session updated successfully.")
        return redirect("bookings:session_list")
    return render(
        request,
        "bookings/manage/form.html",
        {"form": form, "title": "Edit Session", "layout_template": management_layout(request.user), "active_sidebar": "sessions"},
    )


@staff_required
def session_cancel(request, session_id):
    """Cancel a session and its confirmed member bookings."""
    session = get_object_or_404(Session.objects.select_related("service"), pk=session_id)
    if request.method == "POST":
        session.status = Session.Status.CANCELLED
        session.save(update_fields=["status"])
        session.bookings.filter(status=Booking.Status.CONFIRMED).update(
            status=Booking.Status.CANCELLED,
            cancelled_at=timezone.now(),
        )
        messages.success(request, "Session and its active bookings were cancelled.")
        return redirect("bookings:session_list")
    return render(
        request,
        "bookings/manage/session_confirm_cancel.html",
        {"session": session, "layout_template": management_layout(request.user), "active_sidebar": "sessions"},
    )


@staff_required
def session_roster(request, session_id):
    """Display the members with confirmed bookings for a session."""
    session = get_object_or_404(Session.objects.select_related("service", "instructor"), pk=session_id)
    bookings = session.bookings.filter(status=Booking.Status.CONFIRMED).select_related("member")
    return render(
        request,
        "bookings/manage/session_roster.html",
        {"session": session, "bookings": bookings, "layout_template": management_layout(request.user), "active_sidebar": "sessions"},
    )


@staff_required
def booking_report(request):
    """Generate filtered booking statistics and service popularity summaries."""
    bookings = Booking.objects.select_related("member", "session", "session__service")
    date_from = valid_date(request.GET.get("date_from", ""))
    date_to = valid_date(request.GET.get("date_to", ""))
    status = request.GET.get("status", "")
    if date_from:
        bookings = bookings.filter(session__date__gte=date_from)
    if date_to:
        bookings = bookings.filter(session__date__lte=date_to)
    if status:
        bookings = bookings.filter(status=status)

    popular_services = (
        bookings.values("session__service__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )
    daily_totals = (
        bookings.annotate(day=TruncDate("booked_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("-day")
    )
    context = {
        "bookings": bookings.order_by("-session__date", "-session__start_time"),
        "total_bookings": bookings.count(),
        "confirmed_total": bookings.filter(status=Booking.Status.CONFIRMED).count(),
        "cancelled_total": bookings.filter(status=Booking.Status.CANCELLED).count(),
        "popular_services": popular_services,
        "daily_totals": daily_totals,
        "status_choices": Booking.Status.choices,
        "selected_status": status,
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "layout_template": management_layout(request.user),
        "active_sidebar": "bookings",
    }
    return render(request, "bookings/manage/booking_report.html", context)
