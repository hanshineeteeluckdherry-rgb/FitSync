from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import MemberQRCode
from django.utils import timezone
from .models import AttendanceRecord
from django.contrib import messages
from django.contrib.auth import get_user_model

import qrcode
import io
import base64

GYM_MAX_CAPACITY = 50

User = get_user_model()

# Create your views here.
@login_required
def my_qr_code(request):
    qr_code, created = MemberQRCode.objects.get_or_create(member=request.user)

    qr_image_base64 = None
    if qr_code.is_active:
        img = qrcode.make(str(qr_code.qr_token))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_image_base64 = base64.b64encode(buffer.getvalue()).decode()

    context = {
        "qr_code": qr_code,
        "qr_image": qr_image_base64,
    }
    return render(request, "attendance/my_qr_code.html", context)

@login_required
def staff_attendance(request):
    today = timezone.localdate()

    if request.method == "POST":
        identifier = request.POST.get("member_identifier", "").strip()
        action = request.POST.get("action")

        member = None

        # Try QR token lookup first
        qr_code = MemberQRCode.objects.filter(qr_token=identifier, is_active=True).first()
        if qr_code:
            member = qr_code.member
        else:
            # Fall back to email lookup
            member = User.objects.filter(email=identifier).first()

        if not member:
            messages.error(request, "No member found with that QR code or email.")
            return redirect("attendance:staff_attendance")
        
        if action == "check_in":
            already_checked_in = AttendanceRecord.objects.filter(
                member=member,
                check_out_time__isnull=True
            ).exists()

            current_occupancy = AttendanceRecord.objects.filter(
                check_out_time__isnull = True
            ).count()

            #TODO: once person 3 updates add:
            #if not hasattr(member, "membership") or not member.membership.is_active:
            #       messages.error(request, f"{member} does not have an active membership.")
            # return redirect("attendance:staff_attendance")

            if already_checked_in:
                messages.error(request, f"{member} is already checked in.")

            elif current_occupancy >= GYM_MAX_CAPACITY:
                messages.error(request, "Gym is at maximum capacity. Check-in denied.")
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

@login_required
def attendance_history(request):
    records = AttendanceRecord.objects.all().select_related("member").order_by("check_in_time")
    return render(request, "attendance/attendance_history.html", {"records": records})

@login_required
def correct_attendance(request, pk):
    record = get_object_or_404(AttendanceRecord, pk=pk)

    if request.method == "POST":
        note = request.POST.get("correction_note", "").strip()
        check_in = request.POST.get("check_in_time")
        check_out = request.POST.get("check_out_time")

        if not note:
            messages.error(request, "A correction note is required.")
            return redirect("attendance:correct_attendance", pk=pk)

        if check_in:
            record.check_in_time = check_in
        if check_out:
            record.check_out_time = check_out

        record.correction_note = note
        record.corrected_by = request.user
        record.save()

        messages.success(request, "Attendance record corrected successfully.")
        return redirect("attendance:attendance_history")

    return render(request, "attendance/correct_attendance.html", {"record": record})