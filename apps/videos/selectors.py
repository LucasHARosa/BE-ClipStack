from django.core.cache import cache
from django.db.models import Count, Q, Sum

from apps.videos.models import Video

STATS_CACHE_TTL = 5 * 60
STATS_ALL_KEY = "dashboard:stats:all"


def stats_cache_key(user_id):
    return f"dashboard:stats:user:{user_id}"


def video_queryset(*, user, with_jobs=False):
    qs = Video.objects.visible_to(user).select_related("owner", "metadata").prefetch_related("tags")
    if with_jobs:
        qs = qs.prefetch_related("jobs")
    return qs


def dashboard_stats(*, user):
    # Invalidado pelos signals; o TTL cobre escritas que escapam deles (ex.: update()).
    is_admin = getattr(user, "is_admin", False)
    key = STATS_ALL_KEY if is_admin else stats_cache_key(user.pk)
    return cache.get_or_set(
        key, lambda: _compute_dashboard_stats(user=user, is_admin=is_admin), STATS_CACHE_TTL
    )


def _compute_dashboard_stats(*, user, is_admin):
    videos = Video.objects.alive()
    if not is_admin:
        videos = videos.owned_by(user)

    # O JOIN com metadata é 1:1 e não duplica linhas; com comments (1:N) os COUNTs errariam.
    by_status = videos.aggregate(
        total=Count("id"),
        total_duration=Sum("metadata__duration_seconds"),
        **{status: Count("id", filter=Q(status=status)) for status in Video.Status.values},
    )
    total = by_status.pop("total")
    total_duration = by_status.pop("total_duration") or 0

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
