from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, Service, Session
from memberships.models import Membership, MembershipPackage

from .models import Notice, Notification


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
        response = self.client.get(reverse("notifications:detail", args=[notification.id]))
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
        self.assertFalse(Notification.objects.filter(recipient=self.member, is_read=False).exists())

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
                recipient=self.member,
                title="Booking Confirmed",
            ).exists()
        )

    def test_member_cancellation_creates_notification(self):
        booking = Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.member)
        self.client.post(reverse("bookings:cancel_booking", args=[booking.id]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member,
                title="Booking Cancelled",
            ).exists()
        )

    def test_session_cancellation_notifies_affected_member(self):
        Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.staff)
        self.client.post(reverse("bookings:session_cancel", args=[self.session.id]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member,
                title="Session Cancelled",
            ).exists()
        )

    def test_membership_reminder_is_not_duplicated(self):
        self.membership.end_date = timezone.localdate() + timedelta(days=5)
        self.membership.save(update_fields=["end_date"])
        self.client.force_login(self.member)
        self.client.get(reverse("memberships:current_membership"))
        self.client.get(reverse("memberships:current_membership"))
        reminders = Notification.objects.filter(
            recipient=self.member,
            title="Membership Expiry Reminder",
        )
        self.assertEqual(reminders.count(), 1)
