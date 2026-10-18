from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import CoachAssignment, User
from bookings.models import Booking, Session
from memberships.models import Membership
from workouts.models import WaterIntake, WeightRecord, WorkoutExerciseRecord, WorkoutPlan, WorkoutSession


class DemoMemberSeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo_members", password="DemoTest123!", stdout=StringIO())

    def test_complete_demo_dataset(self):
        members = User.objects.filter(role=User.Role.MEMBER)
        self.assertEqual(members.count(), 10)
        self.assertEqual(CoachAssignment.objects.count(), 10)
        self.assertEqual(Membership.objects.count(), 10)
        self.assertEqual(WorkoutPlan.objects.count(), 20)
        self.assertEqual(WorkoutSession.objects.count(), 60)
        self.assertEqual(WorkoutExerciseRecord.objects.count(), 540)
        self.assertEqual(WeightRecord.objects.count(), 70)
        self.assertEqual(WaterIntake.objects.count(), 70)
        self.assertEqual(Booking.objects.count(), 20)
        self.assertEqual(Session.objects.count(), 6)
        for member in members:
            self.assertTrue(member.check_password("DemoTest123!"))
            self.assertEqual(member.workout_plans.count(), 2)
            self.assertEqual(member.coach_links.filter(active=True).count(), 1)
        for session in Session.objects.all():
            self.assertLessEqual(session.confirmed_booking_count, session.capacity)

    def test_rerun_does_not_duplicate_or_overwrite(self):
        member = User.objects.get(email="rachel_green_m@fitsync.com")
        member.set_password("Changed123!")
        member.save()
        weight = member.weight_records.first()
        weight.weight_kg = 77
        weight.save()
        call_command("seed_demo_members", password="Different123!", stdout=StringIO())
        member.refresh_from_db()
        weight.refresh_from_db()
        self.assertTrue(member.check_password("Changed123!"))
        self.assertEqual(weight.weight_kg, 77)
        self.assertEqual(WorkoutSession.objects.count(), 60)
        self.assertEqual(WorkoutExerciseRecord.objects.count(), 540)
        self.assertEqual(Booking.objects.count(), 20)
        self.assertEqual(WeightRecord.objects.count(), 70)
        self.assertEqual(Session.objects.count(), 6)

    def test_member_dashboard_progress_and_bookings_render(self):
        member = User.objects.get(email="rachel_green_m@fitsync.com")
        self.client.force_login(member)
        for url in [reverse("accounts:member_dashboard"), reverse("workouts:progress"),
                    reverse("workouts:plans"), reverse("bookings:my_bookings")]:
            self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.get(reverse("workouts:progress"))
        self.assertEqual(response.context["workout_count"], 3)
        self.assertEqual(len(response.context["weight_chart"]), 3)
        self.assertIsNone(response.context["estimated_calories"])

    def test_coach_sees_only_their_members_and_classes(self):
        coach = User.objects.get(email="chris.bumstead@fitsync.com")
        self.client.force_login(coach)
        response = self.client.get(reverse("accounts:coach_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assignment_count"], 2)
        response = self.client.get(reverse("bookings:session_list"))
        self.assertEqual(len(response.context["sessions"]), 1)
        self.assertEqual(response.context["sessions"][0].instructor, coach)

    def test_legacy_rename_preserves_identity_password_and_records(self):
        member = User.objects.get(email="rachel_green_m@fitsync.com")
        original_pk = member.pk
        original_password = member.password
        member.email = "demo.member01@fitsync.local"
        member.username = "demo_member_01"
        member.first_name = "Aarav"
        member.last_name = "Sharma"
        member.save()
        call_command("rename_demo_members", stdout=StringIO())
        member.refresh_from_db()
        self.assertEqual(member.pk, original_pk)
        self.assertEqual(member.password, original_password)
        self.assertEqual(member.get_full_name(), "Rachel Green")
        self.assertEqual(member.username, "rachel_green_m")
        self.assertEqual(member.email, "rachel_green_m@fitsync.com")
        self.assertEqual(member.workout_sessions.count(), 6)
        self.assertEqual(Booking.objects.filter(member=member).count(), 2)
        self.assertEqual(User.objects.filter(role=User.Role.MEMBER).count(), 10)
        call_command("seed_demo_members", password="Another123!", stdout=StringIO())
        self.assertEqual(User.objects.filter(role=User.Role.MEMBER).count(), 10)
        self.assertEqual(WorkoutSession.objects.count(), 60)

    def test_existing_coach_domain_change_keeps_same_coach(self):
        coach = User.objects.get(email="chris.bumstead@fitsync.com")
        old_pk, old_password = coach.pk, coach.password
        assignments = list(coach.coach_assignments.values_list("pk", flat=True))
        coach.email = coach.username = "chris.bumstead@fitsync.local"
        coach.save()
        count = User.objects.count()
        call_command("rename_demo_members", stdout=StringIO())
        call_command("rename_demo_members", stdout=StringIO())
        coach.refresh_from_db()
        self.assertEqual(coach.pk, old_pk)
        self.assertEqual(coach.password, old_password)
        self.assertEqual(coach.email, "chris.bumstead@fitsync.com")
        self.assertEqual(list(coach.coach_assignments.values_list("pk", flat=True)), assignments)
        self.assertEqual(User.objects.count(), count)

    def test_friends_local_address_is_renamed_without_new_member(self):
        member = User.objects.get(email="rachel_green_m@fitsync.com")
        original_pk = member.pk
        member.email = "rachel_green_m@fitsync.local"
        member.save()
        call_command("rename_demo_members", stdout=StringIO())
        member.refresh_from_db()
        self.assertEqual(member.pk, original_pk)
        self.assertEqual(member.email, "rachel_green_m@fitsync.com")
        self.assertEqual(User.objects.filter(role=User.Role.MEMBER).count(), 10)
