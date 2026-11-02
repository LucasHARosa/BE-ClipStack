"""Extensões do drf-spectacular (OpenAPI)."""

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class ContextJWTScheme(SimpleJWTScheme):
    # O drf-spectacular só reconhece a classe original do simplejwt; esta extensão ensina que a
    # subclasse do projeto é o mesmo "Bearer JWT" (botão Authorize no Swagger).
    target_class = "apps.core.authentication.ContextJWTAuthentication"
    name = "jwtAuth"
