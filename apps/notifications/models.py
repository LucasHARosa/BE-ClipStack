from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    # SET_NULL: a notificação continua no histórico se o vídeo for apagado de verdade.
    video = models.ForeignKey(
        "videos.Video",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    message = models.CharField("mensagem", max_length=255)
    is_read = models.BooleanField("lida", default=False)
    # Ex.: "job:12:finished". Única: a task pode rodar duas vezes sem duplicar.
    event_key = models.CharField(max_length=100, blank=True, default="")
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "is_read"], name="notification_user_read_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["event_key"],
                condition=~Q(event_key=""),
                name="unique_notification_event_key",
            ),
        ]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"

    def __str__(self):
        return f"{self.user_id}: {self.message[:40]}"
