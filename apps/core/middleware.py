"""Middlewares do projeto."""

import logging
import re
import time
import uuid

from apps.core.request_context import request_id_var, user_id_var

logger = logging.getLogger("clipstack.request")

# Aceita o id de quem chamou (proxy, outro serviço) só se for "seguro" para log e header.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _describe(user):
    if user is None:
        return None
    return "anonymous" if not user.is_authenticated else f"user:{user.pk}"


class RequestIdMiddleware:
    # Middleware "novo estilo": __init__ recebe get_response (o resto da cadeia) uma vez, no
    # boot; __call__ roda a cada requisição. O que vem ANTES de get_response() é a ida; o que
    # vem DEPOIS é a volta (em ordem inversa à da lista MIDDLEWARE).
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        request_token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)

        # O que o middleware ENXERGA antes da view: o AuthenticationMiddleware do Django só
        # entende SESSÃO. Com JWT, aqui o usuário é AnonymousUser, porque a autenticação JWT
        # só acontece dentro da view do DRF (APIView.initial()), depois de todos os middlewares.
        user_before_view = _describe(getattr(request, "user", None))
        started = time.perf_counter()
        try:
            response = self.get_response(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            request_id_var.reset(request_token)

        # Na volta, request.user JÁ é o usuário do JWT: o setter Request.user do DRF copia o
        # usuário autenticado para o HttpRequest do Django (request._request.user = user).
        logger.info(
            "request_finished",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user_before_view": user_before_view,
                "user_after_view": _describe(getattr(request, "user", None)),
                "user_id": user_id_var.get(),
            },
        )
        user_id_var.reset(user_token)
        response["X-Request-ID"] = request_id
        return response
