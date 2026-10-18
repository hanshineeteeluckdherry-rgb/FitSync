from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import CoachProfile, User


class TeamSeedTests(TestCase):
    def test_creates_team_accounts_and_coach_profiles(self):
        call_command("seed_team", password="LocalTest123!", stdout=StringIO())
        self.assertEqual(User.objects.count(), 8)
        self.assertEqual(CoachProfile.objects.count(), 6)
        self.assertEqual(User.objects.get(email="dwayne.johnson@fitsync.com").role, User.Role.ADMIN)
        self.assertEqual(User.objects.get(email="julie.bowen@fitsync.com").role, User.Role.STAFF)
        for user in User.objects.all():
            self.assertTrue(user.check_password("LocalTest123!"))

    def test_rerunning_keeps_existing_passwords_and_details(self):
        call_command("seed_team", password="LocalTest123!", stdout=StringIO())
        user = User.objects.get(email="sam.sulek@fitsync.com")
        user.first_name = "Updated"
        user.set_password("ChangedPassword123!")
        user.save()
        call_command("seed_team", password="Different123!", stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual(User.objects.count(), 8)
        self.assertEqual(user.first_name, "Updated")
        self.assertTrue(user.check_password("ChangedPassword123!"))

    def test_booking_seed_and_team_seed_work_in_either_order(self):
        call_command("seed_bookings", stdout=StringIO())
        call_command("seed_team", password="LocalTest123!", stdout=StringIO())
        call_command("seed_bookings", stdout=StringIO())
        self.assertEqual(User.objects.count(), 8)
        self.assertEqual(User.objects.get(email="julie.bowen@fitsync.com").role, User.Role.STAFF)
        for user in User.objects.all():
            self.assertTrue(user.check_password("LocalTest123!"))

    def test_catalogue_only_does_not_create_users_or_sessions(self):
        from bookings.models import Service, Session
        call_command("seed_bookings", services_only=True, stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Session.objects.count(), 0)
        self.assertEqual(Service.objects.count(), 11)
        service = Service.objects.first()
        service.price = 42
        service.save()
        call_command("seed_bookings", services_only=True, stdout=StringIO())
        service.refresh_from_db()
        self.assertEqual(service.price, 42)
