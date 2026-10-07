from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("memberships", "0004_match_public_figma_477_27"),
    ]

    operations = [
        migrations.AddField(
            model_name="membershippackage",
            name="allowed_service_types",
            field=models.CharField(
                blank=True,
                help_text="Leave empty to allow every service type.",
                max_length=200,
            ),
        ),
    ]
