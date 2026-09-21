import uuid
from datetime import date

from django.conf import settings
from django.db import models


class MembershipPackage(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_months = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=220, blank=True)
    features = models.TextField(help_text="One feature per line")
    audience = models.CharField(max_length=80, blank=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price", "name"]

    @property
    def feature_list(self):
        return [item.strip() for item in self.features.splitlines() if item.strip()]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    package = models.ForeignKey(
        MembershipPackage,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]

    @property
    def display_status(self):
        if self.status == self.Status.ACTIVE and self.end_date < date.today():
            return self.Status.EXPIRED
        return self.status

    def __str__(self):
        return f"{self.member} - {self.package.name}"


class Payment(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    class Method(models.TextChoices):
        CARD = "CARD", "Demo Card"
        CASH = "CASH", "Cash"

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership_payments",
    )
    package = models.ForeignKey(
        MembershipPackage,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    membership = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(max_length=12, choices=Method.choices, default=Method.CARD)
    status = models.CharField(max_length=12, choices=Status.choices)
    receipt_number = models.CharField(max_length=24, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f"FS-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} - {self.member}"
