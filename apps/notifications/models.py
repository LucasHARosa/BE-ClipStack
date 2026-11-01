from django.conf import settings
from django.db import models
from django.db.models import Q


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
    # Chave do evento que gerou a notificação (ex.: "job:12:finished"). A task que cria a
    # notificação pode rodar duas vezes (retry, acks_late); com a chave única, a segunda
    # execução encontra a notificação existente em vez de duplicar.
    event_key = models.CharField(max_length=100, blank=True, default="")
    # Quando o email foi enviado: a task de email não reenvia se já estiver preenchido.
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # "-id" desempata: a CursorPagination exige uma ordenação estável e única.
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "is_read"], name="notification_user_read_idx"),
        ]
        constraints = [
            # Único só quando preenchido: notificações sem evento (event_key="") não conflitam.
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
