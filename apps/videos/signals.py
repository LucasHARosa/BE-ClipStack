"""Só invalidação de cache: regra de negócio em signal fica escondida do service."""

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.videos.models import Comment, Video, VideoMetadata
from apps.videos.selectors import STATS_ALL_KEY, stats_cache_key


def _invalidate_stats(owner_id):
    # Depois do COMMIT: antes dele, outra requisição recalcularia com os dados antigos.
    keys = [STATS_ALL_KEY] if owner_id is None else [stats_cache_key(owner_id), STATS_ALL_KEY]
    transaction.on_commit(lambda: cache.delete_many(keys))


def _owner_of(video_id):
    # .first(): não falha se o vídeo já foi apagado em cascata.
    return Video.objects.filter(pk=video_id).values_list("owner_id", flat=True).first()


@receiver([post_save, post_delete], sender=Video)
def video_changed(sender, instance, **kwargs):
    _invalidate_stats(instance.owner_id)


@receiver([post_save, post_delete], sender=VideoMetadata)
def metadata_changed(sender, instance, **kwargs):
    _invalidate_stats(_owner_of(instance.video_id))


@receiver([post_save, post_delete], sender=Comment)
def comment_changed(sender, instance, **kwargs):
    # A chave é a do dono do vídeo, não a do autor do comentário.
    _invalidate_stats(_owner_of(instance.video_id))
