from datetime import date, timedelta

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
            reverse("memberships:admin_payment_list"),
            {"q": "search-member"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.payment.receipt_number)

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
            {
                "payment_method": Payment.Method.CASH,
                "status": Payment.Status.SUCCESS,
            },
        )
        self.assertRedirects(
            response,
            reverse("memberships:admin_payment_detail", args=[self.payment.pk]),
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.payment_method, Payment.Method.CASH)
