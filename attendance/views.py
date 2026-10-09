import base64
import io
import uuid
from datetime import date

import qrcode
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import admin_required, member_required, staff_required
from accounts.models import User
from memberships.models import Membership

from .forms import AttendanceCorrectionForm, GymConfigurationForm
from .models import AttendanceRecord, GymConfiguration, MemberQRCode


def has_active_membership(member):
    today = timezone.localdate()
    return Membership.objects.filter(
        member=member,
        status=Membership.Status.ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).exists()


def dashboard_base(user):
    if user.is_superuser or user.role == User.Role.ADMIN:
        return "layouts/admin_base.html"
    return "layouts/staff_base.html"


def attendance_sidebar(user):
    if user.is_superuser or user.role == User.Role.ADMIN:
        return "attendance"
    return "attendance-history"


def valid_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@member_required
def my_qr_code(request):
    qr_code, _ = MemberQRCode.objects.get_or_create(member=request.user)
    qr_active = qr_code.is_active and has_active_membership(request.user)

    qr_image = None
    if qr_active:
        image = qrcode.make(str(qr_code.qr_token))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        qr_image = base64.b64encode(buffer.getvalue()).decode()

    return render(
        request,
        "attendance/my_qr_code.html",
        {
            "qr_code": qr_code,
            "qr_image": qr_image,
            "qr_active": qr_active,
            "active_sidebar": "qr",
        },
    )


@member_required
def occupancy(request):
    current_occupancy = AttendanceRecord.objects.filter(
        check_out_time__isnull=True
    ).count()
    max_capacity = GymConfiguration.get_capacity()
    occupancy_percent = min(round((current_occupancy / max_capacity) * 100), 100)

    return render(
        request,
        "attendance/occupancy.html",
        {
            "current_occupancy": current_occupancy,
            "max_capacity": max_capacity,
            "available_spaces": max(max_capacity - current_occupancy, 0),
            "occupancy_percent": occupancy_percent,
            "active_sidebar": "occupancy",
        },
    )


@staff_required
def staff_attendance(request):
    if request.method == "POST":
        identifier = request.POST.get("member_identifier", "").strip()
        action = request.POST.get("action")
        member = None

        try:
            qr_token = uuid.UUID(identifier)
            qr_code = MemberQRCode.objects.select_related("member").filter(
                qr_token=qr_token,
                is_active=True,
            ).first()
            if qr_code:
                member = qr_code.member
        except (ValueError, AttributeError):
            pass

        if member is None:
            member = get_user_model().objects.filter(
                email__iexact=identifier,
                role=User.Role.MEMBER,
                is_active=True,
            ).first()

        if member is None:
            messages.error(request, "No member was found with that QR code or email.")
            return redirect("attendance:staff_attendance")

        active_record = AttendanceRecord.objects.filter(
            member=member,
            check_out_time__isnull=True,
        ).first()

        if action == "check_in":
            if not has_active_membership(member):
                messages.error(request, f"{member} does not have an active membership.")
            elif active_record:
                messages.error(request, f"{member} is already checked in.")
            elif (
                AttendanceRecord.objects.filter(check_out_time__isnull=True).count()
                >= GymConfiguration.get_capacity()
            ):
                messages.error(request, "Gym is at maximum capacity. Check-in denied.")
            else:
                AttendanceRecord.objects.create(member=member)
                messages.success(request, f"{member} checked in successfully.")
        elif action == "check_out":
            if active_record is None:
                messages.error(request, f"{member} has no active check-in.")
            else:
                active_record.check_out_time = timezone.now()
                active_record.save(update_fields=["check_out_time"])
                messages.success(request, f"{member} checked out successfully.")
        else:
            messages.error(request, "Select check-in or check-out.")

        return redirect("attendance:staff_attendance")

    today_records = AttendanceRecord.objects.filter(
        check_in_time__date=timezone.localdate()
    ).select_related("member")
    current_occupancy = AttendanceRecord.objects.filter(
        check_out_time__isnull=True
    ).count()

    return render(
        request,
        "attendance/staff_attendance.html",
        {
            "today_records": today_records,
            "current_occupancy": current_occupancy,
            "max_capacity": GymConfiguration.get_capacity(),
            "base_template": dashboard_base(request.user),
            "active_sidebar": "attendance",
        },
    )


@staff_required
def attendance_history(request):
    records = AttendanceRecord.objects.select_related("member", "corrected_by")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    date_from = valid_date(request.GET.get("date_from", ""))
    date_to = valid_date(request.GET.get("date_to", ""))

    if query:
        records = records.filter(
            Q(member__first_name__icontains=query)
            | Q(member__last_name__icontains=query)
            | Q(member__email__icontains=query)
        )
    if status == "INSIDE":
        records = records.filter(check_out_time__isnull=True)
    elif status == "COMPLETED":
        records = records.filter(check_out_time__isnull=False)
    if date_from:
        records = records.filter(check_in_time__date__gte=date_from)
    if date_to:
        records = records.filter(check_in_time__date__lte=date_to)

    return render(
        request,
        "attendance/attendance_history.html",
        {
            "records": records,
            "query": query,
            "status_filter": status,
            "date_from": date_from,
            "date_to": date_to,
            "base_template": dashboard_base(request.user),
            "active_sidebar": attendance_sidebar(request.user),
        },
    )


@staff_required
def correct_attendance(request, pk):
    record = get_object_or_404(AttendanceRecord, pk=pk)
    initial = {
        "check_in_time": timezone.localtime(record.check_in_time),
        "check_out_time": (
            timezone.localtime(record.check_out_time) if record.check_out_time else None
        ),
        "correction_note": record.correction_note,
    }
    form = AttendanceCorrectionForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        record.check_in_time = form.cleaned_data["check_in_time"]
        record.check_out_time = form.cleaned_data["check_out_time"]
        record.correction_note = form.cleaned_data["correction_note"]
        record.corrected_by = request.user
        record.save()
        messages.success(request, "Attendance record corrected successfully.")
        return redirect("attendance:attendance_history")

    return render(
        request,
        "attendance/correct_attendance.html",
        {
            "record": record,
            "form": form,
            "base_template": dashboard_base(request.user),
            "active_sidebar": attendance_sidebar(request.user),
        },
    )


@staff_required
def attendance_report(request):
    records = AttendanceRecord.objects.all()
    date_from = valid_date(request.GET.get("date_from", ""))
    date_to = valid_date(request.GET.get("date_to", ""))
    if date_from:
        records = records.filter(check_in_time__date__gte=date_from)
    if date_to:
        records = records.filter(check_in_time__date__lte=date_to)

    daily_counts = (
        records.annotate(day=TruncDate("check_in_time"))
        .values("day")
        .annotate(total_check_ins=Count("id"))
        .order_by("-day")
    )

    return render(
        request,
        "attendance/attendance_report.html",
        {
            "daily_counts": daily_counts,
            "total_check_ins": records.count(),
            "current_occupancy": AttendanceRecord.objects.filter(
                check_out_time__isnull=True
            ).count(),
            "date_from": date_from,
            "date_to": date_to,
            "base_template": dashboard_base(request.user),
            "active_sidebar": "reports",
        },
    )


@admin_required
def capacity_settings(request):
    configuration, _ = GymConfiguration.objects.get_or_create(pk=1)
    form = GymConfigurationForm(request.POST or None, instance=configuration)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Gym capacity updated.")
        return redirect("attendance:capacity_settings")

    return render(
        request,
        "attendance/capacity_settings.html",
        {
            "form": form,
            "current_occupancy": AttendanceRecord.objects.filter(
                check_out_time__isnull=True
            ).count(),
            "active_sidebar": "settings",
        },
    )
