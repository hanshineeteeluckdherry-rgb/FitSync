from django.core.management.base import BaseCommand
from django.db import transaction
from gym.models import CoachProfile, User
from django.core.management.base import CommandError


def existing_team_user(handle):
    email = f"{handle}@fitsync.com"
    old_email = f"{handle}@fitsync.local"
    current = User.objects.filter(email=email).first()
    legacy = User.objects.filter(email=old_email).first()
    if current and legacy and (current.pk != legacy.pk):
        raise CommandError(
            f"Both {email} and {old_email} exist. No accounts were merged."
        )
    if legacy:
        if legacy.username == old_email:
            if User.objects.filter(username=email).exclude(pk=legacy.pk).exists():
                raise CommandError(f"Username {email} is already in use.")
            legacy.username = email
        legacy.email = email
        legacy.save(update_fields=["email", "username"])
    return legacy or current


TEAM = [
    ("dwayne.johnson", "Dwayne", "The Rock Johnson", User.Role.ADMIN, "", 0, ""),
    ("julie.bowen", "Julie", "Bowen", User.Role.STAFF, "", 0, ""),
    (
        "chris.bumstead",
        "Chris",
        "Bumstead",
        User.Role.COACH,
        "Bodybuilding, Strength Training",
        8,
        "chrisb.png",
    ),
    (
        "sarah.safforti",
        "Sarah",
        "Safforti",
        User.Role.COACH,
        "HIIT, Endurance Training",
        6,
        "sarah.jpg",
    ),
    (
        "chris.heria",
        "Chris",
        "Heria",
        User.Role.COACH,
        "Calisthenics, Mobility",
        9,
        "chrish.jpg",
    ),
    (
        "emily.watson",
        "Emily",
        "Watson",
        User.Role.COACH,
        "Nutrition, Mindfulness",
        7,
        "emily.jpg",
    ),
    (
        "sam.sulek",
        "Sam",
        "Sulek",
        User.Role.COACH,
        "Functional Training, Hypertrophy",
        5,
        "sam.jpg",
    ),
    (
        "chloe.ting",
        "Chloe",
        "Ting",
        User.Role.COACH,
        "Home Workouts, Pilates",
        7,
        "chloe.jpg",
    ),
]


class Command(BaseCommand):
    help = "Create local Our Team demo accounts without resetting existing users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            required=True,
            help="Initial password for newly created demo accounts only.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        for handle, first, last, role, specialties, years, photo in TEAM:
            email = f"{handle}@fitsync.com"
            user = existing_team_user(handle)
            created = user is None
            if created:
                user = User.objects.create(
                    username=email,
                    email=email,
                    first_name=first,
                    last_name=last,
                    role=role,
                )
            if created or not user.has_usable_password():
                user.set_password(options["password"])
                user.save(update_fields=["password"])
            if user.role == User.Role.COACH:
                CoachProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "specialties": specialties,
                        "years_experience": years,
                        "photo_url": f"/static/img/ourteam/{photo}",
                    },
                )
            action = "Created" if created else "Kept existing"
            self.stdout.write(f"{action}: {email} ({user.get_role_display()})")
        self.stdout.write(
            self.style.SUCCESS(
                "Our Team demo accounts are ready. Do not use shared demo passwords in production."
            )
        )
