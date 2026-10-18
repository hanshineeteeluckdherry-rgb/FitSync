from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="service_type",
            field=models.CharField(max_length=30, choices=[
                ("YOGA", "Yoga"), ("ZUMBA", "Zumba"), ("FITNESS", "Fitness"),
                ("SAUNA", "Sauna"), ("PERSONAL_TRAINING", "Personal Training"),
                ("PILATES", "Pilates"), ("BOXING", "Boxing"), ("HIIT", "HIIT"),
                ("CYCLING", "Cycling"), ("STRENGTH_TRAINING", "Strength Training"),
            ]),
        ),
    ]
