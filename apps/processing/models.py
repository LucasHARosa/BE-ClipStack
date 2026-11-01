from django.db import models
from django.db.models import Q


class ProcessingJob(models.Model):
    # Uma linha por TENTATIVA de processamento: um vídeo pode ter vários jobs (reprocessamento).
    class Status(models.TextChoices):
        QUEUED = "queued", "Na fila"
        PROCESSING = "processing", "Processando"
        COMPLETED = "completed", "Concluído"
        FAILED = "failed", "Falhou"

    ACTIVE_STATUSES = (Status.QUEUED, Status.PROCESSING)

    # String "videos.Video": processing referencia videos sem import (e não o contrário).
    # CASCADE: o job é histórico do vídeo; se o vídeo for apagado de verdade, vai junto.
    video = models.ForeignKey("videos.Video", on_delete=models.CASCADE, related_name="jobs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    progress = models.PositiveSmallIntegerField("progresso (%)", default=0)
    # Incrementado com F("attempts") + 1 no worker: a soma acontece no banco, sem corrida.
    attempts = models.PositiveSmallIntegerField("tentativas", default=0)
    error_message = models.TextField("erro", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # UniqueConstraint parcial (condition): no máximo UM job ativo por vídeo.
            # É a última barreira contra job duplicado; o select_for_update no service evita
            # chegar aqui, mas a garantia final é do banco.
            models.UniqueConstraint(
                fields=["video"],
                condition=Q(status__in=["queued", "processing"]),
                name="one_active_job_per_video",
            ),
            # CheckConstraint: regra de integridade validada pelo próprio Postgres.
            models.CheckConstraint(
                condition=Q(progress__gte=0) & Q(progress__lte=100),
                name="job_progress_between_0_and_100",
            ),
        ]
        indexes = [
            # Atende a task periódica do Beat: "jobs em processing iniciados há mais de X min".
            models.Index(fields=["status", "started_at"], name="job_status_started_idx"),
        ]
        verbose_name = "job de processamento"
        verbose_name_plural = "jobs de processamento"

    def __str__(self):
        return f"Job {self.pk} ({self.status}) do vídeo {self.video_id}"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES
