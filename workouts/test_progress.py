from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import MemberProfile, User
from .models import Exercise, WeightRecord, WorkoutExerciseRecord, WorkoutPlan, WorkoutSession


class ProgressOverviewTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="progress_member", email="progress_member@example.com", role="MEMBER")
        self.other_member = User.objects.create_user(username="progress_other", email="progress_other@example.com", role="MEMBER")
        MemberProfile.objects.create(user=self.member, current_weight_kg=80, target_weight_kg=70)
        self.today = timezone.localdate()
        self.url = reverse("workouts:progress")
        self.client.force_login(self.member)

    def test_period_filters_and_weight_goal_use_real_records(self):
        WeightRecord.objects.create(member=self.member, recorded_date=self.today - timedelta(days=40), weight_kg=80)
        WeightRecord.objects.create(member=self.member, recorded_date=self.today - timedelta(days=10), weight_kg=78)
        WeightRecord.objects.create(member=self.member, recorded_date=self.today, weight_kg=75)
        for period, expected in [("weekly", 1), ("monthly", 2), ("all", 3)]:
            response = self.client.get(self.url, {"period": period})
            self.assertEqual(len(response.context["weight_chart"]), expected)
            self.assertEqual(response.context["goal_percent"], 50)
            self.assertEqual(response.context["remaining_weight"], Decimal("5"))
        response = self.client.get(self.url, {"period": "monthly"})
        self.assertEqual(response.context["weight_change"], Decimal("-3"))

    def test_empty_overview_does_not_invent_calories_or_duration(self):
        plan = WorkoutPlan.objects.create(member=self.member, name="Strength", goal="Build Strength")
        WorkoutSession.objects.create(member=self.member, workout_plan=plan, completed_at=timezone.now())
        response = self.client.get(self.url)
        self.assertEqual(response.context["workout_count"], 1)
        self.assertIsNone(response.context["average_minutes"])
        self.assertIsNone(response.context["estimated_calories"])
        self.assertEqual(response.context["breakdown"][0]["count"], 1)
        self.assertNotContains(response, "Consumed: not tracked")

    def test_workout_statistics_and_personal_records_are_private(self):
        exercise = Exercise.objects.create(name="Progress Squat", category="LEGS")
        session = WorkoutSession.objects.create(member=self.member, completed_at=timezone.now(), duration_minutes=30)
        WorkoutExerciseRecord.objects.create(workout_session=session, exercise=exercise, weight_kg=40)
        WorkoutExerciseRecord.objects.create(workout_session=session, exercise=exercise, weight_kg=50)
        other_session = WorkoutSession.objects.create(member=self.other_member, completed_at=timezone.now(), duration_minutes=100)
        WorkoutExerciseRecord.objects.create(workout_session=other_session, exercise=exercise, weight_kg=100)
        WeightRecord.objects.create(member=self.other_member, recorded_date=self.today, weight_kg=99)
        response = self.client.get(self.url)
        self.assertEqual(response.context["workout_count"], 1)
        self.assertEqual(response.context["estimated_calories"], 210)
        self.assertEqual(response.context["average_minutes"], 30)
        self.assertEqual(sum(day["value"] for day in response.context["calorie_chart"]), 210)
        self.assertEqual(len(response.context["personal_records"]), 1)
        self.assertEqual(response.context["personal_records"][0].weight_kg, Decimal("50"))
        self.assertEqual(response.context["weight_chart"], [])

    def test_invalid_period_uses_weekly_and_weight_gain_goal_works(self):
        profile = self.member.member_profile
        profile.target_weight_kg = 90
        profile.save()
        WeightRecord.objects.create(member=self.member, recorded_date=self.today - timedelta(days=2), weight_kg=80)
        WeightRecord.objects.create(member=self.member, recorded_date=self.today, weight_kg=85)
        response = self.client.get(self.url, {"period": "invalid"})
        self.assertEqual(response.context["period"], "weekly")
        self.assertEqual(response.context["goal_percent"], 50)
