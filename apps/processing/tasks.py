"""Tasks do processamento.

Quando usar Celery e quando usar view async:
- Celery: trabalho que o usuário NÃO precisa esperar na resposta (processar vídeo, email),
  que é pesado (CPU/ffmpeg), que precisa de retry ou de agendamento. Sai da requisição e
  sobrevive a ela.
- View async: o usuário PRECISA da resposta, mas a view espera vários I/Os que podem rodar em
  paralelo (ex.: o health check consultando banco, Redis e RabbitMQ). Async não tira trabalho
  da requisição e não ajuda com CPU.
"""

import random

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError

from apps.processing import services
from apps.processing.exceptions import ProcessingError, TransientProcessingError

BACKOFF_BASE_SECONDS = 10
BACKOFF_MAX_SECONDS = 300


def backoff_seconds(retries):
    # Exponencial (10 s, 20 s, 40 s... até 5 min) + jitter: sem a aleatoriedade, vários jobs
    # que falharam juntos (ex.: banco fora do ar) voltariam todos no mesmo segundo.
    delay = min(BACKOFF_BASE_SECONDS * 2**retries, BACKOFF_MAX_SECONDS)
    return delay + random.uniform(0, BACKOFF_BASE_SECONDS)  # noqa: S311 (não é criptografia)


# acks_late=True: a mensagem só é confirmada (e sai da fila) quando a task TERMINA. Se o worker
# morrer no meio (deploy, OOM), o RabbitMQ entrega a mensagem a outro worker. O preço: a task
# pode rodar mais de uma vez, então precisa ser idempotente (run_job ignora job terminado).
# Retry MANUAL (self.retry): permite decidir o que é temporário e o que fazer ao esgotar.
@shared_task(bind=True, acks_late=True, max_retries=3)
def process_video(self, job_id):
    try:
        services.run_job(job_id=job_id)
    except (TransientProcessingError, OperationalError) as exc:
        if self.request.retries >= self.max_retries:
            services.fail_job(
                job_id=job_id,
                error_message=f"Falhou após {self.request.retries + 1} tentativas: {exc}",
            )
            return
        # retry() publica uma NOVA mensagem com atraso (countdown) e lança Retry; a mensagem
        # atual é confirmada. O job continua "processing" até a próxima tentativa.
        raise self.retry(exc=exc, countdown=backoff_seconds(self.request.retries)) from exc
    except SoftTimeLimitExceeded:
        services.fail_job(job_id=job_id, error_message="Tempo limite de processamento excedido.")
    except ProcessingError as exc:
        # Falha permanente (arquivo corrompido): tentar de novo não adianta.
        services.fail_job(job_id=job_id, error_message=str(exc))


@shared_task
def fail_stuck_jobs():
    # Agendada pelo Celery Beat (settings.CELERY_BEAT_SCHEDULE). Rede de segurança para jobs que
    # ficaram em "processing": worker morto sem redelivery, mensagem perdida.
    return services.fail_stuck_jobs()
