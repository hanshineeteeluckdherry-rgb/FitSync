"""Add missing team and contact details without changing login accounts."""

# Team and contact sample data — Shared
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from gym.models import MemberProfile, User
from gym.models import GymSettings
from gym.models import TeamMember


class Command(BaseCommand):
    help = "Create missing public team/contact content without overwriting edits."

    @transaction.atomic
    def handle(self, *args, **options):
        GymSettings.objects.get_or_create(pk=1)
        data = json.loads(
            (Path(settings.BASE_DIR) / "gym/seed_data/public_team.json").read_text()
        )
        for row in data:
            email = row.pop("account_email")
            user = User.objects.filter(email=email).first()
            member, created = TeamMember.objects.get_or_create(
                slug=slugify(row["display_name"]), defaults={**row, "user": user}
            )
            self.stdout.write(
                f"{'Created' if created else 'Kept'} {member.display_name}"
            )
        # This is demo fixture data, not a runtime email-based avatar rule.
        demo = User.objects.filter(
            email="member@fitsync.com", role=User.Role.MEMBER
        ).first()
        if demo:
            profile, _ = MemberProfile.objects.get_or_create(user=demo)
            if not profile.profile_picture and not profile.avatar_static_path:
                profile.avatar_static_path = "img/member-dashboard/lionel.png"
                profile.save(update_fields=["avatar_static_path"])
        self.stdout.write(
            self.style.SUCCESS(
                "Public content is ready; existing edits and login accounts were preserved."
            )
        )
