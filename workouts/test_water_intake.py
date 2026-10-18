from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import WaterIntake


class WaterIntakeTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            username="water_member", email="water@example.com", role="MEMBER",
        )
        self.today = timezone.localdate()
        self.url = reverse("workouts:water_intake")
        self.client.force_login(self.member)

    def test_saving_daily_total_updates_existing_record_and_dashboard(self):
        data = {"recorded_date": self.today, "litres": "1.25"}
        self.assertRedirects(self.client.post(self.url, data), self.url)
        data["litres"] = "2.50"
        self.assertRedirects(self.client.post(self.url, data), self.url)

        self.assertEqual(WaterIntake.objects.filter(member=self.member).count(), 1)
        response = self.client.get(reverse("accounts:member_dashboard"))
        self.assertEqual(response.context["today_water_litres"], WaterIntake.objects.get().litres)
        self.assertContains(response, "2.50")

    def test_rejects_invalid_totals_and_future_dates(self):
        cases = [
            {"recorded_date": self.today, "litres": "-1"},
            {"recorded_date": self.today, "litres": "abc"},
            {"recorded_date": self.today + timedelta(days=1), "litres": "1"},
        ]
        for data in cases:
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(WaterIntake.objects.exists())

    def test_records_are_private_and_previous_days_do_not_change_today(self):
        other_member = User.objects.create_user(
            username="other_water", email="other_water@example.com", role="MEMBER",
        )
        WaterIntake.objects.create(member=other_member, recorded_date=self.today, litres="3.75")
        yesterday = self.today - timedelta(days=1)
        self.client.post(self.url, {"recorded_date": yesterday, "litres": "1.50"})

        response = self.client.get(self.url)
        self.assertNotContains(response, "3.75")
        self.assertEqual(response.context["today_litres"], 0)
        self.client.post(self.url, {"recorded_date": self.today, "litres": "0.50"})
        other_record = WaterIntake.objects.get(member=other_member)
        self.assertEqual(str(other_record.litres), "3.75")

    def test_anonymous_and_non_members_cannot_track_water(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        coach = User.objects.create_user(
            username="water_coach", email="water_coach@example.com", role="COACH",
        )
        self.client.force_login(coach)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"recorded_date": self.today, "litres": "1"}).status_code, 403)
