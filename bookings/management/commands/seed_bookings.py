"""Create reusable booking data based on the FitSync Figma design."""

from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Service, Session


User = get_user_model()


class Command(BaseCommand):
    """Create the coaches, services and sessions shown in Figma."""

    help = "Create reusable sample data for testing the booking page."

    def handle(self, *args, **options):
        """Create coaches and six future sessions without duplicates."""

        today = timezone.localdate()

        days_until_monday = (7 - today.weekday()) % 7

        if days_until_monday == 0:
            days_until_monday = 7

        next_monday = today + timedelta(days=days_until_monday)

        coach_data = [
            {
                "username": "chloe_ting",
                "first_name": "Chloe",
                "last_name": "Ting",
                "email": "chloe.ting@fitsync.local",
            },
            {
                "username": "sarah_saffari",
                "first_name": "Sarah",
                "last_name": "Saffari",
                "email": "sarah.saffari@fitsync.local",
            },
            {
                "username": "chris_heria",
                "first_name": "Chris",
                "last_name": "Heria",
                "email": "chris.heria@fitsync.local",
            },
            {
                "username": "julie_bowen",
                "first_name": "Julie",
                "last_name": "Bowen",
                "email": "julie.bowen@fitsync.local",
            },
            {
                "username": "sam_sulek",
                "first_name": "Sam",
                "last_name": "Sulek",
                "email": "sam.sulek@fitsync.local",
            },
            {
                "username": "chris_bumstead",
                "first_name": "Chris",
                "last_name": "Bumstead",
                "email": "chris.bumstead@fitsync.local",
            },
        ]

        coaches = {}

        for item in coach_data:
            coach, created = User.objects.get_or_create(
                username=item["username"],
                defaults={
                    "email": item["email"],
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "role": User.Role.COACH,
                    "is_active": True,
                },
            )

            coach.first_name = item["first_name"]
            coach.last_name = item["last_name"]
            coach.role = User.Role.COACH
            coach.is_active = True

            if created:
                coach.set_unusable_password()

            coach.save()

            coaches[item["username"]] = coach

        sessions = [
            {
                "name": "Power Yoga",
                "service_type": Service.Type.YOGA,
                "description": (
                    "A dynamic yoga practice that builds strength, "
                    "flexibility and focus."
                ),
                "price": Decimal("100.00"),
                "coach": "chloe_ting",
                "day_offset": 0,
                "start_time": time(7, 0),
                "end_time": time(8, 0),
                "capacity": 15,
            },
            {
                "name": "HIIT Blast",
                "service_type": Service.Type.FITNESS,
                "description": (
                    "High-intensity interval training to torch calories "
                    "and build endurance."
                ),
                "price": Decimal("150.00"),
                "coach": "sarah_saffari",
                "day_offset": 0,
                "start_time": time(9, 0),
                "end_time": time(10, 0),
                "capacity": 20,
            },
            {
                "name": "Zumba Fiesta",
                "service_type": Service.Type.ZUMBA,
                "description": (
                    "Dance your way to fitness with this high-energy "
                    "Latin-inspired class."
                ),
                "price": Decimal("100.00"),
                "coach": "chris_heria",
                "day_offset": 1,
                "start_time": time(18, 0),
                "end_time": time(19, 0),
                "capacity": 25,
            },
            {
                "name": "Sauna Session",
                "service_type": Service.Type.SAUNA,
                "description": (
                    "Relaxing sauna session for recovery and wellness."
                ),
                "price": Decimal("50.00"),
                "coach": "julie_bowen",
                "day_offset": 1,
                "start_time": time(16, 0),
                "end_time": time(17, 0),
                "capacity": 8,
            },
            {
                "name": "Personal Training",
                "service_type": Service.Type.PERSONAL_TRAINING,
                "description": (
                    "One-on-one training session tailored to your "
                    "specific fitness goals."
                ),
                "price": Decimal("500.00"),
                "coach": "sam_sulek",
                "day_offset": 2,
                "start_time": time(10, 0),
                "end_time": time(11, 0),
                "capacity": 1,
            },
            {
                "name": "Spin Cycle",
                "service_type": Service.Type.FITNESS,
                "description": (
                    "High-energy indoor cycling class for all fitness levels."
                ),
                "price": Decimal("200.00"),
                "coach": "chris_bumstead",
                "day_offset": 3,
                "start_time": time(6, 30),
                "end_time": time(7, 30),
                "capacity": 16,
            },
        ]

        created_count = 0
        updated_count = 0

        for item in sessions:
            service, unused_created = Service.objects.update_or_create(
                name=item["name"],
                defaults={
                    "service_type": item["service_type"],
                    "description": item["description"],
                    "price": item["price"],
                    "is_active": True,
                },
            )

            session_date = next_monday + timedelta(
                days=item["day_offset"]
            )

            session, created = Session.objects.update_or_create(
                service=service,
                date=session_date,
                start_time=item["start_time"],
                defaults={
                    "instructor": coaches[item["coach"]],
                    "end_time": item["end_time"],
                    "capacity": item["capacity"],
                    "status": Session.Status.SCHEDULED,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Booking sample data is ready. "
                f"Created {created_count} session(s) and "
                f"updated {updated_count} session(s)."
            )
        )
