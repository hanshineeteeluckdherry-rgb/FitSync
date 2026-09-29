from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from memberships.models import Membership, MembershipPackage

from .models import Booking, Service, Session


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
            reverse(
                "bookings:book_session",
                args=[self.session.id],
            )
        )

        self.assertRedirects(response, reverse("bookings:schedule"))

        self.assertTrue(
            Booking.objects.filter(
                member=self.member,
                session=self.session,
                status=Booking.Status.CONFIRMED,
            ).exists()
        )

    def test_member_without_active_membership_cannot_book(self):
        """A member without an active membership should be blocked."""

        self.membership.delete()

        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "bookings:book_session",
                args=[self.session.id],
            ),
            follow=True,
        )

        self.assertContains(
            response,
            "You need an active membership to book a session.",
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

        booking_url = reverse(
            "bookings:book_session",
            args=[self.session.id],
        )

        self.client.post(booking_url)
        self.client.post(booking_url)

        confirmed_count = Booking.objects.filter(
            member=self.member,
            session=self.session,
            status=Booking.Status.CONFIRMED,
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
            member=other_member,
            session=self.session,
            status=Booking.Status.CONFIRMED,
        )

        self.client.force_login(self.member)

        self.client.post(
            reverse(
                "bookings:book_session",
                args=[self.session.id],
            )
        )

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
            member=self.member,
            session=self.session,
            status=Booking.Status.CONFIRMED,
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
            reverse(
                "bookings:book_session",
                args=[overlapping_session.id],
            ),
            follow=True,
        )

        self.assertContains(
            response,
            "You already have another booking at this time.",
        )

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
            member=self.member,
            session=self.session,
            status=Booking.Status.CONFIRMED,
        )

        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "bookings:cancel_booking",
                args=[booking.id],
            )
        )

        self.assertRedirects(response, reverse("bookings:my_bookings"))

        booking.refresh_from_db()

        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)
        self.assertTrue(Booking.objects.filter(id=booking.id).exists())
