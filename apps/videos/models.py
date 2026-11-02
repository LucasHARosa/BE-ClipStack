from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q


def video_upload_path(instance, filename):
    # Nome aleatório: evita colisão e não expõe o nome original.
    return f"videos/{instance.owner_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class Tag(models.Model):
    name = models.CharField("nome", max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class VideoQuerySet(models.QuerySet):
    def not_deleted(self):
        return self.filter(is_deleted=False)

    def completed(self):
        return self.filter(status=Video.Status.COMPLETED)

    def public(self):
        return self.filter(visibility=Video.Visibility.PUBLIC)

    def owned_by(self, user):
        return self.filter(owner=user)

    def visible_to(self, user):
        # O que fica fora daqui vira 404 nas views.
        videos = self.not_deleted()
        if not user.is_authenticated:
            return videos.public().completed()
        if getattr(user, "is_admin", False):
            return videos
        return videos.filter(
            Q(owner=user) | Q(visibility=Video.Visibility.PUBLIC, status=Video.Status.COMPLETED)
        )


class Video(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Enviado"
        QUEUED = "queued", "Na fila"
        PROCESSING = "processing", "Processando"
        COMPLETED = "completed", "Concluído"
        FAILED = "failed", "Falhou"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Público"
        PRIVATE = "private", "Privado"

    # PROTECT: usuário com vídeos é desativado, não apagado.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="videos"
    )
    title = models.CharField("título", max_length=200)
    description = models.TextField("descrição", blank=True)
    file = models.FileField("arquivo", upload_to=video_upload_path)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    visibility = models.CharField(
        "visibilidade", max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    tags = models.ManyToManyField(Tag, related_name="videos", blank=True)
    # Soft delete: jobs e notificações continuam apontando para o vídeo.
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Não esconde os apagados por padrão (quebraria Admin e FKs reversas): quem lista usa
    # .not_deleted()/.visible_to().
    objects = VideoQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # "Meus vídeos com status X". Serve para owner sozinho, não para status sozinho.
            models.Index(fields=["owner", "status"], name="video_owner_status_idx"),
        ]

    def __str__(self):
        return self.title

    def can_be_reprocessed(self):
        return not self.is_deleted and self.status == self.Status.FAILED

    @property
    def is_processing(self) -> bool:
        return self.status in {self.Status.QUEUED, self.Status.PROCESSING}


class VideoMetadata(models.Model):
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name="metadata")
    duration_seconds = models.PositiveIntegerField("duração (s)", null=True, blank=True)
    resolution = models.CharField("resolução", max_length=20, blank=True)
    thumbnail = models.ImageField(upload_to="thumbnails/%Y/%m/", blank=True)

    class Meta:
        verbose_name_plural = "video metadata"

    def __str__(self):
        return f"Metadados de {self.video_id}"


class Comment(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    text = models.CharField("texto", max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["video", "created_at"], name="comment_video_created_idx")]

    def __str__(self):
        return self.text[:50]
