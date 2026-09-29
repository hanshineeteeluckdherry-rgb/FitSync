from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Service(models.Model):
    """Stores the different services offered by the gym."""

    class Type(models.TextChoices):
        YOGA = "YOGA", "Yoga"
        ZUMBA = "ZUMBA", "Zumba"
        FITNESS = "FITNESS", "Fitness"
        SAUNA = "SAUNA", "Sauna"
        PERSONAL_TRAINING = "PERSONAL_TRAINING", "Personal Training"

    name = models.CharField(max_length=100)
    service_type = models.CharField(
        max_length=30,
        choices=Type.choices,
    )
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        # Services will be displayed alphabetically.
        ordering = ["name"]

    def __str__(self):
        return self.name


class Session(models.Model):
    """Stores a scheduled date and time for a particular service."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    # One service can have several scheduled sessions.
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="sessions",
    )

    # The instructor must be a user with the Coach role.
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
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )

    class Meta:
        # Earlier sessions will be displayed first.
        ordering = ["date", "start_time"]

    def clean(self):
        """Validate the session before it is saved through a form."""
        if self.end_time and self.start_time:
            if self.end_time <= self.start_time:
                raise ValidationError(
                    {"end_time": "End time must be later than start time."}
                )

        if self.capacity == 0:
            raise ValidationError(
                {"capacity": "Capacity must be greater than zero."}
            )

    @property
    def confirmed_booking_count(self):
        """Return the number of confirmed bookings for this session."""
        return self.bookings.filter(
            status=Booking.Status.CONFIRMED
        ).count()

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
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    # The person making the booking must have the Member role.
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        limit_choices_to={"role": "MEMBER"},
    )

    # One session can have bookings from several members.
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )

    booked_at = models.DateTimeField(auto_now_add=True)

    # This remains empty until the booking is cancelled.
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        # Newest bookings will be displayed first.
        ordering = ["-booked_at"]

        constraints = [
            # A member cannot have two confirmed bookings
            # for the same session.
            models.UniqueConstraint(
                fields=["member", "session"],
                condition=models.Q(status="CONFIRMED"),
                name="unique_confirmed_member_session_booking",
            )
        ]

    def __str__(self):
        return f"{self.member} - {self.session}"