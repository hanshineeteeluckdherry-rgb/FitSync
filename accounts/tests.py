from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import CoachAssignment, MemberProfile, User


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
        self.assertEqual(User.objects.filter(email__iexact="same@example.com").count(), 1)

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
        self.assertContains(response, "lionel-messi.png")
        self.assertContains(response, "fitsync-logo.png")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "Demo Accounts")
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
            reverse("accounts:login"),
            {"email": user.email, "password": self.password},
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


class RolePermissionTests(AccountTestMixin, TestCase):
    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("accounts:member_dashboard"))
        expected = f"{reverse('accounts:login')}?next={reverse('accounts:member_dashboard')}"
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
            reverse("accounts:password_reset"),
            {"email": self.user.email},
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
            CoachAssignment.objects.filter(coach=self.coach, member=self.member1).exists()
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
