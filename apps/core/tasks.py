from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.core.models import IdempotencyKey


@shared_task
def purge_expired_idempotency_keys():
    cutoff = timezone.now() - timedelta(hours=settings.IDEMPOTENCY_KEY_TTL_HOURS)
    deleted, _ = IdempotencyKey.objects.filter(created_at__lt=cutoff).delete()
    return deleted
