"""Idempotency-Key: repetir um POST com a mesma chave devolve a resposta original.

O cliente gera uma chave única por OPERAÇÃO (ex.: um UUID por clique em "enviar") e a reenvia
em caso de timeout ou queda de conexão. Sem isso, o retry criaria outro vídeo.
"""

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.exceptions import IdempotencyKeyReused
from apps.core.models import IdempotencyKey

HEADER = "Idempotency-Key"


def run_idempotent(request, handler):
    # handler: função sem argumentos que executa a operação e devolve a Response.
    key = request.headers.get(HEADER)
    if not key:
        return handler()
    if len(key) > 255:
        raise ValidationError({HEADER: "Use no máximo 255 caracteres."})

    # Tudo numa transação: a reserva da chave e a criação do recurso entram juntas. Se a
    # operação falhar (ex.: 400 de validação), a reserva some no rollback e o cliente pode
    # corrigir e tentar de novo com a mesma chave.
    with transaction.atomic():
        record, created = _reserve(request.user, key, request.path)
        if not created:
            return _replay(record, request.path)
        response = handler()
        record.response_status = response.status_code
        record.response_snapshot = response.data
        record.save(update_fields=["response_status", "response_snapshot"])
    return response


def _reserve(user, key, path):
    try:
        # Savepoint: um IntegrityError aqui não invalida a transação de fora.
        with transaction.atomic():
            record = IdempotencyKey.objects.create(
                user=user, key=key, request_path=path, response_status=0, response_snapshot={}
            )
        return record, True
    except IntegrityError:
        # Corrida: duas requisições com a mesma chave ao mesmo tempo. O INSERT da segunda
        # ESPERA no índice único até a primeira terminar; se ela commitou, a segunda cai aqui
        # e lê a resposta já gravada (READ COMMITTED enxerga o que foi commitado).
        return IdempotencyKey.objects.get(user=user, key=key), False


def _replay(record, path):
    if record.request_path != path:
        raise IdempotencyKeyReused(details={"original_path": record.request_path})
    return Response(
        record.response_snapshot,
        status=record.response_status,
        headers={"Idempotent-Replayed": "true"},
    )
