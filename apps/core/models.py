from django.conf import settings
from django.db import models


class IdempotencyKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    key = models.CharField(max_length=255)
    request_path = models.CharField(max_length=255)
    response_status = models.PositiveSmallIntegerField()
    response_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Por usuário, e é ela que resolve a corrida de duas requisições simultâneas.
            models.UniqueConstraint(fields=["user", "key"], name="unique_idempotency_key_per_user"),
        ]
        verbose_name = "chave de idempotência"
        verbose_name_plural = "chaves de idempotência"

    def __str__(self):
        return f"{self.user_id}:{self.key}"
