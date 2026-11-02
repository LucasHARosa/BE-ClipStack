import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.module_loading import import_string

from apps.videos.exceptions import VideoNotReprocessable
from apps.videos.models import Video, VideoMetadata

logger = logging.getLogger(__name__)


def _start_processing(video):
    # videos não importa processing (import-linter): a função vem do settings.
    return import_string(settings.VIDEO_PROCESSING_ENTRYPOINT)(video=video)


def create_video(
    *, owner, file, title, description="", visibility=Video.Visibility.PUBLIC, tags=()
):
    with transaction.atomic():
        video = Video.objects.create(
            owner=owner, file=file, title=title, description=description, visibility=visibility
        )
        video.tags.set(tags)
        _start_processing(video)
    return video


def reprocess_video(*, video_id):
    with transaction.atomic():
        # Lock antes da checagem: a segunda requisição simultânea espera e já lê "queued".
        # Sem select_related: FOR UPDATE com LEFT JOIN dá erro no Postgres.
        video = Video.objects.select_for_update().get(pk=video_id)
        if not video.can_be_reprocessed():
            raise VideoNotReprocessable(details={"status": video.status})
        _start_processing(video)
    return video


def update_video(*, video, data):
    tags = data.pop("tags", None)
    for field, value in data.items():
        setattr(video, field, value)
    with transaction.atomic():
        # update_fields: não sobrescreve o status que o worker pode ter mudado.
        video.save(update_fields=[*data.keys(), "updated_at"])
        if tags is not None:
            video.tags.set(tags)
    return video


def set_video_status(*, video, status):
    # Usado pela app processing, que não mexe direto no model de outra app.
    video.status = status
    video.save(update_fields=["status", "updated_at"])


def save_video_metadata(*, video, duration_seconds, resolution, thumbnail=None):
    # Reprocessar sobrescreve em vez de violar o OneToOne.
    metadata, _ = VideoMetadata.objects.update_or_create(
        video=video,
        defaults={"duration_seconds": duration_seconds, "resolution": resolution},
    )
    if thumbnail:
        metadata.thumbnail.save(f"{video.pk}.jpg", ContentFile(thumbnail), save=True)
    return metadata


def delete_video(*, video, actor):
    video.is_deleted = True
    video.save(update_fields=["is_deleted", "updated_at"])
    logger.info("video_deleted", extra={"video_id": video.pk, "actor_id": actor.pk})
