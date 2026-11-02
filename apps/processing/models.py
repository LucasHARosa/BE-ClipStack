from django.db import models
from django.db.models import Q


class ProcessingJob(models.Model):
    # Um vídeo reprocessado tem vários jobs.
    class Status(models.TextChoices):
        QUEUED = "queued", "Na fila"
        PROCESSING = "processing", "Processando"
        COMPLETED = "completed", "Concluído"
        FAILED = "failed", "Falhou"

    ACTIVE_STATUSES = (Status.QUEUED, Status.PROCESSING)

    video = models.ForeignKey("videos.Video", on_delete=models.CASCADE, related_name="jobs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    progress = models.PositiveSmallIntegerField("progresso (%)", default=0)
    attempts = models.PositiveSmallIntegerField("tentativas", default=0)
    error_message = models.TextField("erro", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Garantia final contra job duplicado; o select_for_update no service evita chegar aqui.
            models.UniqueConstraint(
                fields=["video"],
                condition=Q(status__in=["queued", "processing"]),
                name="one_active_job_per_video",
            ),
            models.CheckConstraint(
                condition=Q(progress__gte=0) & Q(progress__lte=100),
                name="job_progress_between_0_and_100",
            ),
        ]
        indexes = [
            # Para o fail_stuck_jobs do Beat.
            models.Index(fields=["status", "started_at"], name="job_status_started_idx"),
        ]
        verbose_name = "job de processamento"
        verbose_name_plural = "jobs de processamento"

    def __str__(self):
        return f"Job {self.pk} ({self.status}) do vídeo {self.video_id}"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES
