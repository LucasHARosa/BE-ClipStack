import logging
from functools import partial

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.videos.models import Video

logger = logging.getLogger(__name__)


def mark_all_read(*, user):
    # update() pula save() e signals; Notification não depende de nenhum dos dois.
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)


def notify_video_processed(*, video_id, succeeded, event_key):
    # Import local: tasks.py importa este módulo.
    from apps.notifications import tasks

    video = Video.objects.select_related("owner").get(pk=video_id)
    if succeeded:
        message = f'Seu vídeo "{video.title}" está pronto.'
    else:
        message = f'O processamento de "{video.title}" falhou. Você pode reprocessá-lo.'

    with transaction.atomic():
        notification, created = Notification.objects.get_or_create(
            event_key=event_key,
            defaults={"user": video.owner, "video": video, "message": message[:255]},
        )
        if created:
            # Task própria: se o SMTP falhar, só o email é retentado.
            transaction.on_commit(partial(tasks.send_notification_email.delay, notification.pk))
    logger.info(
        "notification_created" if created else "notification_already_exists",
        extra={"notification_id": notification.pk, "event_key": event_key},
    )
    return notification


def send_notification_email(*, notification_id):
    with transaction.atomic():
        notification = (
            Notification.objects.select_for_update(of=("self",))
            .select_related("user")
            .get(pk=notification_id)
        )
        if notification.emailed_at:
            return notification
        # At-least-once: se o envio der certo e o UPDATE falhar, o retry reenvia.
        send_mail(
            subject="ClipStack: processamento do seu vídeo",
            message=notification.message,
            from_email=None,
            recipient_list=[notification.user.email],
        )
        notification.emailed_at = timezone.now()
        notification.save(update_fields=["emailed_at"])
    return notification
