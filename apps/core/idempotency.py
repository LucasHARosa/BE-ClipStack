from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.exceptions import IdempotencyKeyReused
from apps.core.models import IdempotencyKey

HEADER = "Idempotency-Key"


def run_idempotent(request, operation):
    key = request.headers.get(HEADER)
    if not key:
        return operation()
    if len(key) > 255:
        raise ValidationError({HEADER: "Use no máximo 255 caracteres."})

    # Reserva e operação na mesma transação: se a operação falhar, a chave fica livre de novo.
    with transaction.atomic():
        idempotency_key, created = _reserve_key(request.user, key, request.path)
        if not created:
            return _replay_stored_response(idempotency_key, request.path)
        response = operation()
        idempotency_key.response_status = response.status_code
        idempotency_key.response_snapshot = response.data
        idempotency_key.save(update_fields=["response_status", "response_snapshot"])
    return response


def _reserve_key(user, key, path):
    try:
        with transaction.atomic():
            idempotency_key = IdempotencyKey.objects.create(
                user=user, key=key, request_path=path, response_status=0, response_snapshot={}
            )
        return idempotency_key, True
    except IntegrityError:
        # Corrida: o INSERT da segunda requisição espera no índice único até a primeira
        # commitar, e então lê a resposta já gravada.
        return IdempotencyKey.objects.get(user=user, key=key), False


def _replay_stored_response(idempotency_key, path):
    if idempotency_key.request_path != path:
        raise IdempotencyKeyReused(details={"original_path": idempotency_key.request_path})
    return Response(
        idempotency_key.response_snapshot,
        status=idempotency_key.response_status,
        headers={"Idempotent-Replayed": "true"},
    )
