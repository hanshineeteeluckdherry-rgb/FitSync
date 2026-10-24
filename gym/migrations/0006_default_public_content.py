# Team and contact information — Shared
# 1.6 Public team; 4.13 Team profiles; 4.14 Contact details

from django.db import migrations
from django.utils.text import slugify


TEAM_MEMBERS = [
    {
        "account_email": "dwayne.johnson@fitsync.com",
        "display_name": "Dwayne The Rock Johnson",
        "job_title": "Owner & Head of Operations",
        "department": "founder",
        "bio": "Founder of FitSync, building a fitness community that puts members first.",
        "featured_bio": "Dwayne founded FitSync in 2026 with a vision to build a gym that puts members first. With a background in sports science and business management, he has grown FitSync into one of the city's most respected fitness communities.",
        "specialties": "Strength & Conditioning\nBusiness Strategy\nTeam Leadership",
        "experience": "FitSync founder",
        "static_photo": "img/ourteam/dwane.png",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "account_email": "julie.bowen@fitsync.com",
        "display_name": "Julie Bowen",
        "job_title": "Operations Manager",
        "department": "operations",
        "bio": "Over 10 years of experience managing fitness facilities and ensuring smooth operations.",
        "specialties": "Facility Management\nScheduling",
        "experience": "10 yrs experience",
        "static_photo": "img/ourteam/julie.png",
        "sort_order": 2,
    },
    {
        "account_email": "chris.bumstead@fitsync.com",
        "display_name": "Chris Bumstead",
        "job_title": "Head Coach",
        "department": "coaching",
        "bio": "Specialist in bodybuilding and strength training with 8 years of coaching experience.",
        "specialties": "Bodybuilding\nStrength Training",
        "experience": "8 yrs experience",
        "static_photo": "img/ourteam/chrisb.png",
        "sort_order": 3,
    },
    {
        "account_email": "sarah.safforti@fitsync.com",
        "display_name": "Sarah Safforti",
        "job_title": "Performance Coach",
        "department": "coaching",
        "bio": "Dedicated to helping athletes reach peak performance through personalized training plans.",
        "specialties": "HIIT\nEndurance Training",
        "experience": "6 yrs experience",
        "static_photo": "img/ourteam/sarah.jpg",
        "sort_order": 4,
    },
    {
        "account_email": "emily.watson@fitsync.com",
        "display_name": "Emily Watson",
        "job_title": "Wellness Specialist",
        "department": "wellness",
        "bio": "Expert in holistic health, nutrition, and mindfulness practices for overall well-being.",
        "specialties": "Nutrition\nMindfulness",
        "experience": "7 yrs experience",
        "static_photo": "img/ourteam/emily.jpg",
        "sort_order": 5,
    },
    {
        "account_email": "sam.sulek@fitsync.com",
        "display_name": "Sam Sulek",
        "job_title": "Fitness Trainer",
        "department": "fitness",
        "bio": "Passionate about functional training and helping clients build sustainable fitness routines.",
        "specialties": "Functional Training\nHypertrophy",
        "experience": "5 yrs experience",
        "static_photo": "img/ourteam/sam.jpg",
        "sort_order": 6,
    },
    {
        "account_email": "chris.heria@fitsync.com",
        "display_name": "Chris Heria",
        "job_title": "Calisthenics Expert",
        "department": "coaching",
        "bio": "Renowned for bodyweight training techniques and innovative fitness programs.",
        "specialties": "Calisthenics\nMobility",
        "experience": "9 yrs experience",
        "static_photo": "img/ourteam/chrish.jpg",
        "sort_order": 7,
    },
    {
        "account_email": "chloe.ting@fitsync.com",
        "display_name": "Chloe Ting",
        "job_title": "Fitness Instructor",
        "department": "fitness",
        "bio": "Creator of viral workout programs, inspiring millions to stay active and healthy.",
        "specialties": "Home Workouts\nPilates",
        "experience": "7 yrs experience",
        "static_photo": "img/ourteam/chloe.jpg",
        "sort_order": 8,
    },
]


def add_public_content(apps, schema_editor):
    GymSettings = apps.get_model("gym", "GymSettings")
    TeamMember = apps.get_model("gym", "TeamMember")
    User = apps.get_model("gym", "User")
    database = schema_editor.connection.alias

    GymSettings.objects.using(database).get_or_create(pk=1)
    featured_exists = (
        TeamMember.objects.using(database).filter(is_featured=True).exists()
    )

    for item in TEAM_MEMBERS:
        details = dict(item)
        email = details.pop("account_email")
        slug = slugify(details["display_name"])
        user = (
            User.objects.using(database)
            .filter(email__iexact=email, role__in=["COACH", "STAFF", "ADMIN"])
            .first()
        )
        if user and TeamMember.objects.using(database).filter(user_id=user.pk).exists():
            user = None

        details["user_id"] = user.pk if user else None
        if details.get("is_featured") and featured_exists:
            details["is_featured"] = False

        person, created = TeamMember.objects.using(database).get_or_create(
            slug=slug, defaults=details
        )
        if person.is_featured:
            featured_exists = True


class Migration(migrations.Migration):
    dependencies = [
        ("gym", "0005_contactmessage_gymsettings_and_more"),
    ]

    operations = [
        migrations.RunPython(add_public_content, migrations.RunPython.noop),
    ]
