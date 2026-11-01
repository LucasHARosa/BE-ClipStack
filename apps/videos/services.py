"""Casos de uso que ESCREVEM (regra de negócio, transações, enfileiramento de tasks).

Funções com argumentos nomeados (*): a chamada fica legível (create_video(owner=..., file=...))
e trocar a ordem dos parâmetros não quebra ninguém. Views, tasks e Admin chamam estas funções
em vez de mexer nos models diretamente.
"""

import logging

from django.core.files.base import ContentFile
from django.db import transaction

from apps.videos.models import Video, VideoMetadata

logger = logging.getLogger(__name__)


def create_video(
    *, owner, file, title, description="", visibility=Video.Visibility.PUBLIC, tags=()
):
    # atomic: vídeo e tags entram juntos ou nada entra. A etapa 5 acrescenta aqui a criação
    # do job e o enfileiramento do processamento (via transaction.on_commit).
    with transaction.atomic():
        video = Video.objects.create(
            owner=owner, file=file, title=title, description=description, visibility=visibility
        )
        video.tags.set(tags)
    return video


def update_video(*, video, data):
    # Só os dados descritivos; o arquivo não muda (exigiria reprocessar).
    tags = data.pop("tags", None)
    for field, value in data.items():
        setattr(video, field, value)
    with transaction.atomic():
        # update_fields: o UPDATE grava só essas colunas, sem sobrescrever outras que um
        # worker possa ter mudado nesse meio-tempo (ex.: status).
        video.save(update_fields=[*data.keys(), "updated_at"])
        if tags is not None:
            video.tags.set(tags)
    return video


def set_video_status(*, video, status):
    # Porta de entrada para OUTRAS apps mudarem o status (processing chama isto, em vez de
    # fazer video.status = ... direto no model de outra app).
    video.status = status
    video.save(update_fields=["status", "updated_at"])


def save_video_metadata(*, video, duration_seconds, resolution, thumbnail=None):
    # update_or_create: idempotente. Reprocessar sobrescreve os metadados em vez de falhar
    # na unicidade do OneToOne.
    metadata, _ = VideoMetadata.objects.update_or_create(
        video=video,
        defaults={"duration_seconds": duration_seconds, "resolution": resolution},
    )
    if thumbnail:
        # save=True grava o arquivo no storage e o caminho na coluna thumbnail.
        metadata.thumbnail.save(f"{video.pk}.jpg", ContentFile(thumbnail), save=True)
    return metadata


def delete_video(*, video, actor):
    # Soft delete: a linha fica (jobs, notificações, auditoria) e some das listagens.
    video.is_deleted = True
    video.save(update_fields=["is_deleted", "updated_at"])
    logger.info("video_deleted", extra={"video_id": video.pk, "actor_id": actor.pk})
