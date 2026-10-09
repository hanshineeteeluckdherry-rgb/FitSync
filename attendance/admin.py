from django.contrib import admin

from .models import AttendanceRecord, GymConfiguration, MemberQRCode


admin.site.register(MemberQRCode)
admin.site.register(AttendanceRecord)
admin.site.register(GymConfiguration)
