import re
from datetime import time

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceRecord
from bookings.models import Service, Session
from workouts.models import WorkoutSession


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

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
            member=member,
            completed_at=timezone.now(),
            duration_minutes=30,
        )
        service = Service.objects.create(
            name="Live Class",
            service_type=Service.Type.FITNESS,
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
        self.assertTemplateUsed(response, "core/contact.html")
        self.assertContains(response, "We'd Love to")
        self.assertContains(
            response,
            f'class="nav-link active" href="{reverse("core:contact")}">Contact',
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
            pattern = rf'class="nav-link active"[^>]*href="{re.escape(url)}"'
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
