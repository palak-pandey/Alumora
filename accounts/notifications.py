from django.core.mail import send_mail
from django.conf import settings
from .models import Notification


def notify(recipient, title, message, notification_type='GENERAL', sender=None, link_url=None, send_email=True):
    """
    Creates an in-app Notification and optionally emails the recipient.
    recipient must be a User instance with a usable .email.
    """
    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        title=title,
        message=message,
        link_url=link_url,
    )

    if send_email and recipient.email:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=True,
            )
            notification.email_sent = True
            notification.save(update_fields=['email_sent'])
        except Exception:
            pass  # in-app notification still exists even if email fails

    return notification