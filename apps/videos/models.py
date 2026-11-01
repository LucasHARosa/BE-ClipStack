from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q


def video_upload_path(instance, filename):
    # upload_to como função: nome aleatório evita colisão e não expõe o nome original.
    # Precisa ser função de módulo (não lambda) para a migration conseguir serializá-la.
    return f"videos/{instance.owner_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class Tag(models.Model):
    # unique=True cria um índice único no banco; o ModelSerializer também valida isso.
    name = models.CharField("nome", max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class VideoQuerySet(models.QuerySet):
    # QuerySet customizado: consultas reutilizáveis e encadeáveis, ex.:
    # Video.objects.visible_to(user).completed(). É o "repository" idiomático do Django.

    def alive(self):
        return self.filter(is_deleted=False)

    def completed(self):
        return self.filter(status=Video.Status.COMPLETED)

    def public(self):
        return self.filter(visibility=Video.Visibility.PUBLIC)

    def owned_by(self, user):
        return self.filter(owner=user)

    def visible_to(self, user):
        # Regra de VISIBILIDADE (o que cada um pode ver). Usada no get_queryset() das views:
        # o que fica fora daqui vira 404, sem revelar que o vídeo existe.
        qs = self.alive()
        if not user.is_authenticated:
            return qs.public().completed()
        if getattr(user, "is_admin", False):
            return qs
        # Q(): permite OR entre condições (o filter() comum só faz AND).
        return qs.filter(
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

    # FK com string "app.Model" via settings: não importa a app accounts e respeita o
    # AUTH_USER_MODEL. related_name="videos" habilita o reverso: user.videos.all().
    # PROTECT: não dá para apagar um usuário que tem vídeos (ProtectedError). Usuário sai do
    # sistema por is_active=False; apagar de verdade é decisão explícita (ex.: LGPD), em service.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="videos"
    )
    title = models.CharField("título", max_length=200)
    description = models.TextField("descrição", blank=True)
    # FileField guarda só o caminho no banco; o arquivo vai para o storage (MEDIA_ROOT/S3).
    file = models.FileField("arquivo", upload_to=video_upload_path)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    visibility = models.CharField(
        "visibilidade", max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC
    )
    # ManyToMany: o Django cria a tabela intermediária (videos_video_tags) sozinho.
    # Não tem on_delete: apagar uma tag só remove as linhas da tabela intermediária.
    tags = models.ManyToManyField(Tag, related_name="videos", blank=True)
    # Soft delete: o registro fica (auditoria, jobs, notificações) mas some da API.
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # as_manager(): transforma o QuerySet em manager, expondo os métodos em Video.objects.
    # O manager padrão NÃO esconde os apagados: um default que filtra quebraria o Admin, as
    # FKs reversas e as migrations. Quem lista usa .alive()/.visible_to() de forma explícita.
    objects = VideoQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Índice composto: atende "meus vídeos com status X" (dashboard e filtros).
            # A ordem importa: serve para filtrar por owner sozinho, mas não por status sozinho.
            models.Index(fields=["owner", "status"], name="video_owner_status_idx"),
        ]

    def __str__(self):
        return self.title

    # Método de model: pergunta sobre o ESTADO do próprio objeto. A regra completa de
    # reprocessar (lock da linha, não ter job ativo, enfileirar) fica no service.
    def can_be_reprocessed(self):
        return not self.is_deleted and self.status == self.Status.FAILED

    # @property usada pelo serializer: o frontend usa para decidir se faz polling.
    @property
    def is_processing(self):
        return self.status in {self.Status.QUEUED, self.Status.PROCESSING}


class VideoMetadata(models.Model):
    # OneToOneField: FK com unique=True. Reverso sem _set: video.metadata (um objeto, não
    # um manager). CASCADE: metadado não faz sentido sem o vídeo.
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name="metadata")
    duration_seconds = models.PositiveIntegerField("duração (s)", null=True, blank=True)
    resolution = models.CharField("resolução", max_length=20, blank=True)
    # ImageField = FileField que valida se é imagem (precisa do Pillow).
    thumbnail = models.ImageField(upload_to="thumbnails/%Y/%m/", blank=True)

    class Meta:
        verbose_name_plural = "video metadata"

    def __str__(self):
        return f"Metadados de {self.video_id}"


class Comment(models.Model):
    # CASCADE nos dois lados: comentário não existe sem o vídeo nem sem o autor.
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
