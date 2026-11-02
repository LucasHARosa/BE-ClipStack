from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class ContextJWTScheme(SimpleJWTScheme):
    # O drf-spectacular só reconhece a classe original do simplejwt.
    target_class = "apps.core.authentication.ContextJWTAuthentication"
    name = "jwtAuth"
