import logging

from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.request_context import user_id_var

logger = logging.getLogger("clipstack.auth")


class ContextJWTAuthentication(JWTAuthentication):
    # Primeiro ponto em que o usuário do JWT é conhecido: daqui em diante os logs têm user_id.
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            user_id_var.set(user.pk)
            logger.debug("jwt_authenticated", extra={"user_id": user.pk})
        return result
