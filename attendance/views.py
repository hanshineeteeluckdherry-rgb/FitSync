from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import MemberQRCode
from django.utils import timezone
from .models import AttendanceRecord

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
    today_records = AttendanceRecord.objects.filter(check_in_time__date=today).select_related("member")

    context = {
        "today_records": today_records,
    }
    return render(request, "attendance/staff_attendance.html", context)