from django.conf import settings
from django.db import models


class IdempotencyKey(models.Model):
    # Guarda a resposta de um POST feito com o header Idempotency-Key. Se o cliente repetir
    # a requisição (timeout, retry, clique duplo), a API devolve a mesma resposta em vez de
    # criar outro recurso.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    key = models.CharField(max_length=255)
    # Rota em que a chave foi usada: a mesma chave em outro endpoint é erro do cliente.
    request_path = models.CharField(max_length=255)
    response_status = models.PositiveSmallIntegerField()
    response_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # A chave é única POR USUÁRIO: dois usuários podem gerar o mesmo UUID por acaso.
            # A UniqueConstraint também resolve a corrida de duas requisições simultâneas:
            # a segunda falha com IntegrityError em vez de duplicar.
            models.UniqueConstraint(fields=["user", "key"], name="unique_idempotency_key_per_user"),
        ]
        verbose_name = "chave de idempotência"
        verbose_name_plural = "chaves de idempotência"

    def __str__(self):
        return f"{self.user_id}:{self.key}"
