from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.demo_members import MEMBERS, get_demo_member
from accounts.demo_team import existing_team_user
from accounts.management.commands.seed_team import TEAM


class Command(BaseCommand):
    help = "Rename existing demo members to Friends characters without changing their data or passwords."

    @transaction.atomic
    def handle(self, *args, **options):
        for index in range(1, len(MEMBERS) + 1):
            member = get_demo_member(index, create=False)
            self.stdout.write(f"{member.get_full_name()}: {member.email}")
        for handle, *_ in TEAM:
            user = existing_team_user(handle)
            if user:
                self.stdout.write(f"Existing team account: {user.email}")
        self.stdout.write(self.style.SUCCESS("10 demo identities updated; existing records and passwords preserved."))
