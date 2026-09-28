from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """FitSync user with one simple role used for dashboard access."""

    class Role(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        STAFF = "STAFF", "Staff"
        COACH = "COACH", "Coach"
        ADMIN = "ADMIN", "Admin"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    def __str__(self):
        return self.get_full_name() or self.email or self.username


class MemberProfile(models.Model):
    """Extra member and fitness details kept separate from login details."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_profile",
    )

    profile_picture=models.ImageField(upload_to="profile_pics/",blank=True,null=True)
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    age = models.PositiveSmallIntegerField(blank=True, null=True)
    height_cm = models.PositiveIntegerField(blank=True, null=True)
    current_weight_kg = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    target_weight_kg = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    fitness_goal = models.CharField(max_length=200, blank=True)
    medical_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user} - Member profile"


class CoachProfile(models.Model):
    """Simple public/professional details for users with the coach role."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coach_profile",
    )
    bio = models.TextField(blank=True)
    specialties = models.CharField(max_length=255, blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    qualifications = models.CharField(max_length=255, blank=True)
    photo_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.user} - Coach profile"


class CoachAssignment(models.Model):
    """Links one coach to one member without adding complex permissions."""

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coach_assignments",
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coach_links",
    )
    active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["coach", "member"],
                name="unique_coach_member_assignment",
            )
        ]

    def clean(self):
        # Keep the rule here so the admin form and normal form share the same check.
        if self.coach_id and self.coach.role != User.Role.COACH:
            raise ValidationError({"coach": "Selected user must have the Coach role."})
        if self.member_id and self.member.role != User.Role.MEMBER:
            raise ValidationError({"member": "Selected user must have the Member role."})
        if self.coach_id and self.member_id and self.coach_id == self.member_id:
            raise ValidationError("A coach cannot be assigned to themselves.")

    def __str__(self):
        return f"{self.coach} -> {self.member}"
