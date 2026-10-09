# Create your models here.
from django.db import models
from django.conf import settings


class OutdoorActivity(models.Model):
    ACTIVITY_CHOICES = [
        ("walking", "Walking"),
        ("running", "Running"),
        ("cycling", "Cycling"),
    ]

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="outdoor_activities"
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    date = models.DateField()
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.member} - {self.activity_type} ({self.date})"

    class Meta:
        ordering = ["-date"]
