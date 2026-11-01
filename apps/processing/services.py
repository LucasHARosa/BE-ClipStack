"""Casos de uso do processamento.

Fluxo: start_processing (na requisição) → enqueue_job (após o commit) → run_job (no worker)
→ completed, ou fail_job ao esgotar as tentativas. A task Celery (etapa 8) só embrulha o
run_job com retry; a regra fica aqui, testável sem Celery.
"""

import logging
from datetime import timedelta
from functools import partial

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.notifications import tasks as notification_tasks
from apps.processing.exceptions import ProcessingAlreadyActive
from apps.processing.models import ProcessingJob
from apps.processing.processors import get_video_processor
from apps.videos import services as video_services
from apps.videos.models import Video

logger = logging.getLogger(__name__)


def start_processing(*, video):
    # Chamado DENTRO da transação de quem criou ou reprocessou o vídeo (via settings
    # VIDEO_PROCESSING_ENTRYPOINT, porque videos não importa processing).
    try:
        # atomic aninhado = SAVEPOINT. Se o INSERT violar a constraint, só o savepoint é
        # desfeito; sem ele, a transação de fora ficaria quebrada para qualquer query seguinte.
        with transaction.atomic():
            job = ProcessingJob.objects.create(video=video)
    except IntegrityError as exc:
        if "one_active_job_per_video" not in str(exc):
            raise
        raise ProcessingAlreadyActive() from exc

    video_services.set_video_status(video=video, status=Video.Status.QUEUED)

    # on_commit: publica na fila só DEPOIS do COMMIT. Sem isso, o worker pode pegar a
    # mensagem antes do commit e não achar o job (a linha ainda não é visível para outras
    # conexões), ou a transação sofre rollback e a task roda sobre um job que nunca existiu.
    transaction.on_commit(partial(enqueue_job, job.pk))
    return job


def enqueue_job(job_id):
    # Import local: tasks.py importa este módulo (import circular no topo).
    from apps.processing.tasks import process_video

    # Publica no RabbitMQ; o CELERY_TASK_ROUTES manda para a fila "processing". Passa o ID,
    # nunca o objeto: a mensagem é JSON e pode esperar na fila; o worker lê o estado atual.
    process_video.delay(job_id)
    logger.info("job_enqueued", extra={"job_id": job_id})


def _notify_finished(job, *, succeeded):
    # Avisa o dono na fila "default" (leve), depois do commit do resultado. event_key torna a
    # notificação idempotente se esta função for chamada de novo para o mesmo job.
    transaction.on_commit(
        partial(
            notification_tasks.notify_video_processed.delay,
            job.video_id,
            succeeded,
            f"job:{job.pk}:finished",
        )
    )


def run_job(*, job_id, processor=None):
    # processor por parâmetro: nos testes, passa-se um fake; em produção vem do settings.
    job = ProcessingJob.objects.select_related("video").get(pk=job_id)

    # Idempotência: a mesma mensagem pode ser entregue de novo (retry, acks_late, worker que
    # morreu depois de terminar). Job terminado não é processado outra vez.
    if job.status in {ProcessingJob.Status.COMPLETED, ProcessingJob.Status.FAILED}:
        logger.info("job_already_finished", extra={"job_id": job_id, "status": job.status})
        return job

    # F("attempts") + 1: o incremento acontece no banco (UPDATE ... SET attempts = attempts + 1),
    # sem ler-somar-gravar em Python, que perderia incrementos com dois workers ao mesmo tempo.
    ProcessingJob.objects.filter(pk=job.pk).update(
        status=ProcessingJob.Status.PROCESSING,
        progress=0,
        attempts=F("attempts") + 1,
        started_at=timezone.now(),
        error_message="",
    )
    video = job.video
    video_services.set_video_status(video=video, status=Video.Status.PROCESSING)

    def on_progress(percent):
        # UPDATE direto e curto: o frontend lê o progresso por polling enquanto o job roda.
        ProcessingJob.objects.filter(pk=job.pk).update(progress=percent)

    processor = processor or get_video_processor()
    # .path só existe no FileSystemStorage. Com S3 (django-storages), o worker baixaria o
    # arquivo para um temporário antes de chamar o ffmpeg.
    result = processor.process(video.file.path, on_progress)

    with transaction.atomic():
        video_services.save_video_metadata(
            video=video,
            duration_seconds=result.duration_seconds,
            resolution=result.resolution,
            thumbnail=result.thumbnail,
        )
        ProcessingJob.objects.filter(pk=job.pk).update(
            status=ProcessingJob.Status.COMPLETED, progress=100, finished_at=timezone.now()
        )
        video_services.set_video_status(video=video, status=Video.Status.COMPLETED)
        _notify_finished(job, succeeded=True)

    job.refresh_from_db()
    return job


def fail_job(*, job_id, error_message):
    with transaction.atomic():
        # select_for_update(of=("self",)): trava só a linha do job, não a do vídeo trazida
        # pelo JOIN do select_related (FOR UPDATE OF processing_processingjob).
        job = (
            ProcessingJob.objects.select_for_update(of=("self",))
            .select_related("video")
            .get(pk=job_id)
        )
        # Idempotente: job já terminado (por outra execução ou pelo Beat) não muda.
        if job.status in {ProcessingJob.Status.COMPLETED, ProcessingJob.Status.FAILED}:
            return job
        job.status = ProcessingJob.Status.FAILED
        job.error_message = error_message[:2000]
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "finished_at"])
        video_services.set_video_status(video=job.video, status=Video.Status.FAILED)
        _notify_finished(job, succeeded=False)
    return job


def fail_stuck_jobs():
    cutoff = timezone.now() - timedelta(minutes=settings.STUCK_JOB_TIMEOUT_MINUTES)
    # Usa o índice (status, started_at) criado no model para esta consulta.
    stuck_ids = list(
        ProcessingJob.objects.filter(
            status=ProcessingJob.Status.PROCESSING, started_at__lt=cutoff
        ).values_list("pk", flat=True)
    )
    for job_id in stuck_ids:
        fail_job(
            job_id=job_id,
            error_message=(
                f"Job preso em processing por mais de {settings.STUCK_JOB_TIMEOUT_MINUTES} min."
            ),
        )
    if stuck_ids:
        logger.warning("stuck_jobs_failed", extra={"job_ids": stuck_ids})
    return len(stuck_ids)
