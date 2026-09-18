from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import MemberQRCode

# Create your views here.
@login_required
def my_qr_code(request):
    qr_code, created = MemberQRCode.objects.get_or_create(member=request.user)

    context = {
        "qr_code": qr_code,
    }
    return render(request, "attendance/my_qr_code.html", context)