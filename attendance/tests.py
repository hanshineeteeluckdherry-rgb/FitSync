from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from memberships.models import Membership, MembershipPackage

from .models import AttendanceRecord, GymConfiguration, MemberQRCode


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
            reverse("attendance:capacity_settings"),
            {"max_capacity": 75},
        )

        self.assertRedirects(response, reverse("attendance:capacity_settings"))
        self.assertEqual(GymConfiguration.get_capacity(), 75)

    def test_staff_can_view_attendance_report(self):
        AttendanceRecord.objects.create(member=self.member)
        self.client.force_login(self.staff)

        response = self.client.get(reverse("attendance:attendance_report"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_check_ins"], 1)
