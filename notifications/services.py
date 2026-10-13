from .models import Notification


def create_notification(
    recipient,
    notification_type,
    title,
    message,
    link="",
    reference_key="",
):
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
