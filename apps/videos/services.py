"""Casos de uso que ESCREVEM (regra de negócio, transações, enfileiramento de tasks).

Funções com argumentos nomeados (*): a chamada fica legível (create_video(owner=..., file=...))
e trocar a ordem dos parâmetros não quebra ninguém. Views, tasks e Admin chamam estas funções
em vez de mexer nos models diretamente.
"""

import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.module_loading import import_string

from apps.videos.exceptions import VideoNotReprocessable
from apps.videos.models import Video, VideoMetadata

logger = logging.getLogger(__name__)


def _start_processing(video):
    # Inversão de dependência: videos não importa processing (contrato do import-linter).
    # Chama a função configurada em settings.VIDEO_PROCESSING_ENTRYPOINT, que cria o job e
    # agenda o enfileiramento para depois do commit. Nos testes, dá para trocar por um fake.
    return import_string(settings.VIDEO_PROCESSING_ENTRYPOINT)(video=video)


def create_video(
    *, owner, file, title, description="", visibility=Video.Visibility.PUBLIC, tags=()
):
    # atomic: vídeo, tags e job entram juntos ou nada entra. A mensagem para a fila só é
    # publicada depois do COMMIT (on_commit dentro de start_processing).
    with transaction.atomic():
        video = Video.objects.create(
            owner=owner, file=file, title=title, description=description, visibility=visibility
        )
        video.tags.set(tags)
        _start_processing(video)
    return video


def reprocess_video(*, video_id):
    with transaction.atomic():
        # select_for_update: SELECT ... FOR UPDATE trava a linha do vídeo até o fim da
        # transação. Duas requisições simultâneas: a segunda ESPERA aqui; quando a primeira
        # commita, a segunda lê o status já "queued" e cai no 409 abaixo. Sem o lock, as duas
        # leriam "failed" e tentariam criar dois jobs (a UniqueConstraint seria a última
        # barreira). A checagem tem de vir DEPOIS do lock.
        # Sem select_related: FOR UPDATE com LEFT JOIN (metadata) daria erro no Postgres.
        video = Video.objects.select_for_update().get(pk=video_id)
        if not video.can_be_reprocessed():
            raise VideoNotReprocessable(details={"status": video.status})
        _start_processing(video)
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
