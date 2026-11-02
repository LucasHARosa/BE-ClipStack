"""Só invalidação de cache: regra de negócio em signal fica escondida do service."""

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.videos.models import Comment, Video, VideoMetadata
from apps.videos.selectors import PLATFORM_STATS_CACHE_KEY, user_stats_cache_key


def _invalidate_dashboard_stats(owner_id):
    # Depois do COMMIT: antes dele, outra requisição recalcularia com os dados antigos.
    keys = [PLATFORM_STATS_CACHE_KEY]
    if owner_id is not None:
        keys.append(user_stats_cache_key(owner_id))
    transaction.on_commit(lambda: cache.delete_many(keys))


def _video_owner_id(video_id):
    # .first(): não falha se o vídeo já foi apagado em cascata.
    return Video.objects.filter(pk=video_id).values_list("owner_id", flat=True).first()


@receiver([post_save, post_delete], sender=Video)
def invalidate_stats_on_video_change(sender, instance, **kwargs):
    _invalidate_dashboard_stats(instance.owner_id)


@receiver([post_save, post_delete], sender=VideoMetadata)
def invalidate_stats_on_metadata_change(sender, instance, **kwargs):
    _invalidate_dashboard_stats(_video_owner_id(instance.video_id))


@receiver([post_save, post_delete], sender=Comment)
def invalidate_stats_on_comment_change(sender, instance, **kwargs):
    # A chave é a do dono do vídeo, não a do autor do comentário.
    _invalidate_dashboard_stats(_video_owner_id(instance.video_id))
