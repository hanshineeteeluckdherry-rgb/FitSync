from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking, Service, Session


class CoachSessionTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(username="teacher", email="teacher@test.com", role="COACH")
        self.other = User.objects.create_user(username="other", email="other@test.com", role="COACH")
        self.member = User.objects.create_user(username="member", email="member@test.com", role="MEMBER")
        self.service = Service.objects.create(name="Strength Class", service_type="FITNESS")
        self.day = timezone.localdate() + timedelta(days=5)
        self.session = Session.objects.create(service=self.service, instructor=self.coach,
            date=self.day, start_time=time(9), end_time=time(10), capacity=10)
        self.other_session = Session.objects.create(service=self.service, instructor=self.other,
            date=self.day, start_time=time(11), end_time=time(12), capacity=10)
        self.client.force_login(self.coach)

    def payload(self, **changes):
        data = {"service": self.service.pk, "instructor": self.other.pk,
                "date": self.day.isoformat(), "start_time": "13:00", "end_time": "14:00",
                "capacity": 12, "status": "CANCELLED"}
        data.update(changes)
        return data

    def test_coach_can_create_class_only_for_themselves(self):
        response = self.client.post(reverse("bookings:session_create"), self.payload())
        self.assertRedirects(response, reverse("bookings:session_list"))
        session = Session.objects.latest("pk")
        self.assertEqual(session.instructor, self.coach)
        self.assertEqual(session.status, Session.Status.SCHEDULED)
        self.assertContains(self.client.get(reverse("bookings:schedule")), "Strength Class")

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
        response = self.client.post(reverse("bookings:session_edit", args=[self.session.pk]), self.payload())
        self.assertRedirects(response, reverse("bookings:session_list"))
        self.session.refresh_from_db()
        self.assertEqual(self.session.instructor, self.coach)
        self.assertEqual(self.session.start_time, time(13))

    def test_cancel_updates_bookings_and_notifies_member(self):
        booking = Booking.objects.create(member=self.member, session=self.session)
        self.assertEqual(self.client.get(reverse("bookings:session_roster", args=[self.session.pk])).status_code, 200)
        response = self.client.post(reverse("bookings:session_cancel", args=[self.session.pk]))
        self.assertRedirects(response, reverse("bookings:session_list"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        from notifications.models import Notification
        self.assertTrue(Notification.objects.filter(recipient=self.member, title="Session Cancelled").exists())

    def test_invalid_times_and_overlaps_are_rejected(self):
        for changes in [{"start_time": "09:30", "end_time": "10:30"},
                        {"date": (self.day - timedelta(days=10)).isoformat()},
                        {"start_time": "14:00", "end_time": "13:00"}, {"capacity": 0}]:
            response = self.client.post(reverse("bookings:session_create"), self.payload(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(Session.objects.count(), 2)

    def test_member_cannot_manage_classes_and_coach_cannot_manage_services(self):
        self.assertEqual(self.client.get(reverse("bookings:service_create")).status_code, 403)
        self.client.force_login(self.member)
        for name in ["session_list", "session_create"]:
            self.assertEqual(self.client.get(reverse(f"bookings:{name}")).status_code, 403)

    def test_staff_form_has_scrollable_layout_and_new_service_types(self):
        from bookings.forms import ServiceForm
        from memberships.forms import MembershipPackageForm
        staff = User.objects.create_user(username="staff", email="staff@test.com", role="STAFF")
        self.client.force_login(staff)
        response = self.client.get(reverse("bookings:session_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="dashboard-scroll-content"')
        for value in ["PILATES", "BOXING", "HIIT", "CYCLING", "STRENGTH_TRAINING"]:
            self.assertIn(value, dict(ServiceForm().fields["service_type"].choices))
            self.assertIn(value, dict(MembershipPackageForm().fields["allowed_service_types"].choices))
