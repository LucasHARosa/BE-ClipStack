"""Exception handler da API (REST_FRAMEWORK["EXCEPTION_HANDLER"]).

O DRF chama esta função para TODA exceção que sai de uma view (inclusive autenticação,
permissão e throttling, que rodam no initial()). Todo erro sai num formato único:

    {"error": {"code": "...", "message": "...", "details": {...}}}

O frontend trata erros sempre do mesmo jeito: `code` para lógica, `message` para exibir e
`details` para erros por campo (validação) ou dados extras (wait do 429, status do 409).
"""

import logging

from django.conf import settings
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

from apps.core.exceptions import DomainError

logger = logging.getLogger("clipstack.errors")


def _error(code, message, details=None):
    return {"error": {"code": code, "message": str(message), "details": details or {}}}


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        set_rollback()
        return Response(_error(exc.code, exc.message, exc.details), status=exc.status_code)

    # O handler padrão converte Http404/PermissionDenied do Django em exceções do DRF, monta a
    # resposta (com headers como Retry-After e WWW-Authenticate) e marca rollback da transação.
    response = drf_exception_handler(exc, context)

    if response is None:
        # Exceção não tratada (bug): em DEBUG deixa subir para a página de erro do Django;
        # em produção, loga com traceback (e request_id) e devolve 500 no mesmo formato.
        if settings.DEBUG:
            return None
        logger.exception("unhandled_exception", exc_info=exc)
        set_rollback()
        return Response(
            _error("server_error", "Erro interno. Use o X-Request-ID para rastrear."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        # Erros por campo vão em details: {"title": ["Este campo é obrigatório."]}
        response.data = _error(
            "validation_error", "Os dados enviados são inválidos.", response.data
        )
        return response

    data = response.data if isinstance(response.data, dict) else {"detail": response.data}
    message = data.pop("detail", "Erro.")
    # simplejwt devolve {"detail", "code", "messages"}; o resto do DRF guarda o code no detail.
    code = str(data.pop("code", None) or getattr(message, "code", None) or "error")
    details = data
    if isinstance(exc, exceptions.Throttled):
        details = {**details, "wait_seconds": exc.wait}
    response.data = _error(code, message, details)
    return response
