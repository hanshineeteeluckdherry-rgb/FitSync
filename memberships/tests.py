from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Membership, MembershipPackage, Payment


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
        response = self.client.get(reverse("memberships:auth_required", args=[self.package.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in to continue")
        self.assertContains(response, "AUTHENTICATION REQUIRED")

    def test_authenticated_member_skips_auth_gate(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("memberships:auth_required", args=[self.package.pk]))
        self.assertRedirects(response, reverse("memberships:checkout", args=[self.package.pk]))

    def test_member_checkout_success_creates_membership(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("memberships:checkout", args=[self.package.pk]),
            {
                "payer_name": "Test Member",
                "payment_method": Payment.Method.CARD,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Membership.objects.filter(member=self.member).count(), 1)
        self.assertEqual(Payment.objects.get(member=self.member).status, Payment.Status.SUCCESS)

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
        self.assertEqual(Payment.objects.get(member=self.member).status, Payment.Status.FAILED)


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
