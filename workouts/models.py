from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


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
        max_length=20,
        choices=EQUIPMENT_CHOICES,
        default="OTHER",
    )
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="BEGINNER",
    )
    intensity = models.CharField(
        max_length=20,
        choices=INTENSITY_CHOICES,
        default="MODERATE",
    )
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    image = models.ImageField(upload_to="exercises/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    @property
    def fallback_image(self):
        return f"img/exercises/{self.category.lower()}.jpg"

    @property
    def library_image(self):
        return f"img/exercises/library/{self.category.lower()}/{slugify(self.name)}.jpg"

    def __str__(self):
        return self.name


class WorkoutPlan(models.Model):
    PLAN_TYPE_CHOICES = [
        ("PERSONAL", "Personal"),
        ("COACH_ASSIGNED", "Coach Assigned"),
    ]

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workout_plans",
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
        max_length=20,
        choices=PLAN_TYPE_CHOICES,
        default="PERSONAL",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class WorkoutPlanExercise(models.Model):
    workout_plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.CASCADE,
        related_name="plan_exercises",
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.PROTECT,
        related_name="workout_plan_entries",
    )
    day_number = models.PositiveIntegerField(default=1)
    sets = models.PositiveIntegerField(default=1)
    reps = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["day_number", "order", "id"]

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

    def __str__(self):
        return f"{self.member.username} - {self.started_at:%Y-%m-%d}"


class WorkoutExerciseRecord(models.Model):
    workout_session = models.ForeignKey(
        WorkoutSession,
        on_delete=models.CASCADE,
        related_name="exercise_records",
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.PROTECT,
        related_name="workout_records",
    )
    sets = models.PositiveIntegerField(default=1)
    reps = models.PositiveIntegerField(default=1)
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.workout_session} - {self.exercise.name}"


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
        upload_to="progress_photos/",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_date", "-id"]

    def __str__(self):
        return f"{self.member.username} - {self.weight_kg} kg"
