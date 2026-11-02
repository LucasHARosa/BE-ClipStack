from django.apps import AppConfig


class CoreConfig(AppConfig):
    # name: caminho de import da app (as apps ficam dentro do pacote "apps").
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        # Registra a extensão de autenticação do OpenAPI (basta importar o módulo).
        from apps.core import schema  # noqa: F401
