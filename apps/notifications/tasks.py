from smtplib import SMTPException

from celery import shared_task

from apps.notifications import services

RETRY_OPTIONS = {
    "autoretry_for": (SMTPException, ConnectionError, TimeoutError),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "max_retries": 5,
    "acks_late": True,
}


@shared_task(**RETRY_OPTIONS)
def notify_video_processed(video_id, succeeded, event_key):
    services.notify_video_processed(video_id=video_id, succeeded=succeeded, event_key=event_key)


@shared_task(**RETRY_OPTIONS)
def send_notification_email(notification_id):
    services.send_notification_email(notification_id=notification_id)
