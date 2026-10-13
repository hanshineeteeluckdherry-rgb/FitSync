from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class Type(models.TextChoices):
        BOOKING = "BOOKING", "Booking"
        MEMBERSHIP = "MEMBERSHIP", "Membership"
        NOTICE = "NOTICE", "Gym Notice"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=120)
    message = models.TextField()
    link = models.CharField(max_length=250, blank=True)
    reference_key = models.CharField(max_length=100, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient} - {self.title}"


class Notice(models.Model):
    title = models.CharField(max_length=120)
    message = models.TextField()
    publish_date = models.DateField(default=timezone.localdate)
    expires_on = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_notices",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-publish_date", "-created_at"]

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.is_active and self.publish_date <= today and (
            self.expires_on is None or self.expires_on >= today
        )

    def __str__(self):
        return self.title
