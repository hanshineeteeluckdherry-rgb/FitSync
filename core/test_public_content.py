from io import StringIO
from smtplib import SMTPException
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import MemberProfile, User
from core.models import ContactMessage, GymSettings
from ourteam.models import TeamMember


class EditablePublicContentTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(username="existing", email="chris.bumstead@fitsync.com", role="COACH")
        self.demo = User.objects.create_user(username="member", email="member@fitsync.com", role="MEMBER")
        call_command("seed_public_content", stdout=StringIO())

    def test_seed_reuses_existing_accounts_and_preserves_renamed_profiles(self):
        person = TeamMember.objects.get(user=self.coach)
        person.display_name = "Updated Coach Name"
        person.bio = "Edited in admin."
        person.save()
        call_command("seed_public_content", stdout=StringIO())
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(TeamMember.objects.count(), 8)
        person.refresh_from_db()
        self.assertEqual(person.bio, "Edited in admin.")
        self.assertEqual(person.display_name, "Updated Coach Name")

    def test_team_page_reads_edits_and_hides_inactive_profiles(self):
        person = TeamMember.objects.get(user=self.coach)
        person.display_name = "Edited Public Name"
        person.bio = "Database biography"
        person.save()
        response = self.client.get(reverse("ourteam:index"))
        self.assertContains(response, "Edited Public Name")
        self.assertContains(response, "Database biography")
        person.is_active = False
        person.save()
        self.assertNotContains(self.client.get(reverse("ourteam:index")), "Edited Public Name")

    def test_contact_details_are_editable_and_seed_does_not_overwrite(self):
        gym = GymSettings.load()
        gym.address = "New gym address"
        gym.phone = "+230 1234 5678"
        gym.public_email = "office@example.com"
        gym.opening_hours = "Monday 08:00-17:00\nClosed Sunday"
        gym.save()
        call_command("seed_public_content", stdout=StringIO())
        response = self.client.get(reverse("core:contact"))
        self.assertContains(response, "New gym address")
        self.assertContains(response, "tel:+23012345678")
        self.assertContains(response, "office@example.com")
        self.assertContains(response, "Closed Sunday")
        self.assertEqual(GymSettings.objects.count(), 1)

    def test_avatar_is_not_tied_to_email_and_upload_takes_priority(self):
        profile = self.demo.member_profile
        self.assertTrue(profile.avatar_url.endswith("member-dashboard/lionel.png"))
        self.demo.email = "changed@example.com"
        self.demo.save()
        self.client.force_login(self.demo)
        self.assertContains(self.client.get(reverse("core:home")), "member-dashboard/lionel.png")
        profile.profile_picture = "profile_pics/uploaded.jpg"
        profile.save()
        self.assertTrue(profile.avatar_url.endswith("profile_pics/uploaded.jpg"))

    def test_admin_pages_require_privileged_login(self):
        for model in ["core_contactmessage", "core_gymsettings", "ourteam_teammember"]:
            response = self.client.get(reverse(f"admin:{model}_changelist"))
            self.assertEqual(response.status_code, 302)
        self.client.force_login(self.coach)
        self.assertEqual(self.client.get(reverse("admin:core_contactmessage_changelist")).status_code, 302)
        admin = User.objects.create_superuser(username="root", email="root@example.com", password="TestOnly123!")
        self.client.force_login(admin)
        for model in ["core_contactmessage", "core_gymsettings", "ourteam_teammember"]:
            self.assertEqual(self.client.get(reverse(f"admin:{model}_changelist")).status_code, 200)


class ContactInboxTests(TestCase):
    data = {"full_name": "Sample Member", "email": "member@example.com", "topic": "CLASSES", "message": "Please tell me about your classes."}

    @override_settings(CONTACT_RECIPIENT_EMAIL="recipient@example.com")
    def test_saves_enquiry_and_uses_configured_recipient(self):
        response = self.client.post(reverse("core:contact"), self.data)
        self.assertRedirects(response, reverse("core:contact"))
        enquiry = ContactMessage.objects.get()
        self.assertEqual(enquiry.email, self.data["email"])
        self.assertEqual(enquiry.status, "NEW")
        self.assertTrue(enquiry.email_notification_sent)
        self.assertEqual(mail.outbox[0].to, ["recipient@example.com"])
        self.client.get(reverse("core:contact"))
        self.assertEqual(ContactMessage.objects.count(), 1)

    @override_settings(CONTACT_RECIPIENT_EMAIL="")
    def test_blank_config_uses_public_gym_email(self):
        GymSettings.objects.create(public_email="desk@example.com")
        self.client.post(reverse("core:contact"), self.data)
        self.assertEqual(mail.outbox[0].to, ["desk@example.com"])

    @patch("core.views.send_mail", side_effect=SMTPException("Unavailable"))
    def test_failed_email_does_not_lose_enquiry(self, mocked):
        response = self.client.post(reverse("core:contact"), self.data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ContactMessage.objects.get().email_notification_sent)

    def test_invalid_message_is_not_stored(self):
        response = self.client.post(reverse("core:contact"), {**self.data, "email": "invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_public_page_does_not_disclose_enquiries(self):
        ContactMessage.objects.create(**self.data)
        self.assertNotContains(self.client.get(reverse("core:contact")), self.data["message"])
