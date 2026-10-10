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

    def test_plan_can_restrict_service_types(self):
        self.package.allowed_service_types = Service.Type.ZUMBA
        self.package.save(update_fields=["allowed_service_types"])
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("bookings:book_session", args=[self.session.id]),
            follow=True,
        )

        self.assertContains(
            response,
            "Your membership plan does not include this service.",
        )
        self.assertFalse(
            Booking.objects.filter(member=self.member, session=self.session).exists()
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
        response = self.client.get(reverse("bookings:session_detail", args=[self.session.id]))
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
            reverse("bookings:book_session", args=[started_session.id]),
            follow=True,
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
            reverse("bookings:cancel_booking", args=[booking.id]),
            follow=True,
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
        response = self.client.get(reverse("bookings:booking_detail", args=[booking.id]))
        self.assertEqual(response.status_code, 200)

        other_member = User.objects.create_user(
            username="other_detail_member",
            password="TestPassword123!",
            role="MEMBER",
        )
        self.client.force_login(other_member)
        response = self.client.get(reverse("bookings:booking_detail", args=[booking.id]))
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
        self.assertTrue(Session.objects.filter(date=timezone.localdate() + timedelta(days=12)).exists())

    def test_member_cannot_open_session_management(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("bookings:session_list"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_session_roster(self):
        Booking.objects.create(member=self.member, session=self.session)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("bookings:session_roster", args=[self.session.id]))
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
            {"date_from": self.session.date.isoformat(), "date_to": self.session.date.isoformat()},
        )
        self.assertEqual(response.context["total_bookings"], 1)
        self.assertContains(response, "Evening Fitness")

    def test_service_with_sessions_is_deactivated_instead_of_deleted(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("bookings:service_delete", args=[self.service.id]))
        self.service.refresh_from_db()
        self.assertFalse(self.service.is_active)
