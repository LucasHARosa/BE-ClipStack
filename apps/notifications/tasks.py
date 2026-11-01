"""Tasks da fila "default" (leves): notificação no app e email.

A task só embrulha o service: recebe IDs (nunca objetos, porque a mensagem é JSON e pode
esperar na fila; o worker busca o estado atual no banco) e delega.
"""

from smtplib import SMTPException

from celery import shared_task

from apps.notifications import services

# Retry DECLARATIVO (autoretry_for): falha de rede/SMTP → nova tentativa com backoff exponencial
# (1 s, 2 s, 4 s... até 10 min) e jitter (aleatoriedade para os retries não chegarem juntos).
RETRY_OPTIONS = {
    "autoretry_for": (SMTPException, ConnectionError, TimeoutError),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "max_retries": 5,
    # acks_late: confirma a mensagem só no fim. Se o worker morrer no meio, outra execução
    # acontece, por isso o service é idempotente (event_key / emailed_at).
    "acks_late": True,
}


@shared_task(**RETRY_OPTIONS)
def notify_video_processed(video_id, succeeded, event_key):
    services.notify_video_processed(video_id=video_id, succeeded=succeeded, event_key=event_key)


@shared_task(**RETRY_OPTIONS)
def send_notification_email(notification_id):
    services.send_notification_email(notification_id=notification_id)
