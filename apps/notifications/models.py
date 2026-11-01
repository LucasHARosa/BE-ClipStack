from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    # SET_NULL: a notificação continua existindo (histórico do usuário) mesmo se o vídeo for
    # apagado de verdade. Exige null=True.
    video = models.ForeignKey(
        "videos.Video",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    message = models.CharField("mensagem", max_length=255)
    is_read = models.BooleanField("lida", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # "-id" desempata: a CursorPagination exige uma ordenação estável e única.
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "is_read"], name="notification_user_read_idx"),
        ]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"

    def __str__(self):
        return f"{self.user_id}: {self.message[:40]}"
