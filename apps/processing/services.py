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
    # Roda dentro da transação de quem criou ou reprocessou o vídeo.
    try:
        # Savepoint: sem ele, o IntegrityError quebraria a transação de fora.
        with transaction.atomic():
            job = ProcessingJob.objects.create(video=video)
    except IntegrityError as exc:
        if "one_active_job_per_video" not in str(exc):
            raise
        raise ProcessingAlreadyActive() from exc

    video_services.set_video_status(video=video, status=Video.Status.QUEUED)

    # Publica só depois do COMMIT: antes dele, o worker não enxerga o job, e um rollback
    # deixaria uma mensagem órfã na fila.
    transaction.on_commit(partial(enqueue_job, job.pk))
    return job


def enqueue_job(job_id):
    # Import local: tasks.py importa este módulo.
    from apps.processing.tasks import process_video

    # Só o id: o worker lê o estado atual do banco quando for processar.
    process_video.delay(job_id)
    logger.info("job_enqueued", extra={"job_id": job_id})


def _schedule_finish_notification(job, *, succeeded):
    transaction.on_commit(
        partial(
            notification_tasks.notify_video_processed.delay,
            job.video_id,
            succeeded,
            f"job:{job.pk}:finished",
        )
    )


def run_job(*, job_id, processor=None):
    job = ProcessingJob.objects.select_related("video").get(pk=job_id)

    # Idempotente: com acks_late, a mesma mensagem pode chegar de novo.
    if job.status in {ProcessingJob.Status.COMPLETED, ProcessingJob.Status.FAILED}:
        logger.info("job_already_finished", extra={"job_id": job_id, "status": job.status})
        return job

    # F(): o incremento acontece no banco, sem corrida entre workers.
    ProcessingJob.objects.filter(pk=job.pk).update(
        status=ProcessingJob.Status.PROCESSING,
        progress=0,
        attempts=F("attempts") + 1,
        started_at=timezone.now(),
        error_message="",
    )
    video = job.video
    video_services.set_video_status(video=video, status=Video.Status.PROCESSING)

    def save_progress(percent):
        ProcessingJob.objects.filter(pk=job.pk).update(progress=percent)

    processor = processor or get_video_processor()
    # .path só existe no FileSystemStorage; com S3, baixaria para um temporário antes.
    result = processor.process(video.file.path, save_progress)

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
        _schedule_finish_notification(job, succeeded=True)

    job.refresh_from_db()
    return job


def fail_job(*, job_id, error_message):
    with transaction.atomic():
        # of=("self",): trava só o job, não o vídeo do JOIN.
        job = (
            ProcessingJob.objects.select_for_update(of=("self",))
            .select_related("video")
            .get(pk=job_id)
        )
        # Job já terminado (por outra execução ou pelo Beat) não muda.
        if job.status in {ProcessingJob.Status.COMPLETED, ProcessingJob.Status.FAILED}:
            return job
        job.status = ProcessingJob.Status.FAILED
        job.error_message = error_message[:2000]
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "finished_at"])
        video_services.set_video_status(video=job.video, status=Video.Status.FAILED)
        _schedule_finish_notification(job, succeeded=False)
    return job


def fail_stuck_jobs():
    cutoff = timezone.now() - timedelta(minutes=settings.STUCK_JOB_TIMEOUT_MINUTES)
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
