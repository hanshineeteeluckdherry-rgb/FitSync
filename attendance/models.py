# Create your models here.
import uuid
from django.db import models
from django.conf import settings


class MemberQRCode(models.Model):
    member = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="qr_code"
    )
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR Code for {self.member}"


class AttendanceRecord(models.Model):
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records"
    )
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)

    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_corrections"
    )
    correction_note = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.member} - {self.check_in_time.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ["-check_in_time"]