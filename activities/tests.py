from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import OutdoorActivity


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
            response,
            reverse("activities:activity_detail", args=[activity.pk]),
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

        self.assertContains(response, reverse("activities:activity_detail", args=[own_activity.pk]))
        self.assertNotContains(response, reverse("activities:activity_detail", args=[other_activity.pk]))

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
