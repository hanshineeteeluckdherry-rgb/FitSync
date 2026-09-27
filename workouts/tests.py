from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import CoachAssignment, User

from .models import Exercise, WeightRecord, WorkoutPlan


class WorkoutFeatureTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            username="member_test",
            email="member_test@fitsync.com",
            password="Testpass123!",
            role="MEMBER",
        )

        self.other_member = User.objects.create_user(
            username="other_member",
            email="other_member@fitsync.com",
            password="Testpass123!",
            role="MEMBER",
        )

        self.coach = User.objects.create_user(
            username="coach_test",
            email="coach_test@fitsync.com",
            password="Testpass123!",
            role="COACH",
        )

        self.staff = User.objects.create_user(
            username="staff_test",
            email="staff_test@fitsync.com",
            password="Testpass123!",
            role="STAFF",
        )

        self.exercise = Exercise.objects.create(
            name="Test Squat",
            category="LEGS",
            equipment="BARBELL",
            difficulty="BEGINNER",
            intensity="MODERATE",
            is_active=True,
        )

    def test_member_can_open_workout_plans(self):
        self.client.force_login(self.member)

        response = self.client.get(
            reverse("workouts:plans")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_member_can_create_personal_plan(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("workouts:plan_create"),
            {
                "name": "My Strength Plan",
                "goal": "Build Strength",
                "description": "Simple personal plan",
                "workout_days": ["Mon", "Wed"],
                "exercise_ids": [self.exercise.id],
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        plan = WorkoutPlan.objects.get(
            name="My Strength Plan"
        )

        self.assertEqual(
            plan.member,
            self.member,
        )

        self.assertEqual(
            plan.plan_type,
            "PERSONAL",
        )

        self.assertEqual(
            plan.plan_exercises.count(),
            1,
        )

        self.assertEqual(
            plan.plan_exercises.first().exercise,
            self.exercise,
        )

    def test_member_cannot_view_another_members_plan(self):
        plan = WorkoutPlan.objects.create(
            member=self.other_member,
            name="Private Plan",
            plan_type="PERSONAL",
        )

        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "workouts:plan_detail",
                args=[plan.id],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_coach_can_open_assigned_members(self):
        CoachAssignment.objects.create(
            coach=self.coach,
            member=self.member,
            active=True,
        )

        self.client.force_login(self.coach)

        response = self.client.get(
            reverse("workouts:coach_members")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.member.username,
        )

    def test_staff_can_manage_exercises(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("workouts:exercise_manage")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.exercise.name,
        )

    def test_member_can_add_weight_record(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("workouts:weight_add"),
            {
                "weight_kg": "70.50",
                "recorded_date": date.today().isoformat(),
                "note": "Weekly check",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertTrue(
            WeightRecord.objects.filter(
                member=self.member
            ).exists()
        )