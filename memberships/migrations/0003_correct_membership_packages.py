from django.db import migrations


PACKAGES = {
    "starter": {
        "name": "Starter",
        "price": "1000.00",
        "features": "Gym Access (6am–10pm)\nBasic Equipment\n1 Class / Week\nFitSync App",
        "is_featured": False,
    },
    "premium": {
        "name": "Premium",
        "price": "1990.00",
        "features": "24/7 Gym Access\nAll Group Classes\n1 PT Session/Month\nFull Analytics\nPriority Booking",
        "is_featured": True,
    },
    "elite": {
        "name": "Elite",
        "price": "2990.00",
        "features": "Everything in Premium\n4 PT Sessions/Month\nDedicated Coach\nCustom Meal Plans\nBody Scans",
        "is_featured": False,
    },
    "student": {
        "name": "Student",
        "price": "900.00",
        "features": "24/7 Gym Access\nBasic Equipment\nFitSync App",
        "is_featured": False,
    },
}


def correct_packages(apps, schema_editor):
    package_model = apps.get_model("memberships", "MembershipPackage")
    for slug, values in PACKAGES.items():
        package_model.objects.filter(slug=slug).update(**values)


class Migration(migrations.Migration):
    dependencies = [("memberships", "0002_seed_packages")]
    operations = [migrations.RunPython(correct_packages, migrations.RunPython.noop)]
