from django.core.management.base import BaseCommand

from accounts.models import CoachProfile, MemberProfile, User


class Command(BaseCommand):
    help = "Create or refresh the shared FitSync demo accounts."

    DEMO_PASSWORD = "FitSync123!"

    def handle(self, *args, **options):
        demo_users = [
            {
                "email": "member@fitsync.com",
                "first_name": "Lionel",
                "last_name": "Messi",
                "role": User.Role.MEMBER,
            },
            {
                "email": "coach@fitsync.com",
                "first_name": "Demo",
                "last_name": "Coach",
                "role": User.Role.COACH,
            },
            {
                "email": "staff@fitsync.com",
                "first_name": "Demo",
                "last_name": "Staff",
                "role": User.Role.STAFF,
            },
            {
                "email": "admin@fitsync.com",
                "first_name": "Demo",
                "last_name": "Admin",
                "role": User.Role.ADMIN,
            },
        ]

        for data in demo_users:
            email = data["email"]
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"username": email},
            )

            # These are demo accounts, so rerunning the command safely refreshes them.
            user.username = email
            user.first_name = data["first_name"]
            user.last_name = data["last_name"]
            user.role = data["role"]
            user.is_active = True
            user.set_password(self.DEMO_PASSWORD)
            user.save()

            if user.role == User.Role.MEMBER:
                MemberProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "age": 38,
                        "height_cm": 170,
                        "current_weight_kg": 72,
                        "fitness_goal": "Improve Endurance",
                    },
                )

            if user.role == User.Role.COACH:
                CoachProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "bio": "FitSync demo coach account.",
                        "specialties": "Strength and conditioning",
                        "years_experience": 5,
                    },
                )

            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action} {email} ({user.get_role_display()})"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("FitSync demo users are ready."))
        self.stdout.write(f"Shared demo password: {self.DEMO_PASSWORD}")
