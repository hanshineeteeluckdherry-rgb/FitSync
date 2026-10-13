from django.utils import timezone

from .models import Notice, Notification


def notification_menu(request):
    # Runs on every page (it is registered in settings.py) and makes the
    # notification data available to all templates, such as the navbar bell.

    # Guests have no notifications, so there is nothing to add for them.
    if not request.user.is_authenticated:
        return {}

    # This user's notifications that have not been read yet.
    unread = Notification.objects.filter(recipient=request.user, is_read=False)
    today = timezone.localdate()
    # Gym notices that are active, already published, and either have no
    # expiry date or have not expired yet.
    notices = Notice.objects.filter(
        is_active=True,
        publish_date__lte=today,
    ).filter(expires_on__isnull=True) | Notice.objects.filter(
        is_active=True,
        publish_date__lte=today,
        expires_on__gte=today,
    )

    return {
        # The latest 5 unread notifications, for the bell dropdown.
        "notification_menu_items": unread[:5],
        # The number shown in the bell's badge.
        "unread_notification_count": unread.count(),
        # Up to 3 current gym notices to display.
        "active_gym_notices": notices.distinct()[:3],
    }
