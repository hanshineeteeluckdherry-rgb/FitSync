# Notifications and notices — Anjie


from django.utils import timezone
from gym.models import Notice, Notification


def notification_menu(request):
    if not request.user.is_authenticated:
        return {}
    unread = Notification.objects.filter(recipient=request.user, is_read=False)
    today = timezone.localdate()
    notices = Notice.objects.filter(is_active=True, publish_date__lte=today).filter(
        expires_on__isnull=True
    ) | Notice.objects.filter(
        is_active=True, publish_date__lte=today, expires_on__gte=today
    )
    return {
        "notification_menu_items": unread[:5],
        "unread_notification_count": unread.count(),
        "active_gym_notices": notices.distinct()[:3],
    }
