import random

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError

from apps.processing import services
from apps.processing.exceptions import ProcessingError, TransientProcessingError

BACKOFF_BASE_SECONDS = 10
BACKOFF_MAX_SECONDS = 300


def backoff_seconds(retries):
    # Jitter: jobs que falharam juntos (ex.: banco fora do ar) não voltam no mesmo segundo.
    delay = min(BACKOFF_BASE_SECONDS * 2**retries, BACKOFF_MAX_SECONDS)
    return delay + random.uniform(0, BACKOFF_BASE_SECONDS)  # noqa: S311


# acks_late: worker que morre no meio devolve a mensagem à fila (run_job é idempotente).
# Retry manual: decide o que é temporário e marca o job como failed ao esgotar.
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
        raise self.retry(exc=exc, countdown=backoff_seconds(self.request.retries)) from exc
    except SoftTimeLimitExceeded:
        services.fail_job(job_id=job_id, error_message="Tempo limite de processamento excedido.")
    except ProcessingError as exc:
        services.fail_job(job_id=job_id, error_message=str(exc))


@shared_task
def fail_stuck_jobs():
    return services.fail_stuck_jobs()
