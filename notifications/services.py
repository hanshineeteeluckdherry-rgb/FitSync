from .models import Notification


def create_notification(
    recipient,
    notification_type,
    title,
    message,
    link="",
    reference_key="",
):
    # Helper used by other apps (bookings, memberships) to create a notification
    # in one line. It returns the notification and True if a new one was created.

    # With a reference_key, look for an existing notification for the same event
    # first, so repeating the action never sends the same notification twice.

    if reference_key:
        notification, created = Notification.objects.get_or_create(
            recipient=recipient,
            notification_type=notification_type,
            reference_key=reference_key,
            defaults={
                "title": title,
                "message": message,
                "link": link,
            },
        )
        return notification, created

    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
    )
    return notification, True
