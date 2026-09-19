from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import MemberQRCode
from django.utils import timezone
from .models import AttendanceRecord
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth import get_user_model

GYM_MAX_CAPACITY = 50

User = get_user_model()

# Create your views here.
@login_required
def my_qr_code(request):
    qr_code, created = MemberQRCode.objects.get_or_create(member=request.user)

    context = {
        "qr_code": qr_code,
    }
    return render(request, "attendance/my_qr_code.html", context)

@login_required
def staff_attendance(request):
    today = timezone.localdate()

    if request.method == "POST":
        identifier = request.POST.get("member_identifier", "").strip()
        action = request.POST.get("action")

        member = User.objects.filter(email=identifier).first()

        if not member:
            messages.error(request, "No member found with that email.")
            return redirect("attendance:staff_attendance")

        if action == "check_in":
            already_checked_in = AttendanceRecord.objects.filter(
                member=member,
                check_out_time__isnull=True
            ).exists()

            #TODO: once person 3 updates add:
            #if not hasattr(member, "membership") or not member.membership.is_active:
            #       messages.error(request, f"{member} does not have an active membership.")
            # return redirect("attendance:staff_attendance")

            if already_checked_in:
                messages.error(request, f"{member} is already checked in.")
            else:
                AttendanceRecord.objects.create(member=member)
                messages.success(request, f"{member} checked in successfully.")

        elif action == "check_out":
            record = AttendanceRecord.objects.filter(
                member=member,
                check_out_time__isnull=True
            ).order_by("-check_in_time").first()

            if not record:
                messages.error(request, f"{member} has no active check-in.")
            else:
                record.check_out_time = timezone.now()
                record.save()
                messages.success(request, f"{member} checked out successfully.")

        return redirect("attendance:staff_attendance")

    today_records = AttendanceRecord.objects.filter(
        check_in_time__date=today
    ).select_related("member")

    current_occupancy = AttendanceRecord.objects.filter(
        check_out_time__isnull = True
    ).count()

    context = {
        "today_records": today_records,
        "current_occupancy": current_occupancy,
        "max_capacity": GYM_MAX_CAPACITY,
    }
    return render(request, "attendance/staff_attendance.html", context)