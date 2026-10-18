from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CoachAssignment, MemberProfile, User
from workouts.models import Exercise, WeightRecord, WorkoutPlan, WorkoutPlanExercise, WorkoutSession


class CoachWorkspaceTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(username="workspacecoach", email="workspacecoach@test.com", role="COACH")
        self.member = User.objects.create_user(username="workspace_member", email="workspace_member@test.com", role="MEMBER")
        self.other = User.objects.create_user(username="private_member", email="private_member@test.com", role="MEMBER")
        self.assignment = CoachAssignment.objects.create(coach=self.coach, member=self.member)
        MemberProfile.objects.create(user=self.member, target_weight_kg=70, fitness_goal="Build Strength")
        self.plan = WorkoutPlan.objects.create(member=self.member, coach=self.coach, name="Assigned Strength", plan_type="COACH_ASSIGNED")
        self.hidden = WorkoutPlan.objects.create(member=self.other, coach=self.coach, name="Private Plan", plan_type="COACH_ASSIGNED")
        WorkoutPlan.objects.create(member=self.member, name="Private Personal Plan", plan_type="PERSONAL")
        exercise = Exercise.objects.create(name="Sample Squat", category="LEGS")
        WorkoutPlanExercise.objects.create(workout_plan=self.plan, exercise=exercise)
        WeightRecord.objects.create(member=self.member, weight_kg=75, recorded_date=timezone.localdate())
        WeightRecord.objects.create(member=self.other, weight_kg=99, recorded_date=timezone.localdate())
        self.session = WorkoutSession.objects.create(member=self.member, workout_plan=self.plan, completed_at=timezone.now())
        WorkoutSession.objects.create(member=self.member, completed_at=timezone.now() - timedelta(days=10))
        self.client.force_login(self.coach)

    def test_sidebar_has_distinct_destinations_and_templates(self):
        for name, template, active in [("coach_members", "coach_members.html", "members"),
                ("coach_plans", "coach_plans.html", "plans"), ("coach_progress", "coach_progress.html", "progress")]:
            response = self.client.get(reverse(f"workouts:{name}"))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, f"workouts/{template}")
            self.assertEqual(response.context["active_sidebar"], active)
            for destination in ["coach_members", "coach_plans", "coach_progress"]:
                self.assertContains(response, f'href="{reverse(f"workouts:{destination}")}"')

    def test_plans_show_only_own_assigned_plans(self):
        response = self.client.get(reverse("workouts:coach_plans"))
        self.assertEqual(list(response.context["plans"]), [self.plan])
        self.assertEqual(response.context["plans"][0].exercise_count, 1)
        self.assertNotContains(response, "Private Plan")
        self.assertNotContains(response, "Private Personal Plan")
        self.assertContains(response, reverse("workouts:plan_detail", args=[self.plan.pk]))
        self.assertEqual(self.client.get(reverse("workouts:coach_plans"), {"member": self.other.pk}).status_code, 404)
        self.assertEqual(self.client.get(reverse("workouts:coach_plans"), {"member": "invalid"}).status_code, 404)

    def test_progress_uses_assigned_members_real_records(self):
        response = self.client.get(reverse("workouts:coach_progress"))
        members = list(response.context["members"])
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].latest_weight, Decimal("75"))
        self.assertEqual(members[0].completed_count, 2)
        self.assertEqual(members[0].weekly_count, 1)
        self.assertNotContains(response, "private_member")
        self.assertContains(response, reverse("workouts:coach_member_progress", args=[self.member.pk]))
        response = self.client.get(reverse("workouts:history_detail", args=[self.session.pk]))
        self.assertEqual(response.context["active_sidebar"], "progress")
        self.assertContains(response, reverse("workouts:coach_member_progress", args=[self.member.pk]))

    def test_revoked_assignment_hides_plans_and_progress(self):
        self.assignment.active = False
        self.assignment.save()
        self.assertEqual(len(self.client.get(reverse("workouts:coach_plans")).context["plans"]), 0)
        self.assertEqual(len(self.client.get(reverse("workouts:coach_progress")).context["members"]), 0)
        self.assertEqual(self.client.get(reverse("workouts:coach_member_progress", args=[self.member.pk])).status_code, 403)

    def test_non_coaches_cannot_open_overviews(self):
        self.client.force_login(self.member)
        for name in ["coach_members", "coach_plans", "coach_progress"]:
            self.assertEqual(self.client.get(reverse(f"workouts:{name}")).status_code, 403)

    def test_multiple_members_and_multiple_plans_have_correct_actions(self):
        self.member.first_name = "Zoe"
        self.member.save()
        second = User.objects.create_user(username="another_member", email="another@test.com", first_name="Amy", role="MEMBER")
        CoachAssignment.objects.create(coach=self.coach, member=second)
        other_plan = WorkoutPlan.objects.create(member=second, coach=self.coach, name="Amy Upper", plan_type="COACH_ASSIGNED")
        WorkoutPlan.objects.create(member=second, coach=self.coach, name="Amy Lower", plan_type="COACH_ASSIGNED")
        response = self.client.get(reverse("workouts:coach_plans"))
        self.assertEqual(response.context["plan_count"], 3)
        self.assertEqual([plan.member_id for plan in response.context["plans"]], [second.pk, second.pk, self.member.pk])
        self.assertContains(response, "Choose a member")
        for member in [self.member, second]:
            self.assertContains(response, reverse("workouts:coach_plan_create", args=[member.pk]))
        for plan in response.context["plans"]:
            for action in ["plan_detail", "plan_edit", "plan_add_exercises"]:
                self.assertContains(response, reverse(f"workouts:{action}", args=[plan.pk]))
        html = response.content.decode()
        self.assertLess(html.index('<th scope="col">Member'), html.index('<th scope="col">Plan'))
        response = self.client.get(reverse("workouts:coach_plans"), {"member": second.pk})
        self.assertEqual(response.context["plan_count"], 2)
        self.assertNotContains(response, self.plan.name)
        self.assertContains(response, other_plan.name)

    def test_large_plan_list_paginates_and_keeps_member_filter(self):
        for index in range(17):
            WorkoutPlan.objects.create(member=self.member, coach=self.coach, name=f"Training {index}", plan_type="COACH_ASSIGNED")
        response = self.client.get(reverse("workouts:coach_plans"), {"member": self.member.pk})
        self.assertEqual(response.context["plan_count"], 18)
        self.assertEqual(len(response.context["plans"]), 15)
        self.assertContains(response, f'?page=2&amp;member={self.member.pk}')
        response = self.client.get(reverse("workouts:coach_plans"), {"member": self.member.pk, "page": 2})
        self.assertEqual(len(response.context["plans"]), 3)
        self.assertTrue(all(plan.member_id == self.member.pk for plan in response.context["plans"]))
