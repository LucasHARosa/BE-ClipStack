"""Autenticação JWT com o usuário no contexto de log."""

import logging

from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.request_context import user_id_var

logger = logging.getLogger("clipstack.auth")


class ContextJWTAuthentication(JWTAuthentication):
    # A camada do DRF é o primeiro lugar em que o usuário do JWT é conhecido. Gravar o id aqui
    # faz todo log daí em diante (view, service, middleware na volta) sair com user_id.
    # É uma das soluções para "o middleware não vê o usuário do JWT" (laboratório 2).
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            user_id_var.set(user.pk)
            logger.debug("jwt_authenticated", extra={"user_id": user.pk})
        return result
