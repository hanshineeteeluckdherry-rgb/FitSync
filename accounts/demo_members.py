"""Stable identities for the ten Friends-themed local demo members."""
from django.core.management.base import CommandError

from accounts.models import User


MEMBERS = [
    ("Rachel", "Green"), ("Monica", "Geller"), ("Phoebe", "Buffay"),
    ("Joey", "Tribbiani"), ("Chandler", "Bing"), ("Ross", "Geller"),
    ("Gunther", ""), ("Janice", "Hosenstein"), ("Mike", "Hannigan"),
    ("Carol", "Willick"),
]


def get_demo_member(index, password=None, create=True):
    first, last = MEMBERS[index - 1]
    handle = "_".join(part.lower() for part in (first, last) if part) + "_m"
    email = f"{handle}@fitsync.com"
    legacy_email = f"demo.member{index:02d}@fitsync.local"
    legacy = User.objects.filter(email=legacy_email, username=f"demo_member_{index:02d}").first()
    old_friends = User.objects.filter(email=f"{handle}@fitsync.local", username=handle).first()
    current = User.objects.filter(email=email).first()
    matches = {user.pk: user for user in (legacy, old_friends, current) if user}
    if len(matches) > 1:
        raise CommandError(f"{email} already belongs to another account. No accounts were merged.")
    user = legacy or old_friends or current
    if user and user.role != User.Role.MEMBER:
        raise CommandError(f"{user.email} is not a member account.")
    if User.objects.filter(username=handle).exclude(pk=user.pk if user else None).exists():
        raise CommandError(f"Username {handle} is already in use.")
    if legacy or old_friends:
        # Update the same row so every foreign-key relationship and password survives.
        user.username = handle
        user.email = email
        user.first_name = first
        user.last_name = last
        user.save(update_fields=["username", "email", "first_name", "last_name"])
    elif user is None:
        if not create:
            raise CommandError(f"Demo member {index:02d} was not found. Run seed_demo_members first.")
        user = User.objects.create_user(username=handle, email=email, password=password,
            first_name=first, last_name=last, role=User.Role.MEMBER)
    return user
