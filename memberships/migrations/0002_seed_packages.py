from django.db import migrations


PACKAGES = [
    {
        "name": "Starter",
        "slug": "starter",
        "price": "1000.00",
        "duration_months": 1,
        "description": "Simple gym access for members beginning their fitness journey.",
        "features": "Gym Access (6am–10pm)\nBasic Equipment\n1 Class / Week\nFitSync App",
        "audience": "Essential access",
        "is_featured": False,
    },
    {
        "name": "Premium",
        "slug": "premium",
        "price": "1990.00",
        "duration_months": 1,
        "description": "Full gym access, classes and extra support for consistent training.",
        "features": "24/7 Gym Access\nAll Group Classes\n1 PT Session/Month\nFull Analytics\nPriority Booking",
        "audience": "Most popular",
        "is_featured": True,
    },
    {
        "name": "Elite",
        "slug": "elite",
        "price": "2990.00",
        "duration_months": 1,
        "description": "Premium training access with enhanced coaching benefits.",
        "features": "Everything in Premium\n4 PT Sessions/Month\nDedicated Coach\nCustom Meal Plans\nBody Scans",
        "audience": "Advanced training",
        "is_featured": False,
    },
    {
        "name": "Student",
        "slug": "student",
        "price": "900.00",
        "duration_months": 1,
        "description": "Affordable FitSync access designed for student members.",
        "features": "24/7 Gym Access\nBasic Equipment\nFitSync App",
        "audience": "Student plan",
        "is_featured": False,
    },
]


def create_packages(apps, schema_editor):
    package_model = apps.get_model("memberships", "MembershipPackage")
    for package in PACKAGES:
        package_model.objects.update_or_create(slug=package["slug"], defaults=package)


def remove_packages(apps, schema_editor):
    package_model = apps.get_model("memberships", "MembershipPackage")
    package_model.objects.filter(slug__in=[item["slug"] for item in PACKAGES]).delete()


class Migration(migrations.Migration):
    dependencies = [("memberships", "0001_initial")]
    operations = [migrations.RunPython(create_packages, remove_packages)]
