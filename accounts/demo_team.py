"""Rename existing team identities without replacing their database rows."""
from django.core.management.base import CommandError

from accounts.models import User


def existing_team_user(handle):
    email = f"{handle}@fitsync.com"
    old_email = f"{handle}@fitsync.local"
    current = User.objects.filter(email=email).first()
    legacy = User.objects.filter(email=old_email).first()
    if current and legacy and current.pk != legacy.pk:
        raise CommandError(f"Both {email} and {old_email} exist. No accounts were merged.")
    if legacy:
        if legacy.username == old_email:
            if User.objects.filter(username=email).exclude(pk=legacy.pk).exists():
                raise CommandError(f"Username {email} is already in use.")
            legacy.username = email
        legacy.email = email
        legacy.save(update_fields=["email", "username"])
    return legacy or current
