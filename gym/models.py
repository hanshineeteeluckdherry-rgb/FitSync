from datetime import date
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import uuid

# Accounts and profiles — Rheva

# 2.3 Fitness information and goals


class User(AbstractUser):
    """FitSync user with one simple role used for dashboard access."""

    class Role(models.TextChoices):
        MEMBER = ("MEMBER", "Member")
        STAFF = ("STAFF", "Staff")
        COACH = ("COACH", "Coach")
        ADMIN = ("ADMIN", "Admin")

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    def __str__(self):
        return self.get_full_name() or self.email or self.username

    class Meta:
        db_table = "accounts_user"


class MemberProfile(models.Model):
    """Extra member and fitness details kept separate from login details."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_profile",
    )
    profile_picture = models.ImageField(
        upload_to="profile_pics/", blank=True, null=True
    )
    avatar_static_path = models.CharField(max_length=255, blank=True)

    @property
    def avatar_url(self):
        from django.templatetags.static import static

        if self.profile_picture:
            return self.profile_picture.url
        return static(self.avatar_static_path) if self.avatar_static_path else ""

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

    class Meta:
        db_table = "accounts_memberprofile"


class CoachProfile(models.Model):
    """Simple public/professional details for users with the coach role."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_profile"
    )
    bio = models.TextField(blank=True)
    specialties = models.CharField(max_length=255, blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    qualifications = models.CharField(max_length=255, blank=True)
    photo_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.user} - Coach profile"

    class Meta:
        db_table = "accounts_coachprofile"


class CoachAssignment(models.Model):
    """Links one coach to one member without adding complex permissions."""

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coach_assignments",
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_links"
    )
    active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["coach", "member"], name="unique_coach_member_assignment"
            )
        ]
        db_table = "accounts_coachassignment"

    def clean(self):
        if self.coach_id and self.coach.role != User.Role.COACH:
            raise ValidationError({"coach": "Selected user must have the Coach role."})
        if self.member_id and self.member.role != User.Role.MEMBER:
            raise ValidationError(
                {"member": "Selected user must have the Member role."}
            )
        if self.coach_id and self.member_id and (self.coach_id == self.member_id):
            raise ValidationError("A coach cannot be assigned to themselves.")

    def __str__(self):
        return f"{self.coach} -> {self.member}"


# Memberships and payments — Noorie

# 1.2 Package comparison; 2.4–2.6 Memberships and payments; 4.4–4.5 Management


class MembershipPackage(models.Model):
    SERVICE_TYPE_CHOICES = [
        ("YOGA", "Yoga"),
        ("ZUMBA", "Zumba"),
        ("FITNESS", "Fitness"),
        ("SAUNA", "Sauna"),
        ("PERSONAL_TRAINING", "Personal Training"),
        ("PILATES", "Pilates"),
        ("BOXING", "Boxing"),
        ("HIIT", "HIIT"),
        ("CYCLING", "Cycling"),
        ("STRENGTH_TRAINING", "Strength Training"),
    ]
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_months = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=220, blank=True)
    features = models.TextField(help_text="One feature per line")
    audience = models.CharField(max_length=80, blank=True)
    allowed_service_types = models.CharField(
        max_length=200, blank=True, help_text="Leave empty to allow every service type."
    )
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price", "name"]
        db_table = "memberships_membershippackage"

    @property
    def feature_list(self):
        return [item.strip() for item in self.features.splitlines() if item.strip()]

    @property
    def allowed_service_type_list(self):
        return [
            item.strip()
            for item in self.allowed_service_types.split(",")
            if item.strip()
        ]

    def allows_service(self, service_type):
        allowed_types = self.allowed_service_type_list
        return not allowed_types or service_type in allowed_types

    def __str__(self):
        return self.name


class Membership(models.Model):

    class Status(models.TextChoices):
        ACTIVE = ("ACTIVE", "Active")
        EXPIRED = ("EXPIRED", "Expired")
        CANCELLED = ("CANCELLED", "Cancelled")

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    package = models.ForeignKey(
        MembershipPackage, on_delete=models.PROTECT, related_name="memberships"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        db_table = "memberships_membership"

    @property
    def display_status(self):
        if self.status == self.Status.ACTIVE and self.end_date < date.today():
            return self.Status.EXPIRED
        return self.status

    def __str__(self):
        return f"{self.member} - {self.package.name}"


class Payment(models.Model):

    class Status(models.TextChoices):
        SUCCESS = ("SUCCESS", "Success")
        FAILED = ("FAILED", "Failed")

    class Method(models.TextChoices):
        CARD = ("CARD", "Demo Card")
        CASH = ("CASH", "Cash")

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership_payments",
    )
    package = models.ForeignKey(
        MembershipPackage, on_delete=models.PROTECT, related_name="payments"
    )
    membership = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(
        max_length=12, choices=Method.choices, default=Method.CARD
    )
    status = models.CharField(max_length=12, choices=Status.choices)
    receipt_number = models.CharField(max_length=24, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "memberships_payment"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f"FS-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} - {self.member}"


# Services, sessions and bookings — Mehnaz

# 1.3 Public schedule; 2.8–2.12 Bookings; 3.6–3.7 Session management; 4.6 Services


class Service(models.Model):
    """Stores the different services offered by the gym."""

    class Type(models.TextChoices):
        YOGA = ("YOGA", "Yoga")
        ZUMBA = ("ZUMBA", "Zumba")
        FITNESS = ("FITNESS", "Fitness")
        SAUNA = ("SAUNA", "Sauna")
        PERSONAL_TRAINING = ("PERSONAL_TRAINING", "Personal Training")
        PILATES = ("PILATES", "Pilates")
        BOXING = ("BOXING", "Boxing")
        HIIT = ("HIIT", "HIIT")
        CYCLING = ("CYCLING", "Cycling")
        STRENGTH_TRAINING = ("STRENGTH_TRAINING", "Strength Training")

    name = models.CharField(max_length=100)
    service_type = models.CharField(max_length=30, choices=Type.choices)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        db_table = "bookings_service"

    def __str__(self):
        return self.name


class Session(models.Model):
    """Stores a scheduled date and time for a particular service."""

    class Status(models.TextChoices):
        SCHEDULED = ("SCHEDULED", "Scheduled")
        CANCELLED = ("CANCELLED", "Cancelled")
        COMPLETED = ("COMPLETED", "Completed")

    service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="sessions"
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instructed_sessions",
        limit_choices_to={"role": "COACH"},
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )

    class Meta:
        ordering = ["date", "start_time"]
        db_table = "bookings_session"

    def clean(self):
        """Validate the session before it is saved through a form."""
        if self.end_time and self.start_time:
            if self.end_time <= self.start_time:
                raise ValidationError(
                    {"end_time": "End time must be later than start time."}
                )
        if self.capacity == 0:
            raise ValidationError({"capacity": "Capacity must be greater than zero."})

    @property
    def confirmed_booking_count(self):
        """Return the number of confirmed bookings for this session."""
        return self.bookings.filter(status=Booking.Status.CONFIRMED).count()

    @property
    def remaining_spaces(self):
        """Return the number of places still available."""
        return max(self.capacity - self.confirmed_booking_count, 0)

    @property
    def is_full(self):
        """Return True when the session has no remaining places."""
        return self.remaining_spaces == 0

    def __str__(self):
        return f"{self.service.name} - {self.date} at {self.start_time}"


class Booking(models.Model):
    """Connects a member to a session that they have booked."""

    class Status(models.TextChoices):
        CONFIRMED = ("CONFIRMED", "Confirmed")
        CANCELLED = ("CANCELLED", "Cancelled")
        COMPLETED = ("COMPLETED", "Completed")

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        limit_choices_to={"role": "MEMBER"},
    )
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="bookings"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CONFIRMED
    )
    booked_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-booked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "session"],
                condition=models.Q(status="CONFIRMED"),
                name="unique_confirmed_member_session_booking",
            )
        ]
        db_table = "bookings_booking"

    def __str__(self):
        return f"{self.member} - {self.session}"


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


class Exercise(models.Model):
    MUSCLE_CHOICES = [
        ("CHEST", "Chest"),
        ("BACK", "Back"),
        ("SHOULDERS", "Shoulders"),
        ("BICEPS", "Biceps"),
        ("TRICEPS", "Triceps"),
        ("LEGS", "Legs"),
        ("GLUTES", "Glutes"),
        ("CORE", "Core"),
    ]
    EQUIPMENT_CHOICES = [
        ("BARBELL", "Barbell"),
        ("DUMBBELL", "Dumbbell"),
        ("CABLE", "Cable"),
        ("MACHINE", "Machine"),
        ("BODYWEIGHT", "Bodyweight"),
        ("KETTLEBELL", "Kettlebell"),
        ("BAND", "Resistance Band"),
        ("OTHER", "Other"),
    ]
    DIFFICULTY_CHOICES = [
        ("BEGINNER", "Beginner"),
        ("INTERMEDIATE", "Intermediate"),
        ("ADVANCED", "Advanced"),
    ]
    INTENSITY_CHOICES = [
        ("LOW", "Low"),
        ("MODERATE", "Moderate"),
        ("HIGH", "High"),
        ("VERY_HIGH", "Very High"),
    ]
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=MUSCLE_CHOICES)
    secondary_muscles = models.CharField(max_length=150, blank=True)
    equipment = models.CharField(
        max_length=20, choices=EQUIPMENT_CHOICES, default="OTHER"
    )
    difficulty = models.CharField(
        max_length=20, choices=DIFFICULTY_CHOICES, default="BEGINNER"
    )
    intensity = models.CharField(
        max_length=20, choices=INTENSITY_CHOICES, default="MODERATE"
    )
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    image = models.ImageField(upload_to="exercises/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]
        db_table = "workouts_exercise"

    @property
    def fallback_image(self):
        return f"img/exercises/{self.category.lower()}.jpg"

    @property
    def library_image(self):
        return f"img/exercises/library/{self.category.lower()}/{slugify(self.name)}.jpg"

    def __str__(self):
        return self.name


class WorkoutPlan(models.Model):
    PLAN_TYPE_CHOICES = [("PERSONAL", "Personal"), ("COACH_ASSIGNED", "Coach Assigned")]
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_plans"
    )
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_workout_plans",
    )
    name = models.CharField(max_length=100)
    goal = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    workout_days = models.CharField(max_length=100, blank=True)
    plan_type = models.CharField(
        max_length=20, choices=PLAN_TYPE_CHOICES, default="PERSONAL"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "workouts_workoutplan"


class WorkoutPlanExercise(models.Model):
    workout_plan = models.ForeignKey(
        WorkoutPlan, on_delete=models.CASCADE, related_name="plan_exercises"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.PROTECT, related_name="workout_plan_entries"
    )
    day_number = models.PositiveIntegerField(default=1)
    sets = models.PositiveIntegerField(default=1)
    reps = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["day_number", "order", "id"]
        db_table = "workouts_workoutplanexercise"

    def __str__(self):
        return f"{self.workout_plan.name} - {self.exercise.name}"


class WorkoutSession(models.Model):
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workout_sessions",
    )
    workout_plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        db_table = "workouts_workoutsession"

    def __str__(self):
        return f"{self.member.username} - {self.started_at:%Y-%m-%d}"


class WorkoutExerciseRecord(models.Model):
    workout_session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name="exercise_records"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.PROTECT, related_name="workout_records"
    )
    set_number = models.PositiveIntegerField(null=True, blank=True)
    sets = models.PositiveIntegerField(default=1)
    reps = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.workout_session} - {self.exercise.name}"

    class Meta:
        db_table = "workouts_workoutexerciserecord"


class WeightRecord(models.Model):
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weight_records",
    )
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    recorded_date = models.DateField()
    note = models.TextField(blank=True)
    progress_photo = models.ImageField(
        upload_to="progress_photos/", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_date", "-id"]
        db_table = "workouts_weightrecord"

    def __str__(self):
        return f"{self.member.username} - {self.weight_kg} kg"


class WaterIntake(models.Model):
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="water_records"
    )
    recorded_date = models.DateField(default=timezone.localdate)
    litres = models.DecimalField(
        max_digits=4, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["-recorded_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "recorded_date"], name="unique_member_water_date"
            )
        ]
        db_table = "workouts_waterintake"

    def __str__(self):
        return f"{self.member} - {self.recorded_date}: {self.litres} L"


# Attendance — Bhavshika

# 2.7 QR code; 2.13 Occupancy; 3.3–3.5 Entry; 4.7–4.8 Capacity and corrections


class GymConfiguration(models.Model):
    max_capacity = models.PositiveIntegerField(default=50)

    @classmethod
    def get_capacity(cls):
        configuration, _ = cls.objects.get_or_create(pk=1)
        return configuration.max_capacity

    def __str__(self):
        return f"Maximum capacity: {self.max_capacity}"

    class Meta:
        db_table = "attendance_gymconfiguration"


class MemberQRCode(models.Model):
    member = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="qr_code"
    )
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR Code for {self.member}"

    class Meta:
        db_table = "attendance_memberqrcode"


class AttendanceRecord(models.Model):
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_corrections",
    )
    correction_note = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.member} - {self.check_in_time.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ["-check_in_time"]
        db_table = "attendance_attendancerecord"


# Outdoor activities — Bhavshika

# 2.20–2.21 Outdoor summaries and history; GPS recording remains mobile-phase work


class OutdoorActivity(models.Model):
    ACTIVITY_CHOICES = [
        ("walking", "Walking"),
        ("running", "Running"),
        ("cycling", "Cycling"),
    ]
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="outdoor_activities",
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    date = models.DateField()
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.member} - {self.activity_type} ({self.date})"

    class Meta:
        ordering = ["-date"]
        db_table = "activities_outdooractivity"


# Notifications and notices — Anjie

# 2.24 Member notifications; 4.10 Gym notices


class Notification(models.Model):

    class Type(models.TextChoices):
        BOOKING = ("BOOKING", "Booking")
        MEMBERSHIP = ("MEMBERSHIP", "Membership")
        NOTICE = ("NOTICE", "Gym Notice")

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
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
        db_table = "notifications_notification"

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
        db_table = "notifications_notice"

    @property
    def is_current(self):
        today = timezone.localdate()
        return (
            self.is_active
            and self.publish_date <= today
            and (self.expires_on is None or self.expires_on >= today)
        )

    def __str__(self):
        return self.title


# Public team and contact content — Shared

# 1.7 Contact enquiries; 4.14 Contact information; 4.15 Private inbox


class GymSettings(models.Model):
    """One editable set of public gym contact details."""

    address = models.CharField(max_length=255, default="Réduit, Mauritius")
    phone = models.CharField(max_length=40, default="+230 5678905")
    public_email = models.EmailField(default="hello@fitsync.com")
    careers_email = models.EmailField(default="careers@fitsync.com")
    opening_hours = models.TextField(
        default="Mon–Fri 05:30–23:00 · Sat 06:00–22:00\nSun 08:00–21:00\nPremium & Elite: 24/7 access"
    )
    response_time = models.CharField(
        max_length=200, default="We'll respond within 2–4 business hours."
    )
    instagram_url = models.URLField(blank=True, default="https://www.instagram.com/")
    facebook_url = models.URLField(blank=True, default="https://www.facebook.com/")
    social_handle = models.CharField(max_length=80, default="@fitsync")
    map_image = models.ImageField(upload_to="contact/", blank=True)
    map_static_path = models.CharField(
        max_length=255, blank=True, default="img/contact/reduit-map.png"
    )

    class Meta:
        verbose_name_plural = "Gym settings"
        db_table = "core_gymsettings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.filter(pk=1).first() or cls()

    @property
    def phone_link(self):
        return "".join((char for char in self.phone if char.isdigit() or char == "+"))

    @property
    def map_image_url(self):
        from django.templatetags.static import static

        return (
            self.map_image.url
            if self.map_image
            else static(self.map_static_path) if self.map_static_path else ""
        )

    def __str__(self):
        return "FitSync contact details"


class ContactMessage(models.Model):

    class Status(models.TextChoices):
        NEW = ("NEW", "New")
        IN_PROGRESS = ("IN_PROGRESS", "In progress")
        REPLIED = ("REPLIED", "Replied")
        ARCHIVED = ("ARCHIVED", "Archived")

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    topic = models.CharField(max_length=30, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    staff_notes = models.TextField(blank=True)
    email_notification_sent = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        db_table = "core_contactmessage"

    def __str__(self):
        return self.full_name


# Public team and contact content — Shared

# 1.6 Public team; 4.13 Team profile management


class TeamMember(models.Model):

    class Department(models.TextChoices):
        FOUNDER = ("founder", "Founder")
        OPERATIONS = ("operations", "Operations")
        COACHING = ("coaching", "Coaching")
        WELLNESS = ("wellness", "Wellness")
        FITNESS = ("fitness", "Fitness")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="public_team_profile",
        help_text="Link an existing staff/coach account; does not create another login.",
    )
    slug = models.SlugField(
        unique=True,
        help_text="Stable internal identifier; changing the display name does not change this key.",
    )
    display_name = models.CharField(max_length=120)
    job_title = models.CharField(max_length=150)
    department = models.CharField(max_length=20, choices=Department.choices)
    bio = models.TextField()
    featured_bio = models.TextField(blank=True)
    specialties = models.TextField(blank=True, help_text="One specialty per line.")
    experience = models.CharField(max_length=80, blank=True)
    photo = models.ImageField(upload_to="team/", blank=True)
    static_photo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional bundled image path, used when no photo is uploaded.",
    )
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "display_name", "pk"]
        db_table = "ourteam_teammember"

    @property
    def photo_url(self):
        from django.templatetags.static import static

        return (
            self.photo.url
            if self.photo
            else static(self.static_photo) if self.static_photo else ""
        )

    @property
    def specialty_list(self):
        return [line.strip() for line in self.specialties.splitlines() if line.strip()]

    @property
    def badge_class(self):
        return {
            "founder": "badge-leadership",
            "operations": "badge-ops",
            "coaching": "badge-coach",
            "wellness": "badge-wellness",
            "fitness": "badge-fitness",
        }.get(self.department, "")

    def __str__(self):
        return self.display_name
