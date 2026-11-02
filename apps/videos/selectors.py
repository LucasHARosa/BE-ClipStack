"""Leituras de vídeos (selectors). Selector não escreve e devolve QuerySet sempre que possível,
para a view ainda poder filtrar e paginar (o LIMIT entra no mesmo SQL)."""

from django.core.cache import cache
from django.db.models import Count, Q, Sum

from apps.videos.models import Video

STATS_CACHE_TTL = 5 * 60
# Chave das estatísticas de toda a plataforma (o que o admin vê).
STATS_ALL_KEY = "dashboard:stats:all"


def stats_cache_key(user_id):
    return f"dashboard:stats:user:{user_id}"


def video_queryset(*, user, with_jobs=False):
    # select_related: JOIN para relações "para frente" de 1 objeto (owner) e para o reverso
    # do OneToOne (metadata). prefetch_related: query separada com IN (...) para relações
    # de vários (tags e, no detalhe, os jobs).
    qs = Video.objects.visible_to(user).select_related("owner", "metadata").prefetch_related("tags")
    if with_jobs:
        qs = qs.prefetch_related("jobs")
    return qs


def dashboard_stats(*, user):
    # Cache-aside: tenta o cache; se não houver (miss), calcula no banco e grava com TTL.
    # A invalidação (a parte difícil) fica em apps/videos/signals.py: quando um vídeo, os
    # metadados ou um comentário mudam, a chave do dono e a da plataforma são apagadas. O TTL
    # é só uma rede de segurança para alguma escrita que escape dos signals (ex.: update()).
    is_admin = getattr(user, "is_admin", False)
    key = STATS_ALL_KEY if is_admin else stats_cache_key(user.pk)
    return cache.get_or_set(
        key, lambda: _compute_dashboard_stats(user=user, is_admin=is_admin), STATS_CACHE_TTL
    )


def _compute_dashboard_stats(*, user, is_admin):
    # Escopo: o usuário vê as estatísticas dos próprios vídeos; o admin, da plataforma toda.
    videos = Video.objects.alive()
    if not is_admin:
        videos = videos.owned_by(user)

    # aggregate(): UM resultado para o conjunto inteiro, numa query só.
    # Count(..., filter=Q(...)) é a agregação condicional (COUNT(*) FILTER (WHERE ...)).
    # Sum atravessa o OneToOne (LEFT JOIN em metadata); por ser 1:1, o JOIN não duplica
    # linhas e os COUNTs continuam certos. Com um reverso de FK (comments) aqui, contaria errado.
    by_status = videos.aggregate(
        total=Count("id"),
        total_duration=Sum("metadata__duration_seconds"),
        **{status: Count("id", filter=Q(status=status)) for status in Video.Status.values},
    )
    total = by_status.pop("total")
    total_duration = by_status.pop("total_duration") or 0

    # annotate(): um valor calculado POR LINHA (comentários de cada vídeo).
    top_commented = (
        videos.annotate(comments_count=Count("comments"))
        .filter(comments_count__gt=0)
        .order_by("-comments_count", "-created_at")
        .values("id", "title", "comments_count")[:5]
    )
    return {
        "total_videos": total,
        "by_status": by_status,
        "total_duration_seconds": total_duration,
        "top_commented": list(top_commented),
    }
