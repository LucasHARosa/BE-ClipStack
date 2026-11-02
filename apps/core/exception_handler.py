"""Todo erro sai como {"error": {"code", "message", "details"}}."""

import logging

from django.conf import settings
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

from apps.core.exceptions import DomainError

logger = logging.getLogger("clipstack.errors")


def _error_body(code, message, details=None):
    return {"error": {"code": code, "message": str(message), "details": details or {}}}


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        set_rollback()
        return Response(_error_body(exc.code, exc.message, exc.details), status=exc.status_code)

    response = drf_exception_handler(exc, context)

    if response is None:
        if settings.DEBUG:
            return None
        logger.exception("unhandled_exception", exc_info=exc)
        set_rollback()
        return Response(
            _error_body("server_error", "Erro interno. Use o X-Request-ID para rastrear."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        response.data = _error_body(
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
    response.data = _error_body(code, message, details)
    return response
