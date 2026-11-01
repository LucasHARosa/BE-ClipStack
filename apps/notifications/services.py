"""Casos de uso que ESCREVEM (regra de negócio, transações, enfileiramento de tasks).

Funções com argumentos nomeados; views e tasks chamam essas funções em vez de mexer nos
models diretamente.
"""

import logging
from functools import partial

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.videos.models import Video

logger = logging.getLogger(__name__)


def mark_all_read(*, user):
    # QuerySet.update(): um único UPDATE no banco, sem carregar os objetos. Ok aqui porque
    # Notification não tem lógica no save() nem signals. Devolve o número de linhas.
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)


def notify_video_processed(*, video_id, succeeded, event_key):
    # O detalhe técnico do erro fica no job (error_message); o usuário recebe uma mensagem
    # simples.
    # Import local: tasks.py importa este módulo; importar tasks no topo daria import circular.
    from apps.notifications import tasks

    video = Video.objects.select_related("owner").get(pk=video_id)
    if succeeded:
        message = f'Seu vídeo "{video.title}" está pronto.'
    else:
        message = f'O processamento de "{video.title}" falhou. Você pode reprocessá-lo.'

    with transaction.atomic():
        # get_or_create pela event_key: idempotente. Se a task rodar de novo, não duplica
        # (e a UniqueConstraint garante isso mesmo com duas execuções simultâneas).
        notification, created = Notification.objects.get_or_create(
            event_key=event_key,
            defaults={"user": video.owner, "video": video, "message": message[:255]},
        )
        if created:
            # Email só depois do COMMIT e numa task própria (fila default): se o SMTP falhar,
            # a notificação no app já existe e só o email é retentado.
            transaction.on_commit(partial(tasks.send_notification_email.delay, notification.pk))
    logger.info(
        "notification_created" if created else "notification_already_exists",
        extra={"notification_id": notification.pk, "event_key": event_key},
    )
    return notification


def send_notification_email(*, notification_id):
    with transaction.atomic():
        # Lock na linha: duas execuções simultâneas da mesma task não mandam dois emails.
        notification = (
            Notification.objects.select_for_update(of=("self",))
            .select_related("user")
            .get(pk=notification_id)
        )
        if notification.emailed_at:
            return notification
        # Entrega "pelo menos uma vez": se o envio der certo e o UPDATE abaixo falhar, o retry
        # reenvia. "Exatamente uma vez" com um sistema externo (SMTP) não existe de graça.
        send_mail(
            subject="ClipStack: processamento do seu vídeo",
            message=notification.message,
            from_email=None,  # DEFAULT_FROM_EMAIL
            recipient_list=[notification.user.email],
        )
        notification.emailed_at = timezone.now()
        notification.save(update_fields=["emailed_at"])
    return notification
