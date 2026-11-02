from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.exceptions import IdempotencyKeyReused
from apps.core.models import IdempotencyKey

HEADER = "Idempotency-Key"


def run_idempotent(request, handler):
    key = request.headers.get(HEADER)
    if not key:
        return handler()
    if len(key) > 255:
        raise ValidationError({HEADER: "Use no máximo 255 caracteres."})

    # Reserva e operação na mesma transação: se a operação falhar, a chave fica livre de novo.
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
        with transaction.atomic():
            record = IdempotencyKey.objects.create(
                user=user, key=key, request_path=path, response_status=0, response_snapshot={}
            )
        return record, True
    except IntegrityError:
        # Corrida: o INSERT da segunda requisição espera no índice único até a primeira
        # commitar, e então lê a resposta já gravada.
        return IdempotencyKey.objects.get(user=user, key=key), False


def _replay(record, path):
    if record.request_path != path:
        raise IdempotencyKeyReused(details={"original_path": record.request_path})
    return Response(
        record.response_snapshot,
        status=record.response_status,
        headers={"Idempotent-Replayed": "true"},
    )
