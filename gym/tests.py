from datetime import date, time, timedelta
from decimal import Decimal
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import URLResolver, get_resolver, reverse
from django.utils import timezone
from gym.models import (
    AttendanceRecord,
    Booking,
    CoachAssignment,
    CoachProfile,
    ContactMessage,
    Exercise,
    GymConfiguration,
    GymSettings,
    MemberProfile,
    MemberQRCode,
    Membership,
    MembershipPackage,
    Notice,
    Notification,
    OutdoorActivity,
    Payment,
    Service,
    Session,
    TeamMember,
    User,
    WaterIntake,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)
from io import StringIO
from pathlib import Path
from smtplib import SMTPException
from unittest.mock import patch
import ast
import importlib
import hashlib
import json
import re
from types import SimpleNamespace
from django.db import connection

# Accounts and profiles — Rheva

# 2.3 Fitness information and goals


class DemoMemberSeedTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("seed_team", password="DemoTest123!", stdout=StringIO())
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

    def test_demo_members_use_paid_catalogue_package_without_extra_coaches(self):
        before = User.objects.filter(role=User.Role.COACH).count()
        call_command("seed_demo_members", password="Different123!", stdout=StringIO())
        self.assertEqual(User.objects.filter(role=User.Role.COACH).count(), before)
        self.assertFalse(
            MembershipPackage.objects.filter(slug="demo-all-access").exists()
        )
        self.assertEqual(
            set(Membership.objects.values_list("package__slug", flat=True)), {"premium"}
        )

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
        for url in [
            reverse("accounts:member_dashboard"),
            reverse("workouts:progress"),
            reverse("workouts:plans"),
            reverse("bookings:my_bookings"),
        ]:
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
        call_command("seed_team", password="NewTest123!", stdout=StringIO())
        call_command("seed_demo_members", password="NewTest123!", stdout=StringIO())
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
        old_pk, old_password = (coach.pk, coach.password)
        assignments = list(coach.coach_assignments.values_list("pk", flat=True))
        coach.email = coach.username = "chris.bumstead@fitsync.local"
        coach.save()
        count = User.objects.count()
        call_command("seed_team", password="NewTest123!", stdout=StringIO())
        call_command("seed_demo_members", password="NewTest123!", stdout=StringIO())
        call_command("seed_team", password="NewTest123!", stdout=StringIO())
        call_command("seed_demo_members", password="NewTest123!", stdout=StringIO())
        coach.refresh_from_db()
        self.assertEqual(coach.pk, old_pk)
        self.assertEqual(coach.password, old_password)
        self.assertEqual(coach.email, "chris.bumstead@fitsync.com")
        self.assertEqual(
            list(coach.coach_assignments.values_list("pk", flat=True)), assignments
        )
        self.assertEqual(User.objects.count(), count)

    def test_friends_local_address_is_renamed_without_new_member(self):
        member = User.objects.get(email="rachel_green_m@fitsync.com")
        original_pk = member.pk
        member.email = "rachel_green_m@fitsync.local"
        member.save()
        call_command("seed_team", password="NewTest123!", stdout=StringIO())
        call_command("seed_demo_members", password="NewTest123!", stdout=StringIO())
        member.refresh_from_db()
        self.assertEqual(member.pk, original_pk)
        self.assertEqual(member.email, "rachel_green_m@fitsync.com")
        self.assertEqual(User.objects.filter(role=User.Role.MEMBER).count(), 10)


# Accounts and profiles — Rheva

# 2.3 Fitness information and goals


class TeamSeedTests(TestCase):

    def test_creates_team_accounts_and_coach_profiles(self):
        call_command("seed_team", password="LocalTest123!", stdout=StringIO())
        self.assertEqual(User.objects.count(), 8)
        self.assertEqual(CoachProfile.objects.count(), 6)
        self.assertEqual(
            User.objects.get(email="dwayne.johnson@fitsync.com").role, User.Role.ADMIN
        )
        self.assertEqual(
            User.objects.get(email="julie.bowen@fitsync.com").role, User.Role.STAFF
        )
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
        self.assertEqual(
            User.objects.get(email="julie.bowen@fitsync.com").role, User.Role.STAFF
        )
        for user in User.objects.all():
            self.assertTrue(user.check_password("LocalTest123!"))

    def test_catalogue_only_does_not_create_users_or_sessions(self):
        from gym.models import Service, Session

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


# Accounts and profiles — Rheva

# 2.3 Fitness information and goals


class AccountTestMixin:
    password = "TestPass123!"

    def make_user(self, email, role=User.Role.MEMBER, **extra):
        return User.objects.create_user(
            username=email,
            email=email,
            password=self.password,
            role=role,
            first_name=extra.pop("first_name", role.title()),
            last_name=extra.pop("last_name", "User"),
            **extra,
        )


class RegistrationLoginTests(AccountTestMixin, TestCase):

    def test_registration_creates_member_and_profile(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Asha",
                "last_name": "Patel",
                "email": "asha@example.com",
                "password1": self.password,
                "password2": self.password,
                "age": "24",
                "height_cm": "168",
                "current_weight_kg": "64.5",
                "fitness_goal": "Improve Endurance",
            },
        )
        self.assertRedirects(response, reverse("accounts:member_dashboard"))
        user = User.objects.get(email="asha@example.com")
        self.assertEqual(user.role, User.Role.MEMBER)
        profile = MemberProfile.objects.get(user=user)
        self.assertEqual(profile.age, 24)
        self.assertEqual(profile.height_cm, 168)
        self.assertEqual(str(profile.current_weight_kg), "64.50")
        self.assertEqual(profile.fitness_goal, "Improve Endurance")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_registration_rejects_duplicate_email(self):
        self.make_user("same@example.com")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Another",
                "last_name": "Person",
                "email": "SAME@example.com",
                "password1": self.password,
                "password2": self.password,
                "age": "30",
                "height_cm": "175",
                "current_weight_kg": "72",
                "fitness_goal": "General Wellness",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(
            User.objects.filter(email__iexact="same@example.com").count(), 1
        )

    def test_member_login_redirects_to_member_dashboard(self):
        user = self.make_user("member@example.com")
        MemberProfile.objects.create(user=user)
        response = self.client.post(
            reverse("accounts:login"),
            {"email": user.email, "password": self.password},
            follow=True,
        )
        self.assertRedirects(response, reverse("accounts:member_dashboard"))
        self.assertContains(response, "Member Dashboard")

    def test_invalid_login_shows_error(self):
        self.make_user("member@example.com")
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "member@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password")

    def test_inactive_user_cannot_login(self):
        self.make_user("inactive@example.com", is_active=False)
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "inactive@example.com", "password": self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account is inactive")

    def test_login_page_uses_figma_auth_layout(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back")
        self.assertContains(response, "login-hero.jpeg")
        self.assertContains(response, "member-dashboard/lionel.png")
        self.assertContains(response, "fitsync-logo.png")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "Demo Accounts")
        self.assertContains(response, "admin@fitsync.com")
        self.assertNotContains(response, "fitsync-navbar")

    def test_registration_page_uses_two_step_figma_layout(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Your Account")
        self.assertContains(response, "Account Info")
        self.assertContains(response, "Fitness Profile")
        self.assertContains(response, "register-hero.jpeg")
        self.assertContains(response, "fitsync-logo.png")
        self.assertContains(response, "data-theme-toggle")

    def test_login_without_remember_me_expires_at_browser_close(self):
        user = self.make_user("browser@example.com")
        MemberProfile.objects.create(user=user)
        self.client.post(
            reverse("accounts:login"), {"email": user.email, "password": self.password}
        )
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_login_with_remember_me_keeps_normal_session(self):
        user = self.make_user("remember@example.com")
        MemberProfile.objects.create(user=user)
        self.client.post(
            reverse("accounts:login"),
            {"email": user.email, "password": self.password, "remember_me": "on"},
        )
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_logout_requires_post_and_logs_user_out(self):
        user = self.make_user("member@example.com")
        self.client.force_login(user)
        get_response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(get_response.status_code, 302)
        self.assertEqual(get_response.url, reverse("accounts:dashboard"))
        self.assertIn("_auth_user_id", self.client.session)
        post_response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(post_response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_member_dashboard_uses_figma_sidebar_navigation(self):
        user = self.make_user("sidebar@example.com")
        MemberProfile.objects.create(user=user)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:member_dashboard"))
        self.assertContains(response, "member-dashboard-sidebar")
        self.assertContains(response, "Classes &amp; Services")
        self.assertContains(response, "Our Team")
        self.assertContains(response, "My Membership")
        self.assertContains(response, "dashboard-topbar-actions")
        self.assertContains(response, user.get_full_name())
        self.assertContains(response, reverse("accounts:profile"))

    def test_member_dashboard_shows_live_overview_data(self):
        user = self.make_user("overview@example.com", first_name="Asha")
        MemberProfile.objects.create(
            user=user, current_weight_kg=Decimal("64.5"), fitness_goal="Build Strength"
        )
        GymConfiguration.objects.create(pk=1, max_capacity=20)
        AttendanceRecord.objects.create(member=user)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:member_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back, Asha")
        self.assertContains(response, "Build Strength")
        self.assertContains(response, "64.5")
        self.assertContains(response, "1 <small>/ 20 members</small>", html=True)
        self.assertContains(response, "Start Workout")
        self.assertContains(response, "Book Class")
        self.assertContains(response, "View Progress")


class RolePermissionTests(AccountTestMixin, TestCase):

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("accounts:member_dashboard"))
        expected = (
            f"{reverse('accounts:login')}?next={reverse('accounts:member_dashboard')}"
        )
        self.assertRedirects(response, expected)

    def test_dashboard_redirect_matches_each_role(self):
        cases = [
            (User.Role.MEMBER, "accounts:member_dashboard"),
            (User.Role.STAFF, "accounts:staff_dashboard"),
            (User.Role.COACH, "accounts:coach_dashboard"),
            (User.Role.ADMIN, "accounts:admin_dashboard"),
        ]
        for index, (role, target_name) in enumerate(cases):
            with self.subTest(role=role):
                self.client.logout()
                user = self.make_user(f"role{index}@example.com", role=role)
                if role == User.Role.MEMBER:
                    MemberProfile.objects.create(user=user)
                self.client.force_login(user)
                response = self.client.get(reverse("accounts:dashboard"))
                self.assertRedirects(response, reverse(target_name))

    def test_member_cannot_open_admin_dashboard(self):
        member = self.make_user("member@example.com")
        self.client.force_login(member)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access denied", status_code=403)

    def test_staff_cannot_manage_admin_users(self):
        staff = self.make_user("staff@example.com", role=User.Role.STAFF)
        self.client.force_login(staff)
        response = self.client.get(reverse("accounts:admin_user_list"))
        self.assertEqual(response.status_code, 403)

    def test_member_cannot_open_staff_member_list(self):
        member = self.make_user("member@example.com")
        self.client.force_login(member)
        response = self.client.get(reverse("accounts:staff_member_list"))
        self.assertEqual(response.status_code, 403)


class ProfilePasswordTests(AccountTestMixin, TestCase):

    def setUp(self):
        self.user = self.make_user("member@example.com", first_name="Mina")
        self.profile = MemberProfile.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_member_can_update_profile_and_fitness_details(self):
        response = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "first_name": "Mina",
                "last_name": "Joseph",
                "email": "mina.new@example.com",
                "phone": "555-0100",
                "date_of_birth": "2002-06-12",
                "emergency_contact": "Family 555-0199",
                "age": "24",
                "height_cm": "168",
                "current_weight_kg": "64.5",
                "target_weight_kg": "60.0",
                "fitness_goal": "Improve endurance",
                "medical_notes": "",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.email, "mina.new@example.com")
        self.assertEqual(self.user.username, "mina.new@example.com")
        self.assertEqual(self.profile.fitness_goal, "Improve endurance")

    def test_password_change_keeps_user_logged_in(self):
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": self.password,
                "new_password1": "NewSecurePass456!",
                "new_password2": "NewSecurePass456!",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass456!"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_password_reset_sends_email_for_active_user(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": self.user.email}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("FitSync password reset", mail.outbox[0].subject)
        self.assertIn("password/reset/", mail.outbox[0].body)


class AdminUserManagementTests(AccountTestMixin, TestCase):

    def setUp(self):
        self.admin = self.make_user("admin@example.com", role=User.Role.ADMIN)
        self.member = self.make_user("member@example.com")
        MemberProfile.objects.create(user=self.member)
        self.client.force_login(self.admin)

    def test_admin_user_list_and_search(self):
        response = self.client.get(reverse("accounts:admin_user_list"), {"q": "member"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "member@example.com")
        self.assertNotContains(response, "admin@example.com")

    def test_admin_user_list_filters_active_accounts(self):
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])
        response = self.client.get(
            reverse("accounts:admin_user_list"), {"status": "active"}
        )
        self.assertContains(response, "admin@example.com")
        self.assertNotContains(response, "member@example.com")

    def test_admin_can_create_member_account(self):
        response = self.client.post(
            reverse("accounts:admin_user_create"),
            {
                "first_name": "New",
                "last_name": "Member",
                "email": "new.member@example.com",
                "role": User.Role.MEMBER,
                "password1": self.password,
                "password2": self.password,
                "is_active": "on",
            },
        )
        user = User.objects.get(email="new.member@example.com")
        self.assertRedirects(
            response, reverse("accounts:admin_user_detail", args=[user.id])
        )
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())

    def test_admin_can_create_coach_account(self):
        self.client.post(
            reverse("accounts:admin_user_create"),
            {
                "first_name": "New",
                "last_name": "Coach",
                "email": "new.coach@example.com",
                "role": User.Role.COACH,
                "password1": self.password,
                "password2": self.password,
                "is_active": "on",
            },
        )
        coach = User.objects.get(email="new.coach@example.com")
        self.assertTrue(CoachProfile.objects.filter(user=coach).exists())

    def test_admin_user_creation_rejects_duplicate_email(self):
        response = self.client.post(
            reverse("accounts:admin_user_create"),
            {
                "first_name": "Duplicate",
                "last_name": "Member",
                "email": self.member.email,
                "role": User.Role.MEMBER,
                "password1": self.password,
                "password2": self.password,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
        self.assertEqual(User.objects.filter(email=self.member.email).count(), 1)

    def test_member_cannot_open_admin_user_creation(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("accounts:admin_user_create"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_change_user_role(self):
        response = self.client.post(
            reverse("accounts:admin_user_role", args=[self.member.id]),
            {"role": User.Role.STAFF},
        )
        self.assertRedirects(
            response, reverse("accounts:admin_user_detail", args=[self.member.id])
        )
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, User.Role.STAFF)

    def test_admin_can_deactivate_other_user(self):
        response = self.client.post(
            reverse("accounts:admin_user_status", args=[self.member.id])
        )
        self.assertRedirects(
            response, reverse("accounts:admin_user_detail", args=[self.member.id])
        )
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_admin_cannot_deactivate_self(self):
        self.client.post(reverse("accounts:admin_user_status", args=[self.admin.id]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_dashboard_shows_role_counts(self):
        self.make_user("coach@example.com", role=User.Role.COACH)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["member_count"], 1)
        self.assertEqual(response.context["coach_count"], 1)
        self.assertEqual(response.context["admin_count"], 1)


class AdminDashboardTests(AccountTestMixin, TestCase):

    def setUp(self):
        self.admin = self.make_user("admin.dashboard@example.com", role=User.Role.ADMIN)
        self.member = self.make_user("dashboard.member@example.com")
        self.package = MembershipPackage.objects.create(
            name="Monthly Fitness",
            slug="monthly-fitness-dashboard",
            price=Decimal("850.00"),
            duration_months=1,
            features="Gym access",
        )
        self.membership = Membership.objects.create(
            member=self.member,
            package=self.package,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            status=Membership.Status.ACTIVE,
        )
        Payment.objects.create(
            member=self.member,
            package=self.package,
            membership=self.membership,
            amount=Decimal("850.00"),
            payment_method=Payment.Method.CARD,
            status=Payment.Status.SUCCESS,
        )
        self.service = Service.objects.create(
            name="Morning Yoga", service_type=Service.Type.YOGA
        )
        self.session = Session.objects.create(
            service=self.service,
            date=date.today() + timedelta(days=1),
            start_time="09:00",
            end_time="10:00",
            capacity=12,
            status=Session.Status.SCHEDULED,
        )
        Booking.objects.create(
            member=self.member, session=self.session, status=Booking.Status.CONFIRMED
        )
        AttendanceRecord.objects.create(member=self.member)

    def test_admin_dashboard_uses_current_gym_data(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_membership_count"], 1)
        self.assertEqual(response.context["today_attendance_count"], 1)
        self.assertEqual(response.context["current_occupancy"], 1)
        self.assertEqual(response.context["upcoming_session_count"], 1)
        self.assertEqual(response.context["confirmed_booking_count"], 1)
        self.assertEqual(response.context["successful_payment_count"], 1)
        self.assertEqual(response.context["total_revenue"], Decimal("850.00"))
        self.assertGreaterEqual(len(response.context["recent_activity"]), 4)

    def test_admin_dashboard_contains_report_links(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertContains(response, reverse("memberships:admin_membership_report"))
        self.assertContains(response, reverse("attendance:attendance_report"))
        self.assertContains(response, reverse("bookings:booking_report"))

    def test_admin_dashboard_stat_cards_link_to_management_pages(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        expected_urls = [
            reverse("accounts:admin_user_list"),
            reverse("memberships:admin_membership_list"),
            reverse("attendance:attendance_history"),
            reverse("attendance:capacity_settings"),
            reverse("bookings:session_list"),
            reverse("bookings:booking_report"),
            reverse("memberships:admin_payment_list"),
            reverse("memberships:admin_membership_report"),
        ]
        for url in expected_urls:
            self.assertContains(response, f'href="{url}')

    def test_member_cannot_view_admin_dashboard(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertEqual(response.status_code, 403)


class CoachAssignmentTests(AccountTestMixin, TestCase):

    def setUp(self):
        self.admin = self.make_user("admin@example.com", role=User.Role.ADMIN)
        self.coach = self.make_user("coach@example.com", role=User.Role.COACH)
        self.member1 = self.make_user("member1@example.com")
        self.member2 = self.make_user("member2@example.com")
        MemberProfile.objects.create(user=self.member1)
        MemberProfile.objects.create(user=self.member2)

    def test_admin_can_create_coach_assignment(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:coach_assignment_create"),
            {"coach": self.coach.id, "member": self.member1.id, "active": "on"},
        )
        self.assertRedirects(response, reverse("accounts:coach_assignment_list"))
        self.assertTrue(
            CoachAssignment.objects.filter(
                coach=self.coach, member=self.member1
            ).exists()
        )

    def test_non_admin_cannot_create_assignment(self):
        self.client.force_login(self.coach)
        response = self.client.get(reverse("accounts:coach_assignment_create"))
        self.assertEqual(response.status_code, 403)

    def test_coach_dashboard_only_lists_assigned_members(self):
        CoachAssignment.objects.create(coach=self.coach, member=self.member1)
        self.client.force_login(self.coach)
        response = self.client.get(reverse("accounts:coach_dashboard"))
        self.assertContains(response, "member1@example.com")
        self.assertNotContains(response, "member2@example.com")


class StaffMemberTests(AccountTestMixin, TestCase):

    def setUp(self):
        self.staff = self.make_user("staff@example.com", role=User.Role.STAFF)
        self.member = self.make_user(
            "searchmember@example.com", first_name="Searchable", last_name="Member"
        )
        MemberProfile.objects.create(user=self.member, fitness_goal="Build strength")
        self.client.force_login(self.staff)

    def test_staff_can_search_member(self):
        response = self.client.get(
            reverse("accounts:staff_member_list"), {"q": "Searchable"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "searchmember@example.com")

    def test_staff_can_view_appropriate_member_details(self):
        response = self.client.get(
            reverse("accounts:staff_member_detail", args=[self.member.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Build strength")
        self.assertNotContains(response, "medical_notes")


class SeedUsersCommandTests(TestCase):

    def test_seed_users_creates_shared_demo_accounts(self):
        from django.core.management import call_command

        call_command("seed_users", verbosity=0)
        expected_roles = {
            "member@fitsync.com": User.Role.MEMBER,
            "coach@fitsync.com": User.Role.COACH,
            "staff@fitsync.com": User.Role.STAFF,
            "admin@fitsync.com": User.Role.ADMIN,
        }
        for email, role in expected_roles.items():
            with self.subTest(email=email):
                user = User.objects.get(email=email)
                self.assertEqual(user.role, role)
                self.assertTrue(user.is_active)
                self.assertTrue(user.check_password("FitSync123!"))
        member = User.objects.get(email="member@fitsync.com")
        coach = User.objects.get(email="coach@fitsync.com")
        self.assertTrue(MemberProfile.objects.filter(user=member).exists())
        self.assertTrue(hasattr(coach, "coach_profile"))

    def test_seed_users_can_run_twice_without_duplicates(self):
        from django.core.management import call_command

        call_command("seed_users", verbosity=0)
        call_command("seed_users", verbosity=0)
        self.assertEqual(
            User.objects.filter(
                email__in=[
                    "member@fitsync.com",
                    "coach@fitsync.com",
                    "staff@fitsync.com",
                    "admin@fitsync.com",
                ]
            ).count(),
            4,
        )


# Memberships and payments — Noorie


class MembershipFlowTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="member@example.com",
            email="member@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        self.package = MembershipPackage.objects.create(
            name="Premium",
            slug="premium-test",
            price="1990.00",
            duration_months=1,
            description="Premium membership",
            features="24/7 Gym Access\nAll Group Classes",
            is_active=True,
        )

    def test_public_packages_page_works(self):
        response = self.client.get(reverse("memberships:public_packages"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Premium")

    def test_figma_package_order(self):
        response = self.client.get(reverse("memberships:public_packages"))
        names = [package.name for package in response.context["packages"]]
        self.assertEqual(names[:4], ["Starter", "Premium", "Elite", "Student"])

    def test_guest_choose_plan_uses_auth_gate(self):
        response = self.client.get(
            reverse("memberships:auth_required", args=[self.package.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in to continue")
        self.assertContains(response, "AUTHENTICATION REQUIRED")

    def test_authenticated_member_skips_auth_gate(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("memberships:auth_required", args=[self.package.pk])
        )
        self.assertRedirects(
            response, reverse("memberships:checkout", args=[self.package.pk])
        )

    def test_member_checkout_success_creates_membership(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("memberships:checkout", args=[self.package.pk]),
            {"payer_name": "Test Member", "payment_method": Payment.Method.CARD},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Membership.objects.filter(member=self.member).count(), 1)
        self.assertEqual(
            Payment.objects.get(member=self.member).status, Payment.Status.SUCCESS
        )

    def test_failed_payment_does_not_activate_membership(self):
        self.client.force_login(self.member)
        self.client.post(
            reverse("memberships:checkout", args=[self.package.pk]),
            {
                "payer_name": "Test Member",
                "payment_method": Payment.Method.CARD,
                "simulate_failure": "on",
            },
        )
        self.assertFalse(Membership.objects.filter(member=self.member).exists())
        self.assertEqual(
            Payment.objects.get(member=self.member).status, Payment.Status.FAILED
        )

    def test_renewal_extends_existing_membership(self):
        old_end_date = date.today() + timedelta(days=12)
        membership = Membership.objects.create(
            member=self.member,
            package=self.package,
            start_date=date.today() - timedelta(days=18),
            end_date=old_end_date,
            status=Membership.Status.ACTIVE,
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("memberships:checkout", args=[self.package.pk]),
            {
                "payer_name": "Test Member",
                "payment_method": Payment.Method.CARD,
                "renewal_id": membership.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        membership.refresh_from_db()
        self.assertEqual(membership.end_date, old_end_date + timedelta(days=30))
        self.assertEqual(Membership.objects.filter(member=self.member).count(), 1)
        self.assertEqual(Payment.objects.get().membership, membership)

    def test_member_can_download_own_receipt(self):
        payment = Payment.objects.create(
            member=self.member,
            package=self.package,
            amount=self.package.price,
            payment_method=Payment.Method.CARD,
            status=Payment.Status.SUCCESS,
        )
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("memberships:receipt_download", args=[payment.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertContains(response, payment.receipt_number)


class MembershipRouteSmokeTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="route-member@example.com",
            email="route-member@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        self.admin = User.objects.create_superuser(
            username="route-admin@example.com",
            email="route-admin@example.com",
            password="TestPass123!",
            role=User.Role.ADMIN,
        )
        self.package = MembershipPackage.objects.create(
            name="Route Plan",
            slug="route-plan",
            price="1200.00",
            duration_months=1,
            description="Route test",
            features="Gym Access\nFitSync App",
            is_active=True,
        )

    def test_public_routes_render(self):
        for url in [
            reverse("memberships:public_packages"),
            reverse("memberships:public_package_detail", args=[self.package.slug]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_member_routes_render(self):
        self.client.force_login(self.member)
        for url in [
            reverse("memberships:member_packages"),
            reverse("memberships:current_membership"),
            reverse("memberships:membership_history"),
            reverse("memberships:payment_history"),
            reverse("memberships:checkout", args=[self.package.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_routes_render(self):
        self.client.force_login(self.admin)
        for url in [
            reverse("memberships:admin_package_list"),
            reverse("memberships:admin_package_create"),
            reverse("memberships:admin_membership_list"),
            reverse("memberships:admin_payment_list"),
            reverse("memberships:admin_membership_report"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)


class MembershipAdminTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="membership-admin@example.com",
            email="membership-admin@example.com",
            password="TestPass123!",
            role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            username="search-member@example.com",
            email="search-member@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        self.package = MembershipPackage.objects.create(
            name="Admin Plan",
            slug="admin-plan",
            price="1500.00",
            duration_months=1,
            features="Gym Access",
        )
        self.membership = Membership.objects.create(
            member=self.member,
            package=self.package,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            status=Membership.Status.ACTIVE,
        )
        self.payment = Payment.objects.create(
            member=self.member,
            package=self.package,
            membership=self.membership,
            amount=self.package.price,
            payment_method=Payment.Method.CARD,
            status=Payment.Status.SUCCESS,
        )
        self.client.force_login(self.admin)

    def test_payment_list_filters_by_member(self):
        response = self.client.get(
            reverse("memberships:admin_payment_list"), {"q": "search-member"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.payment.receipt_number)

    def test_membership_report_filters_statistics_by_date(self):
        older_member = User.objects.create_user(
            username="older-member@example.com",
            email="older-member@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        older_membership = Membership.objects.create(
            member=older_member,
            package=self.package,
            start_date=date.today() - timedelta(days=60),
            end_date=date.today() - timedelta(days=30),
            status=Membership.Status.EXPIRED,
        )
        older_payment = Payment.objects.create(
            member=older_member,
            package=self.package,
            membership=older_membership,
            amount="500.00",
            payment_method=Payment.Method.CASH,
            status=Payment.Status.SUCCESS,
        )
        older_time = timezone.now() - timedelta(days=60)
        Membership.objects.filter(pk=older_membership.pk).update(created_at=older_time)
        Payment.objects.filter(pk=older_payment.pk).update(created_at=older_time)
        today = date.today().isoformat()
        response = self.client.get(
            reverse("memberships:admin_membership_report"),
            {"date_from": today, "date_to": today},
        )
        self.payment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_count"], 1)
        self.assertEqual(response.context["expired_count"], 0)
        self.assertEqual(response.context["successful_payments"], 1)
        self.assertEqual(response.context["payment_total"], self.payment.amount)
        self.assertContains(response, 'name="date_from"')
        self.assertContains(response, 'name="date_to"')

    def test_admin_can_correct_membership_record(self):
        new_end_date = date.today() + timedelta(days=60)
        response = self.client.post(
            reverse("memberships:admin_membership_edit", args=[self.membership.pk]),
            {
                "package": self.package.pk,
                "start_date": self.membership.start_date,
                "end_date": new_end_date,
                "status": Membership.Status.ACTIVE,
            },
        )
        self.assertRedirects(response, reverse("memberships:admin_membership_list"))
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.end_date, new_end_date)

    def test_admin_can_correct_payment_record(self):
        response = self.client.post(
            reverse("memberships:admin_payment_edit", args=[self.payment.pk]),
            {"payment_method": Payment.Method.CASH, "status": Payment.Status.SUCCESS},
        )
        self.assertRedirects(
            response,
            reverse("memberships:admin_payment_detail", args=[self.payment.pk]),
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_method, Payment.Method.CASH)


# Services, sessions and bookings — Mehnaz

# 3.6 Manage scheduled sessions


class CoachSessionTests(TestCase):

    def setUp(self):
        self.coach = User.objects.create_user(
            username="teacher", email="teacher@test.com", role="COACH"
        )
        self.other = User.objects.create_user(
            username="other", email="other@test.com", role="COACH"
        )
        self.member = User.objects.create_user(
            username="member", email="member@test.com", role="MEMBER"
        )
        self.service = Service.objects.create(
            name="Strength Class", service_type="FITNESS"
        )
        self.day = timezone.localdate() + timedelta(days=5)
        self.session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=self.day,
            start_time=time(9),
            end_time=time(10),
            capacity=10,
        )
        self.other_session = Session.objects.create(
            service=self.service,
            instructor=self.other,
            date=self.day,
            start_time=time(11),
            end_time=time(12),
            capacity=10,
        )
        self.client.force_login(self.coach)

    def payload(self, **changes):
        data = {
            "service": self.service.pk,
            "instructor": self.other.pk,
            "date": self.day.isoformat(),
            "start_time": "13:00",
            "end_time": "14:00",
            "capacity": 12,
            "status": "CANCELLED",
        }
        data.update(changes)
        return data

    def test_coach_can_create_class_only_for_themselves(self):
        response = self.client.post(reverse("bookings:session_create"), self.payload())
        self.assertRedirects(response, reverse("bookings:session_list"))
        session = Session.objects.latest("pk")
        self.assertEqual(session.instructor, self.coach)
        self.assertEqual(session.status, Session.Status.SCHEDULED)
        self.assertContains(
            self.client.get(reverse("bookings:schedule")), "Strength Class"
        )

    def test_list_shows_own_classes_and_coach_layout(self):
        response = self.client.get(reverse("bookings:session_list"))
        self.assertEqual(list(response.context["sessions"]), [self.session])
        self.assertTemplateUsed(response, "layouts/coach_base.html")
        self.assertContains(response, "Add Class")
        self.assertNotContains(response, "Manage Services")
        self.assertContains(response, 'class="dashboard-scroll-content"')

    def test_other_coach_sessions_are_protected(self):
        for name in ["session_edit", "session_cancel", "session_roster"]:
            url = reverse(f"bookings:{name}", args=[self.other_session.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, self.payload()).status_code, 404)

    def test_coach_can_edit_own_class(self):
        response = self.client.post(
            reverse("bookings:session_edit", args=[self.session.pk]), self.payload()
        )
        self.assertRedirects(response, reverse("bookings:session_list"))
        self.session.refresh_from_db()
        self.assertEqual(self.session.instructor, self.coach)
        self.assertEqual(self.session.start_time, time(13))

    def test_cancel_updates_bookings_and_notifies_member(self):
        booking = Booking.objects.create(member=self.member, session=self.session)
        self.assertEqual(
            self.client.get(
                reverse("bookings:session_roster", args=[self.session.pk])
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("bookings:session_cancel", args=[self.session.pk])
        )
        self.assertRedirects(response, reverse("bookings:session_list"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        from gym.models import Notification

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member, title="Session Cancelled"
            ).exists()
        )

    def test_invalid_times_and_overlaps_are_rejected(self):
        for changes in [
            {"start_time": "09:30", "end_time": "10:30"},
            {"date": (self.day - timedelta(days=10)).isoformat()},
            {"start_time": "14:00", "end_time": "13:00"},
            {"capacity": 0},
        ]:
            response = self.client.post(
                reverse("bookings:session_create"), self.payload(**changes)
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(Session.objects.count(), 2)

    def test_member_cannot_manage_classes_and_coach_cannot_manage_services(self):
        self.assertEqual(
            self.client.get(reverse("bookings:service_create")).status_code, 403
        )
        self.client.force_login(self.member)
        for name in ["session_list", "session_create"]:
            self.assertEqual(
                self.client.get(reverse(f"bookings:{name}")).status_code, 403
            )

    def test_staff_form_has_scrollable_layout_and_new_service_types(self):
        from gym.forms import ServiceForm
        from gym.forms import MembershipPackageForm

        staff = User.objects.create_user(
            username="staff", email="staff@test.com", role="STAFF"
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("bookings:session_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="dashboard-scroll-content"')
        for value in ["PILATES", "BOXING", "HIIT", "CYCLING", "STRENGTH_TRAINING"]:
            self.assertIn(value, dict(ServiceForm().fields["service_type"].choices))
            self.assertIn(
                value,
                dict(MembershipPackageForm().fields["allowed_service_types"].choices),
            )


# Services, sessions and bookings — Mehnaz

# 3.6 Manage scheduled sessions


User = get_user_model()


class BookingViewTests(TestCase):
    """Tests the main member booking and cancellation flow."""

    def setUp(self):
        """Create reusable users, membership data, service and session."""
        self.member = User.objects.create_user(
            username="test_member",
            email="member@example.com",
            password="TestPassword123!",
            role="MEMBER",
        )
        self.coach = User.objects.create_user(
            username="test_coach",
            email="coach@example.com",
            password="TestPassword123!",
            role="COACH",
        )
        self.package = MembershipPackage.objects.create(
            name="Standard Membership",
            slug="standard-membership",
            price=1000,
            duration_months=1,
            description="Standard gym access.",
            features="Gym access\nSession booking",
            is_active=True,
        )
        today = timezone.localdate()
        self.membership = Membership.objects.create(
            member=self.member,
            package=self.package,
            start_date=today - timedelta(days=7),
            end_date=today + timedelta(days=30),
            status=Membership.Status.ACTIVE,
        )
        self.service = Service.objects.create(
            name="Morning Yoga",
            service_type=Service.Type.YOGA,
            description="A relaxing yoga session.",
            price=300,
            is_active=True,
        )
        self.session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=today + timedelta(days=7),
            start_time=time(8, 0),
            end_time=time(9, 0),
            capacity=2,
            status=Session.Status.SCHEDULED,
        )

    def test_schedule_page_displays_future_session(self):
        """The public schedule should display a future active session."""
        response = self.client.get(reverse("bookings:schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Morning Yoga")

    def test_member_can_book_available_session(self):
        """A member with an active membership should be able to book."""
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("bookings:book_session", args=[self.session.id])
        )
        self.assertRedirects(response, reverse("bookings:schedule"))
        self.assertTrue(
            Booking.objects.filter(
                member=self.member,
                session=self.session,
                status=Booking.Status.CONFIRMED,
            ).exists()
        )

    def test_plan_can_restrict_service_types(self):
        self.package.allowed_service_types = Service.Type.ZUMBA
        self.package.save(update_fields=["allowed_service_types"])
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("bookings:book_session", args=[self.session.id]), follow=True
        )
        self.assertContains(
            response, "Your membership plan does not include this service."
        )
        self.assertFalse(
            Booking.objects.filter(member=self.member, session=self.session).exists()
        )

    def test_member_without_active_membership_cannot_book(self):
        """A member without an active membership should be blocked."""
        self.membership.delete()
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("bookings:book_session", args=[self.session.id]), follow=True
        )
        self.assertContains(
            response, "You need an active membership to book a session."
        )
        self.assertFalse(
            Booking.objects.filter(
                member=self.member,
                session=self.session,
                status=Booking.Status.CONFIRMED,
            ).exists()
        )

    def test_member_cannot_book_same_session_twice(self):
        """The same member should not receive two confirmed bookings."""
        self.client.force_login(self.member)
        booking_url = reverse("bookings:book_session", args=[self.session.id])
        self.client.post(booking_url)
        self.client.post(booking_url)
        confirmed_count = Booking.objects.filter(
            member=self.member, session=self.session, status=Booking.Status.CONFIRMED
        ).count()
        self.assertEqual(confirmed_count, 1)

    def test_member_cannot_book_full_session(self):
        """A booking should not be created after capacity is reached."""
        self.session.capacity = 1
        self.session.save(update_fields=["capacity"])
        other_member = User.objects.create_user(
            username="other_member",
            email="other@example.com",
            password="TestPassword123!",
            role="MEMBER",
        )
        Booking.objects.create(
            member=other_member, session=self.session, status=Booking.Status.CONFIRMED
        )
        self.client.force_login(self.member)
        self.client.post(reverse("bookings:book_session", args=[self.session.id]))
        self.assertFalse(
            Booking.objects.filter(
                member=self.member,
                session=self.session,
                status=Booking.Status.CONFIRMED,
            ).exists()
        )

    def test_member_cannot_book_overlapping_session(self):
        """A member cannot book two sessions whose times overlap."""
        Booking.objects.create(
            member=self.member, session=self.session, status=Booking.Status.CONFIRMED
        )
        overlapping_session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=self.session.date,
            start_time=time(8, 30),
            end_time=time(9, 30),
            capacity=10,
            status=Session.Status.SCHEDULED,
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("bookings:book_session", args=[overlapping_session.id]), follow=True
        )
        self.assertContains(response, "You already have another booking at this time.")
        self.assertFalse(
            Booking.objects.filter(
                member=self.member,
                session=overlapping_session,
                status=Booking.Status.CONFIRMED,
            ).exists()
        )

    def test_member_can_cancel_own_booking(self):
        """Cancelling should update the status instead of deleting it."""
        booking = Booking.objects.create(
            member=self.member, session=self.session, status=Booking.Status.CONFIRMED
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("bookings:cancel_booking", args=[booking.id])
        )
        self.assertRedirects(response, reverse("bookings:my_bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)
        self.assertTrue(Booking.objects.filter(id=booking.id).exists())


class CompletedBookingFeatureTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="member_two",
            email="member2@example.com",
            password="TestPassword123!",
            role="MEMBER",
        )
        self.coach = User.objects.create_user(
            username="coach_two",
            email="coach2@example.com",
            password="TestPassword123!",
            role="COACH",
            first_name="Alex",
            last_name="Coach",
        )
        self.staff = User.objects.create_user(
            username="staff_user",
            email="staff@example.com",
            password="TestPassword123!",
            role="STAFF",
        )
        self.package = MembershipPackage.objects.create(
            name="Complete Plan",
            slug="complete-plan",
            price=1200,
            duration_months=1,
            description="Complete access.",
            features="Gym access",
            is_active=True,
        )
        Membership.objects.create(
            member=self.member,
            package=self.package,
            start_date=timezone.localdate() - timedelta(days=2),
            end_date=timezone.localdate() + timedelta(days=30),
            status=Membership.Status.ACTIVE,
        )
        self.service = Service.objects.create(
            name="Evening Fitness",
            service_type=Service.Type.FITNESS,
            description="A guided fitness session.",
            price=250,
            is_active=True,
        )
        self.session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=timezone.localdate() + timedelta(days=5),
            start_time=time(18, 0),
            end_time=time(19, 0),
            capacity=8,
            status=Session.Status.SCHEDULED,
        )

    def test_schedule_filters_by_date_and_instructor(self):
        response = self.client.get(
            reverse("bookings:schedule"),
            {"date": self.session.date.isoformat(), "instructor": self.coach.id},
        )
        self.assertContains(response, "Evening Fitness")
        response = self.client.get(
            reverse("bookings:schedule"),
            {"date": (self.session.date + timedelta(days=1)).isoformat()},
        )
        self.assertNotContains(response, "Evening Fitness")

    def test_public_session_detail_displays_capacity(self):
        response = self.client.get(
            reverse("bookings:session_detail", args=[self.session.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "8 of 8")

    def test_member_cannot_book_session_that_started_today(self):
        started_session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=timezone.localdate(),
            start_time=time(0, 0),
            end_time=time(0, 1),
            capacity=8,
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("bookings:book_session", args=[started_session.id]), follow=True
        )
        self.assertContains(response, "already started")
        self.assertFalse(Booking.objects.filter(session=started_session).exists())

    def test_member_cannot_cancel_after_session_started(self):
        started_session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=timezone.localdate(),
            start_time=time(0, 0),
            end_time=time(0, 1),
            capacity=8,
        )
        booking = Booking.objects.create(member=self.member, session=started_session)
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("bookings:cancel_booking", args=[booking.id]), follow=True
        )
        self.assertContains(response, "cannot be cancelled")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_my_bookings_are_separated(self):
        upcoming = Booking.objects.create(member=self.member, session=self.session)
        past_session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=timezone.localdate() - timedelta(days=2),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity=8,
        )
        previous = Booking.objects.create(member=self.member, session=past_session)
        cancelled_session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=timezone.localdate() + timedelta(days=8),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity=8,
        )
        cancelled = Booking.objects.create(
            member=self.member,
            session=cancelled_session,
            status=Booking.Status.CANCELLED,
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse("bookings:my_bookings"))
        self.assertIn(upcoming, response.context["upcoming_bookings"])
        self.assertIn(previous, response.context["previous_bookings"])
        self.assertIn(cancelled, response.context["cancelled_bookings"])

    def test_member_can_only_open_own_booking_detail(self):
        booking = Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("bookings:booking_detail", args=[booking.id])
        )
        self.assertEqual(response.status_code, 200)
        other_member = User.objects.create_user(
            username="other_detail_member", password="TestPassword123!", role="MEMBER"
        )
        self.client.force_login(other_member)
        response = self.client.get(
            reverse("bookings:booking_detail", args=[booking.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_staff_can_create_service(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("bookings:service_create"),
            {
                "name": "Pilates",
                "service_type": Service.Type.FITNESS,
                "description": "Pilates class",
                "price": "200.00",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("bookings:service_list"))
        self.assertTrue(Service.objects.filter(name="Pilates").exists())

    def test_staff_can_create_session(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("bookings:session_create"),
            {
                "service": self.service.id,
                "instructor": self.coach.id,
                "date": (timezone.localdate() + timedelta(days=12)).isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "capacity": 10,
                "status": Session.Status.SCHEDULED,
            },
        )
        self.assertRedirects(response, reverse("bookings:session_list"))
        self.assertTrue(
            Session.objects.filter(
                date=timezone.localdate() + timedelta(days=12)
            ).exists()
        )

    def test_member_cannot_open_session_management(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("bookings:session_list"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_session_roster(self):
        Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("bookings:session_roster", args=[self.session.id])
        )
        self.assertContains(response, "member2@example.com")

    def test_cancelling_session_cancels_confirmed_bookings(self):
        booking = Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.staff)
        self.client.post(reverse("bookings:session_cancel", args=[self.session.id]))
        self.session.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(self.session.status, Session.Status.CANCELLED)
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)

    def test_booking_report_filters_by_session_date(self):
        Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("bookings:booking_report"),
            {
                "date_from": self.session.date.isoformat(),
                "date_to": self.session.date.isoformat(),
            },
        )
        self.assertEqual(response.context["total_bookings"], 1)
        self.assertContains(response, "Evening Fitness")

    def test_service_with_sessions_is_deactivated_instead_of_deleted(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("bookings:service_delete", args=[self.service.id]))
        self.service.refresh_from_db()
        self.assertFalse(self.service.is_active)


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


class CoachWorkspaceTests(TestCase):

    def setUp(self):
        self.coach = User.objects.create_user(
            username="workspacecoach", email="workspacecoach@test.com", role="COACH"
        )
        self.member = User.objects.create_user(
            username="workspace_member",
            email="workspace_member@test.com",
            role="MEMBER",
        )
        self.other = User.objects.create_user(
            username="private_member", email="private_member@test.com", role="MEMBER"
        )
        self.assignment = CoachAssignment.objects.create(
            coach=self.coach, member=self.member
        )
        MemberProfile.objects.create(
            user=self.member, target_weight_kg=70, fitness_goal="Build Strength"
        )
        self.plan = WorkoutPlan.objects.create(
            member=self.member,
            coach=self.coach,
            name="Assigned Strength",
            plan_type="COACH_ASSIGNED",
        )
        self.hidden = WorkoutPlan.objects.create(
            member=self.other,
            coach=self.coach,
            name="Private Plan",
            plan_type="COACH_ASSIGNED",
        )
        WorkoutPlan.objects.create(
            member=self.member, name="Private Personal Plan", plan_type="PERSONAL"
        )
        exercise = Exercise.objects.create(name="Sample Squat", category="LEGS")
        WorkoutPlanExercise.objects.create(workout_plan=self.plan, exercise=exercise)
        WeightRecord.objects.create(
            member=self.member, weight_kg=75, recorded_date=timezone.localdate()
        )
        WeightRecord.objects.create(
            member=self.other, weight_kg=99, recorded_date=timezone.localdate()
        )
        self.session = WorkoutSession.objects.create(
            member=self.member, workout_plan=self.plan, completed_at=timezone.now()
        )
        WorkoutSession.objects.create(
            member=self.member, completed_at=timezone.now() - timedelta(days=10)
        )
        self.client.force_login(self.coach)

    def test_sidebar_has_distinct_destinations_and_templates(self):
        for name, template, active in [
            ("coach_members", "assigned_members.html", "members"),
            ("coach_plans", "workout_plans.html", "plans"),
            ("coach_progress", "progress.html", "progress"),
        ]:
            response = self.client.get(reverse(f"workouts:{name}"))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, f"coach/{template}")
            self.assertEqual(response.context["active_sidebar"], active)
            for destination in ["coach_members", "coach_plans", "coach_progress"]:
                self.assertContains(
                    response, f'''href="{reverse(f'workouts:{destination}')}"'''
                )

    def test_plans_show_only_own_assigned_plans(self):
        response = self.client.get(reverse("workouts:coach_plans"))
        self.assertEqual(list(response.context["plans"]), [self.plan])
        self.assertEqual(response.context["plans"][0].exercise_count, 1)
        self.assertNotContains(response, "Private Plan")
        self.assertNotContains(response, "Private Personal Plan")
        self.assertContains(
            response, reverse("workouts:plan_detail", args=[self.plan.pk])
        )
        self.assertEqual(
            self.client.get(
                reverse("workouts:coach_plans"), {"member": self.other.pk}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("workouts:coach_plans"), {"member": "invalid"}
            ).status_code,
            404,
        )

    def test_progress_uses_assigned_members_real_records(self):
        response = self.client.get(reverse("workouts:coach_progress"))
        members = list(response.context["members"])
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].latest_weight, Decimal("75"))
        self.assertEqual(members[0].completed_count, 2)
        self.assertEqual(members[0].weekly_count, 1)
        self.assertNotContains(response, "private_member")
        self.assertContains(
            response, reverse("workouts:coach_member_progress", args=[self.member.pk])
        )
        response = self.client.get(
            reverse("workouts:history_detail", args=[self.session.pk])
        )
        self.assertEqual(response.context["active_sidebar"], "progress")
        self.assertContains(
            response, reverse("workouts:coach_member_progress", args=[self.member.pk])
        )

    def test_revoked_assignment_hides_plans_and_progress(self):
        self.assignment.active = False
        self.assignment.save()
        self.assertEqual(
            len(self.client.get(reverse("workouts:coach_plans")).context["plans"]), 0
        )
        self.assertEqual(
            len(self.client.get(reverse("workouts:coach_progress")).context["members"]),
            0,
        )
        self.assertEqual(
            self.client.get(
                reverse("workouts:coach_member_progress", args=[self.member.pk])
            ).status_code,
            403,
        )

    def test_non_coaches_cannot_open_overviews(self):
        self.client.force_login(self.member)
        for name in ["coach_members", "coach_plans", "coach_progress"]:
            self.assertEqual(
                self.client.get(reverse(f"workouts:{name}")).status_code, 403
            )

    def test_multiple_members_and_multiple_plans_have_correct_actions(self):
        self.member.first_name = "Zoe"
        self.member.save()
        second = User.objects.create_user(
            username="another_member",
            email="another@test.com",
            first_name="Amy",
            role="MEMBER",
        )
        CoachAssignment.objects.create(coach=self.coach, member=second)
        other_plan = WorkoutPlan.objects.create(
            member=second,
            coach=self.coach,
            name="Amy Upper",
            plan_type="COACH_ASSIGNED",
        )
        WorkoutPlan.objects.create(
            member=second,
            coach=self.coach,
            name="Amy Lower",
            plan_type="COACH_ASSIGNED",
        )
        response = self.client.get(reverse("workouts:coach_plans"))
        self.assertEqual(response.context["plan_count"], 3)
        self.assertEqual(
            [plan.member_id for plan in response.context["plans"]],
            [second.pk, second.pk, self.member.pk],
        )
        self.assertContains(response, "Choose a member")
        for member in [self.member, second]:
            self.assertContains(
                response, reverse("workouts:coach_plan_create", args=[member.pk])
            )
        for plan in response.context["plans"]:
            for action in ["plan_detail", "plan_edit", "plan_add_exercises"]:
                self.assertContains(
                    response, reverse(f"workouts:{action}", args=[plan.pk])
                )
        html = response.content.decode()
        self.assertLess(
            html.index('<th scope="col">Member'), html.index('<th scope="col">Plan')
        )
        response = self.client.get(
            reverse("workouts:coach_plans"), {"member": second.pk}
        )
        self.assertEqual(response.context["plan_count"], 2)
        self.assertNotContains(response, self.plan.name)
        self.assertContains(response, other_plan.name)

    def test_large_plan_list_paginates_and_keeps_member_filter(self):
        for index in range(17):
            WorkoutPlan.objects.create(
                member=self.member,
                coach=self.coach,
                name=f"Training {index}",
                plan_type="COACH_ASSIGNED",
            )
        response = self.client.get(
            reverse("workouts:coach_plans"), {"member": self.member.pk}
        )
        self.assertEqual(response.context["plan_count"], 18)
        self.assertEqual(len(response.context["plans"]), 15)
        self.assertContains(response, f"?page=2&amp;member={self.member.pk}")
        response = self.client.get(
            reverse("workouts:coach_plans"), {"member": self.member.pk, "page": 2}
        )
        self.assertEqual(len(response.context["plans"]), 3)
        self.assertTrue(
            all(
                (plan.member_id == self.member.pk for plan in response.context["plans"])
            )
        )


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


class ProgressOverviewTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="progress_member",
            email="progress_member@example.com",
            role="MEMBER",
        )
        self.other_member = User.objects.create_user(
            username="progress_other", email="progress_other@example.com", role="MEMBER"
        )
        MemberProfile.objects.create(
            user=self.member, current_weight_kg=80, target_weight_kg=70
        )
        self.today = timezone.localdate()
        self.url = reverse("workouts:progress")
        self.client.force_login(self.member)

    def test_period_filters_and_weight_goal_use_real_records(self):
        WeightRecord.objects.create(
            member=self.member,
            recorded_date=self.today - timedelta(days=40),
            weight_kg=80,
        )
        WeightRecord.objects.create(
            member=self.member,
            recorded_date=self.today - timedelta(days=10),
            weight_kg=78,
        )
        WeightRecord.objects.create(
            member=self.member, recorded_date=self.today, weight_kg=75
        )
        for period, expected in [("weekly", 1), ("monthly", 2), ("all", 3)]:
            response = self.client.get(self.url, {"period": period})
            self.assertEqual(len(response.context["weight_chart"]), expected)
            self.assertEqual(response.context["goal_percent"], 50)
            self.assertEqual(response.context["remaining_weight"], Decimal("5"))
        response = self.client.get(self.url, {"period": "monthly"})
        self.assertEqual(response.context["weight_change"], Decimal("-3"))

    def test_empty_overview_does_not_invent_calories_or_duration(self):
        plan = WorkoutPlan.objects.create(
            member=self.member, name="Strength", goal="Build Strength"
        )
        WorkoutSession.objects.create(
            member=self.member, workout_plan=plan, completed_at=timezone.now()
        )
        response = self.client.get(self.url)
        self.assertEqual(response.context["workout_count"], 1)
        self.assertIsNone(response.context["average_minutes"])
        self.assertIsNone(response.context["estimated_calories"])
        self.assertEqual(response.context["breakdown"][0]["count"], 1)
        self.assertNotContains(response, "Consumed: not tracked")

    def test_workout_statistics_and_personal_records_are_private(self):
        exercise = Exercise.objects.create(name="Progress Squat", category="LEGS")
        session = WorkoutSession.objects.create(
            member=self.member, completed_at=timezone.now(), duration_minutes=30
        )
        WorkoutExerciseRecord.objects.create(
            workout_session=session, exercise=exercise, weight_kg=40
        )
        WorkoutExerciseRecord.objects.create(
            workout_session=session, exercise=exercise, weight_kg=50
        )
        other_session = WorkoutSession.objects.create(
            member=self.other_member, completed_at=timezone.now(), duration_minutes=100
        )
        WorkoutExerciseRecord.objects.create(
            workout_session=other_session, exercise=exercise, weight_kg=100
        )
        WeightRecord.objects.create(
            member=self.other_member, recorded_date=self.today, weight_kg=99
        )
        response = self.client.get(self.url)
        self.assertEqual(response.context["workout_count"], 1)
        self.assertEqual(response.context["estimated_calories"], 210)
        self.assertEqual(response.context["average_minutes"], 30)
        self.assertEqual(
            sum((day["value"] for day in response.context["calorie_chart"])), 210
        )
        self.assertEqual(len(response.context["personal_records"]), 1)
        self.assertEqual(
            response.context["personal_records"][0].weight_kg, Decimal("50")
        )
        self.assertEqual(response.context["weight_chart"], [])

    def test_invalid_period_uses_weekly_and_weight_gain_goal_works(self):
        profile = self.member.member_profile
        profile.target_weight_kg = 90
        profile.save()
        WeightRecord.objects.create(
            member=self.member,
            recorded_date=self.today - timedelta(days=2),
            weight_kg=80,
        )
        WeightRecord.objects.create(
            member=self.member, recorded_date=self.today, weight_kg=85
        )
        response = self.client.get(self.url, {"period": "invalid"})
        self.assertEqual(response.context["period"], "weekly")
        self.assertEqual(response.context["goal_percent"], 50)


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


class WaterIntakeTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="water_member", email="water@example.com", role="MEMBER"
        )
        self.today = timezone.localdate()
        self.url = reverse("workouts:water_intake")
        self.client.force_login(self.member)

    def test_saving_daily_total_updates_existing_record_and_dashboard(self):
        data = {"recorded_date": self.today, "litres": "1.25"}
        self.assertRedirects(self.client.post(self.url, data), self.url)
        data["litres"] = "2.50"
        self.assertRedirects(self.client.post(self.url, data), self.url)
        self.assertEqual(WaterIntake.objects.filter(member=self.member).count(), 1)
        response = self.client.get(reverse("accounts:member_dashboard"))
        self.assertEqual(
            response.context["today_water_litres"], WaterIntake.objects.get().litres
        )
        self.assertContains(response, "2.50")

    def test_rejects_invalid_totals_and_future_dates(self):
        cases = [
            {"recorded_date": self.today, "litres": "-1"},
            {"recorded_date": self.today, "litres": "abc"},
            {"recorded_date": self.today + timedelta(days=1), "litres": "1"},
        ]
        for data in cases:
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(WaterIntake.objects.exists())

    def test_records_are_private_and_previous_days_do_not_change_today(self):
        other_member = User.objects.create_user(
            username="other_water", email="other_water@example.com", role="MEMBER"
        )
        WaterIntake.objects.create(
            member=other_member, recorded_date=self.today, litres="3.75"
        )
        yesterday = self.today - timedelta(days=1)
        self.client.post(self.url, {"recorded_date": yesterday, "litres": "1.50"})
        response = self.client.get(self.url)
        self.assertNotContains(response, "3.75")
        self.assertEqual(response.context["today_litres"], 0)
        self.client.post(self.url, {"recorded_date": self.today, "litres": "0.50"})
        other_record = WaterIntake.objects.get(member=other_member)
        self.assertEqual(str(other_record.litres), "3.75")

    def test_anonymous_and_non_members_cannot_track_water(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        coach = User.objects.create_user(
            username="water_coach", email="water_coach@example.com", role="COACH"
        )
        self.client.force_login(coach)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.url, {"recorded_date": self.today, "litres": "1"}
            ).status_code,
            403,
        )


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


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
            workout_plan=plan, exercise=self.exercise, sets=3, reps=10, order=1
        )
        return plan

    def test_member_can_open_workout_plans(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("workouts:plans"))
        self.assertEqual(response.status_code, 200)

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
        self.assertEqual(response.status_code, 302)
        plan = WorkoutPlan.objects.get(name="My Strength Plan")
        self.assertEqual(plan.member, self.member)
        self.assertEqual(plan.plan_type, "PERSONAL")
        self.assertEqual(plan.plan_exercises.count(), 1)
        self.assertEqual(plan.plan_exercises.first().exercise, self.exercise)

    def test_member_cannot_view_another_members_plan(self):
        plan = WorkoutPlan.objects.create(
            member=self.other_member, name="Private Plan", plan_type="PERSONAL"
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse("workouts:plan_detail", args=[plan.id]))
        self.assertEqual(response.status_code, 403)

    def test_coach_can_open_assigned_members(self):
        CoachAssignment.objects.create(
            coach=self.coach, member=self.member, active=True
        )
        self.client.force_login(self.coach)
        response = self.client.get(reverse("workouts:coach_members"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.username)

    def test_coach_can_select_exercises_for_assigned_members_plan(self):
        CoachAssignment.objects.create(
            coach=self.coach, member=self.member, active=True
        )
        plan = self.create_plan(plan_type="COACH_ASSIGNED", coach=self.coach)
        additional = Exercise.objects.create(
            name="Additional Press", category="CHEST", is_active=True
        )
        self.client.force_login(self.coach)
        url = reverse("workouts:plan_add_exercises", args=[plan.id])
        response = self.client.get(url)
        self.assertContains(response, "Coach Menu")
        self.assertContains(response, "exercise-selection-image")
        self.assertContains(response, additional.library_image)
        self.assertNotContains(response, "img/exercises/chest.jpg")
        response = self.client.post(
            url, {"exercise_ids": [self.exercise.id, additional.id]}
        )
        self.assertRedirects(response, reverse("workouts:plan_detail", args=[plan.id]))
        self.assertEqual(plan.plan_exercises.count(), 2)
        self.client.post(url, {"exercise_ids": [additional.id]})
        self.assertEqual(plan.plan_exercises.count(), 2)

    def test_unassigned_coach_cannot_add_exercises(self):
        plan = self.create_plan(plan_type="COACH_ASSIGNED", coach=self.coach)
        self.client.force_login(self.coach)
        url = reverse("workouts:plan_add_exercises", args=[plan.id])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {"exercise_ids": [self.exercise.id]}).status_code, 403
        )

    def test_history_library_link_is_a_header_button(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("workouts:history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'class="btn btn-secondary-fitsync" href="{reverse("workouts:exercise_library")}"',
        )
        tabs = response.content.decode().split('class="workout-tabs"', 1)[1].split('</div>', 1)[0]
        self.assertNotIn("Exercise Library", tabs)
        self.assertIn("Workout Plans", tabs)
        self.assertIn("History", tabs)

    def test_member_library_has_back_button_without_workout_tabs(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("workouts:exercise_library"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="workout-tabs')
        self.assertContains(response, 'class="btn workout-back-button"')
        self.assertContains(response, 'class="exercise-filters')

    def test_coach_library_and_exercise_detail_keep_coach_layout(self):
        self.client.force_login(self.coach)
        response = self.client.get(reverse("workouts:exercise_library"))
        self.assertContains(response, "Coach Menu")
        self.assertNotContains(response, "Member Menu")
        response = self.client.get(
            reverse("workouts:exercise_detail", args=[self.exercise.id])
        )
        self.assertContains(response, "Coach Menu")

    def test_staff_can_manage_exercises(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("workouts:exercise_manage"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.exercise.name)

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
        self.assertEqual(response.status_code, 302)
        self.assertTrue(WeightRecord.objects.filter(member=self.member).exists())

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
        self.assertRedirects(response, reverse("workouts:plan_detail", args=[plan.id]))
        plan.refresh_from_db()
        self.assertEqual(plan.name, "Updated Strength Plan")
        self.assertEqual(plan.workout_days, "Tue,Thu,Sat")

    def test_member_can_delete_personal_plan(self):
        plan = self.create_plan()
        self.client.force_login(self.member)
        response = self.client.post(reverse("workouts:plan_delete", args=[plan.id]))
        self.assertRedirects(response, reverse("workouts:plans"))
        self.assertFalse(WorkoutPlan.objects.filter(id=plan.id).exists())

    def test_member_cannot_edit_coach_assigned_plan(self):
        CoachAssignment.objects.create(
            coach=self.coach, member=self.member, active=True
        )
        plan = self.create_plan(plan_type="COACH_ASSIGNED", coach=self.coach)
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
        self.assertRedirects(response, reverse("workouts:plan_detail", args=[plan.id]))
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
            start_response, reverse("workouts:active_workout", args=[session.id])
        )
        finish_response = self.client.post(
            reverse("workouts:finish_workout", args=[session.id]),
            {
                f"completed_sets_{entry.id}": ["1", "2"],
                f"set_{entry.id}_1-reps": "8",
                f"set_{entry.id}_1-weight_kg": "45.5",
                f"set_{entry.id}_2-reps": "6",
                f"set_{entry.id}_2-weight_kg": "50",
                "notes": "Good session",
            },
        )
        self.assertRedirects(
            finish_response, reverse("workouts:history_detail", args=[session.id])
        )
        session.refresh_from_db()
        self.assertIsNotNone(session.completed_at)
        self.assertEqual(session.duration_minutes, 0)
        self.assertEqual(session.notes, "Good session")
        self.assertEqual(session.exercise_records.count(), 2)
        record = session.exercise_records.get(set_number=1)
        self.assertEqual(record.sets, 1)
        self.assertEqual(record.reps, 8)
        self.assertEqual(str(record.weight_kg), "45.50")
        second = session.exercise_records.get(set_number=2)
        self.assertEqual(second.reps, 6)
        self.assertEqual(str(second.weight_kg), "50.00")

    def finish_timed_session(self, started_at):
        plan = self.create_plan()
        entry = plan.plan_exercises.first()
        session = WorkoutSession.objects.create(
            member=self.member, workout_plan=plan, started_at=started_at
        )
        self.client.force_login(self.member)
        data = {
            f"completed_sets_{entry.id}": ["1"],
            f"set_{entry.id}_1-reps": "10",
            f"set_{entry.id}_1-weight_kg": "25",
            "session_duration": "9999",
        }
        self.client.post(reverse("workouts:finish_workout", args=[session.pk]), data)
        session.refresh_from_db()
        return session, data

    def test_timer_includes_rests_and_ignores_posted_duration(self):
        now = timezone.now()
        with patch("gym.views.timezone.now", return_value=now):
            session, _ = self.finish_timed_session(
                now - timedelta(minutes=42, seconds=40)
            )
        self.assertEqual(session.duration_minutes, 43)

    def test_repeat_finish_preserves_duration_and_completed_sets(self):
        now = timezone.now()
        session, data = self.finish_timed_session(now - timedelta(minutes=12))
        saved_time = session.completed_at
        with patch("gym.views.timezone.now", return_value=now + timedelta(hours=2)):
            self.client.post(
                reverse("workouts:finish_workout", args=[session.pk]), data
            )
        session.refresh_from_db()
        self.assertEqual(session.completed_at, saved_time)
        self.assertEqual(session.duration_minutes, 12)
        self.assertEqual(session.exercise_records.count(), 1)

    def test_timer_never_saves_negative_minutes(self):
        session, _ = self.finish_timed_session(timezone.now() + timedelta(minutes=3))
        self.assertEqual(session.duration_minutes, 0)

    def test_newly_timed_workout_appears_in_progress_average(self):
        self.finish_timed_session(timezone.now() - timedelta(minutes=20))
        response = self.client.get(reverse("workouts:progress"))
        self.assertEqual(response.context["average_minutes"], 20)

    def test_completed_sets_ignore_duplicates_and_invalid_numbers(self):
        plan = self.create_plan()
        entry = plan.plan_exercises.first()
        skipped = WorkoutPlanExercise.objects.create(
            workout_plan=plan, exercise=self.exercise, sets=3, reps=10, order=2
        )
        session = WorkoutSession.objects.create(member=self.member, workout_plan=plan)
        self.client.force_login(self.member)
        self.client.post(
            reverse("workouts:finish_workout", args=[session.id]),
            {
                f"completed_sets_{entry.id}": ["1", "1", "3", "0", "999", "abc"],
                f"set_{entry.id}_1-reps": "10",
                f"set_{entry.id}_3-reps": "8",
                f"sets_{skipped.id}": "3",
                "session_duration": "500",
            },
        )
        self.assertEqual(session.exercise_records.count(), 2)
        self.assertEqual(
            list(session.exercise_records.values_list("set_number", flat=True)), [1, 3]
        )
        session.refresh_from_db()
        self.assertEqual(session.duration_minutes, 0)

    def test_workout_cannot_finish_without_completed_sets(self):
        plan = self.create_plan()
        session = WorkoutSession.objects.create(member=self.member, workout_plan=plan)
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("workouts:finish_workout", args=[session.id]), {}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mark at least one set complete")
        session.refresh_from_db()
        self.assertIsNone(session.completed_at)
        self.assertFalse(session.exercise_records.exists())

    def test_invalid_set_values_keep_workout_open_without_partial_records(self):
        plan = self.create_plan()
        entry = plan.plan_exercises.first()
        session = WorkoutSession.objects.create(member=self.member, workout_plan=plan)
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("workouts:finish_workout", args=[session.id]),
            {
                f"completed_sets_{entry.id}": ["1", "2"],
                f"set_{entry.id}_1-reps": "10",
                f"set_{entry.id}_1-weight_kg": "20",
                f"set_{entry.id}_2-reps": "0",
                f"set_{entry.id}_2-weight_kg": "-5",
                "notes": "Keep my notes",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keep my notes")
        self.assertContains(response, 'value="20"')
        session.refresh_from_db()
        self.assertIsNone(session.completed_at)
        self.assertFalse(session.exercise_records.exists())

    def test_set_history_preserves_weights_and_counts_one_exercise(self):
        plan = self.create_plan()
        entry = plan.plan_exercises.first()
        session = WorkoutSession.objects.create(member=self.member, workout_plan=plan)
        self.client.force_login(self.member)
        data = {
            f"completed_sets_{entry.id}": ["1", "3"],
            f"set_{entry.id}_1-reps": "10",
            f"set_{entry.id}_1-weight_kg": "20",
            f"set_{entry.id}_3-reps": "8",
            f"set_{entry.id}_3-weight_kg": "25",
        }
        self.client.post(reverse("workouts:finish_workout", args=[session.id]), data)
        self.client.post(reverse("workouts:finish_workout", args=[session.id]), data)
        self.assertEqual(session.exercise_records.count(), 2)
        response = self.client.get(
            reverse("workouts:history_detail", args=[session.id])
        )
        self.assertContains(response, "20.00")
        self.assertContains(response, "25.00")
        response = self.client.get(reverse("workouts:history"))
        self.assertEqual(
            response.context["sessions"].get(id=session.id).exercise_count, 1
        )

    def test_workout_history_only_shows_completed_sessions(self):
        plan = self.create_plan()
        completed_session = WorkoutSession.objects.create(
            member=self.member,
            workout_plan=plan,
            completed_at=timezone.now(),
            duration_minutes=30,
        )
        WorkoutSession.objects.create(member=self.member, workout_plan=plan)
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
            member=self.member, weight_kg="70.50", recorded_date=date.today()
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse("accounts:member_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["personal_plan_count"], 1)
        self.assertEqual(response.context["coach_plan_count"], 0)
        self.assertEqual(str(response.context["latest_weight"].weight_kg), "70.50")

    def test_coach_dashboard_shows_workout_summary(self):
        CoachAssignment.objects.create(
            coach=self.coach, member=self.member, active=True
        )
        self.create_plan(plan_type="COACH_ASSIGNED", coach=self.coach)
        self.client.force_login(self.coach)
        response = self.client.get(reverse("accounts:coach_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assignment_count"], 1)
        self.assertEqual(response.context["coach_plan_count"], 1)


# Attendance — Bhavshika

# 4.8 Attendance corrections


class AttendanceTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="attendance-member@example.com",
            email="attendance-member@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        self.staff = User.objects.create_user(
            username="attendance-staff@example.com",
            email="attendance-staff@example.com",
            password="TestPass123!",
            role=User.Role.STAFF,
        )
        self.admin = User.objects.create_superuser(
            username="attendance-admin@example.com",
            email="attendance-admin@example.com",
            password="TestPass123!",
            role=User.Role.ADMIN,
        )
        self.package = MembershipPackage.objects.create(
            name="Attendance Plan",
            slug="attendance-plan",
            price="1000.00",
            duration_months=1,
            features="Gym access",
        )
        today = timezone.localdate()
        self.membership = Membership.objects.create(
            member=self.member,
            package=self.package,
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=28),
            status=Membership.Status.ACTIVE,
        )

    def test_member_can_view_active_qr_code(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("attendance:my_qr_code"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data:image/png;base64")
        self.assertTrue(MemberQRCode.objects.filter(member=self.member).exists())

    def test_expired_membership_disables_qr_code(self):
        self.membership.end_date = timezone.localdate() - timedelta(days=1)
        self.membership.save(update_fields=["end_date"])
        self.client.force_login(self.member)
        response = self.client.get(reverse("attendance:my_qr_code"))
        self.assertContains(response, "QR code unavailable")
        self.assertNotContains(response, "data:image/png;base64")

    def test_member_cannot_open_staff_attendance(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("attendance:staff_attendance"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_check_member_in_and_out(self):
        self.client.force_login(self.staff)
        attendance_url = reverse("attendance:staff_attendance")
        self.client.post(
            attendance_url,
            {"member_identifier": self.member.email, "action": "check_in"},
        )
        record = AttendanceRecord.objects.get(member=self.member)
        self.assertIsNone(record.check_out_time)
        self.client.post(
            attendance_url,
            {"member_identifier": self.member.email, "action": "check_out"},
        )
        record.refresh_from_db()
        self.assertIsNotNone(record.check_out_time)

    def test_duplicate_check_in_is_blocked(self):
        AttendanceRecord.objects.create(member=self.member)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("attendance:staff_attendance"),
            {"member_identifier": self.member.email, "action": "check_in"},
            follow=True,
        )
        self.assertContains(response, "already checked in")
        self.assertEqual(AttendanceRecord.objects.filter(member=self.member).count(), 1)

    def test_check_in_is_blocked_when_gym_is_full(self):
        GymConfiguration.objects.create(pk=1, max_capacity=1)
        other_member = User.objects.create_user(
            username="inside@example.com",
            email="inside@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        AttendanceRecord.objects.create(member=other_member)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("attendance:staff_attendance"),
            {"member_identifier": self.member.email, "action": "check_in"},
            follow=True,
        )
        self.assertContains(response, "maximum capacity")
        self.assertFalse(AttendanceRecord.objects.filter(member=self.member).exists())

    def test_member_can_view_current_occupancy(self):
        AttendanceRecord.objects.create(member=self.member)
        self.client.force_login(self.member)
        response = self.client.get(reverse("attendance:occupancy"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_occupancy"], 1)

    def test_staff_can_filter_attendance_history(self):
        AttendanceRecord.objects.create(member=self.member)
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("attendance:attendance_history"),
            {"q": "attendance-member", "status": "INSIDE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.email)

    def test_staff_can_correct_attendance_with_note(self):
        record = AttendanceRecord.objects.create(member=self.member)
        check_in = timezone.localtime(record.check_in_time)
        check_out = check_in + timedelta(hours=1)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("attendance:correct_attendance", args=[record.pk]),
            {
                "check_in_time": check_in.strftime("%Y-%m-%dT%H:%M"),
                "check_out_time": check_out.strftime("%Y-%m-%dT%H:%M"),
                "correction_note": "Member forgot to check out.",
            },
        )
        self.assertRedirects(response, reverse("attendance:attendance_history"))
        record.refresh_from_db()
        self.assertEqual(record.corrected_by, self.staff)
        self.assertEqual(record.correction_note, "Member forgot to check out.")

    def test_admin_can_update_gym_capacity(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("attendance:capacity_settings"), {"max_capacity": 75}
        )
        self.assertRedirects(response, reverse("attendance:capacity_settings"))
        self.assertEqual(GymConfiguration.get_capacity(), 75)

    def test_capacity_page_uses_capacity_navigation_label(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("attendance:capacity_settings"))
        self.assertContains(response, "Capacity Management")
        self.assertContains(response, "Gym Capacity")

    def test_staff_can_view_attendance_report(self):
        AttendanceRecord.objects.create(member=self.member)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("attendance:attendance_report"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_check_ins"], 1)


# Outdoor activities — Bhavshika

# 2.19 GPS activity (mobile phase); 2.20 Activity history


class OutdoorActivityTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="activity-member@example.com",
            email="activity-member@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        self.other_member = User.objects.create_user(
            username="other-activity@example.com",
            email="other-activity@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        self.client.force_login(self.member)

    def create_activity(self, member=None):
        return OutdoorActivity.objects.create(
            member=member or self.member,
            activity_type="running",
            date=timezone.localdate(),
            distance_km="5.00",
            duration_minutes=30,
        )

    def test_member_can_add_activity(self):
        response = self.client.post(
            reverse("activities:add_activity"),
            {
                "activity_type": "walking",
                "date": timezone.localdate(),
                "distance_km": "3.50",
                "duration_minutes": 45,
            },
        )
        activity = OutdoorActivity.objects.get(member=self.member)
        self.assertRedirects(
            response, reverse("activities:activity_detail", args=[activity.pk])
        )

    def test_future_activity_date_is_rejected(self):
        response = self.client.post(
            reverse("activities:add_activity"),
            {
                "activity_type": "cycling",
                "date": timezone.localdate() + timedelta(days=1),
                "distance_km": "10.00",
                "duration_minutes": 40,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot be in the future")
        self.assertFalse(OutdoorActivity.objects.exists())

    def test_zero_distance_is_rejected(self):
        response = self.client.post(
            reverse("activities:add_activity"),
            {
                "activity_type": "walking",
                "date": timezone.localdate(),
                "distance_km": "0",
                "duration_minutes": 20,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Distance must be greater than zero")
        self.assertFalse(OutdoorActivity.objects.exists())

    def test_activity_list_only_shows_current_member_records(self):
        own_activity = self.create_activity()
        other_activity = self.create_activity(self.other_member)
        response = self.client.get(reverse("activities:activity_list"))
        self.assertContains(
            response, reverse("activities:activity_detail", args=[own_activity.pk])
        )
        self.assertNotContains(
            response, reverse("activities:activity_detail", args=[other_activity.pk])
        )

    def test_member_cannot_view_another_members_activity(self):
        activity = self.create_activity(self.other_member)
        response = self.client.get(
            reverse("activities:activity_detail", args=[activity.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_activity_detail_calculates_average_pace(self):
        activity = self.create_activity()
        response = self.client.get(
            reverse("activities:activity_detail", args=[activity.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pace"], 6.0)

    def test_member_can_delete_activity(self):
        activity = self.create_activity()
        response = self.client.post(
            reverse("activities:delete_activity", args=[activity.pk])
        )
        self.assertRedirects(response, reverse("activities:activity_list"))
        self.assertFalse(OutdoorActivity.objects.filter(pk=activity.pk).exists())


# Notifications and notices — Anjie


User = get_user_model()


class NotificationTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            username="notification_member",
            email="notification-member@example.com",
            password="TestPassword123!",
            role="MEMBER",
        )
        self.other_member = User.objects.create_user(
            username="other_notification_member",
            email="other-notification-member@example.com",
            password="TestPassword123!",
            role="MEMBER",
        )
        self.coach = User.objects.create_user(
            username="notification_coach",
            email="notification-coach@example.com",
            password="TestPassword123!",
            role="COACH",
        )
        self.staff = User.objects.create_user(
            username="notification_staff",
            email="notification-staff@example.com",
            password="TestPassword123!",
            role="STAFF",
        )
        self.admin = User.objects.create_user(
            username="notification_admin",
            email="notification-admin@example.com",
            password="TestPassword123!",
            role="ADMIN",
        )
        self.package = MembershipPackage.objects.create(
            name="Notification Plan",
            slug="notification-plan",
            price=900,
            duration_months=1,
            description="Gym access",
            features="Gym access",
            is_active=True,
        )
        self.membership = Membership.objects.create(
            member=self.member,
            package=self.package,
            start_date=timezone.localdate() - timedelta(days=2),
            end_date=timezone.localdate() + timedelta(days=30),
            status=Membership.Status.ACTIVE,
        )
        self.service = Service.objects.create(
            name="Notification Yoga",
            service_type=Service.Type.YOGA,
            description="Yoga session",
            price=100,
            is_active=True,
        )
        self.session = Session.objects.create(
            service=self.service,
            instructor=self.coach,
            date=timezone.localdate() + timedelta(days=5),
            start_time=time(9, 0),
            end_time=time(10, 0),
            capacity=10,
        )

    def test_member_only_sees_own_notifications(self):
        Notification.objects.create(
            recipient=self.member,
            notification_type=Notification.Type.NOTICE,
            title="Member message",
            message="This belongs to the member.",
        )
        Notification.objects.create(
            recipient=self.other_member,
            notification_type=Notification.Type.NOTICE,
            title="Other message",
            message="This belongs to another member.",
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse("notifications:list"))
        self.assertContains(response, "Member message")
        self.assertNotContains(response, "Other message")

    def test_opening_notification_marks_it_as_read(self):
        notification = Notification.objects.create(
            recipient=self.member,
            notification_type=Notification.Type.BOOKING,
            title="Booking update",
            message="Your booking changed.",
        )
        self.client.force_login(self.member)
        self.client.get(reverse("notifications:detail", args=[notification.id]))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_member_cannot_open_another_users_notification(self):
        notification = Notification.objects.create(
            recipient=self.other_member,
            notification_type=Notification.Type.NOTICE,
            title="Private update",
            message="Private message.",
        )
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("notifications:detail", args=[notification.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_mark_all_as_read(self):
        for number in range(2):
            Notification.objects.create(
                recipient=self.member,
                notification_type=Notification.Type.NOTICE,
                title=f"Update {number}",
                message="Message",
            )
        self.client.force_login(self.member)
        self.client.post(reverse("notifications:mark_all_as_read"))
        self.assertFalse(
            Notification.objects.filter(recipient=self.member, is_read=False).exists()
        )

    def test_navbar_shows_unread_count(self):
        Notification.objects.create(
            recipient=self.member,
            notification_type=Notification.Type.NOTICE,
            title="Unread update",
            message="Message",
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.context["unread_notification_count"], 1)

    def test_admin_can_create_notice(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("notifications:notice_create"),
            {
                "title": "Holiday Hours",
                "message": "The gym closes at 18:00.",
                "publish_date": timezone.localdate().isoformat(),
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("notifications:notice_list"))
        self.assertTrue(Notice.objects.filter(title="Holiday Hours").exists())

    def test_member_cannot_manage_notices(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("notifications:notice_list"))
        self.assertEqual(response.status_code, 403)

    def test_current_notice_appears_on_notification_page(self):
        Notice.objects.create(
            title="Pool Maintenance",
            message="The pool is closed today.",
            publish_date=timezone.localdate(),
            is_active=True,
            created_by=self.admin,
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse("notifications:list"))
        self.assertContains(response, "Pool Maintenance")

    def test_successful_booking_creates_notification(self):
        self.client.force_login(self.member)
        self.client.post(reverse("bookings:book_session", args=[self.session.id]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member, title="Booking Confirmed"
            ).exists()
        )

    def test_member_cancellation_creates_notification(self):
        booking = Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.member)
        self.client.post(reverse("bookings:cancel_booking", args=[booking.id]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member, title="Booking Cancelled"
            ).exists()
        )

    def test_session_cancellation_notifies_affected_member(self):
        Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.staff)
        self.client.post(reverse("bookings:session_cancel", args=[self.session.id]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member, title="Session Cancelled"
            ).exists()
        )

    def test_membership_reminder_is_not_duplicated(self):
        self.membership.end_date = timezone.localdate() + timedelta(days=5)
        self.membership.save(update_fields=["end_date"])
        self.client.force_login(self.member)
        self.client.get(reverse("memberships:current_membership"))
        self.client.get(reverse("memberships:current_membership"))
        reminders = Notification.objects.filter(
            recipient=self.member, title="Membership Expiry Reminder"
        )
        self.assertEqual(reminders.count(), 1)


# Public pages and dashboard summaries — Shared

# 1.7 Contact enquiries; 4.14 Public contact details; 4.15 Enquiry management


class HomePageTests(TestCase):

    def test_home_page_loads(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "public/home.html")

    def test_home_page_contains_figma_hero_copy(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "RUN THE GYM.")
        self.assertContains(response, "OWN THE")
        self.assertContains(response, "MOMENT.")
        self.assertContains(response, "Get Started Free")
        self.assertContains(response, "Members in gym")

    def test_home_page_uses_current_database_statistics(self):
        member = User.objects.create_user(
            username="live-member@example.com",
            email="live-member@example.com",
            password="TestPass123!",
            role=User.Role.MEMBER,
        )
        User.objects.create_user(
            username="live-coach@example.com",
            email="live-coach@example.com",
            password="TestPass123!",
            role=User.Role.COACH,
        )
        AttendanceRecord.objects.create(member=member)
        WorkoutSession.objects.create(
            member=member, completed_at=timezone.now(), duration_minutes=30
        )
        service = Service.objects.create(
            name="Live Class", service_type=Service.Type.FITNESS
        )
        Session.objects.create(
            service=service,
            date=timezone.localdate(),
            start_time=time(0, 0),
            end_time=time(23, 59, 59),
            capacity=20,
            status=Session.Status.SCHEDULED,
        )
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.context["live_stats"]["members_in_gym"], 1)
        self.assertEqual(response.context["live_stats"]["workouts_today"], 1)
        self.assertEqual(response.context["live_stats"]["calories_today"], 210)
        self.assertEqual(response.context["live_stats"]["classes_running"], 1)
        self.assertEqual(response.context["live_stats"]["active_members"], 1)
        self.assertEqual(response.context["live_stats"]["coach_count"], 1)


class ContactPageTests(TestCase):

    def test_contact_page_loads_and_marks_navigation_active(self):
        response = self.client.get(reverse("core:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "public/contact.html")
        self.assertContains(response, "We'd Love to")
        self.assertContains(
            response,
            f"""class="nav-link active" href="{reverse('core:contact')}">Contact""",
        )

    def test_contact_form_sends_message(self):
        response = self.client.post(
            reverse("core:contact"),
            {
                "full_name": "Test Member",
                "email": "member@example.com",
                "topic": "MEMBERSHIP",
                "message": "Please send me more information about the plans.",
            },
        )
        self.assertRedirects(response, reverse("core:contact"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["hello@fitsync.com"])
        self.assertIn("Test Member", mail.outbox[0].body)


class PublicNavigationTests(TestCase):

    def test_each_public_page_marks_its_navigation_link_active(self):
        routes = [
            "core:home",
            "aboutus:index",
            "memberships:public_packages",
            "core:features",
            "bookings:schedule",
            "ourteam:index",
            "core:contact",
        ]
        for route_name in routes:
            url = reverse(route_name)
            response = self.client.get(url)
            page = response.content.decode()
            pattern = f'class="nav-link active"[^>]*href="{re.escape(url)}"'
            self.assertRegex(page, pattern)

    def test_signed_in_navigation_uses_compact_account_menu(self):
        user = User.objects.create_user(
            username="header-member@example.com",
            email="header-member@example.com",
            password="TestPass123!",
            first_name="Header",
            last_name="Member",
            role=User.Role.MEMBER,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "navbar-account-toggle")
        self.assertContains(response, "Header Member")
        self.assertContains(response, "data-theme-toggle")


# Integration checks — Shared


class SingleApplicationStructureTests(SimpleTestCase):
    def test_exactly_one_custom_application(self):
        custom = [
            config.name
            for config in apps.get_app_configs()
            if not config.name.startswith("django.")
        ]
        self.assertEqual(custom, ["gym"])

    def test_business_models_live_in_one_module(self):
        models = list(apps.get_app_config("gym").get_models())
        self.assertEqual(len(models), 26)
        self.assertTrue(all(model.__module__ == "gym.models" for model in models))
        self.assertEqual(settings.AUTH_USER_MODEL, "gym.User")

    def test_one_of_each_main_source_file(self):
        for name in (
            "models.py",
            "forms.py",
            "views.py",
            "admin.py",
            "apps.py",
            "tests.py",
        ):
            self.assertEqual(
                sorted(p.name for p in Path(settings.BASE_DIR, "gym").glob(name)),
                [name],
            )
            self.assertFalse(Path(settings.BASE_DIR, "fitsync", name).exists())
        self.assertTrue(Path(settings.BASE_DIR, "fitsync", "urls.py").is_file())
        self.assertFalse(Path(settings.BASE_DIR, "gym", "urls.py").exists())
        for old in (
            "accounts",
            "memberships",
            "bookings",
            "workouts",
            "attendance",
            "activities",
            "notifications",
            "core",
            "ourteam",
            "aboutus",
            "reports",
        ):
            self.assertFalse(Path(settings.BASE_DIR, old).exists())

    def test_route_groups_are_namespaces_not_apps(self):
        namespaces = {
            item.namespace
            for item in get_resolver().url_patterns
            if isinstance(item, URLResolver)
        }
        self.assertEqual(
            namespaces,
            {
                "admin",
                "accounts",
                "memberships",
                "bookings",
                "workouts",
                "attendance",
                "activities",
                "notifications",
                "core",
                "ourteam",
                "aboutus",
            },
        )

    def test_no_legacy_python_imports(self):
        old_apps = {
            "accounts",
            "memberships",
            "bookings",
            "workouts",
            "attendance",
            "activities",
            "notifications",
            "core",
            "ourteam",
            "aboutus",
            "reports",
        }
        for path in Path(settings.BASE_DIR, "gym").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and not node.level:
                    self.assertNotIn(
                        (node.module or "").split(".")[0], old_apps, str(path)
                    )
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name.split(".")[0], old_apps, str(path))

    def test_role_template_folders_and_shared_library(self):
        root = Path(settings.BASE_DIR, "templates")
        for name in [
            "authentication",
            "public",
            "member",
            "coach",
            "staff",
            "admin_dashboard",
            "shared",
            "includes",
            "layouts",
        ]:
            self.assertTrue((root / name).is_dir())
        self.assertTrue((root / "shared/exercise_library.html").is_file())
        self.assertFalse(Path(settings.BASE_DIR, "gym/services.py").exists())
        self.assertFalse(Path(settings.BASE_DIR, "gym/decorators.py").exists())
        self.assertTrue(Path(settings.BASE_DIR, "gym/permissions.py").exists())


# Public team and contact content — Shared
class PublicContentTests(TestCase):
    data = {
        "full_name": "Test Sender",
        "email": "sender@example.com",
        "topic": "CLASSES",
        "message": "Please tell me about classes.",
    }

    def setUp(self):
        # Test the optional seed command with an empty content table.
        TeamMember.objects.all().delete()
        GymSettings.objects.all().delete()
        self.admin_user = User.objects.create_user(
            username="content-admin",
            email="content-admin@example.com",
            role=User.Role.ADMIN,
        )
        self.coach = User.objects.create_user(
            username="existing-coach",
            email="chris.bumstead@fitsync.com",
            role=User.Role.COACH,
        )
        self.demo = User.objects.create_user(
            username="demo-avatar", email="member@fitsync.com", role=User.Role.MEMBER
        )
        call_command("seed_public_content", stdout=StringIO())

    def login_admin(self):
        self.client.force_login(self.admin_user)

    def person_data(self, **changes):
        return {
            "display_name": "New Coach",
            "slug": "new-coach",
            "job_title": "Coach",
            "department": "coaching",
            "bio": "Test biography",
            "sort_order": 10,
            "is_active": "on",
            **changes,
        }

    def management_urls(self):
        person = TeamMember.objects.first()
        enquiry = ContactMessage.objects.create(**self.data)
        return [
            reverse("core:manage_settings"),
            reverse("core:manage_team"),
            reverse("core:manage_team_add"),
            reverse("core:manage_team_edit", args=[person.pk]),
            reverse("core:manage_inbox"),
            reverse("core:manage_enquiry", args=[enquiry.pk]),
        ]

    def test_seed_reuses_accounts_and_preserves_edits(self):
        person = TeamMember.objects.get(user=self.coach)
        person.display_name = "Renamed existing coach"
        person.bio = "Edited biography"
        person.save()
        before = list(
            User.objects.values_list(
                "pk", "password", "role", "is_staff", "is_superuser"
            )
        )
        call_command("seed_public_content", stdout=StringIO())
        person.refresh_from_db()
        self.assertEqual(person.display_name, "Renamed existing coach")
        self.assertEqual(TeamMember.objects.count(), 8)
        self.assertEqual(
            before,
            list(
                User.objects.values_list(
                    "pk", "password", "role", "is_staff", "is_superuser"
                )
            ),
        )

    def test_public_team_reflects_edits_and_hides_inactive(self):
        person = TeamMember.objects.get(user=self.coach)
        person.display_name = "Database Coach Name"
        person.save()
        self.assertContains(
            self.client.get(reverse("ourteam:index")), "Database Coach Name"
        )
        person.is_active = False
        person.save()
        self.assertNotContains(
            self.client.get(reverse("ourteam:index")), "Database Coach Name"
        )

    def test_contacts_are_database_backed_and_singleton(self):
        gym = GymSettings.load()
        gym.address = "Updated address"
        gym.public_email = "office@example.com"
        gym.save()
        call_command("seed_public_content", stdout=StringIO())
        response = self.client.get(reverse("core:contact"))
        self.assertContains(response, "Updated address")
        self.assertContains(response, "office@example.com")
        self.assertEqual(GymSettings.objects.count(), 1)

    @override_settings(CONTACT_RECIPIENT_EMAIL="desk@example.com")
    def test_contact_saves_and_notifies_configured_recipient(self):
        response = self.client.post(reverse("core:contact"), self.data, follow=True)
        self.assertContains(response, "Your message has been received")
        enquiry = ContactMessage.objects.get()
        self.assertTrue(enquiry.email_notification_sent)
        self.assertEqual(mail.outbox[0].to, ["desk@example.com"])
        self.assertEqual(enquiry.status, "NEW")

    @patch("gym.views.send_mail", side_effect=SMTPException("mail unavailable"))
    def test_email_failure_does_not_lose_message(self, send):
        self.assertEqual(
            self.client.post(reverse("core:contact"), self.data).status_code, 302
        )
        self.assertFalse(ContactMessage.objects.get().email_notification_sent)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    @patch("gym.views.send_mail")
    def test_console_backend_does_not_claim_email_sent(self, send):
        self.client.post(reverse("core:contact"), self.data)
        send.assert_not_called()
        self.assertFalse(ContactMessage.objects.get().email_notification_sent)

    def test_invalid_contact_is_not_saved(self):
        self.assertEqual(
            self.client.post(
                reverse("core:contact"), {**self.data, "email": "bad"}
            ).status_code,
            200,
        )
        self.assertFalse(ContactMessage.objects.exists())

    def test_anonymous_management_redirects(self):
        for url in self.management_urls():
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_member_coach_and_staff_cannot_manage_content(self):
        urls = self.management_urls()
        for role in [User.Role.MEMBER, User.Role.COACH, User.Role.STAFF]:
            user = User.objects.create_user(
                username=role, email=f"{role}@example.com", role=role
            )
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403, url)
                self.assertEqual(self.client.post(url, {}).status_code, 403, url)

    def test_normal_admin_without_django_staff_flag_can_manage(self):
        self.assertFalse(self.admin_user.is_staff)
        self.assertFalse(self.admin_user.is_superuser)
        self.login_admin()
        for url in self.management_urls():
            self.assertEqual(self.client.get(url).status_code, 200, url)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertContains(response, "Team Profiles")
        self.assertContains(response, "Contact Enquiries")

    def test_add_profile_links_existing_coach_without_creating_account(self):
        self.login_admin()
        before = User.objects.count()
        old = TeamMember.objects.get(user=self.coach)
        old.user = None
        old.save()
        response = self.client.post(
            reverse("core:manage_team_add"), self.person_data(user=self.coach.pk)
        )
        self.assertRedirects(response, reverse("core:manage_team"))
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(
            TeamMember.objects.get(slug="new-coach").user_id, self.coach.pk
        )

    def test_member_cannot_be_linked_as_team_account(self):
        self.login_admin()
        response = self.client.post(
            reverse("core:manage_team_add"), self.person_data(user=self.demo.pk)
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TeamMember.objects.filter(slug="new-coach").exists())

    def test_new_featured_profile_replaces_previous(self):
        self.login_admin()
        self.client.post(
            reverse("core:manage_team_add"), self.person_data(is_featured="on")
        )
        self.assertEqual(TeamMember.objects.filter(is_featured=True).count(), 1)
        self.assertTrue(TeamMember.objects.get(slug="new-coach").is_featured)

    def test_visibility_is_post_only_and_does_not_deactivate_account(self):
        self.login_admin()
        person = TeamMember.objects.get(user=self.coach)
        url = reverse("core:manage_team_toggle", args=[person.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        person.refresh_from_db()
        self.coach.refresh_from_db()
        self.assertFalse(person.is_active)
        self.assertTrue(self.coach.is_active)

    def test_enquiry_status_notes_and_private_display(self):
        enquiry = ContactMessage.objects.create(**self.data)
        self.assertNotContains(
            self.client.get(reverse("core:contact")), self.data["message"]
        )
        self.login_admin()
        response = self.client.post(
            reverse("core:manage_enquiry", args=[enquiry.pk]),
            {"status": "REPLIED", "staff_notes": "Private follow-up"},
        )
        self.assertEqual(response.status_code, 302)
        enquiry.refresh_from_db()
        self.assertEqual(enquiry.status, "REPLIED")
        self.assertEqual(enquiry.staff_notes, "Private follow-up")
        self.assertEqual(enquiry.message, self.data["message"])

    def test_invalid_enquiry_status_is_rejected(self):
        enquiry = ContactMessage.objects.create(**self.data)
        self.login_admin()
        self.assertEqual(
            self.client.post(
                reverse("core:manage_enquiry", args=[enquiry.pk]), {"status": "INVALID"}
            ).status_code,
            200,
        )
        enquiry.refresh_from_db()
        self.assertEqual(enquiry.status, "NEW")

    def test_management_forms_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin_user)
        self.assertEqual(
            client.post(
                reverse("core:manage_team_add"), self.person_data()
            ).status_code,
            403,
        )

    def test_database_avatar_survives_email_change_and_upload_wins(self):
        profile = self.demo.member_profile
        self.assertTrue(profile.avatar_url.endswith("member-dashboard/lionel.png"))
        self.demo.email = "changed-avatar@example.com"
        self.demo.save()
        self.client.force_login(self.demo)
        self.assertContains(
            self.client.get(reverse("core:home")), "member-dashboard/lionel.png"
        )
        profile.profile_picture = "profile_pics/upload.jpg"
        profile.save()
        self.assertTrue(profile.avatar_url.endswith("profile_pics/upload.jpg"))

    def test_enquiry_list_paginates_and_filters(self):
        ContactMessage.objects.bulk_create(
            [
                ContactMessage(**{**self.data, "full_name": f"Sender {i}"})
                for i in range(25)
            ]
        )
        ContactMessage.objects.create(
            **{**self.data, "full_name": "Archived Sender", "status": "ARCHIVED"}
        )
        self.login_admin()
        response = self.client.get(reverse("core:manage_inbox"))
        self.assertEqual(len(response.context["enquiries"]), 20)
        response = self.client.get(reverse("core:manage_inbox"), {"status": "ARCHIVED"})
        self.assertEqual(response.context["enquiries"].paginator.count, 1)

    def test_untrusted_content_is_escaped(self):
        enquiry = ContactMessage.objects.create(
            **{**self.data, "message": "<script>alert(1)</script>"}
        )
        self.login_admin()
        response = self.client.get(reverse("core:manage_enquiry", args=[enquiry.pk]))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")


# Default team and contact information — Shared
class PublicContentMigrationTests(TestCase):
    def run_content_migration(self):
        migration = importlib.import_module(
            "gym.migrations.0006_default_public_content"
        )
        migration.add_public_content(apps, SimpleNamespace(connection=connection))

    def test_migrate_provides_public_content_without_login_accounts(self):
        self.assertEqual(TeamMember.objects.count(), 8)
        self.assertEqual(GymSettings.objects.count(), 1)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertContains(self.client.get(reverse("ourteam:index")), "Chris Bumstead")
        self.assertContains(
            self.client.get(reverse("core:contact")), "hello@fitsync.com"
        )

    def test_repeating_content_migration_preserves_edits(self):
        person = TeamMember.objects.get(slug="chris-bumstead")
        person.display_name = "Updated coach name"
        person.bio = "Biography edited by an administrator."
        person.photo = "team/edited-photo.jpg"
        person.is_active = False
        person.save()
        gym = GymSettings.objects.get(pk=1)
        gym.address = "Updated gym address"
        gym.public_email = "office@example.com"
        gym.save()
        self.run_content_migration()
        self.run_content_migration()
        person.refresh_from_db()
        gym.refresh_from_db()
        self.assertEqual(person.display_name, "Updated coach name")
        self.assertEqual(person.bio, "Biography edited by an administrator.")
        self.assertEqual(person.photo.name, "team/edited-photo.jpg")
        self.assertFalse(person.is_active)
        self.assertEqual(gym.address, "Updated gym address")
        self.assertEqual(gym.public_email, "office@example.com")
        self.assertEqual(TeamMember.objects.count(), 8)

    def test_missing_profile_can_link_existing_coach_without_changing_account(self):
        TeamMember.objects.filter(slug="chris-bumstead").delete()
        coach = User.objects.create_user(
            username="existing-coach",
            email="chris.bumstead@fitsync.com",
            password="ExistingPassword123!",
            role=User.Role.COACH,
        )
        password_hash = coach.password
        self.run_content_migration()
        coach.refresh_from_db()
        self.assertEqual(
            TeamMember.objects.get(slug="chris-bumstead").user_id, coach.pk
        )
        self.assertEqual(coach.password, password_hash)
        self.assertEqual(coach.role, User.Role.COACH)
        self.assertFalse(coach.is_staff)
        self.assertFalse(coach.is_superuser)
        self.assertEqual(User.objects.count(), 1)

    def test_existing_featured_person_is_not_replaced(self):
        TeamMember.objects.filter(department="founder").delete()
        person = TeamMember.objects.get(slug="sarah-safforti")
        person.is_featured = True
        person.save()
        self.run_content_migration()
        person.refresh_from_db()
        self.assertTrue(person.is_featured)
        self.assertEqual(TeamMember.objects.filter(is_featured=True).count(), 1)

    def test_existing_profile_link_is_preserved(self):
        coach = User.objects.create_user(
            username="chosen-coach", email="chosen@example.com", role=User.Role.COACH
        )
        person = TeamMember.objects.get(slug="chris-bumstead")
        person.user = coach
        person.save()
        self.run_content_migration()
        person.refresh_from_db()
        self.assertEqual(person.user_id, coach.pk)
