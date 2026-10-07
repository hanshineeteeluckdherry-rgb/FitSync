from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CoachAssignment, User

from .models import (
    Exercise,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)


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

    def create_plan(self, member=None, plan_type="PERSONAL", coach=None):
        plan = WorkoutPlan.objects.create(
            member=member or self.member,
            coach=coach,
            name="Strength Plan",
            goal="Build Strength",
            workout_days="Mon,Wed",
            plan_type=plan_type,
        )
        WorkoutPlanExercise.objects.create(
            workout_plan=plan,
            exercise=self.exercise,
            sets=3,
            reps=10,
            order=1,
        )
        return plan

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

    def test_member_can_edit_personal_plan(self):
        plan = self.create_plan()
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("workouts:plan_edit", args=[plan.id]),
            {
                "name": "Updated Strength Plan",
                "goal": "Endurance",
                "description": "Three workouts each week",
                "workout_days": ["Tue", "Thu", "Sat"],
            },
        )

        self.assertRedirects(
            response,
            reverse("workouts:plan_detail", args=[plan.id]),
        )
        plan.refresh_from_db()
        self.assertEqual(plan.name, "Updated Strength Plan")
        self.assertEqual(plan.workout_days, "Tue,Thu,Sat")

    def test_member_can_delete_personal_plan(self):
        plan = self.create_plan()
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("workouts:plan_delete", args=[plan.id])
        )

        self.assertRedirects(response, reverse("workouts:plans"))
        self.assertFalse(WorkoutPlan.objects.filter(id=plan.id).exists())

    def test_member_cannot_edit_coach_assigned_plan(self):
        CoachAssignment.objects.create(
            coach=self.coach,
            member=self.member,
            active=True,
        )
        plan = self.create_plan(
            plan_type="COACH_ASSIGNED",
            coach=self.coach,
        )
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("workouts:plan_edit", args=[plan.id]),
            {
                "name": "Member Changed Plan",
                "goal": "Fat Loss",
                "description": "",
                "workout_days": ["Fri"],
            },
        )

        self.assertRedirects(
            response,
            reverse("workouts:plan_detail", args=[plan.id]),
        )
        plan.refresh_from_db()
        self.assertEqual(plan.name, "Strength Plan")

    def test_member_can_complete_workout(self):
        plan = self.create_plan()
        entry = plan.plan_exercises.first()
        self.client.force_login(self.member)

        start_response = self.client.get(
            reverse("workouts:start_workout", args=[plan.id])
        )
        session = WorkoutSession.objects.get(member=self.member)

        self.assertRedirects(
            start_response,
            reverse("workouts:active_workout", args=[session.id]),
        )

        finish_response = self.client.post(
            reverse("workouts:finish_workout", args=[session.id]),
            {
                f"sets_{entry.id}": "4",
                f"reps_{entry.id}": "8",
                f"weight_{entry.id}": "45.5",
                f"duration_{entry.id}": "12",
                "session_duration": "35",
                "notes": "Good session",
            },
        )

        self.assertRedirects(
            finish_response,
            reverse("workouts:history_detail", args=[session.id]),
        )
        session.refresh_from_db()
        self.assertIsNotNone(session.completed_at)
        self.assertEqual(session.duration_minutes, 35)
        self.assertEqual(session.notes, "Good session")

        record = WorkoutExerciseRecord.objects.get(workout_session=session)
        self.assertEqual(record.sets, 4)
        self.assertEqual(record.reps, 8)
        self.assertEqual(str(record.weight_kg), "45.50")

    def test_workout_history_only_shows_completed_sessions(self):
        plan = self.create_plan()
        completed_session = WorkoutSession.objects.create(
            member=self.member,
            workout_plan=plan,
            completed_at=timezone.now(),
            duration_minutes=30,
        )
        WorkoutSession.objects.create(
            member=self.member,
            workout_plan=plan,
        )
        self.client.force_login(self.member)

        response = self.client.get(reverse("workouts:history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, completed_session.workout_plan.name)
        self.assertEqual(len(response.context["sessions"]), 1)

    def test_member_can_edit_and_delete_weight_record(self):
        record = WeightRecord.objects.create(
            member=self.member,
            weight_kg="72.00",
            recorded_date=date.today(),
            note="First record",
        )
        self.client.force_login(self.member)

        edit_response = self.client.post(
            reverse("workouts:weight_edit", args=[record.id]),
            {
                "weight_kg": "71.40",
                "recorded_date": date.today().isoformat(),
                "note": "Updated record",
            },
        )

        self.assertRedirects(edit_response, reverse("workouts:progress"))
        record.refresh_from_db()
        self.assertEqual(str(record.weight_kg), "71.40")

        delete_response = self.client.post(
            reverse("workouts:weight_delete", args=[record.id])
        )

        self.assertRedirects(delete_response, reverse("workouts:progress"))
        self.assertFalse(WeightRecord.objects.filter(id=record.id).exists())

    def test_coach_cannot_open_unassigned_member_progress(self):
        self.client.force_login(self.coach)

        response = self.client.get(
            reverse("workouts:coach_member_progress", args=[self.member.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_member_dashboard_shows_workout_summary(self):
        self.create_plan()
        WeightRecord.objects.create(
            member=self.member,
            weight_kg="70.50",
            recorded_date=date.today(),
        )
        self.client.force_login(self.member)

        response = self.client.get(reverse("accounts:member_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["personal_plan_count"], 1)
        self.assertEqual(response.context["coach_plan_count"], 0)
        self.assertEqual(str(response.context["latest_weight"].weight_kg), "70.50")

    def test_coach_dashboard_shows_workout_summary(self):
        CoachAssignment.objects.create(
            coach=self.coach,
            member=self.member,
            active=True,
        )
        self.create_plan(
            plan_type="COACH_ASSIGNED",
            coach=self.coach,
        )
        self.client.force_login(self.coach)

        response = self.client.get(reverse("accounts:coach_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assignment_count"], 1)
        self.assertEqual(response.context["coach_plan_count"], 1)
