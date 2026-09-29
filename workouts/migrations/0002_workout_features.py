import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="exercise",
            options={"ordering": ["category", "name"]},
        ),
        migrations.AlterModelOptions(
            name="weightrecord",
            options={"ordering": ["-recorded_date", "-id"]},
        ),
        migrations.AlterModelOptions(
            name="workoutplanexercise",
            options={"ordering": ["day_number", "order", "id"]},
        ),
        migrations.AlterModelOptions(
            name="workoutsession",
            options={"ordering": ["-started_at"]},
        ),
        migrations.AlterField(
            model_name="exercise",
            name="category",
            field=models.CharField(
                choices=[
                    ("CHEST", "Chest"),
                    ("BACK", "Back"),
                    ("SHOULDERS", "Shoulders"),
                    ("BICEPS", "Biceps"),
                    ("TRICEPS", "Triceps"),
                    ("LEGS", "Legs"),
                    ("GLUTES", "Glutes"),
                    ("CORE", "Core"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="exercise",
            name="difficulty",
            field=models.CharField(
                choices=[
                    ("BEGINNER", "Beginner"),
                    ("INTERMEDIATE", "Intermediate"),
                    ("ADVANCED", "Advanced"),
                ],
                default="BEGINNER",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="exercise",
            name="equipment",
            field=models.CharField(
                choices=[
                    ("BARBELL", "Barbell"),
                    ("DUMBBELL", "Dumbbell"),
                    ("CABLE", "Cable"),
                    ("MACHINE", "Machine"),
                    ("BODYWEIGHT", "Bodyweight"),
                    ("KETTLEBELL", "Kettlebell"),
                    ("BAND", "Resistance Band"),
                    ("OTHER", "Other"),
                ],
                default="OTHER",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="exercise",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="exercises/"),
        ),
        migrations.AddField(
            model_name="exercise",
            name="intensity",
            field=models.CharField(
                choices=[
                    ("LOW", "Low"),
                    ("MODERATE", "Moderate"),
                    ("HIGH", "High"),
                    ("VERY_HIGH", "Very High"),
                ],
                default="MODERATE",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="exercise",
            name="secondary_muscles",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="workoutplan",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="workoutplan",
            name="workout_days",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name="workoutsession",
            name="started_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
