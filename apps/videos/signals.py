"""Signals da app videos: SÓ invalidação de cache.

Signal é um gancho implícito: quem lê o service não vê o que acontece depois do save(). Por isso
NÃO deve carregar regra de negócio (criar job, mandar email, mudar status): ela ficaria
escondida, não rodaria em bulk_create/update() e seria difícil de testar e de ordenar com
transações. Invalidar cache é o caso clássico de uso correto: é um efeito colateral técnico,
idempotente, que precisa acontecer em QUALQUER escrita no model, venha de onde vier (API,
worker, Admin, shell).
"""

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.videos.models import Comment, Video, VideoMetadata
from apps.videos.selectors import STATS_ALL_KEY, stats_cache_key


def _invalidate_stats(owner_id):
    # on_commit: apaga depois do COMMIT. Antes disso, outra requisição poderia recalcular com
    # os dados ANTIGOS (ainda não commitados) e gravar de volta no cache um valor velho.
    keys = [STATS_ALL_KEY] if owner_id is None else [stats_cache_key(owner_id), STATS_ALL_KEY]
    transaction.on_commit(lambda: cache.delete_many(keys))


def _owner_of(video_id):
    # .values_list().first(): não falha se o vídeo já foi apagado (DELETE em cascata).
    return Video.objects.filter(pk=video_id).values_list("owner_id", flat=True).first()


@receiver([post_save, post_delete], sender=Video)
def video_changed(sender, instance, **kwargs):
    _invalidate_stats(instance.owner_id)


@receiver([post_save, post_delete], sender=VideoMetadata)
def metadata_changed(sender, instance, **kwargs):
    # A duração total vem dos metadados, que o worker grava ao terminar o processamento.
    _invalidate_stats(_owner_of(instance.video_id))


@receiver([post_save, post_delete], sender=Comment)
def comment_changed(sender, instance, **kwargs):
    # O "top comentados" muda quando alguém comenta no vídeo de outra pessoa: a chave a apagar
    # é a do DONO do vídeo, não a do autor do comentário.
    _invalidate_stats(_owner_of(instance.video_id))
