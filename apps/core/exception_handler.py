"""Exception handler da API (REST_FRAMEWORK["EXCEPTION_HANDLER"]).

O DRF chama esta função para toda exceção que sai de uma view. Aqui as exceções de domínio
viram {"error": {"code", "message", "details"}} com o status definido na própria exceção.
A etapa 7 estende o mesmo formato para todos os outros erros (400, 401, 403, 404, 429...).
"""

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.exceptions import DomainError


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        body = {"error": {"code": exc.code, "message": exc.message, "details": exc.details}}
        return Response(body, status=exc.status_code)
    # O resto segue o tratamento padrão do DRF (ValidationError → 400, NotFound → 404...).
    # Devolver None faz a exceção subir: vira 500 e aparece no log.
    return drf_exception_handler(exc, context)
